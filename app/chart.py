"""Heuristic chart-type suggester. No LLM call — fast and deterministic."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any


def _is_numeric(v: Any) -> bool:
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_temporal(v: Any) -> bool:
    return isinstance(v, (date, datetime))


def suggest_chart(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Return a chart spec like {"type": "bar", "x": "region", "y": "revenue"}.

    Rules:
    - Empty rows → no chart.
    - 1 col → no chart (just the table).
    - 2 cols: if first temporal → line; else if second numeric → bar.
    - 3+ cols: bar of the last numeric column over the first non-numeric column.
    """
    if not rows:
        return {}
    first = rows[0]
    cols = list(first.keys())
    if len(cols) < 2:
        return {}

    sample = first
    if len(cols) == 2:
        x, y = cols
        if _is_temporal(sample[x]) and _is_numeric(sample[y]):
            return {"type": "line", "x": x, "y": y}
        if _is_numeric(sample[y]):
            return {"type": "bar", "x": x, "y": y}
        return {}

    # 3+ columns
    non_numeric = next((c for c in cols if not _is_numeric(sample[c])), None)
    numeric = next((c for c in reversed(cols) if _is_numeric(sample[c])), None)
    if non_numeric and numeric:
        return {"type": "bar", "x": non_numeric, "y": numeric}
    return {}
