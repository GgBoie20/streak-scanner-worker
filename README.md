# Streak 3-Cap Scanner Worker (GitHub Actions + Render Bridge)

Runs Playwright on GitHub Actions (`ubuntu-latest`, 7 GB RAM / 2 vCPUs) in a **Public** repository (unlimited free Actions minutes) to scrape your Streak 3-cap scanner, save the stock list to your GitHub Gist, and trigger your Render bot (`UPL Genie` + Telegram).

## Repository Structure
- `.github/workflows/streak_scan.yml` — Scheduled (every 15 mins during NSE hours) + API-triggerable workflow.
- `scraper.py` — Headless Playwright scraper with passive JSON API interception, Gist sync, and Render webhook callback.
- `capture_session.py` — One-time local PC script to export your logged-in Streak browser session (`STREAK_STORAGE_STATE_B64`).
- `render_bridge/github_dispatcher.py` — Lightweight `aiohttp` module for your Render repo to trigger GitHub Actions on demand.
- `render_bridge/main_scan_command_snippet.py` — Drop-in `/scan` Telegram command for your Render `main.py`.

---

## Setup Guide

### 1. Capture Your Logged-In Streak Session (Local PC)
```bash
pip install playwright
playwright install chromium
python capture_session.py
```
Log in to Streak in the browser window, open your 3-cap scanner, press **Enter** in the terminal, and copy the contents of `streak_state_b64.txt`. Delete `streak_state_b64.txt` afterward.

### 2. Create the Public GitHub Repository & Secrets
1. Create a new **Public** repository on GitHub (e.g., `streak-scanner-worker`) and push all files in this folder (excluding `render_bridge/` if you prefer, though it contains no secrets).
2. Go to **Settings -> Secrets and variables -> Actions -> New repository secret** and add:
   - `STREAK_STORAGE_STATE_B64`: Base64 session string from Step 1
   - `STREAK_SCANNER_URL`: Exact URL of your Streak 3-cap scanner
   - `GIST_TOKEN`: Your GitHub PAT with `gist` scope
   - `GIST_ID`: Your existing Gist ID
   - `RENDER_WEBHOOK_URL`: `https://streak-render-bot.onrender.com/webhook`
   - `TELEGRAM_CHAT_ID`: Your numeric Telegram chat ID

### 3. Connect Your Render Bot to Trigger GitHub Actions (`/scan`)
1. Copy `render_bridge/github_dispatcher.py` into your Render repository.
2. Add the `/scan` snippet from `render_bridge/main_scan_command_snippet.py` into `main.py`.
3. In **Render -> Environment**, add:
   - `GITHUB_DISPATCH_TOKEN`: A GitHub PAT with `workflow` / `actions:write` permission
   - `GITHUB_WORKER_REPO`: `<your-github-username>/streak-scanner-worker`

Now sending `/scan` in Telegram tells Render to dispatch GitHub Actions (zero RAM used on Render), GitHub scrapes Streak on its 7 GB RAM runner, updates your Gist, and posts the tickers back to Render for UPL Genie analysis!
