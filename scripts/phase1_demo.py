"""Phase-1 baseline: naive NL→SQL using the full schema in the prompt.

Useful for the eval comparison ("Phase 1 vs Phase 2/3" deltas in your README).
"""
from __future__ import annotations

import sys
from contextlib import closing

import duckdb

from app.config import settings
from app.llm import get_llm
from app.prompts import NAIVE_SYSTEM, naive_user


def dump_schema(con: duckdb.DuckDBPyConnection) -> str:
    rows = con.execute(
        "SELECT sql FROM duckdb_tables() WHERE schema_name='main'"
    ).fetchall()
    return "\n".join(r[0] for r in rows if r[0])


def main() -> int:
    question = " ".join(sys.argv[1:]) or "Total revenue per region in 1995"
    llm = get_llm()
    with closing(duckdb.connect(settings.db_path, read_only=True)) as con:
        schema = dump_schema(con)
        sql = llm.complete(NAIVE_SYSTEM, naive_user(question, schema)).strip().strip("`")
        print("--- SQL ---\n" + sql)
        print("\n--- RESULT ---")
        try:
            print(con.execute(sql).fetchdf())
        except duckdb.Error as e:
            print(f"FAILED: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
