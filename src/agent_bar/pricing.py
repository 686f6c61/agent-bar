"""Token cost estimation.

There is no API to ask "what does a token cost" — prices live in a built-in
table (USD per 1M tokens) that users can override per CLI in
~/.config/agent-bar/config.toml under [prices.<cli>]. Values are estimates
and go stale as vendors reprice; treat the result as "~", never as an invoice.
Context-window sizes are likewise configurable under [context_window].
"""

from __future__ import annotations

# USD per 1M tokens (defaults; override in config)
DEFAULT_PRICES: dict[str, dict[str, float]] = {
    "kimi":   {"input": 0.60, "output": 2.50, "cache_read": 0.15, "cache_write": 0.60},
    "claude": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "codex":  {"input": 1.25, "output": 10.00, "cache_read": 0.125, "cache_write": 1.25},
}

# tokens per context window (defaults; override in config)
DEFAULT_CONTEXT_WINDOW: dict[str, int] = {
    "kimi": 262_144,
    "claude": 200_000,
    "codex": 200_000,
}


def merged_prices(overrides: dict | None = None) -> dict[str, dict[str, float]]:
    out = {cli: dict(p) for cli, p in DEFAULT_PRICES.items()}
    for cli, p in (overrides or {}).items():
        base = out.setdefault(cli, {"input": 0.0, "output": 0.0,
                                    "cache_read": 0.0, "cache_write": 0.0})
        for k, v in p.items():
            if k in base:
                try:
                    base[k] = float(v)
                except (TypeError, ValueError):
                    pass
    return out


def cost(cli: str, usage: dict, prices: dict | None = None) -> float:
    """Estimated USD for a normalized usage dict.

    Only "fresh" tokens count: input, output and cache-write (cache creation
    is billed). cache-read is excluded — it is re-sent context, cheap or free
    depending on the plan, and it dwarfs everything else.
    """
    p = merged_prices(prices).get(cli)
    if not p:
        return 0.0
    return sum(usage.get(k, 0) * p[k] for k in ("input", "output", "cache_write")) / 1_000_000


def cost_all(per_cli_usage: dict[str, dict], prices: dict | None = None) -> float:
    return sum(cost(cli, u, prices) for cli, u in per_cli_usage.items())


def context_pct(cli: str, last_input: int, windows: dict | None = None) -> float | None:
    """Context-window fill % for the most recent model call (None if unknown)."""
    if not last_input:
        return None
    w = (windows or {}).get(cli) or DEFAULT_CONTEXT_WINDOW.get(cli)
    if not w:
        return None
    return min(100.0, 100.0 * last_input / w)


def fmt_cost(usd: float, currency: str = "$") -> str:
    if usd >= 100:
        return f"~{currency}{usd:.0f}"
    if usd >= 1:
        return f"~{currency}{usd:.2f}"
    return f"~{currency}{usd:.3f}" if usd else f"{currency}0"
