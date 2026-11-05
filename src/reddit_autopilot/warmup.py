"""Account warm-up protocol (adapted from oh-ashen-one/reddit-growth-skill).

A brand-new Reddit account that jumps straight into promotion gets shadowbanned
or removed fast. The fix is boring: for ~7 days, post a few genuinely helpful
comments a day in the communities you care about — no links, no product
mentions — to build the trust/karma that lets later outreach survive.

State is tracked in ~/.reddit-autopilot/warmup.json so progress persists.
"""

from __future__ import annotations

import json
import random
from datetime import datetime, timezone

from reddit_autopilot import content, reddit_api
from reddit_autopilot.config import HOME

STATE_PATH = HOME / "warmup.json"


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"started": None, "days_done": 0, "history": []}


def _save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def start(days: int = 7, subs: list[str] | None = None) -> dict:
    state = _load()
    state["started"] = datetime.now(timezone.utc).isoformat()
    state["days_total"] = days
    state["subs"] = subs or []
    _save(state)
    return state


def status() -> dict:
    state = _load()
    total = state.get("days_total", 0)
    done = state.get("days_done", 0)
    return {
        "started": state.get("started"),
        "days_done": done,
        "days_total": total,
        "ready_for_outreach": total > 0 and done >= total,
        "history": state.get("history", [])[-5:],
    }


def plan_day(per_day: int = 3, subs: list[str] | None = None, topics: list[str] | None = None) -> dict:
    """Return a plan of comments to post today (does not touch Reddit)."""
    subs = subs or ["test"]  # caller should pass real subs
    comments = content.warmup_comments(per_day, topics)
    slots = content.next_slots(len(comments))
    items = []
    for c, slot in zip(comments, slots):
        items.append({"sub": random.choice(subs), "text": c, "at": slot.isoformat()})
    return {"ok": True, "items": items}


def check_ready(min_karma: int = 50) -> dict:
    """Is the account warmed enough to start real outreach?"""
    who = reddit_api.whoami()
    st = status()
    karma = (who.get("karma") or {})
    total_karma = (karma.get("link") or 0) + (karma.get("comment") or 0)
    return {
        "logged_in": who.get("logged_in"),
        "user": who.get("name"),
        "karma": total_karma,
        "warmup_days_done": st["days_done"],
        "warmup_days_total": st["days_total"],
        "ready": bool(who.get("logged_in")) and total_karma >= min_karma and st["ready_for_outreach"],
        "note": "Warm up for >=7 days and reach some karma before any promotional activity.",
    }
