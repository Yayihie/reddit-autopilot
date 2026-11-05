"""Post-publish verification.

Reddit can remove content after you post it: mods remove it, AutoMod filters it,
or Reddit's own spam system removes it ("[ Removed by Reddit ]"). The write call
returning ok=True means nothing about whether it survived.

This module checks, after posting, whether the thing is still visible, and logs
removals to ~/.reddit-autopilot/removals.jsonl so patterns (a sub, a domain, a
time of day) become visible.
"""

from __future__ import annotations

import json
import time

from reddit_autopilot import reddit_api
from reddit_autopilot.config import HOME

REMOVALS_PATH = HOME / "removals.jsonl"
REMOVED_TEXT = "[ Removed by Reddit ]"
REMOVED_MOD = "[ Removed by moderators ]"
DELETED_TEXT = "[deleted]"


def _find_comment(sess, post_id: str, comment_id: str) -> dict | None:
    res = sess.fetch(f"/comments/{post_id}.json?limit=500&sort=new")
    found = None

    def walk(n):
        nonlocal found
        if isinstance(n, dict):
            if n.get("kind") == "t1":
                d = n.get("data") or {}
                if comment_id.replace("t1_", "") in str(d.get("id")):
                    found = d
            for v in n.values():
                walk(v)
        elif isinstance(n, list):
            for v in n:
                walk(v)

    walk(res.get("data"))
    return found


def check_comment(post_id: str, comment_id: str, sess=None) -> dict:
    """Return {'visible', 'removed', 'removed_by', 'category', 'reason'} for a comment."""
    sess = sess or reddit_api.get_session()
    d = _find_comment(sess, post_id, comment_id)
    if d is None:
        return {"visible": False, "removed": True, "removed_by": "gone",
                "reason": "not present in the thread listing (removed or filtered)"}
    body = d.get("body") or ""
    category = d.get("removed_by_category")
    if body == REMOVED_TEXT or category:
        return {"visible": False, "removed": True,
                "removed_by": "reddit" if body == REMOVED_TEXT else (category or "unknown"),
                "category": category, "reason": "sitewide/automated removal"}
    if body in (REMOVED_MOD, DELETED_TEXT):
        return {"visible": False, "removed": True, "removed_by": "moderator_or_author",
                "category": category, "reason": body}
    return {"visible": True, "removed": False, "removed_by": None, "body": body[:200]}


def log_removal(kind: str, sub: str | None, item_id: str, verdict: dict) -> None:
    REMOVALS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with REMOVALS_PATH.open("a") as f:
        f.write(json.dumps({
            "ts": time.time(), "kind": kind, "sub": sub, "id": item_id, "verdict": verdict,
        }) + "\n")


def check_and_log(post_id: str, comment_id: str, sub: str | None = None, sess=None) -> dict:
    verdict = check_comment(post_id, comment_id, sess)
    if verdict["removed"]:
        log_removal("comment", sub, comment_id, verdict)
    return verdict
