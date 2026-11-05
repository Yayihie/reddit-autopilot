"""AppleScript + Chrome backend.

Controls the user's *real, logged-in* Chrome via osascript. This is the same
technique popularised by PHY041/claude-skill-reddit: because it drives the
actual browser session, cookies and the browser fingerprint are authentic, and
there is no `navigator.webdriver` tell (unlike Playwright/Selenium).

Requirements (macOS only):
  * Google Chrome
  * Chrome -> View -> Developer -> "Allow JavaScript from Apple Events" (restart Chrome)
  * You logged into Reddit in Chrome
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import time

REDDIT_HOST = "https://www.reddit.com"


class BrowserError(RuntimeError):
    pass


def chrome_installed() -> bool:
    return bool(shutil.which("osascript")) and os.path.isdir("/Applications/Google Chrome.app")


def _osa(script: str) -> str:
    """Run an AppleScript passed on stdin; return trimmed stdout."""
    p = subprocess.run(["osascript", "-"], input=script, text=True, capture_output=True)
    if p.returncode != 0:
        err = (p.stderr or "").strip()
        raise BrowserError(err or "osascript failed")
    return p.stdout.strip()


def _osa_str(s: str) -> str:
    """Quote a Python string as an AppleScript string literal."""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


def _one_line(js: str) -> str:
    """Collapse JS to a single line (AppleScript string literals can't hold raw newlines)."""
    js = re.sub(r"//[^\n]*", "", js)
    return re.sub(r"\s+", " ", js).strip()


def chrome_windows() -> int:
    try:
        return int(_osa('tell application "Google Chrome" to return count of windows'))
    except (BrowserError, ValueError):
        return 0


def list_tabs() -> list[dict]:
    """Return [{win, tab, url}] for every open Chrome tab."""
    script = (
        'set out to ""\n'
        'tell application "Google Chrome"\n'
        '  repeat with w from 1 to (count of windows)\n'
        '    repeat with t from 1 to (count of tabs of window w)\n'
        '      set out to out & w & "\t" & t & "\t" & (URL of tab t of window w) & "\n"\n'
        '    end repeat\n'
        '  end repeat\n'
        'end tell\n'
        'return out'
    )
    raw = _osa(script)
    tabs = []
    for line in raw.splitlines():
        parts = line.split("\t")
        if len(parts) == 3:
            tabs.append({"win": int(parts[0]), "tab": int(parts[1]), "url": parts[2]})
    return tabs


def find_reddit_tab() -> dict | None:
    for t in list_tabs():
        if "reddit.com" in t["url"]:
            return t
    return None


def open_tab(url: str) -> dict:
    """Open url in a new Chrome tab, return {win, tab}."""
    script = (
        'tell application "Google Chrome"\n'
        '  if (count of windows) = 0 then make new window\n'
        '  tell window 1\n'
        f'    set t to make new tab with properties {{URL:{_osa_str(url)}}}\n'
        '    set active tab index to (count of tabs)\n'
        '    return (count of tabs)\n'
        '  end tell\n'
        'end tell'
    )
    tab = int(_osa(script))
    return {"win": 1, "tab": tab}


def execute_js(js: str, win: int, tab: int) -> str:
    """Execute JS in a specific tab and return its result as a string."""
    script = (
        'tell application "Google Chrome"\n'
        f'  execute javascript {_osa_str(_one_line(js))} in tab {tab} of window {win}\n'
        'end tell'
    )
    return _osa(script)


def wait_ready(win: int, tab: int, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if execute_js("document.readyState", win, tab) == "complete":
                return True
        except BrowserError:
            pass
        time.sleep(0.5)
    return False


def evaluate(win: int, tab: int, js: str) -> str:
    """Evaluate a JS expression synchronously (for simple value reads)."""
    return execute_js(js, win, tab)


def evaluate_async(win: int, tab: int, js: str, timeout: float = 25.0, poll: float = 0.4) -> str:
    """Run JS that resolves asynchronously into window.__rap_state, then return it.

    The snippet must set window.__rap_state to 'PENDING' then later to a final
    string. We poll until it changes.
    """
    execute_js(f"window.__rap_state = 'PENDING'; {js}", win, tab)
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = execute_js("window.__rap_state", win, tab)
        if state and state != "PENDING":
            return state
        time.sleep(poll)
    raise BrowserError(f"async JS timed out after {timeout}s")


def ensure_reddit_session() -> dict:
    """Return a {win, tab} pointing at a reddit.com tab, opening one if needed."""
    tab = find_reddit_tab()
    if tab is None:
        tab = open_tab(REDDIT_HOST)
        wait_ready(tab["win"], tab["tab"])
    return {"win": tab["win"], "tab": tab["tab"]}
