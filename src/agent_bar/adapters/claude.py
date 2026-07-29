"""Adapter for Claude Code hooks.

Payload (stdin): {"hook_event_name": ..., "session_id": ..., "cwd": ...,
"transcript_path": ...}. Notification carries "message"; PermissionRequest
carries "tool_name"/"tool_input". Tokens live in the transcript JSONL as
"message":{"usage":{"input_tokens","output_tokens","cache_read_input_tokens",
"cache_creation_input_tokens"}}.
"""

from __future__ import annotations

from typing import Any, Optional

from .base import (
    Adapter,
    SessionState,
    STATUS_DONE,
    STATUS_IDLE,
    STATUS_NEEDS_YOU,
    STATUS_WORKING,
)


class ClaudeAdapter(Adapter):
    cli = "claude"

    def handle_event(self, payload: dict[str, Any]) -> Optional[SessionState]:
        event = payload.get("hook_event_name", "")
        sid = payload.get("session_id")
        if not sid:
            return None
        st = SessionState(
            cli=self.cli,
            session_id=sid,
            cwd=payload.get("cwd", ""),
            transcript=payload.get("transcript_path"),
        )

        if event in ("SessionStart", "UserPromptSubmit", "PreToolUse", "PostToolUse",
                     "PermissionResult"):
            st.status = STATUS_WORKING
        elif event == "PermissionRequest":
            st.status = STATUS_NEEDS_YOU
            tool = payload.get("tool_name", "tool")
            ti = payload.get("tool_input") or {}
            detail = ti.get("command") or ti.get("file_path") or ""
            st.question = f"{tool}: {detail}" if detail else f"Permission needed: {tool}"
        elif event == "Notification":
            st.status = STATUS_NEEDS_YOU
            st.question = payload.get("message") or "Claude is waiting for you"
        elif event in ("Stop", "SubagentStop"):
            st.status = STATUS_IDLE
        elif event == "SessionEnd":
            st.status = STATUS_DONE
        else:
            return None
        return st
