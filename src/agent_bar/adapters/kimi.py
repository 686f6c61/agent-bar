"""Adapter for Kimi Code CLI hooks.

Payload (stdin): {"hook_event_name": ..., "session_id": ..., "cwd": ...,
"tool_name"/"tool_input" on tool events, "reason"/"type" on others}.
Tokens live in ~/.kimi-code/sessions/<workDirKey>/<sessionId>/agents/*/wire.jsonl
with per-turn records like "usage":{"inputOther","output","inputCacheRead",
"inputCacheCreation"}.
"""

from __future__ import annotations

from typing import Any, Optional

from .. import paths
from .base import (
    Adapter,
    SessionState,
    STATUS_DONE,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_NEEDS_YOU,
    STATUS_WORKING,
)


def _find_transcript(session_id: str) -> Optional[str]:
    """workDirKey embeds a hash of the cwd, so match by session id instead."""
    try:
        for d in paths.kimi_home().glob(f"sessions/*/{session_id}"):
            wire = d / "agents" / "main" / "wire.jsonl"
            if wire.exists():
                return str(wire)
    except OSError:
        pass
    return None


def _question(payload: dict[str, Any]) -> str:
    tool = payload.get("tool_name", "tool")
    ti = payload.get("tool_input") or {}
    for key in ("command", "file_path", "path", "prompt", "description"):
        if ti.get(key):
            return f"{tool}: {ti[key]}"
    return f"Permission needed: {tool}"


class KimiAdapter(Adapter):
    cli = "kimi"

    def handle_event(self, payload: dict[str, Any]) -> Optional[SessionState]:
        event = payload.get("hook_event_name", "")
        sid = payload.get("session_id")
        if not sid:
            return None
        st = SessionState(
            cli=self.cli,
            session_id=sid,
            cwd=payload.get("cwd", ""),
            transcript=_find_transcript(sid),
        )

        if event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                     "PermissionResult", "SubagentStart", "SubagentStop"):
            st.status = STATUS_WORKING
        elif event == "PermissionRequest":
            st.status = STATUS_NEEDS_YOU
            st.question = _question(payload)
        elif event == "Notification":
            # background task status changes; treat completions as needs-you ping
            st.status = STATUS_NEEDS_YOU
            st.question = payload.get("message") or payload.get("type") or "Background task update"
        elif event in ("Stop", "Interrupt", "PostCompact"):
            st.status = STATUS_IDLE
        elif event == "StopFailure":
            st.status = STATUS_ERROR
            st.question = payload.get("error") or "Turn failed"
        elif event == "SessionEnd":
            st.status = STATUS_DONE
        else:
            return None
        return st
