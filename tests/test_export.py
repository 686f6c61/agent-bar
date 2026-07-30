"""CSV export: periods, columns, totals."""

import csv
from datetime import date

from agent_bar.export import export, export_all, HEADER
from agent_bar.stats import Stats


def make_stats(tmp_path):
    db = tmp_path / "stats.db"
    st = Stats(db)
    st.add("kimi", "s1", {"input": 1000, "output": 100, "cache_read": 5000,
                          "cache_write": 0}, title="proj-a")
    st.add("grok", "s2", {"input": 2000, "output": 200, "cache_read": 8000,
                          "cache_write": 0}, title="proj-b")
    return st


def read_csv(path):
    with open(path) as f:
        return list(csv.reader(f))


def test_export_daily_columns_and_totals(tmp_path):
    st = make_stats(tmp_path)
    path = export(st, "daily", tmp_path, prices=None)
    rows = read_csv(path)
    assert rows[0] == HEADER
    assert len(rows) == 4  # header + 2 sessions + TOTAL
    data, total = rows[1:3], rows[3]
    assert total[0] == "TOTAL"
    assert total[3] == "2 sessions"
    assert int(total[4]) == 3000 and int(total[5]) == 300
    assert int(total[6]) == 13000
    # fresh = in+out+write, total = fresh + cache_read
    assert int(total[8]) == 3300 and int(total[9]) == 16300


def test_export_periods_filtering(tmp_path):
    st = make_stats(tmp_path)
    # an old row (40 days ago): only monthly(30)? no — outside all
    old = (date.today().replace(day=1)).isoformat()
    st._db.execute(
        "INSERT INTO usage (day, cli, session_id, title, input, output, cache_read, cache_write) "
        "VALUES (?, 'kimi', 'old1', 'old', 999, 0, 0, 0)",
        (date(2020, 1, 1).isoformat(),))
    st._db.commit()
    path = export(st, "daily", tmp_path, prices=None)
    rows = read_csv(path)
    assert "old1" not in [r[2] for r in rows[1:]]
    assert len(rows) == 4  # header + 2 + TOTAL


def test_export_all_four_files(tmp_path):
    st = make_stats(tmp_path)
    paths = export_all(st, tmp_path, prices=None)
    names = sorted(p.name for p in paths)
    assert len(paths) == 4
    assert any("daily" in n for n in names) and any("monthly" in n for n in names)
    assert any("biweekly" in n for n in names) and any("weekly" in n for n in names)


def test_export_unknown_period_raises(tmp_path):
    st = make_stats(tmp_path)
    import pytest
    with pytest.raises(ValueError):
        export(st, "yearly", tmp_path, prices=None)
