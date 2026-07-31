"""Multi-database adapter: introspection, execution, and validation.

Supported connection strings:
  duckdb:///path/to/file.duckdb   — DuckDB file
  duckdb:///:memory:              — in-memory DuckDB
  sqlite:///path/to/file.db       — SQLite
  postgresql://user:pw@host/db    — PostgreSQL
  mysql+pymysql://user:pw@host/db — MySQL

CSV / SQLite / DuckDB files uploaded directly are handled by the session layer.
"""
from __future__ import annotations

import logging
import os
import re
import tempfile
from contextlib import closing
from pathlib import Path
from typing import Any, Optional

import duckdb
import numpy as np
import sqlglot
import sqlglot.errors

log = logging.getLogger(__name__)

_ROW_LIMIT = 10_000
_DISALLOWED = {"insert", "update", "delete", "drop", "alter", "truncate",
               "create", "grant", "revoke", "attach", "detach", "copy"}


# ---------- URL helpers ----------

def is_duckdb_url(url: str) -> bool:
    return url.startswith("duckdb:///") or url == ":memory:"


def duckdb_path_from_url(url: str) -> str:
    if url.startswith("duckdb:///"):
        return url[len("duckdb:///"):]
    return url


def file_to_duckdb_url(file_path: str) -> str:
    """Load an uploaded file into a DuckDB session and return its duckdb:/// URL.

    For .duckdb: validates by opening; raises if invalid.
    For .db: tries DuckDB first, then SQLite.
    For .csv / .sqlite / .parquet: imports into a fresh temp DuckDB.
    """
    p = Path(file_path)
    suffix = p.suffix.lower()

    # .duckdb and .db may both be DuckDB files — try opening directly first.
    if suffix in (".duckdb", ".db"):
        try:
            with closing(duckdb.connect(file_path, read_only=True)) as con:
                con.execute("SHOW TABLES")
            return f"duckdb:///{file_path}"
        except duckdb.Error:
            if suffix == ".duckdb":
                raise ValueError(
                    "Cannot open as DuckDB database. "
                    "If created with a different DuckDB version, export as CSV and upload that instead."
                )
            # .db failed as DuckDB — fall through and try as SQLite below.

    # Use mkdtemp so we control the path and DuckDB always starts from a clean slate.
    tmp_path = os.path.join(tempfile.mkdtemp(), "data.duckdb")
    con = duckdb.connect(tmp_path)
    try:
        if suffix == ".csv":
            tname = _safe_table_name(p.stem)
            con.execute(f"CREATE TABLE {tname} AS SELECT * FROM read_csv_auto('{file_path}')")
        elif suffix in (".sqlite", ".db"):
            try:
                con.execute(f"ATTACH '{file_path}' AS src (TYPE sqlite)")
                tables = [r[0] for r in con.execute("SHOW TABLES FROM src").fetchall()]
                for t in tables:
                    con.execute(f'CREATE TABLE "{t}" AS SELECT * FROM src."{t}"')
                con.execute("DETACH src")
            except Exception as e:
                raise ValueError(
                    f"Could not read '{p.name}' as SQLite: {e}. "
                    "Try exporting your data as CSV and uploading that instead."
                ) from e
        elif suffix == ".parquet":
            tname = _safe_table_name(p.stem)
            con.execute(f"CREATE TABLE {tname} AS SELECT * FROM read_parquet('{file_path}')")
        else:
            raise ValueError(
                f"Unsupported file type '{suffix}'. Accepted: .csv, .db, .sqlite, .duckdb, .parquet"
            )
    finally:
        con.close()
    return f"duckdb:///{tmp_path}"


def _safe_table_name(stem: str) -> str:
    import re
    name = re.sub(r"[^a-zA-Z0-9_]", "_", stem)
    return name if name and name[0].isalpha() else f"t_{name}"


# ---------- Schema introspection ----------

def enumerate_chunks_from_url(db_url: str) -> list:
    """Return list of Chunk objects for all tables in the database."""
    from .retriever import Chunk

    if is_duckdb_url(db_url):
        return _chunks_duckdb(duckdb_path_from_url(db_url))
    return _chunks_sqlalchemy(db_url)


_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2})?")


def _dtype_hint(dtype: str, sample_vals: list) -> str:
    """Append a cast hint when a VARCHAR column appears to hold date values."""
    if "varchar" in dtype.lower() or "text" in dtype.lower():
        strs = [str(v) for v in sample_vals if v is not None]
        if strs and all(_DATE_RE.match(s) for s in strs[:3]):
            return f"{dtype} [date-like — use col::DATE before date functions]"
    return dtype


def _chunks_duckdb(path: str) -> list:
    from .retriever import Chunk

    chunks = []
    with closing(duckdb.connect(path, read_only=True)) as con:
        tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
        for t in tables:
            cols = con.execute(f"DESCRIBE {t}").fetchall()
            try:
                sample = con.execute(f"SELECT * FROM {t} LIMIT 3").fetchdf().to_dict(orient="records")
            except Exception:
                sample = []
            lines = [f"TABLE {t}"]
            for r in cols:
                lines.append(f"  - {r[0]}: {r[1]}")
            lines.append(f"  sample_rows={sample}")
            chunks.append(Chunk("table", t, "\n".join(lines)))
            for r in cols:
                col, dtype = r[0], r[1]
                try:
                    svals = [s[0] for s in con.execute(f'SELECT DISTINCT "{col}" FROM "{t}" LIMIT 5').fetchall()]
                except Exception:
                    svals = []
                hint = _dtype_hint(dtype, svals)
                body = f"COLUMN {t}.{col} ({hint}) sample_values={svals}"
                chunks.append(Chunk("column", f"{t}.{col}", body))
    return chunks


def _chunks_sqlalchemy(db_url: str) -> list:
    from sqlalchemy import create_engine, inspect, text
    from .retriever import Chunk

    engine = create_engine(db_url)
    insp = inspect(engine)
    chunks = []
    with engine.connect() as conn:
        for t in insp.get_table_names():
            cols = insp.get_columns(t)
            try:
                sample = [dict(r) for r in conn.execute(text(f'SELECT * FROM "{t}" LIMIT 3')).mappings()]
            except Exception:
                sample = []
            lines = [f"TABLE {t}"]
            for c in cols:
                lines.append(f"  - {c['name']}: {c['type']}")
            lines.append(f"  sample_rows={sample}")
            chunks.append(Chunk("table", t, "\n".join(lines)))
            for c in cols:
                try:
                    svals = conn.execute(text(f'SELECT DISTINCT "{c["name"]}" FROM "{t}" LIMIT 5')).scalars().fetchall()
                except Exception:
                    svals = []
                body = f"COLUMN {t}.{c['name']} ({c['type']}) sample_values={svals}"
                chunks.append(Chunk("column", f"{t}.{c['name']}", body))
    return chunks


def list_tables(db_url: str) -> list[str]:
    if is_duckdb_url(db_url):
        path = duckdb_path_from_url(db_url)
        with closing(duckdb.connect(path, read_only=True)) as con:
            return [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    from sqlalchemy import create_engine, inspect
    return inspect(create_engine(db_url)).get_table_names()


# ---------- Execution ----------

def execute_sql(sql: str, db_url: str, row_limit: int = _ROW_LIMIT) -> list[dict[str, Any]]:
    if is_duckdb_url(db_url):
        path = duckdb_path_from_url(db_url)
        with closing(duckdb.connect(path, read_only=True)) as con:
            df = con.execute(sql).fetchdf()
        if len(df) > row_limit:
            df = df.head(row_limit)
        return df.to_dict(orient="records")

    from sqlalchemy import create_engine, text
    engine = create_engine(db_url)
    with engine.connect() as conn:
        result = conn.execute(text(sql))
        rows = result.mappings().fetchmany(row_limit)
        return [dict(r) for r in rows]


# ---------- Validation ----------

def validate_sql(sql: str, db_url: str) -> Optional[str]:
    """Return None if valid, error string otherwise."""
    if not sql or not sql.strip():
        return "empty SQL"

    try:
        parsed = sqlglot.parse_one(sql, read="duckdb")
    except sqlglot.errors.ParseError as e:
        return f"parse error: {e}"

    import re
    head = re.match(r"\s*([a-zA-Z]+)", sql.strip())
    head_word = (head.group(1) if head else "").lower()
    if head_word in _DISALLOWED:
        return f"disallowed statement: {head_word.upper()}"
    if parsed and parsed.key.lower() not in {"select", "union", "with", "show", "describe", "explain"}:
        return f"disallowed statement: {parsed.key.upper()}"

    if is_duckdb_url(db_url):
        path = duckdb_path_from_url(db_url)
        try:
            with closing(duckdb.connect(path, read_only=True)) as con:
                con.execute(f"EXPLAIN {sql}")
            return None
        except duckdb.Error as e:
            return f"explain failed: {e}"
        except Exception as e:
            return f"explain failed: {type(e).__name__}: {e}"

    try:
        from sqlalchemy import create_engine, text
        engine = create_engine(db_url)
        with engine.connect() as conn:
            conn.execute(text(f"SELECT * FROM ({sql}) __dry_run__ LIMIT 0"))
        return None
    except Exception as e:
        return f"dry-run failed: {e}"
