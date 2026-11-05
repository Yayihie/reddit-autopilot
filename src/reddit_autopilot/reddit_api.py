"""Reddit action layer.

All calls go through the logged-in browser session (same-origin fetch with the
real cookies + modhash), exactly like Reddit's own web UI does. No OAuth app,
no API key, no PRAW, no scraping.

Every public action returns a structured dict; nothing here writes to Reddit
unless the caller explicitly asks for it (the CLI gates real actions behind
--live).
"""

from __future__ import annotations

import json
import urllib.parse

from reddit_autopilot import browser

API = "https://www.reddit.com"


def _fetch_js(path: str, method: str = "GET", body: dict | None = None) -> str:
    url = path if path.startswith("http") else API + path
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    opts = {
        "method": method,
        "credentials": "include",
        "headers": headers,
    }
    if body is not None:
        opts["body"] = urllib.parse.urlencode(body)
    js = (
        "var o=" + json.dumps(opts) + ";"
        f"fetch({json.dumps(url)},o)"
        ".then(function(r){return r.text().then(function(t){window.__rap_state='DONE '+r.status+' '+t;});})"
        ".catch(function(e){window.__rap_state='ERR '+e;});"
    )
    return js


def _call(tab: dict, path: str, method: str = "GET", body: dict | None = None) -> dict:
    state = browser.evaluate_async(tab["win"], tab["tab"], _fetch_js(path, method, body))
    if state.startswith("ERR "):
        return {"ok": False, "error": state[4:], "raw": state}
    if state.startswith("DONE "):
        rest = state[5:]
        status, _, text = rest.partition(" ")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {"_text": text}
        ok = 200 <= int(status) < 300
        return {"ok": ok, "status": int(status), "data": data}
    return {"ok": False, "error": "unexpected state", "raw": state}


def whoami(tab: dict | None = None) -> dict:
    """Return {name, modhash, logged_in} using /api/me.json."""
    tab = tab or browser.ensure_reddit_session()
    res = _call(tab, "/api/me.json")
    if not res.get("ok"):
        return {"logged_in": False, "error": res.get("error") or res}
    data = res["data"].get("data") or {}
    return {
        "logged_in": bool(data.get("name")),
        "name": data.get("name"),
        "modhash": data.get("modhash"),
        "karma": {"link": data.get("link_karma"), "comment": data.get("comment_karma")},
    }


def subreddit_rules(sub: str, tab: dict | None = None) -> dict:
    tab = tab or browser.ensure_reddit_session()
    return _call(tab, f"/r/{sub}/about/rules.json")


def submit_text(sub: str, title: str, text: str, modhash: str, tab: dict | None = None) -> dict:
    tab = tab or browser.ensure_reddit_session()
    body = {"api_type": "json", "kind": "self", "sr": sub, "title": title, "text": text, "uh": modhash}
    res = _call(tab, "/api/submit", "POST", body)
    return _flatten_submit(res)


def submit_link(sub: str, title: str, url: str, modhash: str, tab: dict | None = None) -> dict:
    tab = tab or browser.ensure_reddit_session()
    body = {"api_type": "json", "kind": "link", "sr": sub, "title": title, "url": url, "uh": modhash}
    res = _call(tab, "/api/submit", "POST", body)
    return _flatten_submit(res)


def _flatten_submit(res: dict) -> dict:
    if not res.get("ok"):
        return res
    j = (res["data"].get("json") or {})
    errors = j.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors, "data": res["data"]}
    return {"ok": True, "url": (j.get("data") or {}).get("url"), "id": (j.get("data") or {}).get("id")}


def comment(thing_id: str, text: str, modhash: str, tab: dict | None = None) -> dict:
    tab = tab or browser.ensure_reddit_session()
    body = {"api_type": "json", "thing_id": thing_id, "text": text, "uh": modhash}
    res = _call(tab, "/api/comment", "POST", body)
    if not res.get("ok"):
        return res
    j = res["data"].get("json") or {}
    errors = j.get("errors") or []
    if errors:
        return {"ok": False, "errors": errors}
    things = (j.get("data") or {}).get("things") or [{}]
    return {"ok": True, "id": things[0].get("data", {}).get("id"), "raw": things[0].get("data", {})}


def vote(thing_id: str, direction: int, modhash: str, tab: dict | None = None) -> dict:
    """direction: 1 up, 0 clear, -1 down."""
    tab = tab or browser.ensure_reddit_session()
    body = {"id": thing_id, "dir": direction, "uh": modhash}
    return _call(tab, "/api/vote", "POST", body)


def listing(sub: str, sort: str = "hot", limit: int = 25, tab: dict | None = None) -> dict:
    tab = tab or browser.ensure_reddit_session()
    return _call(tab, f"/r/{sub}/{sort}.json?limit={limit}")
