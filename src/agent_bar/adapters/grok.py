"""Adapter for Grok CLI (xAI).

Grok has no hook system, so instead of receiving events we WATCH its files:

- ~/.grok/sessions/<urlencoded-cwd>/<session_id>/events.jsonl — event stream;
  status is derived from the tail (permission_requested without a later
  permission_resolved => needs_you; turn_ended => idle; otherwise working).
- .../updates.jsonl — per-turn token usage (turn_completed records, parsed
  incrementally by tokens.py, including costUsdTicks from xAI).
- ~/.grok/active_sessions.json — sessions currently open.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterator, Optional
from urllib.parse import unquote

from .. import paths
from .base import (
    Adapter,
    SessionState,
    STATUS_IDLE,
    STATUS_NEEDS_YOU,
    STATUS_WORKING,
)

TAIL_BYTES = 64 * 1024


def grok_home() -> Path:
    return Path(os.environ.get("GROK_HOME", "~/.grok")).expanduser()


def status_from_events_tail(text: str) -> tuple[str, Optional[str]]:
    """Derive (status, question) from the tail of an events.jsonl file."""
    status = STATUS_IDLE
    pending_tool: Optional[str] = None
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        t = rec.get("type")
        if t == "permission_requested":
            pending_tool = rec.get("tool_name", "tool")
        elif t == "permission_resolved":
            pending_tool = None
        elif t == "turn_started":
            status = STATUS_WORKING
        elif t == "turn_ended":
            status = STATUS_IDLE
        elif t in ("tool_started", "loop_started"):
            status = STATUS_WORKING
    if pending_tool:
        return STATUS_NEEDS_YOU, f"Permission needed: {pending_tool}"
    return status, None


def _tail(path: Path, n: int = TAIL_BYTES) -> str:
    try:
        size = path.stat().st_size
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            if size > n:
                f.seek(size - n)
            return f.read()
    except OSError:
        return ""


def _active_ids() -> set[str]:
    try:
        data = json.loads((grok_home() / "active_sessions.json").read_text())
        return {s.get("session_id", "") for s in data if isinstance(s, dict)}
    except (OSError, json.JSONDecodeError, TypeError):
        return set()


def discover() -> Iterator[SessionState]:
    """Yield the current state of every Grok session on disk."""
    base = grok_home() / "sessions"
    if not base.is_dir():
        return
    active = _active_ids()
    for cwd_dir in sorted(base.iterdir()):
        if not cwd_dir.is_dir():
            continue
        cwd = unquote(cwd_dir.name)
        for sdir in sorted(cwd_dir.iterdir()):
            if not sdir.is_dir():
                continue
            updates = sdir / "updates.jsonl"
            if not updates.exists():
                continue
            status, question = status_from_events_tail(_tail(sdir / "events.jsonl"))
            st = SessionState(
                cli="grok",
                session_id=sdir.name,
                cwd=cwd,
                title=cwd.rsplit("/", 1)[-1] or sdir.name[:12],
                transcript=str(updates),
                status=status,
                question=question,
            )
            if active and sdir.name not in active and status == STATUS_WORKING:
                st.status = STATUS_IDLE  # process gone: can't still be working
            yield st


class GrokAdapter(Adapter):
    """Present for shape consistency; Grok is polled, not hooked."""

    cli = "grok"

    def handle_event(self, payload):
        return None
