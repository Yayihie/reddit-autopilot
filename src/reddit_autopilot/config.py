"""Configuration loading for reddit-autopilot.

Config is a plain JSON file (zero deps) at ~/.reddit-autopilot/config.json,
overridable by environment variables. Everything has a sane default so the
tool runs with no setup at all.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path

HOME = Path(os.environ.get("REDDIT_AUTOPILOT_HOME", Path.home() / ".reddit-autopilot"))
CONFIG_PATH = HOME / "config.json"
QUEUE_PATH = HOME / "queue.db"

DEFAULT_CONFIG: dict = {
    "target_subreddits": [],
    "posting_window_utc": [13, 16],  # recommended 06-12 UTC is adjusted per-sub by the planner
    "min_minutes_between_actions": 90,
    "warmup_days": 7,
    "warmup_comments_per_day": 3,
    "user_agent": "macos:reddit-autopilot:0.1.0 (by /u/unknown)",
    "bridge_url": "ws://localhost:9334",
}


@dataclass
class Config:
    data: dict = field(default_factory=dict)
    path: Path = CONFIG_PATH

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        p = path or CONFIG_PATH
        data = dict(DEFAULT_CONFIG)
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
