"""Resource-hardening: read cap, partial lines, last-context tracking."""

import json

from agent_bar.tokens import MAX_CHUNK, TokenTracker

KIMI = {"type": "usage.record",
        "usage": {"inputOther": 100, "output": 10,
                  "inputCacheRead": 1000, "inputCacheCreation": 0}}


def test_last_context_kimi(tmp_path):
    p = tmp_path / "w.jsonl"
    p.write_text(json.dumps(KIMI) + "\n")
    t = TokenTracker()
    t.update(str(p), "kimi")
    assert t.last_context(str(p), "kimi") == 1100


def test_last_context_claude(tmp_path):
    rec = {"message": {"id": "m1", "usage": {
        "input_tokens": 5, "output_tokens": 1,
        "cache_read_input_tokens": 50, "cache_creation_input_tokens": 20}},
        "requestId": "r1"}
    p = tmp_path / "t.jsonl"
    p.write_text(json.dumps(rec) + "\n")
    t = TokenTracker()
    t.update(str(p), "claude")
    assert t.last_context(str(p), "claude") == 75


def test_chunk_cap_leaves_remainder(tmp_path, monkeypatch):
    monkeypatch.setattr("agent_bar.tokens.MAX_CHUNK", 4096)
    line = json.dumps(KIMI) + "\n"
    p = tmp_path / "big.jsonl"
    p.write_text(line * 500)  # ~50 KB, way over the fake cap
    t = TokenTracker()
    u1 = t.update(str(p), "kimi")
    assert 0 < u1["input"] < 100 * 500  # partial progress
    # subsequent calls keep consuming until the file is fully read
    for _ in range(100):
        u = t.update(str(p), "kimi")
        if u["input"] == 100 * 500:
            break
    assert u["input"] == 100 * 500
    assert t.last_context(str(p), "kimi") == 1100


def test_cap_does_not_corrupt_json(tmp_path, monkeypatch):
    """No line is ever split mid-JSON: totals stay exact after draining."""
    monkeypatch.setattr("agent_bar.tokens.MAX_CHUNK", 1000)
    line = json.dumps(KIMI) + "\n"
    p = tmp_path / "big.jsonl"
    p.write_text(line * 100)
    t = TokenTracker()
    for _ in range(200):
        u = t.update(str(p), "kimi")
        if u["input"] == 100 * 100:
            break
    assert u["input"] == 100 * 100
    assert u["cache_read"] == 1000 * 100
