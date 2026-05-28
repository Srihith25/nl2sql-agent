"""Execution-accuracy harness.

Usage:
    python eval/run_evals.py eval/tpch_25.jsonl

For each case we:
  1. Run the agent on the question.
  2. Run the gold SQL.
  3. Compare result-sets as sets-of-tuples (order-independent on rows AND columns).
  4. Print a per-case verdict and the final accuracy.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from app.executor import run_sql
from app.graph import get_compiled_agent

logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")


def _normalise_row(r: dict) -> tuple:
    # Cast floats to a fixed precision so 1.0000000001 vs 1.0 don't diverge.
    items = []
    for k, v in r.items():
        if isinstance(v, float):
            v = round(v, 4)
        items.append((str(k).lower(), v))
    return tuple(sorted(items))


def _values_row(r: dict) -> tuple:
    # Column-name-agnostic: compare only values in declaration order.
    vals = []
    for v in r.values():
        if isinstance(v, float):
            v = round(v, 4)
        vals.append(v)
    return tuple(vals)


def exec_equal(gold: list[dict], pred: list[dict]) -> bool:
    # Exact match (keys + values).
    if {_normalise_row(r) for r in gold} == {_normalise_row(r) for r in pred}:
        return True
    # Alias-insensitive fallback: same values, same row count, ignore column names.
    # Handles cases where the model uses descriptive aliases vs the gold's short ones.
    return (
        len(gold) == len(pred)
        and {_values_row(r) for r in gold} == {_values_row(r) for r in pred}
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--limit", type=int, default=0, help="Only run the first N cases.")
    args = ap.parse_args()

    cases = [json.loads(line) for line in Path(args.path).read_text().splitlines() if line.strip()]
    if args.limit:
        cases = cases[: args.limit]

    agent = get_compiled_agent()

    n = ok = parse_fail = exec_err = 0
    total_time = 0.0
    fails = []

    for case in cases:
        n += 1
        t0 = time.time()
        try:
            state = agent.invoke({"question": case["question"]})
            pred = state.get("rows", [])
            gold = run_sql(case["gold_sql"])
            elapsed = time.time() - t0
            total_time += elapsed
            if exec_equal(gold, pred):
                ok += 1
                verdict = "PASS"
            else:
                verdict = "FAIL"
                fails.append((case["id"], case["question"], state.get("sql"), state.get("validation_error")))
            print(f"[{ok:3d}/{n:3d}] {verdict:4s}  {case['question'][:68]:68s} {elapsed:5.1f}s  attempts={state.get('attempts', 0)}")
        except Exception as e:  # noqa: BLE001
            exec_err += 1
            print(f"[ERR ] {case['question'][:68]:68s} {e}")

    acc = 100 * ok / n if n else 0.0
    print()
    print(f"Execution accuracy: {ok}/{n} = {acc:.1f}%   parse_fail={parse_fail}  exec_err={exec_err}")
    print(f"Avg latency:        {total_time/n:.2f}s") if n else None

    if fails:
        print("\nFailures (id, question, sql preview):")
        for fid, q, sql, verr in fails[:10]:
            preview = (sql or "(no sql)").replace("\n", " ")[:80]
            print(f"  - #{fid}: {q[:60]} -> {preview}  err={verr}")

    return 0 if ok == n else 1


if __name__ == "__main__":
    sys.exit(main())
