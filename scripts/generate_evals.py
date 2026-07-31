"""Generate eval question-SQL pairs from any connected database.

DEFAULT — zero flags needed:
    1. Run `make api` in one terminal.
    2. Upload your database via the frontend.
    3. In another terminal:
           python scripts/generate_evals.py --output eval/my_questions.jsonl

    The script discovers the uploaded session from the running API, reads its
    schema, asks Claude to write question-SQL pairs, validates each pair by
    executing the SQL, and writes a JSONL ready for eval/run_evals.py.

DIRECT MODE — when the API is not running:
    python scripts/generate_evals.py \\
        --db-url duckdb:///path/to/my.duckdb \\
        --output eval/my_questions.jsonl

OPTIONS:
    --output FILE      Output .jsonl path (required)
    --n N              Number of pairs to generate (default: 20)
    --api-url URL      API base URL (default: http://localhost:8000)
    --session-id ID    Use a specific session (default: auto-picks most recent upload)
    --db-url URL       Bypass the API; connect directly to this DB URL
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

_GENERATE_SYSTEM = """\
You are a senior data analyst. Given a database schema, generate diverse natural-language \
questions a business user would ask, paired with correct SQL answers.

Rules:
- Generate exactly {n} question-SQL pairs.
- Cover a variety of query shapes: simple counts, aggregations (SUM/AVG), \
top-N rankings, date/time filters, multi-table joins, GROUP BY breakdowns.
- Base every table name and column name strictly on what appears in SCHEMA — never invent.
- DATE HANDLING: For year-only filters on VARCHAR date columns, use LIKE: \
WHERE date_col LIKE '2015%'. For GROUP BY year, always use \
EXTRACT(YEAR FROM date_col::DATE)::INTEGER AS year (never SUBSTR — it returns a string).
- COLUMN SELECTION: Always select the minimal columns that directly answer the question. \
For 'which movie has the highest X', select title and X. For 'how many', SELECT COUNT(*). \
For 'list all X with Y', select the identifier column(s) and Y. \
Never use SELECT * — it creates ambiguity in result comparison.
- MAX/MIN PER GROUP: For 'highest/lowest X for each Y' questions, use \
ROW_NUMBER() OVER (PARTITION BY y_col ORDER BY x_col DESC) in a subquery, \
then filter WHERE rn = 1. Do NOT group by (y, x) — that returns all rows, not one per group.
- Return ONLY a JSON array — no prose, no markdown fences — in this exact shape:
  [{{"question": "...", "sql": "..."}}, ...]
"""

_GENERATE_USER = """\
SCHEMA:
{schema}

Generate {n} diverse question-SQL pairs for a non-technical business analyst.
Return only the JSON array.
"""


def _strip_fences(s: str) -> str:
    return re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", s.strip(), flags=re.MULTILINE).strip()


# ---------- API-mode helpers ----------

def _discover_session(api_url: str, session_id: str | None) -> dict:
    import httpx
    try:
        resp = httpx.get(f"{api_url}/sessions", timeout=5.0)
        resp.raise_for_status()
        sessions: list[dict] = resp.json()
    except Exception as e:
        raise SystemExit(
            f"\nERROR: Cannot reach API at {api_url}\n"
            f"  → {e}\n"
            f"  Start the API first:  make api\n"
        ) from e

    if session_id:
        match = next((s for s in sessions if s["session_id"] == session_id), None)
        if match is None:
            raise SystemExit(f"ERROR: session '{session_id}' not found.")
        return match

    if not sessions:
        raise SystemExit(
            "\nERROR: No active sessions found.\n"
            "  → Upload a database via the frontend first, then re-run."
        )

    non_default = [s for s in sessions if s.get("label") != "TPC-H Demo"]
    candidates = sorted(non_default or sessions, key=lambda s: s["created_at"], reverse=True)

    if len(candidates) > 1:
        print("Multiple sessions found — using most recent. Pass --session-id to pick one:")
        for s in candidates:
            tables_preview = ", ".join(s["tables"][:4])
            print(f"  {s['session_id'][:8]}...  {s['label']}  (tables: {tables_preview})")
        print()

    return candidates[0]


def _api_schema(api_url: str, session_id: str) -> str:
    import httpx
    resp = httpx.get(f"{api_url}/sessions/{session_id}/schema", timeout=30.0)
    resp.raise_for_status()
    return resp.json()["schema"]


def _api_execute(api_url: str, sql: str, session_id: str) -> list[dict]:
    import httpx
    resp = httpx.post(
        f"{api_url}/execute",
        json={"sql": sql, "session_id": session_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


# ---------- Direct-mode helpers ----------

def _direct_schema(db_url: str) -> str:
    from app.db_adapter import enumerate_chunks_from_url
    chunks = enumerate_chunks_from_url(db_url)
    table_chunks = [c for c in chunks if c.kind == "table"]
    if not table_chunks:
        raise RuntimeError(f"No tables found in {db_url}")
    return "\n\n".join(c.body for c in table_chunks)


def _direct_execute(db_url: str, sql: str) -> list[dict]:
    from app.db_adapter import execute_sql
    return execute_sql(sql, db_url)


# ---------- Core generation ----------

def _generate_and_validate(schema_text: str, n: int, execute_fn) -> list[dict]:
    from app.llm import get_llm

    llm = get_llm()
    print(f"Asking LLM to generate {n} question-SQL pairs...")
    # Each pair is ~150-200 tokens in JSON; budget generously to avoid truncation.
    max_tokens = max(4096, n * 250)
    raw = llm.complete(
        _GENERATE_SYSTEM.format(n=n),
        _GENERATE_USER.format(schema=schema_text, n=n),
        max_tokens=max_tokens,
    )

    try:
        pairs = json.loads(_strip_fences(raw))
    except json.JSONDecodeError as e:
        print(f"ERROR: LLM returned invalid JSON — {e}")
        print("Raw output (first 500 chars):", raw[:500])
        return []

    if not isinstance(pairs, list):
        print(f"ERROR: Expected JSON array, got {type(pairs).__name__}")
        return []

    print(f"\nValidating {len(pairs)} pairs against the database:")
    valid: list[dict] = []
    for i, pair in enumerate(pairs, 1):
        question = (pair.get("question") or "").strip()
        sql = (pair.get("sql") or "").strip()
        if not question or not sql:
            print(f"  [{i:2d}] SKIP   missing question or sql")
            continue
        try:
            rows = execute_fn(sql)
            valid.append({"id": len(valid) + 1, "question": question, "gold_sql": sql})
            print(f"  [{i:2d}] OK     {question[:65]:<65}  ({len(rows)} rows)")
        except Exception as e:
            print(f"  [{i:2d}] ERR    {question[:65]:<65}  {e}")

    return valid


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("--output", required=True,
                    help="Output .jsonl path (e.g. eval/my_questions.jsonl)")
    ap.add_argument("--n", type=int, default=20,
                    help="Number of pairs to generate (default: 20)")
    ap.add_argument("--api-url", default="http://localhost:8000",
                    help="API base URL (default: http://localhost:8000)")
    ap.add_argument("--session-id", default=None,
                    help="Use a specific session ID instead of auto-discovering")
    ap.add_argument("--db-url", default=None,
                    help="Bypass the API; connect directly to this DB URL")
    args = ap.parse_args()

    if args.db_url:
        # Direct mode
        print(f"Mode    : direct (no API required)")
        print(f"Database: {args.db_url}")
        try:
            schema_text = _direct_schema(args.db_url)
        except Exception as e:
            print(f"ERROR: {e}")
            return 1
        execute_fn = lambda sql: _direct_execute(args.db_url, sql)  # noqa: E731
    else:
        # API mode
        session = _discover_session(args.api_url, args.session_id)
        sid = session["session_id"]
        print(f"Mode    : API ({args.api_url})")
        print(f"Session : {session['label']}  ({sid[:8]}...)")
        print(f"Tables  : {', '.join(session['tables'][:5])}")
        print()

        print("Fetching schema from API...")
        try:
            schema_text = _api_schema(args.api_url, sid)
        except Exception as e:
            print(f"ERROR fetching schema: {e}")
            return 1
        execute_fn = lambda sql: _api_execute(args.api_url, sql, sid)  # noqa: E731

    table_count = schema_text.count("TABLE ")
    print(f"Schema  : {table_count} table(s)\n")

    valid = _generate_and_validate(schema_text, args.n, execute_fn)

    if not valid:
        print("\nERROR: No valid pairs generated.")
        return 1

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as f:
        for row in valid:
            f.write(json.dumps(row) + "\n")

    print(f"\n{len(valid)}/{args.n} pairs written to {args.output}")
    print(f"\nNext — run evals:")
    if args.db_url:
        print(f'  python eval/run_evals.py {args.output} --db-url "{args.db_url}"')
    else:
        print(f"  python eval/run_evals.py {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
