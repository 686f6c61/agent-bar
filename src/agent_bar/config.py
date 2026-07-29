"""User configuration: ~/.config/agent-bar/config.toml

Written with defaults on first run; every option is documented inline there.
Changing `panel.style` requires a daemon restart; the rest apply live on the
next refresh.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

CONFIG_PATH = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser() \
    / "agent-bar" / "config.toml"

_TEMPLATE = """\
# agent-bar configuration
# (also editable from the panel menu: Settings)

[panel]
# Icon theme: "symbolic" (monochrome, GNOME-style) or "color".
style = "{style}"
# Show today's token counter next to the icon.
show_label = {show_label}
# Blink interval (ms) while a session needs you.
pulse_ms = {pulse_ms}
# Animate the icon while an agent is working.
spinner = {spinner}
# Spinner frame interval (ms).
spinner_ms = {spinner_ms}

[alerts]
# Desktop notification with the question when an agent needs you.
notifications = {notifications}
# Play a subtle sound when an agent needs you.
sound = {sound}

[cost]
# Currency symbol used in the menu and `agent-bar stats`.
currency = "{currency}"
# Show the estimated cost next to token totals.
show_cost = {show_cost}

# Context-window size per CLI (tokens). Used for the "ctx NN%" indicator.
[context_window]
kimi = {cw_kimi}
claude = {cw_claude}
codex = {cw_codex}

# Estimated prices, USD per 1M tokens. Vendors reprice often — adjust to your
# plan. Costs are shown as estimates ("~"), never as exact invoices.
[prices.kimi]
input = {p_kimi_input}
output = {p_kimi_output}
cache_read = {p_kimi_cache_read}
cache_write = {p_kimi_cache_write}

[prices.claude]
input = {p_claude_input}
output = {p_claude_output}
cache_read = {p_claude_cache_read}
cache_write = {p_claude_cache_write}

[prices.codex]
input = {p_codex_input}
output = {p_codex_output}
cache_read = {p_codex_cache_read}
cache_write = {p_codex_cache_write}
"""


def _toml_bool(v: bool) -> str:
    return "true" if v else "false"


@dataclass
class Config:
    style: str = "symbolic"
    show_label: bool = True
    pulse_ms: int = 600
    spinner: bool = True
    spinner_ms: int = 250
    notifications: bool = True
    sound: bool = True
    currency: str = "$"
    show_cost: bool = True
    context_window: dict = field(default_factory=dict)
    prices: dict = field(default_factory=dict)
    extra: dict = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | None = None) -> "Config":
        path = path or CONFIG_PATH
        if not path.exists():
            cls().save(path)
            return cls.load(path)  # read back so prices/context are populated
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            return cls()
        panel, alerts = data.get("panel", {}), data.get("alerts", {})
        cost = data.get("cost", {})
        cfg = cls(
            style=str(panel.get("style", "symbolic")),
            show_label=bool(panel.get("show_label", True)),
            pulse_ms=int(panel.get("pulse_ms", 600)),
            spinner=bool(panel.get("spinner", True)),
            spinner_ms=int(panel.get("spinner_ms", 250)),
            notifications=bool(alerts.get("notifications", True)),
            sound=bool(alerts.get("sound", True)),
            currency=str(cost.get("currency", "$")),
            show_cost=bool(cost.get("show_cost", True)),
            context_window={
                str(k): int(v) for k, v in data.get("context_window", {}).items()
                if isinstance(v, (int, float))
            },
            prices=data.get("prices", {}),
        )
        if cfg.style not in ("symbolic", "color"):
            cfg.style = "symbolic"
        cfg.pulse_ms = max(150, cfg.pulse_ms)
        cfg.spinner_ms = max(100, cfg.spinner_ms)
        return cfg

    def save(self, path: Path | None = None) -> None:
        from .pricing import DEFAULT_CONTEXT_WINDOW, merged_prices
        path = path or CONFIG_PATH
        values: dict = {
            "style": self.style,
            "show_label": _toml_bool(self.show_label),
            "pulse_ms": self.pulse_ms,
            "spinner": _toml_bool(self.spinner),
            "spinner_ms": self.spinner_ms,
            "notifications": _toml_bool(self.notifications),
            "sound": _toml_bool(self.sound),
            "currency": self.currency,
            "show_cost": _toml_bool(self.show_cost),
        }
        prices = merged_prices(self.prices)
        for cli in ("kimi", "claude", "codex"):
            values[f"cw_{cli}"] = self.context_window.get(
                cli, DEFAULT_CONTEXT_WINDOW[cli])
            for k in ("input", "output", "cache_read", "cache_write"):
                values[f"p_{cli}_{k}"] = prices[cli][k]
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(_TEMPLATE.format(**values), encoding="utf-8")
        except OSError:
            pass
