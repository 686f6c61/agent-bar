"""Bridge/adapter tests: hook payloads become correct session states."""

import json

import pytest

from agent_bar import bridge
from agent_bar.adapters import ADAPTERS
from agent_bar.adapters.base import (
    STATUS_DONE,
    STATUS_IDLE,
    STATUS_NEEDS_YOU,
    STATUS_WORKING,
)


def test_kimi_permission_request_is_needs_you():
    st = ADAPTERS["kimi"].handle_event({
        "hook_event_name": "PermissionRequest", "session_id": "s1",
        "cwd": "/p", "tool_name": "Bash",
        "tool_input": {"command": "rm -rf /tmp/x"}})
    assert st.status == STATUS_NEEDS_YOU
    assert "rm -rf /tmp/x" in st.question


def test_kimi_lifecycle():
    a = ADAPTERS["kimi"]
    assert a.handle_event({"hook_event_name": "UserPromptSubmit",
                           "session_id": "s"}).status == STATUS_WORKING
    assert a.handle_event({"hook_event_name": "Stop",
                           "session_id": "s"}).status == STATUS_IDLE
    assert a.handle_event({"hook_event_name": "SessionEnd",
                           "session_id": "s"}).status == STATUS_DONE


def test_claude_notification_includes_message():
    st = ADAPTERS["claude"].handle_event({
        "hook_event_name": "Notification", "session_id": "c1",
        "message": "Claude needs your permission to use Bash",
        "transcript_path": "/tmp/t.jsonl"})
    assert st.status == STATUS_NEEDS_YOU
    assert "permission" in st.question
    assert st.transcript == "/tmp/t.jsonl"


def test_codex_turn_complete():
    st = ADAPTERS["codex"].handle_event({
        "type": "agent-turn-complete", "thread-id": "t-1",
        "last-assistant-message": "All done", "cwd": "/p"})
    assert st.status == STATUS_IDLE
    assert st.title == "All done"


def test_codex_ignores_other_events():
    assert ADAPTERS["codex"].handle_event({"type": "something-else"}) is None


def test_unknown_event_ignored():
    assert ADAPTERS["kimi"].handle_event(
        {"hook_event_name": "Nope", "session_id": "s"}) is None


def test_missing_session_id_ignored():
    assert ADAPTERS["kimi"].handle_event({"hook_event_name": "Stop"}) is None


def test_bridge_writes_state_file(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "sessions_dir", lambda: tmp_path)
    payload = json.dumps({"hook_event_name": "PermissionRequest",
                          "session_id": "s9", "tool_name": "Edit"})
    assert bridge.run_hook("kimi", payload) == 0
    files = list(tmp_path.glob("kimi-s9.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["status"] == STATUS_NEEDS_YOU


def test_bridge_never_fails_on_garbage(tmp_path, monkeypatch):
    monkeypatch.setattr(bridge, "sessions_dir", lambda: tmp_path)
    assert bridge.run_hook("kimi", "not json at all{") == 0
    assert bridge.run_hook("unknown-cli", "{}") == 0
