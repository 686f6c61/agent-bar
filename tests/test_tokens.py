"""Parser tests with real-format fixture lines from the three CLIs."""

import json

from agent_bar.tokens import TokenTracker, fmt_tokens, total_tokens


def write_lines(tmp_path, name, records):
    p = tmp_path / name
    with open(p, "w") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")
    return str(p)


KIMI_WIRE = {
    "type": "usage.record",
    "model": "kimi-code/k3",
    "usageScope": "turn",
    "usage": {"inputOther": 2075, "output": 515,
              "inputCacheRead": 19200, "inputCacheCreation": 0},
}

# The same call ALSO appears as a step.end loop event with identical numbers:
# counting both was the v0.1.0 double-count bug.
KIMI_STEP_END = {
    "type": "context.append_loop_event",
    "event": {
        "type": "step.end",
        "usage": {"inputOther": 2075, "output": 515,
                  "inputCacheRead": 19200, "inputCacheCreation": 0},
    },
}


def test_kimi_counts_usage_record_only(tmp_path):
    """usage.record + identical step.end twin must count ONCE."""
    path = write_lines(tmp_path, "wire.jsonl", [KIMI_WIRE, KIMI_STEP_END])
    u = TokenTracker().update(path, "kimi")
    assert u == {"input": 2075, "output": 515, "cache_read": 19200, "cache_write": 0}

CLAUDE_LINE = {
    "type": "assistant",
    "requestId": "req_abc",
    "message": {
        "id": "msg_1",
        "usage": {"input_tokens": 2, "output_tokens": 100,
                  "cache_read_input_tokens": 5000,
                  "cache_creation_input_tokens": 23060},
    },
}

CODEX_LINE = {
    "type": "event_msg",
    "payload": {
        "type": "token_count",
        "info": {"total_token_usage": {
            "input_tokens": 2934222, "cached_input_tokens": 2650496,
            "output_tokens": 33379, "reasoning_output_tokens": 13718,
            "total_tokens": 2967601}},
    },
}


def test_kimi_sums_usage(tmp_path):
    path = write_lines(tmp_path, "wire.jsonl", [KIMI_WIRE, KIMI_WIRE])
    t = TokenTracker()
    u = t.update(path, "kimi")
    assert u == {"input": 4150, "output": 1030, "cache_read": 38400, "cache_write": 0}


def test_kimi_incremental_append(tmp_path):
    path = write_lines(tmp_path, "wire.jsonl", [KIMI_WIRE])
    t = TokenTracker()
    t.update(path, "kimi")
    with open(path, "a") as f:
        f.write(json.dumps(KIMI_WIRE) + "\n")
    u = t.update(path, "kimi")
    assert u["input"] == 4150 and total_tokens(u) == 4150 + 1030 + 38400


def test_claude_sums_and_dedupes(tmp_path):
    path = write_lines(tmp_path, "t.jsonl", [CLAUDE_LINE, CLAUDE_LINE])  # same requestId+id
    t = TokenTracker()
    u = t.update(path, "claude")
    assert u["input"] == 2 and u["cache_write"] == 23060  # counted once


def test_claude_distinct_requests_count(tmp_path):
    other = json.loads(json.dumps(CLAUDE_LINE))
    other["requestId"] = "req_def"
    path = write_lines(tmp_path, "t.jsonl", [CLAUDE_LINE, other])
    u = TokenTracker().update(path, "claude")
    assert u["input"] == 4


def test_codex_takes_latest_cumulative(tmp_path):
    bigger = json.loads(json.dumps(CODEX_LINE))
    bigger["payload"]["info"]["total_token_usage"]["input_tokens"] = 3000000
    path = write_lines(tmp_path, "rollout.jsonl", [CODEX_LINE, bigger])
    u = TokenTracker().update(path, "codex")
    assert u["input"] == 3000000
    assert u["output"] == 33379 + 13718
    assert u["cache_read"] == 2650496


def test_truncated_file_restarts(tmp_path):
    path = write_lines(tmp_path, "wire.jsonl", [KIMI_WIRE, KIMI_WIRE])
    t = TokenTracker()
    t.update(path, "kimi")
    write_lines(tmp_path, "wire.jsonl", [KIMI_WIRE])  # truncated rewrite
    u = t.update(path, "kimi")
    assert u["input"] == 2075


def test_missing_file_is_safe(tmp_path):
    t = TokenTracker()
    assert t.update(str(tmp_path / "nope.jsonl"), "kimi") == \
        {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}


def test_fmt_tokens():
    assert fmt_tokens(999) == "999"
    assert fmt_tokens(12400) == "12.4k"
    assert fmt_tokens(2_500_000) == "2.5M"
