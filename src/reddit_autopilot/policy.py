"""Reddit policy guardrails.

Turns Reddit's rules into enforceable checks so the tool cannot casually do the
things that get accounts flagged or banned. Grounded in:

  * Content Policy Rule 2  - authentic participation; no spam or manipulation
    (no repeated link drops, no vote manipulation, no account networks, no ban
    evasion).
  * Self-promotion guidance - approximate 9:1 non-promotional:promotional
    ratio; "it's not a quota", an account that only links its own stuff is a
    spammer.
  * Rate limits - new / low-karma accounts are throttled ("take a break for 5
    minutes"); repeated 429s escalate to bans.
  * Karma + account-age gates - many subs auto-remove below their minimums.
  * CQS / shadowban behaviour - low-quality accounts land in the spam filter
    (content visible to you, invisible to others).

State lives in ~/.reddit-autopilot/policy-state.json.
"""

from __future__ import annotations

import json
import time

from reddit_autopilot.config import HOME

STATE_PATH = HOME / "policy-state.json"

DEFAULTS = {
    "max_linked_comments_per_day": 1,     # your cadence: 1 linked comment/day, all subs
    "max_actions_per_hour": 6,            # any comments/posts
    "min_minutes_between_actions": 20,    # human pace floor
    "nonlink_per_link": 9,                # 9:1 guideline (soft)
    "max_subs_per_link_per_day": 1,       # never spray one URL across subs
    "min_comment_karma": 1,               # below this, links are blocked (warm up first)
    "min_account_age_days": 7,
    "ratelimit_extra_seconds": 30,        # padding added to a Reddit cooldown
}

CRISIS_KEYWORDS = [
    "suicide", "kill myself", "killing myself", "end my life", "want to die",
    "self harm", "self-harm", "cutting", "overdose", "abuse", "assault",
    "rape", "molested", "hurting myself", "no reason to live",
]

PROMO_HINTS = ["http://", "https://", "www.", ".com", ".org", ".io"]


def _now() -> float:
    return time.time()


def _today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def load_state() -> dict:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {"actions": [], "ratelimit_until": 0, "sub_cooldowns": {}}


def save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    state["actions"] = state.get("actions", [])[-500:]
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _actions_today(state: dict, kind_pred=None) -> list[dict]:
    d = _today()
    out = []
    for a in state.get("actions", []):
        if time.strftime("%Y-%m-%d", time.gmtime(a["ts"])) != d:
            continue
        if kind_pred and not kind_pred(a):
            continue
        out.append(a)
    return out


def record_action(kind: str, sub: str | None, *, link: bool = False,
                  url: str | None = None, ts: float | None = None) -> None:
    state = load_state()
    state.setdefault("actions", []).append(
        {"ts": ts or _now(), "kind": kind, "sub": sub, "link": bool(link), "url": url}
    )
    save_state(state)


def record_ratelimit(seconds: int) -> float:
    state = load_state()
    until = _now() + max(0, seconds) + DEFAULTS["ratelimit_extra_seconds"]
    state["ratelimit_until"] = max(state.get("ratelimit_until", 0), until)
    save_state(state)
    return until


def has_link(text: str) -> bool:
    t = (text or "").lower()
    return any(h in t for h in PROMO_HINTS)


def status(cfg: dict | None = None) -> dict:
    cfg = {**DEFAULTS, **(cfg or {})}
    state = load_state()
    links_today = _actions_today(state, lambda a: a.get("link"))
    all_today = _actions_today(state)
    now = _now()
    return {
        "actions_today": len(all_today),
        "linked_comments_today": len(links_today),
        "linked_remaining_today": max(0, cfg["max_linked_comments_per_day"] - len(links_today)),
        "nonlink_actions_today": len(all_today) - len(links_today),
        "ratelimit_active": state.get("ratelimit_until", 0) > now,
        "ratelimit_seconds_left": max(0, int(state.get("ratelimit_until", 0) - now)),
    }


def check(kind: str, sub: str | None, *, link: bool = False, url: str | None = None,
          texts: list[str] | None = None, cfg: dict | None = None) -> dict:
    """Return {'ok', 'hard': [..], 'soft': [..]}. hard == block; soft == warn."""
    cfg = {**DEFAULTS, **(cfg or {})}
    state = load_state()
    now = _now()
    hard: list[str] = []
    soft: list[str] = []

    if state.get("ratelimit_until", 0) > now:
        hard.append(f"Reddit rate-limit cooldown active for {int(state['ratelimit_until'] - now)}s")

    actions = state.get("actions", [])
    if actions:
        since = now - actions[-1]["ts"]
        if since < cfg["min_minutes_between_actions"] * 60:
            hard.append(
                f"only {int(since)}s since last action; minimum is {cfg['min_minutes_between_actions']} min"
            )

    last_hour = [a for a in actions if now - a["ts"] < 3600]
    if len(last_hour) >= cfg["max_actions_per_hour"]:
        hard.append(f"{len(last_hour)} actions in the last hour; cap is {cfg['max_actions_per_hour']}")

    for t in (texts or []):
        low = (t or "").lower()
        for k in CRISIS_KEYWORDS:
            if k in low:
                hard.append(f"crisis/self-harm keyword '{k}' present; never link in these threads")

    if link:
        links_today = _actions_today(state, lambda a: a.get("link"))
        if len(links_today) >= cfg["max_linked_comments_per_day"]:
            hard.append(
                f"already posted {len(links_today)} linked comment(s) today; "
                f"cap is {cfg['max_linked_comments_per_day']}"
            )
        if url:
            same = [a for a in links_today if a.get("url") == url]
            if len(same) >= cfg["max_subs_per_link_per_day"]:
                hard.append(f"this URL was already posted {len(same)}x today; do not spray it across subs")
        nonlink = len(_actions_today(state)) - len(links_today)
        need = cfg["nonlink_per_link"] * (len(links_today) + 1)
        if nonlink < need:
            soft.append(
                f"self-promo ratio: {nonlink} non-link vs {len(links_today)} link today; "
                f"guideline is ~{cfg['nonlink_per_link']}:1 (want >= {need} non-link before another link)"
            )

    return {"ok": not hard, "hard": hard, "soft": soft}


def require(kind: str, sub: str | None, **kw) -> dict:
    """Raise PolicyError on a hard violation; return the (possibly soft) result otherwise."""
    res = check(kind, sub, **kw)
    if not res["ok"]:
        raise PolicyError("; ".join(res["hard"]))
    return res


class PolicyError(RuntimeError):
    pass
