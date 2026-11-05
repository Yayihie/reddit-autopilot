"""Scheduler: turn due queue items into Reddit actions through the browser session."""

from __future__ import annotations

import json
import time

from reddit_autopilot import browser, queue, reddit_api


def _execute(item: dict, modhash: str, tab: dict) -> dict:
    kind = item["kind"]
    if kind == "submit_text":
        return reddit_api.submit_text(item["target"], item["title"], item["body"] or "", modhash, tab)
    if kind == "submit_link":
        return reddit_api.submit_link(item["target"], item["title"], item["url"] or "", modhash, tab)
    if kind == "comment":
        return reddit_api.comment(item["target"], item["body"] or "", modhash, tab)
    if kind == "vote":
        return reddit_api.vote(item["target"], item["direction"] or 1, modhash, tab)
    return {"ok": False, "error": f"unknown kind {kind}"}


def run_due(live: bool = False, spacing_seconds: int = 45, limit: int | None = None) -> list[dict]:
    """Process due items. With live=False, everything is a rehearsal (no writes).

    Spacing between actions is applied *even in dry-run* so a real run has the
    same rhythm; pass spacing_seconds=0 to skip waiting during tests.
    """
    items = queue.due()
    if limit:
        items = items[:limit]
    results = []
    tab = modhash = None
    if live and items:
        who = reddit_api.whoami()
        if not who.get("logged_in"):
            return [{"id": None, "status": "failed", "result": "not logged in to Reddit"}]
        tab = browser.ensure_reddit_session()
        modhash = who["modhash"]

    for i, item in enumerate(items):
        if live:
            res = _execute(item, modhash, tab)
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
