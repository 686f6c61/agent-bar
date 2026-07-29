"""Desktop notifications: libnotify via GI if present, else notify-send."""

from __future__ import annotations

import shutil
import subprocess

_app = "agent-bar"
_backend = None

try:
    import gi
    gi.require_version("Notify", "0.7")
    from gi.repository import Notify

    if Notify.init(_app):
        _backend = "gi"
except (ImportError, ValueError):
    pass


def notify(title: str, body: str = "", urgency: str = "normal") -> None:
    if _backend == "gi":
        try:
            n = Notify.Notification.new(title, body, "agent-bar-attention")
            n.set_urgency(
                Notify.Urgency.CRITICAL if urgency == "critical" else Notify.Urgency.NORMAL
            )
            n.show()
            return
        except Exception:
            pass
    if shutil.which("notify-send"):
        args = ["notify-send", "-a", _app]
        if urgency == "critical":
            args += ["-u", "critical"]
        args += [title, body]
        try:
            subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError:
            pass
