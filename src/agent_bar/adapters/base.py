"""Shared session-state model and adapter protocol.

Each CLI adapter converts a hook payload (stdin JSON from Kimi/Claude, or the
argv JSON from Codex's `notify`) into a SessionState update. The daemon only
ever sees SessionState objects serialized as JSON in the sessions dir.
"""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from typing import Any, Optional

# Session lifecycle statuses understood by the UI.
STATUS_WORKING = "working"    # agent is actively doing something
STATUS_NEEDS_YOU = "needs_you"  # waiting on the user: permission / question / input
STATUS_IDLE = "idle"          # turn finished, session open
STATUS_DONE = "done"          # session ended
STATUS_ERROR = "error"        # last turn failed


@dataclass
class SessionState:
    cli: str
    session_id: str
    status: str = STATUS_IDLE
    title: str = ""
    cwd: str = ""
    question: Optional[str] = None       # pending question/permission text
    transcript: Optional[str] = None     # JSONL file with token usage
    tokens: dict = field(default_factory=dict)  # cumulative, filled by daemon
    updated_at: float = field(default_factory=time.time)

    @property
    def key(self) -> str:
        safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in self.session_id)
        return f"{self.cli}-{safe}"

    def to_json(self) -> dict:
        return asdict(self)

    @classmethod
    def from_json(cls, d: dict) -> "SessionState":
        known = {f for f in cls.__dataclass_fields__}
        return cls(**{k: v for k, v in d.items() if k in known})


class Adapter:
    """Base class for per-CLI adapters."""

    cli: str = ""

    def handle_event(self, payload: dict[str, Any]) -> Optional[SessionState]:
        """Map one hook payload to a state update (None = ignore)."""
        raise NotImplementedError
