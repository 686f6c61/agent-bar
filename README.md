# agent-bar

[![CI](https://github.com/686f6c61/agent-bar/actions/workflows/ci.yml/badge.svg)](https://github.com/686f6c61/agent-bar/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**Website:** [agent-bar.686f6c61.dev](https://agent-bar.686f6c61.dev) ·
**Repo:** [github.com/686f6c61/agent-bar](https://github.com/686f6c61/agent-bar) ·
**Changelog:** [CHANGELOG.md](CHANGELOG.md)

A Linux top-bar indicator that watches your AI coding agents — **Kimi Code**,
**Claude Code** and **Codex CLI** — and tells you, at a glance:

- **"Needs you"** — the icon pulses orange when an agent is waiting for a
  permission or an answer, with a desktop notification containing the exact
  question. Never miss an agent blocked on you again.
- **Live token counter** — today's token spend right in the panel, updating in
  real time from each CLI's session transcripts.
- **Multi-session** — every active session in one menu: CLI, status, tokens,
  context-window fill (`ctx 73%` — warns you before a compaction hits),
  project. Click one to see what it's asking.
- **Cost estimation** — per-day/session spend (`~$3.42`) from a built-in,
  user-editable price table (`[prices.<cli>]` in the config). Estimates, not
  invoices.
- **History & stats** — persistent SQLite stats: today, this week, and your
  most expensive sessions. `agent-bar stats` for the terminal version.

Works on GNOME (via AppIndicator support, e.g. Ubuntu's built-in
`ubuntu-appindicators`), KDE Plasma and any desktop with StatusNotifierItem
support. X11 and Wayland.

## Install (Ubuntu/Debian)

```bash
git clone https://github.com/686f6c61/agent-bar.git
cd agent-bar
./scripts/install.sh
```

The installer:

1. Installs system deps (`python3-gi`, GTK3, AyatanaAppIndicator3, libnotify).
2. Installs the `agent-bar` command (via `pipx --system-site-packages` if
   available, otherwise `pip --user`).
3. Registers hooks in your CLI configs — **your originals are backed up** as
   `<file>.agent-bar.bak`:
   - Kimi Code: `[[hooks]]` blocks in `~/.kimi-code/config.toml`
   - Claude Code: `hooks` entries in `~/.claude/settings.json`
   - Codex: `notify = [...]` in `~/.codex/config.toml`
4. Enables a systemd user unit so it starts with your session.

Manual alternative:

```bash
sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-ayatanaappindicator3-0.1 gir1.2-notify-0.7
pipx install --system-site-packages .
agent-bar install-hooks
agent-bar run   # or log out/in for the systemd unit
```

## Panel states

| Icon | Meaning |
|---|---|
| gray outline | no active sessions |
| gray dot | session open, turn finished |
| spinning arc | agent working (animated) |
| **pulsing orange `?`** | **an agent needs you** |
| **pulsing orange `2`…`9`/`+`** | **that many agents need you at once** |
| check mark | session ended (shown for a while) |

The label next to the icon is your token spend today (e.g. `3.5M`).
Icons come in two themes — monochrome `symbolic` (GNOME-style, default) and
`color` — selectable in the config file.

## Configuration

Everything is a user option, adjustable two ways:

- **From the panel menu → Settings**: checkboxes for the token counter,
  working animation, desktop notifications and alert sound; radio buttons for
  the icon style (symbolic/color) and the attention blink speed. Changes apply
  instantly and are saved to disk.
- **Editing `~/.config/agent-bar/config.toml`** directly (created with
  documented defaults on first run; edits apply live within ~2 seconds):

```toml
[panel]
style = "symbolic"   # or "color"
show_label = true    # today's token counter in the panel
pulse_ms = 600       # attention blink interval
spinner = true       # animate while working
spinner_ms = 250

[alerts]
notifications = true # desktop notification with the question
sound = true         # subtle sound when an agent needs you
```

## How it works

```
Kimi/Claude hooks ──stdin JSON──┐
                                ├─► agent-bar hook ──► ~/.local/state/agent-bar/sessions/*.json
Codex notify ────argv JSON──────┘            │
                                             ▼ (Gio.FileMonitor)
                                     agent-bar daemon ──► panel icon + menu
                                             │
        token transcripts (wire.jsonl / claude transcripts / codex rollouts)
             ──► incremental parser ──► ~/.local/share/agent-bar/stats.db
```

Hooks are observational and fail-open: agent-bar can never block or break your
CLI sessions. Token counting parses each CLI's own session logs incrementally
(only new bytes are read), so it costs nothing per refresh.

### Per-CLI support

| CLI | Working / done | "Needs you" alert | Tokens |
|---|---|---|---|
| Kimi Code | ✅ | ✅ (`PermissionRequest`, `Notification`) | ✅ |
| Claude Code | ✅ | ✅ (`Notification`, `PermissionRequest`) | ✅ |
| Codex | ✅ (turn complete) | ❌ (Codex exposes no waiting-for-input hook) | ✅ (cumulative) |

Note on Wayland: there is no reliable API to raise/focus the terminal window
that owns the session, so the "needs you" notification carries the full
question text instead.

## Troubleshooting / bug reports

Run the built-in self-check and paste its output into the issue:

```bash
agent-bar doctor
```

It verifies the GTK/AppIndicator stack, notification and sound tools, hook
registration in all three CLIs, and the systemd service.

## Uninstall

```bash
./scripts/uninstall.sh
```

Removes the daemon, the systemd unit and every hook it registered. Your
original configs are restorable from the `*.agent-bar.bak` backups.

## Development

```bash
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m pytest tests/
```

## License

MIT — see [LICENSE](LICENSE).
