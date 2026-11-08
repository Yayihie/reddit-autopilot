"""Chrome DevTools Protocol (CDP) action backend.

Drives an *isolated* Chrome instance over CDP. Unlike the AppleScript backend
it needs:
  * no "Allow JavaScript from Apple Events" setting (which modern Chrome
    refuses to enable from any script),
  * no accessibility / automation permissions.

It still uses the browser's real same-origin session (cookies + modhash) to hit
Reddit's own /api endpoints, exactly like the AppleScript backend. Requires the
isolated Chrome to be launched once with `rap browser launch`.
"""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import time
import urllib.request

REDDIT = "https://www.reddit.com"


class CDPError(RuntimeError):
    pass


def _port() -> int:
    return int(os.environ.get("RAP_CDP_PORT", "9222"))


def _base() -> str:
    return f"http://127.0.0.1:{_port()}"


def profile_dir() -> str:
    from reddit_autopilot.config import home

    return os.environ.get("RAP_CDP_PROFILE", str(home() / "chrome-profile"))


def _http(path: str, method: str = "GET", timeout: float = 5.0):
    req = urllib.request.Request(_base() + path, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def running() -> bool:
    try:
        _http("/json/version")
        return True
    except Exception:
        return False


def version() -> dict | None:
    try:
        return _http("/json/version")
    except Exception:
        return None


def launch(port: int | None = None, directory: str | None = None) -> bool:
    """Launch the isolated Chrome instance with remote debugging enabled."""
    from reddit_autopilot import activation

    activation.reject_browser_session()
    port = port or _port()
    d = directory or profile_dir()
    os.makedirs(d, exist_ok=True)
    subprocess.run(
        [
            "open", "-na", "Google Chrome", "--args",
            f"--user-data-dir={d}", f"--remote-debugging-port={port}",
            "--no-first-run", "--no-default-browser-check",
        ]
    )
    for _ in range(40):
        if running():
            return True
        time.sleep(0.5)
    return False


def list_tabs() -> list[dict]:
    return [t for t in _http("/json/list") if t.get("type") == "page"]


def find_tab(match: str = "reddit.com") -> dict | None:
    for t in list_tabs():
        if match in (t.get("url") or ""):
            return t
    return None


def new_tab(url: str) -> dict:
    return _http("/json/new?" + url, method="PUT")


def close_tab(tab_id: str) -> None:
    try:
        _http("/json/close/" + tab_id)
    except Exception:
        pass


def evaluate(ws_url: str, expr: str, await_promise: bool = True, timeout: float = 40.0):
    import websockets

    async def go():
        async with websockets.connect(ws_url, max_size=None, open_timeout=timeout) as ws:
            await ws.send(json.dumps({
                "id": 1,
                "method": "Runtime.evaluate",
                "params": {"expression": expr, "awaitPromise": await_promise, "returnByValue": True},
            }))
            while True:
                msg = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
                if msg.get("id") == 1:
                    return msg

    try:
        return asyncio.run(go())
    except Exception as e:
        raise CDPError(str(e))


def evaluate_value(ws_url: str, expr: str, await_promise: bool = True):
    msg = evaluate(ws_url, expr, await_promise)
    result = (msg.get("result") or {})
    if "exceptionDetails" in result:
        raise CDPError(str(result["exceptionDetails"].get("text") or result["exceptionDetails"]))
    res = result.get("result") or {}
    if "value" in res:
        return res["value"]
    return res.get("description")


class CDPSession:
    """A handle to a Reddit tab in the isolated Chrome, speaking the same
    ``fetch(path, method, body)`` surface as the AppleScript backend."""

    def __init__(self, tab: dict | None = None, open_if_missing: bool = True):
        self.tab = tab or find_tab() or (new_tab(REDDIT) if open_if_missing else None)
        if not self.tab:
            raise CDPError("no tab available")
        self.ws_url = self.tab["webSocketDebuggerUrl"]

    def navigate(self, url: str) -> None:
        evaluate_value(
            self.ws_url,
            f"(function(){{location.href={json.dumps(url)}; return 'ok';}})()",
            await_promise=False,
        )
        time.sleep(3)

    def fetch(self, path: str, method: str = "GET", body: dict | None = None) -> dict:
        import urllib.parse

        url = path if path.startswith("http") else REDDIT + path
        opts = {"method": method, "credentials": "include",
                "headers": {"Content-Type": "application/x-www-form-urlencoded"}}
        if body is not None:
            opts["body"] = urllib.parse.urlencode(body)
        expr = (
            "(async()=>{try{const r=await fetch(" + json.dumps(url) + "," + json.dumps(opts) + ");"
            "const t=await r.text();return JSON.stringify({status:r.status,text:t});}"
            "catch(e){return JSON.stringify({error:String(e)});}})()"
        )
        raw = evaluate_value(self.ws_url, expr)
        parsed = json.loads(raw)
        if "error" in parsed:
            return {"ok": False, "error": parsed["error"]}
        try:
            data = json.loads(parsed["text"])
        except json.JSONDecodeError:
            data = {"_text": parsed["text"]}
        status = int(parsed["status"])
        return {"ok": 200 <= status < 300, "status": status, "data": data}
