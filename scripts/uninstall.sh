#!/usr/bin/env bash
# agent-bar uninstaller: stops the daemon, removes hooks, package and unit.
# Original CLI configs were backed up as <file>.agent-bar.bak on first install.
set -euo pipefail

systemctl --user disable --now agent-bar.service 2>/dev/null || true
rm -f "$HOME/.config/systemd/user/agent-bar.service"
systemctl --user daemon-reload 2>/dev/null || true

agent-bar uninstall-hooks 2>/dev/null || true

if command -v pipx >/dev/null 2>&1; then
    pipx uninstall agent-bar || true
fi
rm -f "$HOME/.local/bin/agent-bar"
rm -rf "$HOME/.local/share/agent-bar/venv"

echo "Removed. Stats and state kept under ~/.local/share/agent-bar and"
echo "~/.local/state/agent-bar — delete them manually if you want a full wipe."
