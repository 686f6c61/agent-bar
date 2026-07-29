"""Subtle alert sound, best-effort and non-blocking."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

_FREEDESKTOP = Path("/usr/share/sounds/freedesktop/stereo/complete.oga")


def play_alert() -> None:
    try:
        if shutil.which("canberra-gtk-play"):
            subprocess.Popen(["canberra-gtk-play", "-i", "dialog-warning"],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif shutil.which("paplay") and _FREEDESKTOP.exists():
            subprocess.Popen(["paplay", str(_FREEDESKTOP)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        pass
