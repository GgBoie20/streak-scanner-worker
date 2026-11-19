# ==============================================================================
# DROP-IN SNIPPET FOR YOUR EXISTING RENDER `main.py`
# ==============================================================================
# 1. Copy `render_bridge/github_dispatcher.py` into your Render repository.
# 2. Add these 2 environment variables in Render -> Environment:
#      - GITHUB_DISPATCH_TOKEN : GitHub PAT with `actions:write` (or classic `workflow` / `repo` scope)
#      - GITHUB_WORKER_REPO    : e.g. "your-username/streak-scanner-worker"
# 3. Import at top of `main.py`:
#      from github_dispatcher import trigger_github_streak_scan
# 4. Add this `if text == "/scan":` block inside `handle_telegram_webhook()` right after `if text == "/start":`

if text == "/scan":
    ok, msg = await trigger_github_streak_scan(trigger_source="telegram_render")
    icon = "🚀" if ok else "❌"
    await send_telegram_alert(f"{icon} <b>Streak 3-Cap Scan:</b> {html.escape(msg)}")
    return web.Response(text="OK", status=200)
