"""Tests for the live SQL validator (app/db_adapter.py), used by the graph
and the API. app/validator.py is a separate, unused-in-production module
covered by its own tests/test_validator.py -- these two suites must stay
in sync on error-handling behavior, since only db_adapter is actually wired
into requests.
"""
from __future__ import annotations

from app.db_adapter import validate_sql


def _url(db_path: str) -> str:
    return f"duckdb:///{db_path}"


def test_select_ok(db_path: str):
    assert validate_sql("SELECT COUNT(*) FROM orders", _url(db_path)) is None


def test_with_cte_ok(db_path: str):
    sql = "WITH t AS (SELECT * FROM orders) SELECT COUNT(*) FROM t"
    assert validate_sql(sql, _url(db_path)) is None


def test_unterminated_quote_is_a_graceful_error(db_path: str):
    """Regression test: an unterminated string literal makes sqlglot raise
    TokenError (not ParseError) during tokenizing, before parsing even
    starts. validate_sql must catch it and return an error string like any
    other bad SQL, so the graph's self-heal loop gets a chance -- instead
    of the exception escaping uncaught into api.py's generic 500 handler
    and surfacing a raw stack-trace-shaped message on the frontend.
    """
    bad = "SELECT * FROM' movies WHERE original_title LIKE '%Dark Knight%'"
    err = validate_sql(bad, _url(db_path))
    assert err is not None
    assert "parse error" in err


def test_parse_error(db_path: str):
    err = validate_sql("SELECT FROM ORDER WHERE", _url(db_path))
    assert err is not None


def test_missing_column(db_path: str):
    err = validate_sql("SELECT no_such_col FROM orders", _url(db_path))
    assert err is not None
    assert "explain" in err


def test_blocks_insert(db_path: str):
    err = validate_sql("INSERT INTO orders VALUES (99,1,0,DATE '1995-01-01','O')", _url(db_path))
    assert err is not None
    assert "disallowed" in err.lower()


def test_blocks_drop(db_path: str):
    err = validate_sql("DROP TABLE orders", _url(db_path))
    assert err is not None
    assert "disallowed" in err.lower()


def test_blocks_update(db_path: str):
    err = validate_sql("UPDATE orders SET o_totalprice = 0", _url(db_path))
    assert err is not None
    assert "disallowed" in err.lower()


def test_empty_sql(db_path: str):
    assert validate_sql("", _url(db_path)) is not None
    assert validate_sql("   ", _url(db_path)) is not None
