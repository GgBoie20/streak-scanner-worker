import asyncio
import base64
import json
import logging
import os
import re
from datetime import datetime, timedelta, timezone
import requests
from playwright.async_api import async_playwright

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger("streak_scraper")

IST = timezone(timedelta(hours=5, minutes=30))

STORAGE_STATE_B64 = os.environ.get("STREAK_STORAGE_STATE_B64", "").strip()
SCANNER_URL = os.environ.get("STREAK_SCANNER_URL", "").strip()
GIST_TOKEN = os.environ.get("GIST_TOKEN", "").strip()
GIST_ID = os.environ.get("GIST_ID", "").strip()
RENDER_WEBHOOK_URL = os.environ.get("RENDER_WEBHOOK_URL", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
TRIGGER_SOURCE = os.environ.get("TRIGGER_SOURCE", "schedule").strip()

IGNORE_WORDS = {
    "NSE", "BSE", "NFO", "MCX", "BUY", "SELL", "SCAN", "SCANNER", "ALERT",
    "CMP", "LTP", "VOLUME", "VOL", "CHANGE", "HIGH", "LOW", "OPEN", "CLOSE",
    "STREAK", "BACKTEST", "DEPLOY", "LIVE", "PAPER", "TRADE", "SYMBOL",
    "INSTRUMENT", "SIGNAL", "TIME", "ACTION", "PRICE", "QTY", "ALL", "EQ",
    "BULLISH", "BEARISH", "INTRADAY", "SWING", "COPY", "EDIT", "RUN", "SAVE",
    "RESET", "EXPORT", "CSV", "REFRESH", "DISCOVER", "SCANNERS", "STRATEGIES",
    "TECHNICALS", "DASHBOARD", "HOME", "LOGIN", "LOGOUT", "PRO", "FREE",
}


def update_gist(tickers: list[str]) -> None:
    """Writes the latest Streak 3-cap scanner symbols into your GitHub Gist."""
    if not GIST_TOKEN or not GIST_ID:
        logger.warning("GIST_TOKEN or GIST_ID not set; skipping Gist update.")
        return

    headers = {
        "Authorization": f"token {GIST_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    resp = requests.get(f"https://api.github.com/gists/{GIST_ID}", headers=headers, timeout=20)
    resp.raise_for_status()
    files = resp.json().get("files", {})
    filename = next(iter(files.keys()), "bot_state.json")

    try:
        state = json.loads(files[filename]["content"])
    except Exception:
        state = {}

    state["streak_3cap_stocks"] = {
        "updated_at": datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S IST"),
        "trigger_source": TRIGGER_SOURCE,
        "count": len(tickers),
        "tickers": tickers,
    }

    patch_resp = requests.patch(
        f"https://api.github.com/gists/{GIST_ID}",
        headers=headers,
        json={"files": {filename: {"content": json.dumps(state, indent=2)}}},
        timeout=20,
    )
    patch_resp.raise_for_status()
    logger.info(f"Updated Gist ({filename}) with {len(tickers)} tickers.")


def post_to_render_webhook(text_message: str) -> None:
    """Sends a synthetic Telegram webhook update to Render so Render handles UPL Genie + Telegram."""
    if not RENDER_WEBHOOK_URL or not TELEGRAM_CHAT_ID:
        logger.warning("RENDER_WEBHOOK_URL or TELEGRAM_CHAT_ID missing; skipping webhook trigger.")
        return

    payload = {
        "update_id": int(datetime.now().timestamp() * 1000) % 2_000_000_000,
        "message": {
            "chat": {"id": int(TELEGRAM_CHAT_ID)},
            "text": text_message,
        },
    }
    resp = requests.post(RENDER_WEBHOOK_URL, json=payload, timeout=30)
    logger.info(f"POST {RENDER_WEBHOOK_URL} -> HTTP {resp.status_code}")
    resp.raise_for_status()


def extract_tickers_from_text(raw_blob: str) -> list[str]:
    """Extracts clean unique NSE stock symbols from scraped text."""
    candidates = re.findall(r"\b[A-Z][A-Z0-9&-]{1,14}\b", raw_blob)
    cleaned = []
    for c in candidates:
        if c in IGNORE_WORDS or c.isdigit():
            continue
        if len(c) < 2:
            continue
        cleaned.append(c)
    return list(dict.fromkeys(cleaned))


async def scrape_streak_scanner() -> list[str]:
    if not STORAGE_STATE_B64:
        raise RuntimeError("Missing STREAK_STORAGE_STATE_B64 secret.")
    if not SCANNER_URL:
        raise RuntimeError("Missing STREAK_SCANNER_URL secret.")

    state_dict = json.loads(base64.b64decode(STORAGE_STATE_B64).decode("utf-8"))
    captured_api_symbols: list[str] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            storage_state=state_dict,
            viewport={"width": 1366, "height": 768},
        )
        page = await context.new_page()

        # Passively listen to JSON responses from Streak's scanner API for cleaner symbol extraction
        async def handle_response(response):
            try:
                ctype = response.headers.get("content-type", "")
                if "application/json" in ctype and any(
                    kw in response.url.lower() for kw in ("scan", "result", "screener", "stock")
                ):
                    data = await response.json()
                    blob = json.dumps(data)
                    # Look for common symbol keys like "tradingsymbol", "symbol", "ticker"
                    found = re.findall(
                        r'"(?:tradingsymbol|symbol|ticker|nse_symbol)"\s*:\s*"([A-Z0-9&-]{2,15})"',
                        blob,
                    )
                    if found:
                        captured_api_symbols.extend(found)
            except Exception:
                pass

        page.on("response", handle_response)

        logger.info(f"Opening scanner URL (source={TRIGGER_SOURCE})...")
        await page.goto(SCANNER_URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        if "login" in page.url.lower() or "signin" in page.url.lower():
            await browser.close()
            raise RuntimeError(
                "Streak session expired (redirected to login). Re-run capture_session.py and update STREAK_STORAGE_STATE_B64."
            )

        # Click "Scan" / "Run Scan" button if present
        run_btn = page.locator("button:has-text('Scan'), button:has-text('Run')").first
        if await run_btn.count() > 0:
            try:
                await run_btn.click(timeout=5000)
                await page.wait_for_timeout(5000)
            except Exception as click_err:
                logger.warning(f"Could not click Scan button (may have auto-run): {click_err}")

        # Primary: prefer structured API symbols if intercepted
        if captured_api_symbols:
            tickers = list(dict.fromkeys([s for s in captured_api_symbols if s not in IGNORE_WORDS]))
            await browser.close()
            return tickers

        # Fallback: extract from rendered table rows
        rows = await page.locator("table tbody tr, [role='row']").all_inner_texts()
        raw_blob = "\n".join(rows) if rows else await page.inner_text("body")
        await browser.close()

    return extract_tickers_from_text(raw_blob)


async def main() -> None:
    try:
        tickers = await scrape_streak_scanner()
        logger.info(f"Extracted {len(tickers)} tickers: {tickers}")

        if tickers:
            update_gist(tickers)
            # Limit to first 15 tickers per Telegram/UPL Genie batch to keep response crisp
            batch = tickers[:15]
            post_to_render_webhook(", ".join(batch))
        else:
            logger.info("No tickers matched in this scan cycle.")
    except Exception as exc:
        logger.exception(f"Scraper failed: {exc}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
