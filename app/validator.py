"""SQL validator: parse + write-statement guard + DuckDB EXPLAIN dry-run."""
from __future__ import annotations

import logging
import re
from contextlib import closing

import duckdb
import sqlglot
import sqlglot.errors

from .config import settings

log = logging.getLogger(__name__)


_DISALLOWED = {
    "insert", "update", "delete", "drop", "alter", "truncate",
    "create", "grant", "revoke", "attach", "detach", "copy",
    "vacuum", "analyze", "pragma",
}


def _first_word(sql: str) -> str:
    # Strip CTEs to find the effective leading verb.
    s = sql.strip().lstrip("(").lstrip()
    # If it's a WITH ..., the first SELECT/UPDATE/INSERT is what counts; we
    # rely on sqlglot for that case. Otherwise just take the first token.
    m = re.match(r"\s*([a-zA-Z]+)", s)
    return (m.group(1) if m else "").lower()


def validate_sql(sql: str, db_path: str | None = None) -> str | None:
    """Return None if the SQL is safe and EXPLAIN succeeds; otherwise an error string."""
    if not sql or not sql.strip():
        return "empty SQL"

    # 1. Parse with sqlglot — catches malformed SQL early.
    try:
        parsed = sqlglot.parse_one(sql, read="duckdb")
    except (sqlglot.errors.ParseError, sqlglot.errors.TokenError) as e:
        return f"parse error: {e}"

    # 2. Write-statement guard. We allow only SELECT / WITH / SHOW / DESCRIBE / EXPLAIN.
    head = _first_word(sql)
    if head in _DISALLOWED:
        return f"disallowed statement: {head.upper()}"
    if parsed is not None and parsed.key.lower() not in {"select", "union", "with", "show", "describe", "explain"}:
        return f"disallowed statement: {parsed.key.upper()}"

    # 3. Dry-run with EXPLAIN — catches missing tables/columns without executing.
    path = db_path or settings.db_path
    try:
        with closing(duckdb.connect(path, read_only=True)) as con:
            con.execute(f"EXPLAIN {sql}")
    except duckdb.Error as e:
        return f"explain failed: {e}"
    except Exception as e:  # noqa: BLE001
        return f"explain failed: {type(e).__name__}: {e}"

    return None
