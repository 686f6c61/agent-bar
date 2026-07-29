"""Adapter for OpenAI Codex CLI.

Codex has no hook system; it only supports `notify = ["agent-bar", "hook",
"--cli", "codex"]` in ~/.codex/config.toml, which runs after each completed
turn with the event JSON as the LAST ARGV item (not stdin):

  {"type": "agent-turn-complete", "thread-id": ..., "turn-id": ...,
   "cwd": ..., "input-messages": [...], "last-assistant-message": "..."}

So Codex reports turn completion and tokens, but cannot signal "waiting for
input" — a documented limitation. Tokens live in
~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl as cumulative "token_count"
records.
"""

from __future__ import annotations

from typing import Any, Optional

from .. import paths
from .base import Adapter, SessionState, STATUS_IDLE


def _find_transcript(thread_id: str) -> Optional[str]:
    """The rollout filename ends with the thread id."""
    try:
        matches = sorted(
            paths.codex_home().glob(f"sessions/**/rollout-*{thread_id}*.jsonl"),
            key=lambda p: p.stat().st_mtime,
        )
        return str(matches[-1]) if matches else None
    except OSError:
        return None


class CodexAdapter(Adapter):
    cli = "codex"

    def handle_event(self, payload: dict[str, Any]) -> Optional[SessionState]:
        if payload.get("type") != "agent-turn-complete":
            return None
        tid = payload.get("thread-id") or payload.get("thread_id")
        if not tid:
            return None
        last = payload.get("last-assistant-message") or ""
        return SessionState(
            cli=self.cli,
            session_id=tid,
            cwd=payload.get("cwd", ""),
            title=last[:80],
            transcript=_find_transcript(tid),
            status=STATUS_IDLE,
        )
