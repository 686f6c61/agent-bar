"""Cost estimation and context-window percentage."""

from agent_bar.pricing import (
    DEFAULT_PRICES,
    context_pct,
    cost,
    cost_all,
    fmt_cost,
    merged_prices,
)


def test_cost_uses_price_table():
    u = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
    assert cost("kimi", u) == DEFAULT_PRICES["kimi"]["input"]


def test_cost_all_sums_clis():
    u = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
    total = cost_all({"kimi": u, "claude": u})
    assert total == DEFAULT_PRICES["kimi"]["input"] + DEFAULT_PRICES["claude"]["input"]


def test_user_price_override():
    prices = merged_prices({"kimi": {"input": 99.0}})
    u = {"input": 1_000_000, "output": 0, "cache_read": 0, "cache_write": 0}
    assert cost("kimi", u, prices) == 99.0
    # other keys keep defaults
    assert prices["kimi"]["output"] == DEFAULT_PRICES["kimi"]["output"]


def test_context_pct():
    assert context_pct("kimi", 131_072) == 50.0
    assert context_pct("kimi", 0) is None
    assert context_pct("unknown-cli", 100) is None
    assert context_pct("kimi", 999_999_999) == 100.0  # clamped


def test_cache_read_excluded_from_cost():
    u = {"input": 0, "output": 0, "cache_read": 100_000_000, "cache_write": 0}
    assert cost("kimi", u) == 0.0
    u["cache_write"] = 1_000_000
    assert cost("kimi", u) == DEFAULT_PRICES["kimi"]["cache_write"]


def test_fmt_cost():
    assert fmt_cost(0) == "$0"
    assert fmt_cost(1.5).startswith("~$1.5")
    assert fmt_cost(250) == "~$250"


def test_config_roundtrip_with_prices(tmp_path):
    from agent_bar.config import Config
    path = tmp_path / "config.toml"
    cfg = Config.load(path)  # creates file with prices + context windows
    assert cfg.context_window  # defaults were written and read back
    assert "kimi" in cfg.prices
    cfg2 = Config(style="color", currency="€", show_cost=False)
    cfg2.save(path)
    back = Config.load(path)
    assert back.currency == "€" and back.show_cost is False
    assert back.context_window["kimi"] > 0
