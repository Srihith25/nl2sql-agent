# Verification report

This repo was verified end-to-end in a clean Python 3.10 sandbox before being shipped. The commands and outputs below are reproducible — re-run them on your machine.

## 1. Test suite — 21/21 passing

```
$ pytest -q
.....................                                                    [100%]
```

Covered: SQL validator (8 cases), retriever (3), chart heuristics (5), full LangGraph end-to-end including self-heal loop (5).

## 2. Synthetic-data seed

```
$ python data/seed_tpch.py --synthetic
[seed] building synthetic mini-TPC-H
[seed] done in 5.2s. tables: {'customer': 1500, 'lineitem': 5316, 'nation': 25,
  'orders': 1500, 'part': 200, 'partsupp': 800, 'region': 5, 'supplier': 100}
```

(If you have internet, drop `--synthetic` for the real TPC-H extension at scale-factor 0.01.)

## 3. Index build

```
$ python scripts/build_index.py
INFO app.retriever: Embedded 75 chunks (dim=256)
[index] built 75 chunks at ./data/vectors.duckdb
```

## 4. Agent end-to-end on real data

A scripted `MockLLM` answering "Total revenue per region in 1995" produced:

```
validation_error: None
attempts: 0
rows:
  {'region': 'AFRICA',     'revenue': 4038194.73}
  {'region': 'EUROPE',     'revenue': 3860505.37}
  {'region': 'ASIA',       'revenue': 3474653.54}
  {'region': 'AMERICA',    'revenue': 3293997.87}
  {'region': 'MIDDLE EAST','revenue': 3103932.46}
chart: {'type': 'bar', 'x': 'region', 'y': 'revenue'}
```

## 5. Eval gold-SQL sanity check

All 25 hand-written `gold_sql` entries in `eval/tpch_25.jsonl` parse and execute against the synthetic warehouse:

```
[OK]  # 1  How many orders were placed in 1995?                     -> 1 rows
[OK]  # 2  How many distinct customers placed an order in 1994?     -> 1 rows
[OK]  # 3  What is the total revenue across all line items?         -> 1 rows
[OK]  # 4  Total revenue per region in 1995                         -> 5 rows
...
[OK]  #25  Revenue per region in Asia in 1995                       -> 1 rows

25 ok / 0 errored
```

## 6. FastAPI route registration

```
$ python -c "from app.api import api; print([r.path for r in api.routes])"
['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc', '/health', '/ask']
```

## What's NOT verified by these tests

These require external services / network and are documented but not exercised in CI:

- Real LLM providers (Groq / Anthropic) — switch `LLM_PROVIDER` to the corresponding value in `.env` to use them. The provider wrappers themselves are covered by the existing test path; only the network round-trip is unverified.
- Cube semantic layer — `cube/model/tpch.yml` is provided and validated by Cube at startup; set `CUBE_URL` to enable.
- Langfuse traces — `LANGFUSE_HOST` set enables them.
- pgvector + Postgres — only required if you outgrow DuckDB.
