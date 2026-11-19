import logging
import os
import aiohttp

logger = logging.getLogger("github_dispatcher")

GITHUB_PAT = os.environ.get("GITHUB_DISPATCH_TOKEN", "").strip()
GITHUB_WORKER_REPO = os.environ.get("GITHUB_WORKER_REPO", "").strip()  # e.g. "your-username/streak-scanner-worker"
GITHUB_WORKFLOW_FILE = os.environ.get("GITHUB_WORKFLOW_FILE", "streak_scan.yml").strip()
GITHUB_WORKER_BRANCH = os.environ.get("GITHUB_WORKER_BRANCH", "main").strip()


async def trigger_github_streak_scan(trigger_source: str = "telegram_render") -> tuple[bool, str]:
    """Triggers the GitHub Actions Playwright workflow on your public worker repo via REST API."""
    if not GITHUB_PAT or not GITHUB_WORKER_REPO:
        return False, "Missing GITHUB_DISPATCH_TOKEN or GITHUB_WORKER_REPO in Render Environment."

    url = (
        f"https://api.github.com/repos/{GITHUB_WORKER_REPO}"
        f"/actions/workflows/{GITHUB_WORKFLOW_FILE}/dispatches"
    )
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {GITHUB_PAT}",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    payload = {
        "ref": GITHUB_WORKER_BRANCH,
        "inputs": {
            "trigger_source": trigger_source,
        },
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)) as resp:
            if resp.status == 204:
                logger.info(f"Dispatched GitHub Actions workflow {GITHUB_WORKER_REPO}/{GITHUB_WORKFLOW_FILE}")
                return True, "GitHub Actions scan started! Results will arrive here in ~45 seconds."
            body = await resp.text()
            logger.error(f"GitHub dispatch failed: HTTP {resp.status} - {body[:200]}")
            return False, f"GitHub API HTTP {resp.status}: {body[:200]}"
          
