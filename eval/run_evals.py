"""Execution-accuracy harness.

DEFAULT — zero flags needed:
    1. Run `make api` in one terminal.
    2. Upload your database via the frontend.
    3. In another terminal:
           python eval/run_evals.py eval/my_questions.jsonl

    The script discovers the uploaded session automatically from the running API,
    sends each question through POST /ask, runs the gold SQL via POST /execute,
    and compares the result sets.

DIRECT MODE — when the API is not running:
    python eval/run_evals.py eval/tpch_25.jsonl --db-url duckdb:///data/warehouse.duckdb

OPTIONS:
    --api-url URL      API base URL (default: http://localhost:8000)
    --session-id ID    Use a specific session (default: auto-picks most recent upload)
    --db-url URL       Bypass the API; run the agent in-process against this DB URL
    --limit N          Only run the first N cases
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


# ---------- Result comparison ----------

def _normalise_row(r: dict) -> tuple:
    items = []
    for k, v in r.items():
        if isinstance(v, float):
            v = round(v, 4)
        items.append((str(k).lower(), v))
    return tuple(sorted(items))


def _values_row(r: dict) -> tuple:
    vals = []
    for v in r.values():
        if isinstance(v, float):
            v = round(v, 4)
        vals.append(v)
    return tuple(vals)


def exec_equal(gold: list[dict], pred: list[dict]) -> bool:
    # 1. Exact key+value match
    if {_normalise_row(r) for r in gold} == {_normalise_row(r) for r in pred}:
        return True
    if len(gold) != len(pred):
        return False
    # 2. Alias-insensitive: same values in declaration order, column names ignored
    if {_values_row(r) for r in gold} == {_values_row(r) for r in pred}:
        return True
    # 3. Column-subset: agent returned extra context columns but gold columns are correct.
    #    If every gold column appears in pred (by name) with matching values, accept it.
    if gold and pred:
        gold_keys = {k.lower() for k in next(iter(gold)).keys()}
        pred_keys = {k.lower() for k in next(iter(pred)).keys()}
        if gold_keys and gold_keys.issubset(pred_keys):
            def project(row: dict) -> tuple:
                return tuple(sorted(
                    (k.lower(), round(v, 4) if isinstance(v, float) else v)
                    for k, v in row.items() if k.lower() in gold_keys
                ))
            if {project(r) for r in gold} == {project(r) for r in pred}:
                return True
    return False


# ---------- API-mode helpers ----------

def _discover_session(api_url: str, session_id: str | None) -> dict:
    """Return the session dict to use, auto-picking if session_id is None."""
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
            raise SystemExit(f"ERROR: session '{session_id}' not found. Run GET /sessions to list active ones.")
        return match

    if not sessions:
        raise SystemExit(
            "\nERROR: No active sessions found.\n"
            "  → Upload a database via the frontend first, then re-run."
        )

    # Prefer user-uploaded sessions over the built-in TPC-H demo
    non_default = [s for s in sessions if s.get("label") != "TPC-H Demo"]
    candidates = sorted(non_default or sessions, key=lambda s: s["created_at"], reverse=True)

    if len(candidates) > 1:
        print("Multiple sessions found — using most recent. Pass --session-id to pick one:")
        for s in candidates:
            tables_preview = ", ".join(s["tables"][:4])
            print(f"  {s['session_id'][:8]}...  {s['label']}  (tables: {tables_preview})")
        print()

    return candidates[0]


def _api_ask(api_url: str, question: str, session_id: str) -> dict:
    import httpx
    resp = httpx.post(
        f"{api_url}/ask",
        json={"question": question, "session_id": session_id},
        timeout=120.0,
    )
    resp.raise_for_status()
    return resp.json()


def _api_execute(api_url: str, sql: str, session_id: str) -> list[dict]:
    import httpx
    resp = httpx.post(
        f"{api_url}/execute",
        json={"sql": sql, "session_id": session_id},
        timeout=30.0,
    )
    resp.raise_for_status()
    return resp.json()


# ---------- Main ----------

def main() -> int:
    ap = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=__doc__,
    )
    ap.add_argument("path", help="Path to a .jsonl eval file")
    ap.add_argument("--api-url", default="http://localhost:8000",
                    help="API base URL (default: http://localhost:8000)")
    ap.add_argument("--session-id", default=None,
                    help="Use a specific session ID instead of auto-discovering")
    ap.add_argument("--db-url", default=None,
                    help="Bypass the API; run the agent in-process against this DB URL")
    ap.add_argument("--limit", type=int, default=0,
                    help="Only run the first N cases")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="On failures, print gold SQL, agent SQL, and sample rows")
    ap.add_argument("--retries", type=int, default=0, metavar="N",
                    help="On failure, retry the question up to N more times with rephrasing hints")
    args = ap.parse_args()

    cases = [
        json.loads(line)
        for line in Path(args.path).read_text().splitlines()
        if line.strip()
    ]
    if args.limit:
        cases = cases[: args.limit]

    # ---- Choose mode ----
    if args.db_url:
        return _run_direct(cases, args.db_url, args.verbose, args.retries)
    else:
        return _run_api(cases, args.api_url, args.session_id, args.verbose, args.retries)


def _attempt_with_retries(ask_fn, question: str, gold: list[dict], max_retries: int):
    """Try the question, then retry with hints if it fails. Returns (result, pred, retry_index_used)."""
    result = ask_fn(question)
    pred = result.get("rows", [])
    if exec_equal(gold, pred) or max_retries == 0:
        return result, pred, 0
    for i in range(max_retries):
        hint = _RETRY_HINTS[min(i, len(_RETRY_HINTS) - 1)]
        result = ask_fn(question + hint)
        pred = result.get("rows", [])
        if exec_equal(gold, pred):
            return result, pred, i + 1
    return result, pred, max_retries


# Retry hints — appended to the question on each successive retry attempt.
# They change the LLM input so the model tries a different approach.
_RETRY_HINTS = [
    " Select only the columns that directly answer the question — no extra id or computed columns.",
    " Try a completely different SQL approach, using a subquery or CTE if needed.",
    " Focus on minimal output: only the columns and rows the question explicitly asks for.",
]


# ---------- API mode ----------

def _run_api(cases: list[dict], api_url: str, session_id: str | None, verbose: bool = False, retries: int = 0) -> int:
    session = _discover_session(api_url, session_id)
    sid = session["session_id"]
    label = session["label"]
    tables = ", ".join(session["tables"][:5])
    print(f"Session : {label}  ({sid[:8]}...)")
    print(f"Tables  : {tables}")
    print(f"API     : {api_url}")
    print()

    n = ok = exec_err = 0
    total_time = 0.0
    fails = []

    for case in cases:
        n += 1
        t0 = time.time()
        try:
            gold = _api_execute(api_url, case["gold_sql"], sid)
            result, pred, retry_used = _attempt_with_retries(
                lambda q: _api_ask(api_url, q, sid),
                case["question"], gold, retries,
            )
            elapsed = time.time() - t0
            total_time += elapsed

            retry_tag = f"  retry={retry_used}" if retry_used else ""
            if exec_equal(gold, pred):
                ok += 1
                verdict = "PASS"
            else:
                verdict = "FAIL"
                fails.append((
                    case["id"], case["question"],
                    result.get("sql"), result.get("validation_error"),
                ))
                if verbose:
                    _print_diff(case["gold_sql"], result.get("sql"), gold, pred)
            print(
                f"[{ok:3d}/{n:3d}] {verdict:4s}  {case['question'][:68]:68s} "
                f"{elapsed:5.1f}s  attempts={result.get('attempts', 0)}{retry_tag}"
            )
        except Exception as e:  # noqa: BLE001
            exec_err += 1
            print(f"[ERR ] {case['question'][:68]:68s} {e}")

    return _print_summary(n, ok, exec_err, total_time, fails)


# ---------- Direct / in-process mode ----------

def _run_direct(cases: list[dict], db_url: str, verbose: bool = False, retries: int = 0) -> int:
    from app.config import settings
    from app.db_adapter import execute_sql
    from app.graph import get_compiled_agent
    from app.session import session_manager

    print(f"Mode    : in-process (no API required)")
    print(f"Database: {db_url}")

    if db_url == f"duckdb:///{settings.db_path}":
        session = session_manager.get_default()
    else:
        session = session_manager.create_from_url(db_url)

    if session is None:
        print("ERROR: could not create session for the given db_url.")
        return 1

    print(f"Tables  : {', '.join(session.tables[:5])}")
    print()

    agent = get_compiled_agent(retriever=session.retriever)
    n = ok = exec_err = 0
    total_time = 0.0
    fails = []

    for case in cases:
        n += 1
        t0 = time.time()
        try:
            gold = execute_sql(case["gold_sql"], db_url)

            def ask_direct(q: str) -> dict:
                s = agent.invoke({"question": q, "db_url": db_url})
                return {**s, "rows": s.get("rows", [])}

            state, pred, retry_used = _attempt_with_retries(
                ask_direct, case["question"], gold, retries,
            )
            elapsed = time.time() - t0
            total_time += elapsed

            retry_tag = f"  retry={retry_used}" if retry_used else ""
            if exec_equal(gold, pred):
                ok += 1
                verdict = "PASS"
            else:
                verdict = "FAIL"
                fails.append((
                    case["id"], case["question"],
                    state.get("sql"), state.get("validation_error"),
                ))
                if verbose:
                    _print_diff(case["gold_sql"], state.get("sql"), gold, pred)
            print(
                f"[{ok:3d}/{n:3d}] {verdict:4s}  {case['question'][:68]:68s} "
                f"{elapsed:5.1f}s  attempts={state.get('attempts', 0)}{retry_tag}"
            )
        except Exception as e:  # noqa: BLE001
            exec_err += 1
            print(f"[ERR ] {case['question'][:68]:68s} {e}")

    return _print_summary(n, ok, exec_err, total_time, fails)


# ---------- Verbose diff ----------

def _print_diff(gold_sql: str | None, agent_sql: str | None, gold_rows: list, pred_rows: list) -> None:
    print()
    print("  GOLD SQL :", (gold_sql or "").replace("\n", " "))
    print("  AGENT SQL:", (agent_sql or "(none)").replace("\n", " "))
    print(f"  GOLD rows ({len(gold_rows)} total):", gold_rows[:3])
    print(f"  PRED rows ({len(pred_rows)} total):", pred_rows[:3])
    print()


# ---------- Shared summary ----------

def _print_summary(n: int, ok: int, exec_err: int, total_time: float, fails: list) -> int:
    acc = 100 * ok / n if n else 0.0
    print()
    print(f"Execution accuracy: {ok}/{n} = {acc:.1f}%   exec_err={exec_err}")
    if n:
        print(f"Avg latency:        {total_time/n:.2f}s")

    if fails:
        print("\nFailures:")
        for fid, q, sql, verr in fails[:10]:
            preview = (sql or "(no sql)").replace("\n", " ")[:80]
            print(f"  #{fid}: {q[:60]} → {preview}  err={verr}")

    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
