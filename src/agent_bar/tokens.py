"""Incremental token-usage parsing for the three CLIs' JSONL transcripts.

Normalized cumulative dict: {"input", "output", "cache_read", "cache_write"}.

- kimi:   wire.jsonl lines contain "usage":{"inputOther","output",
          "inputCacheRead","inputCacheCreation"} per model call -> SUM.
- claude: transcript lines contain message.usage with input_tokens /
          output_tokens / cache_*_input_tokens -> SUM, deduped by
          (message.id, requestId) because a message can be rewritten.
- codex:  rollout lines contain cumulative "token_count" totals -> LATEST.
"""

from __future__ import annotations

import json
import os
from typing import Any, Optional

EMPTY = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0}

# Never read more than this in one pass: a runaway transcript writer must not
# be able to OOM the daemon. Remaining bytes are consumed on later calls.
MAX_CHUNK = 64 * 1024 * 1024


def _add(acc: dict, delta: dict) -> None:
    for k in EMPTY:
        acc[k] += delta.get(k, 0)


def _walk_usage(obj: Any) -> list[dict]:
    """Every dict in the tree that looks like a token-usage record."""
    found = []
    if isinstance(obj, dict):
        if "usage" in obj and isinstance(obj["usage"], dict):
            found.append(obj["usage"])
        for v in obj.values():
            found.extend(_walk_usage(v))
    elif isinstance(obj, list):
        for v in obj:
            found.extend(_walk_usage(v))
    return found


class TokenTracker:
    """Reads only new bytes from each transcript and accumulates usage."""

    def __init__(self) -> None:
        self._offsets: dict[str, int] = {}
        self._seen: dict[str, set] = {}
        self._totals: dict[str, dict] = {}
        self._last_ctx: dict[str, int] = {}

    def update(self, path: str, fmt: str) -> dict:
        """Return cumulative normalized usage for `path` (fmt: kimi|claude|codex)."""
        try:
            size = os.path.getsize(path)
        except OSError:
            return dict(self._totals.get(path, EMPTY))

        offset = self._offsets.get(path, 0)
        if size < offset:  # file was rotated/truncated: start over
            offset, self._seen[path] = 0, set()
            self._totals[path] = dict(EMPTY)
        if size == offset:
            return dict(self._totals.get(path, EMPTY))

        total = self._totals.setdefault(path, dict(EMPTY))
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(offset)
            chunk = f.read(MAX_CHUNK + 1)
            self._offsets[path] = f.tell()

        if len(chunk) > MAX_CHUNK:
            # cap hit: keep the last full line for the next pass
            cut = chunk.rfind("\n", 0, MAX_CHUNK)
            cut = cut + 1 if cut > 0 else MAX_CHUNK
            self._offsets[path] = offset + cut
            chunk = chunk[:cut]

        for line in chunk.splitlines():
            line = line.strip()
            if not line or "token" not in line and "usage" not in line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            self._consume(rec, fmt, path, total)
        return dict(total)

    def last_context(self, path: str, fmt: str) -> int:
        """Input tokens of the most recent usage record (context-window fill)."""
        return self._last_ctx.get(path, 0)

    def _consume(self, rec: dict, fmt: str, path: str, total: dict) -> None:
        if fmt == "codex":
            info = self._codex_totals(rec)
            if info:
                total.update(info)  # cumulative: replace, don't add
                ctx = self._codex_last_ctx(rec)
                if ctx:
                    self._last_ctx[path] = ctx
            return

        for usage in _walk_usage(rec):
            if fmt == "kimi":
                # wire.jsonl stores each call TWICE: as "usage.record" and as
                # a step.end loop event with identical numbers. usage.record
                # is the canonical one — anything else would double-count.
                if rec.get("type") != "usage.record":
                    continue
                if "inputOther" in usage or "inputCacheRead" in usage:
                    _add(total, {
                        "input": usage.get("inputOther", 0),
                        "output": usage.get("output", 0),
                        "cache_read": usage.get("inputCacheRead", 0),
                        "cache_write": usage.get("inputCacheCreation", 0),
                    })
                    self._last_ctx[path] = (
                        usage.get("inputOther", 0)
                        + usage.get("inputCacheRead", 0)
                        + usage.get("inputCacheCreation", 0)
                    )
            elif fmt == "claude":
                if "input_tokens" in usage:
                    key = self._claude_dedupe_key(rec)
                    if key and key in self._seen.setdefault(path, set()):
                        continue
                    if key:
                        self._seen[path].add(key)
                    _add(total, {
                        "input": usage.get("input_tokens", 0),
                        "output": usage.get("output_tokens", 0),
                        "cache_read": usage.get("cache_read_input_tokens", 0),
                        "cache_write": usage.get("cache_creation_input_tokens", 0),
                    })
                    self._last_ctx[path] = (
                        usage.get("input_tokens", 0)
                        + usage.get("cache_read_input_tokens", 0)
                        + usage.get("cache_creation_input_tokens", 0)
                    )

    @staticmethod
    def _claude_dedupe_key(rec: dict) -> Optional[str]:
        msg = rec.get("message") or {}
        mid = rec.get("messageId") or msg.get("id")
        rid = rec.get("requestId") or rec.get("request_id")
        return f"{mid}:{rid}" if mid or rid else None

    @staticmethod
    def _codex_last_ctx(rec: dict) -> int:
        def dig(obj: Any) -> int:
            if isinstance(obj, dict):
                t = obj.get("last_token_usage")
                if isinstance(t, dict):
                    return t.get("input_tokens", 0)
                for v in obj.values():
                    r = dig(v)
                    if r:
                        return r
            elif isinstance(obj, list):
                for v in obj:
                    r = dig(v)
                    if r:
                        return r
            return 0

        return dig(rec)

    @staticmethod
    def _codex_totals(rec: dict) -> Optional[dict]:
        def dig(obj: Any) -> Optional[dict]:
            if isinstance(obj, dict):
                t = obj.get("total_token_usage")
                if isinstance(t, dict):
                    return {
                        "input": t.get("input_tokens", 0),
                        "output": t.get("output_tokens", 0)
                                  + t.get("reasoning_output_tokens", 0),
                        "cache_read": t.get("cached_input_tokens", 0),
                        "cache_write": 0,
                    }
                for v in obj.values():
                    r = dig(v)
                    if r:
                        return r
            elif isinstance(obj, list):
                for v in obj:
                    r = dig(v)
                    if r:
                        return r
            return None

        return dig(rec)


def total_tokens(usage: dict) -> int:
    return sum(usage.get(k, 0) for k in EMPTY)


def fmt_tokens(n: float) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}k"
    return str(int(n))
