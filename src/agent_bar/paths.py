"""Filesystem locations used by agent-bar."""

from __future__ import annotations

import os
from pathlib import Path

APP_ID = "agent-bar"


def _xdg(env: str, default: str) -> Path:
    return Path(os.environ.get(env, default)).expanduser()


def state_dir() -> Path:
    """Runtime state written by hooks and read by the daemon."""
    d = _xdg("XDG_STATE_HOME", "~/.local/state") / APP_ID
    return d


def sessions_dir() -> Path:
    d = state_dir() / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    return d


def data_dir() -> Path:
    d = _xdg("XDG_DATA_HOME", "~/.local/share") / APP_ID
    d.mkdir(parents=True, exist_ok=True)
    return d


def stats_db() -> Path:
    return data_dir() / "stats.db"


def assets_dir() -> Path:
    """Bundled SVG icons (works from a wheel and from a source checkout)."""
    return Path(__file__).resolve().parent / "assets"


# --- CLI data roots (overridable for tests) ---

def kimi_home() -> Path:
    return Path(os.environ.get("KIMI_CODE_HOME", "~/.kimi-code")).expanduser()


def claude_home() -> Path:
    return Path(os.environ.get("CLAUDE_CONFIG_DIR", "~/.claude")).expanduser()


def codex_home() -> Path:
    return Path(os.environ.get("CODEX_HOME", "~/.codex")).expanduser()
