"""`agent-bar doctor`: environment self-check for bug reports."""

from __future__ import annotations

import shutil
import subprocess

from . import __version__, paths
from .config import CONFIG_PATH


def _check(label: str, ok: bool, detail: str = "") -> str:
    mark = "OK " if ok else "FAIL"
    suffix = f" — {detail}" if detail else ""
    return f"[{mark}] {label}{suffix}"


def run() -> int:
    lines = [f"agent-bar {__version__} doctor", ""]
    fails = 0

    def add(label, ok, detail=""):
        nonlocal fails
        fails += 0 if ok else 1
        lines.append(_check(label, ok, detail))

    # GTK / AppIndicator stack
    try:
        import gi
        gi.require_version("Gtk", "3.0")
        from gi.repository import Gtk  # noqa: F401
        add("PyGObject + GTK3", True)
    except (ImportError, ValueError) as exc:
        add("PyGObject + GTK3", False, str(exc))

    try:
        gi.require_version("AyatanaAppIndicator3", "0.1")
        from gi.repository import AyatanaAppIndicator3  # noqa: F401
        add("AyatanaAppIndicator3", True)
    except (ImportError, ValueError):
        try:
            gi.require_version("AppIndicator3", "0.1")
            from gi.repository import AppIndicator3  # noqa: F401
            add("AppIndicator3 (legacy)", True)
        except (ImportError, ValueError) as exc:
            add("AppIndicator", False, str(exc))

    add("notify-send", shutil.which("notify-send") is not None)
    add("sound player (canberra/paplay)",
        bool(shutil.which("canberra-gtk-play") or shutil.which("paplay")))

    # hooks registered in each CLI
    checks = {
        "kimi": (paths.kimi_home() / "config.toml", "agent-bar hook"),
        "claude": (paths.claude_home() / "settings.json", "agent-bar hook"),
        "codex": (paths.codex_home() / "config.toml", "agent-bar"),
    }
    for cli, (cfg, needle) in checks.items():
        try:
            found = needle in cfg.read_text(encoding="utf-8")
        except OSError:
            found = False
        add(f"{cli} hooks installed", found, str(cfg))

    # grok needs no hooks: it is watched via its session files
    from .adapters.grok import grok_home
    add("grok data found (file watching, no hooks needed)",
        (grok_home() / "sessions").is_dir(), str(grok_home()))

    # config + state dirs
    add("config file", CONFIG_PATH.exists(), str(CONFIG_PATH))
    add("state dir writable", paths.sessions_dir().exists(),
        str(paths.sessions_dir()))

    # systemd user unit
    if shutil.which("systemctl"):
        r = subprocess.run(["systemctl", "--user", "is-active", "agent-bar"],
                           capture_output=True, text=True)
        state = r.stdout.strip()
        add("systemd user service", state == "active", f"is-active: {state}")

    lines.append("")
    lines.append("All good." if fails == 0
                 else f"{fails} problem(s) found — see lines marked FAIL.")
    print("\n".join(lines))
    return 0 if fails == 0 else 1
