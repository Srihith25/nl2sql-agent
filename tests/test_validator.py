from __future__ import annotations

from app.validator import validate_sql


def test_select_ok(db_path: str):
    assert validate_sql("SELECT COUNT(*) FROM orders", db_path=db_path) is None


def test_with_cte_ok(db_path: str):
    sql = "WITH t AS (SELECT * FROM orders) SELECT COUNT(*) FROM t"
    assert validate_sql(sql, db_path=db_path) is None


def test_parse_error(db_path: str):
    err = validate_sql("SELECT FROM ORDER WHERE", db_path=db_path)
    assert err is not None
    assert "parse" in err or "explain" in err  # depends on whether sqlglot or explain catches it


def test_missing_column(db_path: str):
    err = validate_sql("SELECT no_such_col FROM orders", db_path=db_path)
    assert err is not None
    assert "explain" in err


def test_blocks_insert(db_path: str):
    err = validate_sql("INSERT INTO orders VALUES (99,1,0,DATE '1995-01-01','O')", db_path=db_path)
    assert err is not None
    assert "disallowed" in err.lower()


def test_blocks_drop(db_path: str):
    err = validate_sql("DROP TABLE orders", db_path=db_path)
    assert err is not None
    assert "disallowed" in err.lower()


def test_blocks_update(db_path: str):
    err = validate_sql("UPDATE orders SET o_totalprice = 0", db_path=db_path)
    assert err is not None
    assert "disallowed" in err.lower()


def test_empty_sql(db_path: str):
    assert validate_sql("", db_path=db_path) is not None
    assert validate_sql("   ", db_path=db_path) is not None
