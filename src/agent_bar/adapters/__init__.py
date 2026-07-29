from .base import Adapter, SessionState
from .claude import ClaudeAdapter
from .codex import CodexAdapter
from .kimi import KimiAdapter

ADAPTERS: dict[str, Adapter] = {
    "kimi": KimiAdapter(),
    "claude": ClaudeAdapter(),
    "codex": CodexAdapter(),
}

__all__ = ["Adapter", "SessionState", "ADAPTERS"]
