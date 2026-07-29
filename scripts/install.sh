#!/usr/bin/env bash
# agent-bar installer: system deps + pipx/pip install + CLI hooks + autostart.
set -euo pipefail

echo "== agent-bar install =="

# 1. System dependencies (Ubuntu/Debian). Other distros: see README.
if command -v apt >/dev/null 2>&1; then
    pkgs="python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-notify-0.7"
    missing=""
    for p in $pkgs; do
        dpkg -s "$p" >/dev/null 2>&1 || missing="$missing $p"
    done
    if [ -n "$missing" ]; then
        echo "Installing system packages:$missing (sudo needed)"
        sudo apt install -y $missing
    fi
else
    echo "WARNING: non-apt distro. Install PyGObject, GTK3 and AyatanaAppIndicator3 manually."
fi

# 2. Install the package itself
SRC="$(cd "$(dirname "$0")/.." && pwd)"
if command -v pipx >/dev/null 2>&1; then
    pipx install --system-site-packages --force "$SRC"
else
    # PEP-668-safe fallback: dedicated venv + symlink into ~/.local/bin
    VENV="$HOME/.local/share/agent-bar/venv"
    python3 -m venv --system-site-packages "$VENV"
    "$VENV/bin/pip" install --quiet --force-reinstall "$SRC"
    mkdir -p "$HOME/.local/bin"
    ln -sf "$VENV/bin/agent-bar" "$HOME/.local/bin/agent-bar"
fi

# 3. Register hooks in Kimi Code, Claude Code and Codex
agent-bar install-hooks

# 4. Autostart via systemd user unit
mkdir -p "$HOME/.config/systemd/user"
cp "$SRC/packaging/agent-bar.service" "$HOME/.config/systemd/user/"
systemctl --user daemon-reload
systemctl --user enable --now agent-bar.service

echo
echo "Done. agent-bar is running in your top bar."
echo "Check: agent-bar stats"
