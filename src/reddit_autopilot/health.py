"""Health checks: environment doctor, session/login, and a best-effort shadowban probe."""

from __future__ import annotations

import os
import platform
import shutil

from reddit_autopilot import activation, browser, planner, reddit_api


def doctor(with_browser: bool = False) -> dict:
    """Check the environment needed for the browser backend."""
    checks = {}

    checks["os"] = platform.system()
    checks["is_macos"] = platform.system() == "Darwin"
    checks["osascript"] = bool(shutil.which("osascript"))
    checks["chrome_app"] = os.path.isdir("/Applications/Google Chrome.app")

    # Can we execute JS in Chrome? (proves "Allow JavaScript from Apple Events")
    checks["chrome_windows"] = browser.chrome_windows() if checks["is_macos"] else 0
    js_ok = None
    if with_browser and checks["chrome_windows"] > 0:
        try:
            tab = browser.list_tabs()[0]
            js_ok = browser.execute_js("1+1", tab["win"], tab["tab"]) == "2"
        except browser.BrowserError:
            js_ok = False
    checks["js_from_apple_events"] = js_ok
    checks["reddit_tab_open"] = bool(browser.find_reddit_tab()) if checks["is_macos"] else False

    checks["growth_backend"] = planner._resolve() or "not installed (pip install 'reddit-autopilot[growth]')"

    ok = all([checks["is_macos"], checks["osascript"], checks["chrome_app"]])
    fixes = []
    if not checks["is_macos"]:
        fixes.append("The browser backend is macOS-only. Use the bridge backend on Linux/Windows.")
    if checks["js_from_apple_events"] is False:
        fixes.append("Chrome -> View -> Developer -> Allow JavaScript from Apple Events (then restart Chrome).")
    if not checks["reddit_tab_open"]:
        fixes.append("Open reddit.com in Chrome and log in.")
    if activation.is_hashmark():
        checks["hashmark_draft_only"] = True
        ok = True
        fixes = [
            "Hashmark live browser/CDP/session use is blocked. Draft, queue, and policy checks only.",
            "Do not copy the parent-desktop Reddit session into this environment.",
        ]
    return {"ok": ok, "checks": checks, "fixes": fixes}


def login_status() -> dict:
    who = reddit_api.whoami()
    return who


def shadowban_probe(sub: str = "test") -> dict:
    """Best-effort: check whether the session can see the user's own recent activity.

    Reddit does not expose a shadowban flag. This probe reports what we *can*
    verify: login state and whether /api/me.json resolves a username. A full
    confirmation requires checking a fresh post from a logged-out context.
    """
    who = reddit_api.whoami()
    if not who.get("logged_in"):
        return {"ok": False, "reason": "not logged in", "detail": who}
    return {
        "ok": True,
        "user": who.get("name"),
        "karma": who.get("karma"),
        "verdict": "session valid — for a true shadowban check, confirm a recent post is visible to logged-out users",
    }
