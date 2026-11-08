"""Configuration loading for reddit-autopilot.

Config is a plain JSON file (zero deps). Default state lives at
``~/.reddit-autopilot`` so an existing PWG install is unchanged.

Set ``RAP_PROFILE`` (or ``rap --profile <name>``) to isolate a brand. Hashmark
state is ``~/.reddit-autopilot/profiles/hashmark`` and never shares the default
queue, policy log, or Chrome profile with PWG.

``REDDIT_AUTOPILOT_HOME`` still wins when set (tests and explicit overrides).
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

_PROFILE_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,31}$")
_PACKAGED = Path(__file__).resolve().parent / "profiles"

DEFAULT_CONFIG: dict = {
    "mode": "warmup",  # "warmup" disables all links and tightens caps; "normal" allows the 1/day link
    "target_subreddits": [],
    "posting_window_utc": [13, 16],
    "min_minutes_between_actions": 90,
    "warmup_days": 7,
    "warmup_comments_per_day": 3,
    "user_agent": "macos:reddit-autopilot:0.1.0 (by /u/unknown)",
    "bridge_url": "ws://localhost:9334",
}


def profile_name() -> str | None:
    raw = (os.environ.get("RAP_PROFILE") or "").strip().lower()
    if not raw:
        return None
    if not _PROFILE_RE.match(raw):
        raise ValueError(
            f"invalid RAP_PROFILE {raw!r}: use a lowercase slug (letters, digits, _ or -)"
        )
    return raw


def home() -> Path:
    override = os.environ.get("REDDIT_AUTOPILOT_HOME")
    if override:
        return Path(override)
    name = profile_name()
    if name:
        return Path.home() / ".reddit-autopilot" / "profiles" / name
    return Path.home() / ".reddit-autopilot"


def config_path() -> Path:
    return home() / "config.json"


def queue_path() -> Path:
    return home() / "queue.db"


def packaged_profile(name: str | None) -> dict:
    """Return the committed brand template, or {} if none exists."""
    if not name:
        return {}
    path = _PACKAGED / f"{name}.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


# Backward-compatible aliases. Prefer home() / config_path(); these are snapshots
# at import time and tests that change env should reload this module or call home().
HOME = Path(os.environ.get("REDDIT_AUTOPILOT_HOME", Path.home() / ".reddit-autopilot"))
CONFIG_PATH = HOME / "config.json"
QUEUE_PATH = HOME / "queue.db"


@dataclass
class Config:
    data: dict = field(default_factory=dict)
    path: Path = field(default_factory=config_path)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = path or config_path()
        data = dict(DEFAULT_CONFIG)
        packaged = packaged_profile(profile_name())
        if packaged:
            data.update(packaged)
        if p.exists():
            try:
                data.update(json.loads(p.read_text()))
            except json.JSONDecodeError:
                pass
        # env overrides
        if os.environ.get("RAP_SUBREDDITS"):
            data["target_subreddits"] = [s.strip() for s in os.environ["RAP_SUBREDDITS"].split(",") if s.strip()]
        if os.environ.get("RAP_BRIDGE_URL"):
            data["bridge_url"] = os.environ["RAP_BRIDGE_URL"]
        return cls(data=data, path=p)

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2))

    def get(self, key: str, default=None):
        return self.data.get(key, default)

    def set(self, key: str, value) -> None:
        self.data[key] = value

    @property
    def subreddits(self) -> list[str]:
        return list(self.data.get("target_subreddits") or [])

    @property
    def mode(self) -> str:
        return str(self.data.get("mode", "normal")).lower()

    @property
    def brand(self) -> str | None:
        raw = self.data.get("brand") or profile_name()
        if not raw:
            return None
        return str(raw).strip().lower() or None
