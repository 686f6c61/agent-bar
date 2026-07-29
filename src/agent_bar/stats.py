"""Persistent token statistics in SQLite."""

from __future__ import annotations

import sqlite3
import time
from datetime import date, timedelta

from .tokens import EMPTY, total_tokens

_SCHEMA = """
CREATE TABLE IF NOT EXISTS usage (
    day TEXT NOT NULL,
    cli TEXT NOT NULL,
    session_id TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT '',
    input INTEGER NOT NULL DEFAULT 0,
    output INTEGER NOT NULL DEFAULT 0,
    cache_read INTEGER NOT NULL DEFAULT 0,
    cache_write INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (day, cli, session_id)
);
"""


class Stats:
    def __init__(self, db_path):
        self._db = sqlite3.connect(str(db_path))
        self._db.executescript(_SCHEMA)
        self._db.commit()

    def add(self, cli: str, session_id: str, delta: dict, title: str = "") -> None:
        """Attribute a token delta to today."""
        if total_tokens(delta) <= 0:
            return
        day = date.today().isoformat()
        self._db.execute(
            """INSERT INTO usage (day, cli, session_id, title, input, output, cache_read, cache_write)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(day, cli, session_id) DO UPDATE SET
                 title = CASE WHEN excluded.title != '' THEN excluded.title ELSE usage.title END,
                 input = input + excluded.input,
                 output = output + excluded.output,
                 cache_read = cache_read + excluded.cache_read,
                 cache_write = cache_write + excluded.cache_write""",
            (day, cli, session_id, title,
             delta.get("input", 0), delta.get("output", 0),
             delta.get("cache_read", 0), delta.get("cache_write", 0)),
        )
        self._db.commit()

    def _sum_since(self, since: date) -> dict:
        cur = self._db.execute(
            "SELECT cli, SUM(input), SUM(output), SUM(cache_read), SUM(cache_write) "
            "FROM usage WHERE day >= ? GROUP BY cli",
            (since.isoformat(),),
        )
        out = {}
        for cli, i, o, cr, cw in cur:
            out[cli] = {"input": i or 0, "output": o or 0,
                        "cache_read": cr or 0, "cache_write": cw or 0}
        return out

    def today(self) -> dict:
        return self._sum_since(date.today())

    def week(self) -> dict:
        return self._sum_since(date.today() - timedelta(days=6))

    def top_sessions(self, limit: int = 5) -> list[tuple]:
        cur = self._db.execute(
            "SELECT day, cli, title, session_id, "
            "(input + output + cache_read + cache_write) AS total "
            "FROM usage ORDER BY total DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()

    def close(self) -> None:
        self._db.close()


def sum_total(per_cli: dict) -> int:
    return sum(total_tokens(v) for v in per_cli.values())
