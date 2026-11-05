"""Scheduler: turn due queue items into Reddit actions through the browser session."""

from __future__ import annotations

import json
import time

from reddit_autopilot import policy, queue, reddit_api


def _execute(item: dict, modhash: str, sess) -> dict:
    kind = item["kind"]
    if kind == "submit_text":
        return reddit_api.submit_text(item["target"], item["title"], item["body"] or "", modhash, sess)
    if kind == "submit_link":
        return reddit_api.submit_link(item["target"], item["title"], item["url"] or "", modhash, sess)
    if kind == "comment":
        return reddit_api.comment(item["target"], item["body"] or "", modhash, sess)
    if kind == "vote":
        return reddit_api.vote(item["target"], item["direction"] or 1, modhash, sess)
    return {"ok": False, "error": f"unknown kind {kind}"}


def run_due(live: bool = False, spacing_seconds: int = 45, limit: int | None = None) -> list[dict]:
    """Process due items. With live=False everything is a rehearsal (no writes)."""
    items = queue.due()
    if limit:
        items = items[:limit]
    results = []
    sess = modhash = None
    if live and items:
        who = reddit_api.whoami()
        if not who.get("logged_in"):
            return [{"id": None, "status": "failed", "result": "not logged in to Reddit"}]
        sess = reddit_api.get_session()
        modhash = who["modhash"]

    for i, item in enumerate(items):
        if live:
            is_link = item["kind"] == "submit_link" or (
                item["kind"] == "comment" and reddit_api.policy.has_link(item.get("body") or "")
            )
            guard = policy.check(item["kind"], item.get("target"), link=is_link, url=item.get("url"),
                                 texts=[item.get("title") or "", item.get("body") or ""])
            if not guard["ok"]:
                queue.mark(item["id"], "skipped", json.dumps({"blocked_by_policy": guard["hard"]}))
                results.append({"id": item["id"], "status": "skipped", "result": guard["hard"]})
                continue
            res = _execute(item, modhash, sess)
            status = "done" if res.get("ok") else "failed"
            queue.mark(item["id"], status, json.dumps(res))
            results.append({"id": item["id"], "status": status, "result": res})
            if i < len(items) - 1 and spacing_seconds:
                time.sleep(spacing_seconds)
        else:
            results.append({
                "id": item["id"], "status": "dry-run",
                "result": {"would": item["kind"], "target": item["target"],
                           "title": item.get("title"), "run_at": item["run_at"]},
            })
    return results
