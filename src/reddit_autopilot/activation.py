"""Live-send and session activation gates.

Hashmark must stay draft-only until a parent-managed saved routine authorizes
specific posting *and* a documented official Reddit OAuth backend exists.
This module does not implement OAuth and does not collect credentials.

The default (no RAP_PROFILE) path is unchanged for PWG: ``--live`` still
controls writes, subject to policy.py. Hashmark never reaches a browser session
from this process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from reddit_autopilot.config import Config, home, profile_name


class SessionBlocked(RuntimeError):
    """Raised when a Hashmark (or similarly gated) profile would open a browser session."""


def is_hashmark(cfg: Config | None = None) -> bool:
    name = profile_name()
    if name == "hashmark":
        return True
    cfg = cfg or Config.load()
    return cfg.brand == "hashmark"


def _parse_iso(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def blockers(
    *,
    live: bool,
    kind: str | None = None,
    cfg: Config | None = None,
    now: datetime | None = None,
) -> list[str]:
    """Return hard blockers for a live send. Empty when live is False (draft/dry-run)."""
    if not live:
        return []
    cfg = cfg or Config.load()
    if not is_hashmark(cfg):
        return []

    out: list[str] = []
    if not cfg.get("live_sends_enabled", False):
        out.append("Hashmark live_sends_enabled is false (draft-only)")
    if cfg.get("activation_blocked", True):
        out.append(
            "Hashmark activation is blocked until a parent-managed saved routine "
            "authorizes specific posting behavior"
        )
    if kind == "unattended" and not cfg.get("allow_unattended", False):
        out.append("Hashmark unattended loops are disabled")
    if kind == "vote":
        out.append("Hashmark forbids votes")

    earliest = cfg.get("earliest_live_at")
    if earliest:
        boundary = _parse_iso(str(earliest))
        current = now or datetime.now(timezone.utc)
        if boundary and current < boundary:
            out.append(f"no Reddit until {earliest} (America/Los_Angeles)")

    # Current action backends are CDP / AppleScript / cookie+modhash / www.reddit.com/api/*.
    # Official OAuth is not implemented in this repo. Do not invent access.
    out.append(
        "Hashmark live path cannot use CDP, AppleScript, copied cookies/tokens, "
        "or undocumented www.reddit.com/api/*; official Reddit OAuth is not implemented here"
    )
    return out


def require_live(*, live: bool, kind: str | None = None, cfg: Config | None = None) -> list[str]:
    return blockers(live=live, kind=kind, cfg=cfg)


def reject_browser_session(cfg: Config | None = None) -> None:
    """Block CDP/AppleScript session construction for Hashmark."""
    if is_hashmark(cfg):
        raise SessionBlocked(
            "Hashmark profile forbids driving a logged-in browser (CDP, AppleScript, "
            "or cookie/modhash). Official Reddit OAuth is the documented route and is "
            "not implemented in this repo. Session stays on the parent desktop; do not copy it."
        )


def status(cfg: Config | None = None) -> dict[str, Any]:
    cfg = cfg or Config.load()
    live_block = blockers(live=True, kind="comment", cfg=cfg)
    return {
        "profile": profile_name() or "default",
        "brand": cfg.brand,
        "home": str(home()),
        "hashmark": is_hashmark(cfg),
        "live_sends_enabled": bool(cfg.get("live_sends_enabled", False)),
        "activation_blocked": bool(cfg.get("activation_blocked", is_hashmark(cfg))),
        "allow_unattended": bool(cfg.get("allow_unattended", False)),
        "allow_votes": bool(cfg.get("allow_votes", False)),
        "supported_live_backend": cfg.get("supported_live_backend"),
        "manual_review_required": bool(cfg.get("manual_review_required", is_hashmark(cfg))),
        "earliest_live_at": cfg.get("earliest_live_at"),
        "browser_session_blocked": is_hashmark(cfg),
        "live_would_be_blocked": bool(live_block),
        "live_blockers": live_block if is_hashmark(cfg) else [],
    }
