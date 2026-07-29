"""Hook bridge: runs inside the hooked CLI as `agent-bar hook --cli <name>`.

Reads the event payload (stdin for Kimi/Claude, last argv for Codex), maps it
through the adapter and atomically writes the session state file the daemon
watches. Must be fast, silent and never fail the calling CLI (fail-open).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile

from .adapters import ADAPTERS
from .paths import sessions_dir


def write_state(state) -> None:
    d = sessions_dir()
    fd, tmp = tempfile.mkstemp(dir=d, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(state.to_json(), f)
        os.replace(tmp, d / f"{state.key}.json")
    except OSError:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def run_hook(cli: str, argv_payload: str | None = None) -> int:
    adapter = ADAPTERS.get(cli)
    if adapter is None:
        return 0  # unknown CLI: fail open, never block the caller
    try:
        raw = argv_payload if argv_payload else sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
        state = adapter.handle_event(payload)
        if state is not None:
            write_state(state)
    except Exception:
        pass  # hooks are observational; never break the host CLI
    return 0
