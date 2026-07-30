"""Grok support: turn_completed token parsing + status derivation."""

import json

from agent_bar.adapters.base import (
    STATUS_IDLE,
    STATUS_NEEDS_YOU,
    STATUS_WORKING,
)
from agent_bar.adapters.grok import status_from_events_tail
from agent_bar.tokens import TokenTracker

GROK_TURN = {
    "method": "_x.ai/session/update",
    "params": {
        "sessionId": "s1",
        "update": {
            "sessionUpdate": "turn_completed",
            "prompt_id": "p-1",
            "usage": {
                "inputTokens": 223011, "outputTokens": 1569,
                "totalTokens": 224580, "cachedReadTokens": 219648,
                "reasoningTokens": 177, "modelCalls": 2,
            },
        },
    },
}


def write_lines(tmp_path, name, records):
    p = tmp_path / name
    with open(p, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return str(p)


def test_grok_turn_tokens(tmp_path):
    path = write_lines(tmp_path, "updates.jsonl", [GROK_TURN])
    t = TokenTracker()
    u = t.update(path, "grok")
    assert u["input"] == 223011
    assert u["output"] == 1569 + 177  # reasoning counts as output
    assert u["cache_read"] == 219648
    assert t.last_context(path, "grok") == 223011


def test_grok_dedupes_by_prompt_id(tmp_path):
    path = write_lines(tmp_path, "updates.jsonl", [GROK_TURN, GROK_TURN])
    u = TokenTracker().update(path, "grok")
    assert u["input"] == 223011  # once


def test_grok_ignores_other_updates(tmp_path):
    rec = {"params": {"update": {"sessionUpdate": "agent_message_chunk"}}}
    path = write_lines(tmp_path, "updates.jsonl", [rec])
    u = TokenTracker().update(path, "grok")
    assert u["input"] == 0


def test_status_needs_you_on_pending_permission():
    tail = "\n".join([
        json.dumps({"type": "turn_started"}),
        json.dumps({"type": "permission_requested", "tool_name": "Bash"}),
    ])
    status, q = status_from_events_tail(tail)
    assert status == STATUS_NEEDS_YOU and "Bash" in q


def test_status_resolved_back_to_working():
    tail = "\n".join([
        json.dumps({"type": "permission_requested", "tool_name": "Bash"}),
        json.dumps({"type": "permission_resolved"}),
        json.dumps({"type": "tool_started"}),
    ])
    status, q = status_from_events_tail(tail)
    assert status == STATUS_WORKING and q is None


def test_status_idle_after_turn_end():
    tail = "\n".join([
        json.dumps({"type": "turn_started"}),
        json.dumps({"type": "turn_ended"}),
    ])
    status, _ = status_from_events_tail(tail)
    assert status == STATUS_IDLE
