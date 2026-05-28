from __future__ import annotations

from datetime import date

from app.chart import suggest_chart


def test_empty():
    assert suggest_chart([]) == {}


def test_two_cols_bar():
    rows = [{"region": "EU", "rev": 100.0}, {"region": "US", "rev": 200.0}]
    assert suggest_chart(rows) == {"type": "bar", "x": "region", "y": "rev"}


def test_two_cols_line_on_date():
    rows = [{"d": date(2024, 1, 1), "n": 5}, {"d": date(2024, 2, 1), "n": 7}]
    assert suggest_chart(rows) == {"type": "line", "x": "d", "y": "n"}


def test_three_cols_picks_last_numeric():
    rows = [
        {"region": "EU", "country": "FR", "rev": 100.0},
        {"region": "EU", "country": "DE", "rev": 200.0},
    ]
    cs = suggest_chart(rows)
    assert cs == {"type": "bar", "x": "region", "y": "rev"}


def test_no_numeric_no_chart():
    rows = [{"a": "x", "b": "y"}]
    assert suggest_chart(rows) == {}
