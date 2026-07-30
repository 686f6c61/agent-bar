"""Autostart (login) management via the systemd user unit.

State lives in systemd, not in config.toml: the checkbox in Settings reflects
`systemctl --user is-enabled agent-bar` and toggles enable/disable. The
running daemon is never stopped or started by the toggle — it only affects
the next login.
"""

from __future__ import annotations

import shutil
import subprocess

UNIT = "agent-bar.service"


def available() -> bool:
    """True if systemd user units exist and ours is installed."""
    if not shutil.which("systemctl"):
        return False
    r = subprocess.run(["systemctl", "--user", "cat", UNIT],
                       capture_output=True, text=True)
    return r.returncode == 0


def is_enabled() -> bool:
    r = subprocess.run(["systemctl", "--user", "is-enabled", UNIT],
                       capture_output=True, text=True)
    return r.stdout.strip() == "enabled"


def set_enabled(enabled: bool) -> bool:
    """Enable/disable for next login. Returns success."""
    verb = "enable" if enabled else "disable"
    r = subprocess.run(["systemctl", "--user", verb, UNIT],
                       capture_output=True, text=True)
    return r.returncode == 0
