"""Planning backend: thin wrapper over latent-9/reddit-growth-mcp (the "where/what
to post" engine). It runs fully credential-free off the public Arctic archive.

If the `reddit-growth` CLI is not installed we degrade gracefully and tell the
user how to enable it (`pip install 'reddit-autopilot[growth]'`).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

GROWTH_BIN = "reddit-growth"


def _resolve() -> str | None:
    """Find the reddit-growth binary, checking PATH and the current interpreter's bin dir."""
    found = shutil.which(GROWTH_BIN)
    if found:
        return found
    local = os.path.join(os.path.dirname(sys.executable), GROWTH_BIN)
    return local if os.path.exists(local) else None


def available() -> bool:
    return _resolve() is not None


def _run(args: list[str], timeout: int = 120) -> dict:
    binary = _resolve()
    if not binary:
        return {
            "ok": False,
            "error": "reddit-growth CLI not found. Install with: pip install 'reddit-autopilot[growth]'",
        }
    p = subprocess.run([binary, *args], capture_output=True, text=True, timeout=timeout)
    return {"ok": p.returncode == 0, "stdout": p.stdout, "stderr": p.stderr, "code": p.returncode}


def compare(subs: list[str]) -> dict:
    return _run(["compare", *subs])


def plan(subs: list[str], tz: int | None = None) -> dict:
    args = ["plan", *subs]
    if tz is not None:
        args += ["--tz", str(tz)]
    return _run(args)


def draft(sub: str, title: str, ptype: str = "text", body: str | None = None) -> dict:
    args = ["draft", sub, "--title", title, "--type", ptype]
    if body:
        args += ["--body", body]
    return _run(args)


def patterns(sub: str, timeframe: str = "month") -> dict:
    return _run(["patterns", sub, "--time", timeframe])


def traffic(sub: str) -> dict:
    return _run(["traffic", sub])


def raw(args: list[str]) -> dict:
    """Escape hatch: pass any arguments straight through to reddit-growth."""
    return _run(args)


def best_target(subs: list[str]) -> str | None:
    """Return the top-ranked subreddit from `compare`, or None."""
    res = _run(["compare", *subs])
    if not res.get("ok"):
        return None
    for line in res["stdout"].splitlines():
        line = line.strip()
        if line.lower().startswith("best pick:"):
            return line.split(":", 1)[1].strip().lstrip("r/")
    return None
