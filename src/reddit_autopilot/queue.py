"""SQLite-backed action queue + scheduler state (deps-free)."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone

from reddit_autopilot.config import queue_path

SCHEMA = """
CREATE TABLE IF NOT EXISTS queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    kind TEXT NOT NULL,            -- submit_text | submit_link | comment | vote
    target TEXT NOT NULL,          -- subreddit, or thing_id for comment/vote
    title TEXT,
    body TEXT,
    url TEXT,
    direction INTEGER,
    run_at TEXT NOT NULL,          -- ISO8601 UTC
    status TEXT NOT NULL DEFAULT 'pending',  -- pending | done | failed | skipped
    result TEXT,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_status_runat ON queue(status, run_at);
"""


def _conn() -> sqlite3.Connection:
    path = queue_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    c = sqlite3.connect(path)
    c.executescript(SCHEMA)
    return c


def add(kind: str, target: str, run_at: str, *, title=None, body=None, url=None, direction=None) -> int:
    with _conn() as c:
        cur = c.execute(
            "INSERT INTO queue (kind,target,title,body,url,direction,run_at,status,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (kind, target, title, body, url, direction, run_at, "pending",
             datetime.now(timezone.utc).isoformat()),
        )
        return cur.lastrowid


def due(now: str | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc).isoformat()
    with _conn() as c:
        c.row_factory = sqlite3.Row
        rows = c.execute(
            "SELECT * FROM queue WHERE status='pending' AND run_at <= ? ORDER BY run_at ASC", (now,)
        ).fetchall()
        return [dict(r) for r in rows]


def all_items(status: str | None = None) -> list[dict]:
    with _conn() as c:
        c.row_factory = sqlite3.Row
        if status:
            rows = c.execute("SELECT * FROM queue WHERE status=? ORDER BY run_at ASC", (status,)).fetchall()
        else:
            rows = c.execute("SELECT * FROM queue ORDER BY run_at ASC").fetchall()
        return [dict(r) for r in rows]


def mark(item_id: int, status: str, result: str = "") -> None:
    with _conn() as c:
        c.execute("UPDATE queue SET status=?, result=? WHERE id=?", (status, result, item_id))


def clear(status: str = "done") -> int:
    with _conn() as c:
        return c.execute("DELETE FROM queue WHERE status=?", (status,)).rowcount


def stats() -> dict:
    with _conn() as c:
        rows = c.execute("SELECT status, COUNT(*) FROM queue GROUP BY status").fetchall()
    return {r[0]: r[1] for r in rows}


def dumps() -> str:
    return json.dumps(all_items(), indent=2)
