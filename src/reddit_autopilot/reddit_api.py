"""Reddit action layer.

All calls go through a logged-in browser session (same-origin fetch with the
real cookies + modhash), exactly like Reddit's own web UI does. No OAuth app,
no API key, no PRAW, no scraping.

Two backends implement the same ``fetch(path, method, body)`` surface:
  * CDPSession      - isolated Chrome over the DevTools protocol (recommended)
  * AppleSession    - the macOS AppleScript -> Chrome backend

``get_session()`` auto-selects CDP when the isolated Chrome is running, else the
AppleScript backend. Nothing here writes to Reddit unless the caller asks.
"""

from __future__ import annotations

import json
import urllib.parse

from reddit_autopilot import browser

API = "https://www.reddit.com"

_cache: dict[str, object] = {}


# --------------------------------------------------------------------------- AppleScript backend

def _apple_fetch_js(path: str, method: str = "GET", body: dict | None = None) -> str:
    url = path if path.startswith("http") else API + path
    opts = {"method": method, "credentials": "include",
            "headers": {"Content-Type": "application/x-www-form-urlencoded"}}
    if body is not None:
        opts["body"] = urllib.parse.urlencode(body)
    return (
        "var o=" + json.dumps(opts) + ";"
        f"fetch({json.dumps(url)},o)"
        ".then(function(r){return r.text().then(function(t){window.__rap_state='DONE '+r.status+' '+t;});})"
        ".catch(function(e){window.__rap_state='ERR '+e;});"
    )


class AppleSession:
    """Uses the user's real Chrome via AppleScript (needs the Apple Events setting)."""

    def __init__(self):
        tab = browser.ensure_reddit_session()
        self.win = tab["win"]
        self.tab = tab["tab"]

    def fetch(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        state = browser.evaluate_async(self.win, self.tab, _apple_fetch_js(path, method, body))
        if state.startswith("ERR "):
            return {"ok": False, "error": state[4:]}
        if state.startswith("DONE "):
            status, _, text = state[5:].partition(" ")
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                data = {"_text": text}
            return {"ok": 200 <= int(status) < 300, "status": int(status), "data": data}
        return {"ok": False, "error": "unexpected state", "raw": state}


# --------------------------------------------------------------------------- selection

def get_session(backend: str | None = None):
    """Return a session object. backend: None=auto, 'cdp', or 'apple'."""
    if backend is None:
        from reddit_autopilot import browser_cdp
        backend = "cdp" if browser_cdp.running() else "apple"
    if backend in _cache:
        return _cache[backend]
    if backend == "cdp":
        from reddit_autopilot import browser_cdp
        session = browser_cdp.CDPSession()
    elif backend == "apple":
        session = AppleSession()
    else:
        raise ValueError(f"unknown backend: {backend}")
    _cache[backend] = session
    return session


def reset_sessions() -> None:
    _cache.clear()


# --------------------------------------------------------------------------- actions

def _flatten_submit(res: dict) -> dict:
    if not res.get("ok"):
        return res
    j = res["data"].get("json") or {}
    errors = j.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors, "data": res["data"]}
    return {"ok": True, "url": (j.get("data") or {}).get("url"), "id": (j.get("data") or {}).get("id")}


def whoami(sess=None) -> dict:
    sess = sess or get_session()
    res = sess.fetch("/api/me.json")
    if not res.get("ok"):
        return {"logged_in": False, "error": res.get("error") or res}
    data = res["data"].get("data") or {}
    return {
        "logged_in": bool(data.get("name")),
        "name": data.get("name"),
        "modhash": data.get("modhash"),
        "karma": {"link": data.get("link_karma"), "comment": data.get("comment_karma")},
    }


def subreddit_rules(sub: str, sess=None) -> dict:
    return (sess or get_session()).fetch(f"/r/{sub}/about/rules.json")


def submit_text(sub: str, title: str, text: str, modhash: str, sess=None) -> dict:
    body = {"api_type": "json", "kind": "self", "sr": sub, "title": title, "text": text, "uh": modhash}
    return _flatten_submit((sess or get_session()).fetch("/api/submit", "POST", body))


def submit_link(sub: str, title: str, url: str, modhash: str, sess=None) -> dict:
    body = {"api_type": "json", "kind": "link", "sr": sub, "title": title, "url": url, "uh": modhash}
    return _flatten_submit((sess or get_session()).fetch("/api/submit", "POST", body))


def comment(thing_id: str, text: str, modhash: str, sess=None) -> dict:
    body = {"api_type": "json", "thing_id": thing_id, "text": text, "uh": modhash}
    res = (sess or get_session()).fetch("/api/comment", "POST", body)
    if not res.get("ok"):
        return res
    j = res["data"].get("json") or {}
    errors = j.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    things = (j.get("data") or {}).get("things") or [{}]
    return {"ok": True, "id": things[0].get("data", {}).get("id")}


def vote(thing_id: str, direction: int, modhash: str, sess=None) -> dict:
    body = {"id": thing_id, "dir": direction, "uh": modhash}
    return (sess or get_session()).fetch("/api/vote", "POST", body)


def listing(sub: str, sort: str = "hot", limit: int = 25, sess=None) -> dict:
    return (sess or get_session()).fetch(f"/r/{sub}/{sort}.json?limit={limit}")
