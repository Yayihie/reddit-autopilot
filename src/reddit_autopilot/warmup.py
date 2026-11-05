"""Account warm-up mode.

A cold account that links anything gets removed by Reddit's spam filter. Warm-up
is the boring fix: genuine, unlinked, value-first comments in the communities you
care about, at a human pace, until comment karma and CQS climb.

In warm-up mode the policy engine hard-disables links, so there is no way for
this module to attach one even by mistake. Comments are paced and capped by the
same policy guards as everything else.

State: ~/.reddit-autopilot/warmup.json. Candidates are pulled from Arctic Shift
(live Reddit 403s on /new for fresh sessions).
"""

from __future__ import annotations

import json
import time
import urllib.request
from datetime import datetime, timezone

from reddit_autopilot import content, policy, reddit_api, verify
from reddit_autopilot.config import HOME

STATE_PATH = HOME / "warmup.json"
CANDIDATES_PATH = HOME / "warmup-candidates.json"

UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}

# Never engage here: crisis, self-harm, abuse, debate/apologetics, anti-faith.
SKIP = ["suicide", "kill myself", "killing myself", "end my life", "want to die", "self harm",
        "self-harm", "cutting", "overdose", "abuse", "assault", "rape", "molested",
        "hurting myself", "no reason to live", "exchristian", "ex-christian"]


def _load() -> dict:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text())
    return {"started": None, "days_done": 0, "history": []}


def _save(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2))


def fetch_recent(sub: str, limit: int = 40) -> list[dict]:
    """Recent posts from a sub, filtered against the skip list."""
    url = f"https://arctic-shift.photon-reddit.com/api/posts/search?subreddit={sub}&limit={limit}&sort=desc"
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=40) as r:
        data = json.load(r)["data"]
    out = []
    now = time.time()
    for p in data:
        if p.get("stickied"):
            continue
        blob = ((p.get("title") or "") + " " + (p.get("selftext") or "")).lower()
        if any(k in blob for k in SKIP):
            continue
        out.append({
            "sub": sub,
            "id": p.get("id"),
            "title": p.get("title"),
            "body": (p.get("selftext") or "")[:600],
            "age_days": round((now - p.get("created_utc", now)) / 86400, 1),
            "comments": p.get("num_comments"),
        })
    return out


def sweep(subs: list[str], per_sub: int = 25, spacing: float = 8.0) -> list[dict]:
    """Pull candidates across subs (spaced per the sweep rule) and cache them."""
    rows: list[dict] = []
    for i, s in enumerate(subs):
        try:
            rows.extend(fetch_recent(s, per_sub))
        except Exception as e:
            rows.append({"sub": s, "error": str(e)})
        if i < len(subs) - 1:
            time.sleep(spacing)
    CANDIDATES_PATH.parent.mkdir(parents=True, exist_ok=True)
    CANDIDATES_PATH.write_text(json.dumps(rows, indent=2))
    return rows


def qualifies(text: str) -> dict:
    """A warm-up comment must be link-free and substantive."""
    if policy.has_link(text or ""):
        return {"ok": False, "reason": "warm-up comments must not contain links"}
    if len((text or "").split()) < 15:
        return {"ok": False, "reason": "too short to be a genuine contribution"}
    return {"ok": True}


def post_comment(post_id: str, text: str, sub: str | None = None, live: bool = False, sess=None) -> dict:
    """Post an unlinked warm-up comment under the policy guards."""
    q = qualifies(text)
    if not q["ok"]:
        return {"ok": False, "blocked": q["reason"]}
    try:
        acct = reddit_api.whoami()
    except Exception:
        acct = None
    guard = policy.check("comment", sub, link=False, texts=[text],
                         comment_karma=((acct or {}).get("karma") or {}).get("comment"))
    if not guard["ok"]:
        return {"ok": False, "blocked_by_policy": guard["hard"]}
    if not live:
        return {"ok": True, "dry_run": True, "would_comment": {"post_id": post_id, "sub": sub}}

    sess = sess or reddit_api.get_session()
    res = reddit_api.comment(("t3_" + post_id) if not post_id.startswith("t") else post_id,
                             text, (acct or reddit_api.whoami())["modhash"], sess)
    if res.get("ok"):
        state = _load()
        state.setdefault("history", []).append(
            {"ts": datetime.now(timezone.utc).isoformat(), "sub": sub, "post_id": post_id,
             "comment_id": res.get("id"), "text": text[:200]})
        _save(state)
        if not post_id.startswith("t1_"):
            time.sleep(6)
            res["verification"] = verify.check_and_log(post_id.replace("t3_", ""), res.get("id") or "", sub, sess)
    return res


def upvote_recent(subs: list[str], n: int = 3, live: bool = False, sess=None) -> dict:
    """Light, normal upvoting of good content in the target subs (not manipulation)."""
    try:
        acct = reddit_api.whoami()
    except Exception:
        acct = None
    if not acct or not acct.get("logged_in"):
        return {"ok": False, "error": "not logged in"}
    picked = []
    for s in subs:
        if len(picked) >= n:
            break
        try:
            rows = fetch_recent(s, limit=8)
        except Exception:
            continue
        for r in rows[:2]:
            if len(picked) >= n:
                break
            picked.append((s, r["id"]))
    if not live:
        return {"ok": True, "dry_run": True, "would_upvote": picked}
    sess = sess or reddit_api.get_session()
    done = []
    for s, pid in picked:
        res = reddit_api.vote("t3_" + pid, 1, acct["modhash"], sess)
        done.append({"sub": s, "id": pid, "ok": res.get("ok")})
        time.sleep(5)
    return {"ok": True, "upvoted": done}


# ------------------------------------------------------------------ legacy plan helpers

def plan_day(per_day: int = 3, subs: list[str] | None = None, topics: list[str] | None = None) -> dict:
    subs = subs or ["test"]
    comments = content.warmup_comments(per_day, topics)
    slots = content.next_slots(len(comments))
    items = []
    for c, slot in zip(comments, slots):
        items.append({"sub": subs[len(items) % len(subs)], "text": c, "at": slot.isoformat()})
    return {"ok": True, "items": items}


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
        "mode": _mode(),
        "started": state.get("started"),
        "days_done": done,
        "days_total": total,
        "ready_for_outreach": total > 0 and done >= total,
        "recent": state.get("history", [])[-5:],
    }


def _mode() -> str:
    from reddit_autopilot.config import Config
    return Config.load().mode


def check_ready(min_karma: int = 50) -> dict:
    who = reddit_api.whoami()
    st = status()
    karma = (who.get("karma") or {})
    total_karma = (karma.get("link") or 0) + (karma.get("comment") or 0)
    return {
        "logged_in": who.get("logged_in"),
        "user": who.get("name"),
        "comment_karma": karma.get("comment"),
        "karma": total_karma,
        "ready": bool(who.get("logged_in")) and (karma.get("comment") or 0) >= min_karma
        and st["ready_for_outreach"],
        "note": f"Links unlock at comment karma >= {min_karma} and mode=normal.",
    }
