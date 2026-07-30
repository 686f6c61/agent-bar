"""CSV export of token usage and spend per session.

Periods are rolling windows ending today: daily (today), weekly (7 days),
biweekly (15 days), monthly (30 days). Files land in ~/Downloads by default.
"""

from __future__ import annotations

import csv
from datetime import date, timedelta
from pathlib import Path

from .pricing import cost as cli_cost

PERIODS = {"daily": 1, "weekly": 7, "biweekly": 15, "monthly": 30}

HEADER = ["day", "cli", "session_id", "title",
          "input_tokens", "output_tokens",
          "cache_read_tokens", "cache_write_tokens",
          "fresh_tokens", "total_tokens", "cost_usd"]


def default_out_dir() -> Path:
    dl = Path.home() / "Downloads"
    if dl.is_dir():
        return dl
    dl = Path.home() / "Descargas"  # Spanish desktops
    return dl if dl.is_dir() else Path.cwd()


def _rows(stats, since: date, prices: dict) -> list[list]:
    cur = stats._db.execute(
        "SELECT day, cli, session_id, title, input, output, cache_read, cache_write "
        "FROM usage WHERE day >= ? ORDER BY day DESC, cli, 5 DESC",
        (since.isoformat(),),
    )
    rows = []
    for day, cli, sid, title, i, o, cr, cw in cur:
        usage = {"input": i, "output": o, "cache_read": cr, "cache_write": cw}
        fresh = i + o + cw
        rows.append([day, cli, sid, title or "", i, o, cr, cw,
                     fresh, fresh + cr,
                     f"{cli_cost(cli, usage, prices):.4f}"])
    return rows


def export(stats, period: str, out_dir: Path, prices: dict,
           today: date | None = None) -> Path:
    """Write one CSV for a period; returns the file path."""
    if period not in PERIODS:
        raise ValueError(f"unknown period {period!r}: choose from {sorted(PERIODS)}")
    today = today or date.today()
    since = today - timedelta(days=PERIODS[period] - 1)
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"agent-bar-{period}-{today.isoformat()}.csv"
    rows = _rows(stats, since, prices)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(HEADER)
        w.writerows(rows)
        w.writerow(["TOTAL", "", "", f"{len(rows)} sessions",
                    sum(int(r[4]) for r in rows), sum(int(r[5]) for r in rows),
                    sum(int(r[6]) for r in rows), sum(int(r[7]) for r in rows),
                    sum(int(r[8]) for r in rows), sum(int(r[9]) for r in rows),
                    f"{sum(float(r[10]) for r in rows):.4f}"])
    return path


def export_all(stats, out_dir: Path, prices: dict) -> list[Path]:
    return [export(stats, p, out_dir, prices) for p in PERIODS]
