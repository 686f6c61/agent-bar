"""Install/uninstall agent-bar hooks into Kimi Code, Claude Code and Codex.

All edits are idempotent, marked with `>>> agent-bar >>>` blocks in TOML files
and identifiable by the `agent-bar hook` command in Claude's JSON. Every file
is backed up once (<file>.agent-bar.bak) before the first modification.
"""

from __future__ import annotations

import json
import shlex
import shutil
from pathlib import Path

from . import paths

BEGIN = "# >>> agent-bar >>>"
END = "# <<< agent-bar <<<"

KIMI_EVENTS = [
    "SessionStart", "UserPromptSubmit", "PermissionRequest",
    "PermissionResult", "Stop", "StopFailure", "Interrupt", "SessionEnd",
    "Notification",
]
CLAUDE_EVENTS = [
    "SessionStart", "UserPromptSubmit", "PermissionRequest",
    "Notification", "Stop", "SessionEnd",
]


def _backup(path: Path) -> None:
    bak = path.with_suffix(path.suffix + ".agent-bar.bak")
    if path.exists() and not bak.exists():
        shutil.copy2(path, bak)


def _replace_marked_block(text: str, block: str | None) -> str:
    """Insert or replace the marked block; block=None removes it."""
    lines, out, inside = text.splitlines(), [], False
    for line in lines:
        if line.strip() == BEGIN:
            inside = True
            continue
        if line.strip() == END:
            inside = False
            continue
        if not inside:
            out.append(line)
    text = "\n".join(out).rstrip() + "\n"
    if block:
        text = text + f"\n{BEGIN}\n{block}{END}\n"
    return text


def _hook_cmd(bin_path: str, cli: str) -> str:
    return f"{shlex.quote(bin_path)} hook --cli {cli}"


# --- Kimi Code ---

def install_kimi(bin_path: str) -> str:
    cfg = paths.kimi_home() / "config.toml"
    _backup(cfg)
    cmd = _hook_cmd(bin_path, "kimi")
    block = "".join(
        f'[[hooks]]\nevent = "{ev}"\ncommand = "{cmd}"\ntimeout = 5\n\n'
        for ev in KIMI_EVENTS
    )
    old = cfg.read_text() if cfg.exists() else ""
    cfg.write_text(_replace_marked_block(old, block))
    return str(cfg)


def uninstall_kimi() -> str:
    cfg = paths.kimi_home() / "config.toml"
    if cfg.exists():
        cfg.write_text(_replace_marked_block(cfg.read_text(), None))
    return str(cfg)


# --- Claude Code ---

def _claude_entry(cmd: str) -> dict:
    return {"hooks": [{"type": "command", "command": cmd}]}


def install_claude(bin_path: str) -> str:
    cfg = paths.claude_home() / "settings.json"
    _backup(cfg)
    data = json.loads(cfg.read_text()) if cfg.exists() else {}
    hooks = data.setdefault("hooks", {})
    cmd = _hook_cmd(bin_path, "claude")
    for ev in CLAUDE_EVENTS:
        groups = [g for g in hooks.get(ev, [])
                  if "agent-bar hook" not in json.dumps(g)]
        groups.append(_claude_entry(cmd))
        hooks[ev] = groups
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    return str(cfg)


def uninstall_claude() -> str:
    cfg = paths.claude_home() / "settings.json"
    if not cfg.exists():
        return str(cfg)
    data = json.loads(cfg.read_text())
    hooks = data.get("hooks", {})
    for ev in list(hooks):
        groups = [g for g in hooks[ev] if "agent-bar hook" not in json.dumps(g)]
        if groups:
            hooks[ev] = groups
        else:
            del hooks[ev]
    if not hooks:
        data.pop("hooks", None)
    cfg.write_text(json.dumps(data, indent=2) + "\n")
    return str(cfg)


# --- Codex ---

def install_codex(bin_path: str) -> str:
    cfg = paths.codex_home() / "config.toml"
    _backup(cfg)
    old = cfg.read_text() if cfg.exists() else ""
    if 'notify' in old and "agent-bar" not in old:
        # don't clobber a user-defined notify target
        raise RuntimeError(
            f"{cfg} already defines `notify`; add "
            f'["{bin_path}", "hook", "--cli", "codex"] manually.'
        )
    block = f'notify = ["{bin_path}", "hook", "--cli", "codex"]\n'
    cfg.write_text(_replace_marked_block(old, block))
    return str(cfg)


def uninstall_codex() -> str:
    cfg = paths.codex_home() / "config.toml"
    if cfg.exists():
        cfg.write_text(_replace_marked_block(cfg.read_text(), None))
    return str(cfg)


# --- entry points ---

INSTALLERS = {"kimi": install_kimi, "claude": install_claude, "codex": install_codex}
UNINSTALLERS = {"kimi": uninstall_kimi, "claude": uninstall_claude, "codex": uninstall_codex}


def install_all(bin_path: str) -> list[str]:
    results = []
    for cli, fn in INSTALLERS.items():
        try:
            results.append(f"[{cli}] hooks installed in {fn(bin_path)}")
        except Exception as exc:  # report, don't abort the others
            results.append(f"[{cli}] FAILED: {exc}")
    return results


def uninstall_all() -> list[str]:
    return [f"[{cli}] hooks removed from {fn()}" for cli, fn in UNINSTALLERS.items()]
