# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Setup (first time)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev,groq]"          # free path (Groq)
pip install -e ".[dev,groq,anthropic,embed,langfuse]"  # paid path
python data/seed_tpch.py              # create data/warehouse.duckdb
python scripts/build_index.py         # create data/vectors.duckdb
```

### Running
```bash
make api           # FastAPI on :8000  (uvicorn app.api:api --reload)
make ui            # Streamlit on :8501
make frontend-dev  # Next.js frontend (cd frontend && npm run dev)
make dev           # API + Next.js together
```

### Testing
```bash
make test                       # pytest -q (no API keys needed)
pytest tests/test_graph.py -q   # LangGraph state machine + self-heal loop
pytest tests/test_api.py -q     # HTTP-level /connect + /ask, incl. dual-SQL verify
pytest -k test_validate -q      # by name pattern
```

### Eval & data
```bash
make eval    # python eval/run_evals.py eval/tpch_25.jsonl
make seed    # re-seed TPC-H DuckDB
make index   # rebuild vector index
make clean   # remove __pycache__ + DuckDB files

# Generate eval questions from any DB:
make generate-evals DB_URL=postgresql://... OUT=eval/my.jsonl
```

## Architecture

### LangGraph pipeline (`app/graph.py`)

The agent is a compiled LangGraph state machine over `AgentState` (TypedDict). Flow:

```
retrieve → classify ──► gen_cube   → execute_cube ─► chart → explain → END
                    └──► gen_sql → validate ─► execute_sql ─► chart → explain → END
                                         └──► heal (≤ MAX_HEAL_ATTEMPTS) → validate
```

- `build_graph(llm=..., retriever=...)` — construct without compiling; used in tests to inject mocks.
- `get_compiled_agent()` — production entry point; lazily cached in `api.py`.
- `run_question(question)` — convenience wrapper that builds + invokes in one call.

### Multi-DB layer (`app/db_adapter.py`)

All SQL execution and validation route through this module. It accepts **SQLAlchemy-style URLs**:
- `duckdb:///path/to/file.duckdb` — DuckDB file (default)
- `sqlite:///path/to/file.db` — SQLite
- `postgresql://user:pw@host/db` — PostgreSQL
- `mysql+pymysql://user:pw@host/db` — MySQL

The `validate_sql` function runs `sqlglot` parse + DuckDB `EXPLAIN` and enforces a write-guard (`_DISALLOWED` set). `execute_sql` caps results at 10,000 rows.

### Session management (`app/session.py`)

`session_manager` (module-level singleton) maps `session_id` → `Session` (db URL + per-session vector index + table list). Sessions are **in-memory only** (no persistence across restarts) with a 24-hour TTL. Each session gets its own vector DuckDB built from the connected database's schema. The default "TPC-H Demo" session loads from `data/warehouse.duckdb` + `data/vectors.duckdb`.

### Schema RAG (`app/retriever.py`)

Embeddings are stored in a DuckDB vector table. The retriever returns `Chunk` objects of kind `"table"`, `"column"`, or `"example"`. `build_index` is called once at startup (or via `scripts/build_index.py`). The embedder defaults to `sentence-transformers/all-MiniLM-L6-v2`; falls back to `HashEmbedder` (deterministic, no model download) when `EMBEDDER=hash`.

### API (`app/api.py`)

FastAPI app (`api`) exposes:
- `POST /connect` — connect to any DB via URL string
- `POST /upload` — upload CSV/SQLite/DuckDB/Parquet to create a session
- `GET /sessions` — list active sessions
- `POST /execute` — run a validated read-only SQL string against a session's DB (used by the eval harness)
- `GET /sessions/{session_id}/schema` — schema text for a session (used by `scripts/generate_evals.py`)
- `POST /ask` — run the agent; accepts optional `session_id` and `verify` (bool). When `verify=true`, a second independent LLM call generates naive SQL and its results are compared (`_results_equal`) against the primary result, returning `verified` + `verify_sql`. Every verify attempt logs an outcome line (`log.info("verify ran: ...")` or `"verify requested but skipped: ..."`) so this is checkable server-side, not just via the frontend badge — see `tests/test_api.py`.
- `GET /health`

### Frontend (`frontend/`)

Next.js 14 + Tailwind + Recharts. Single-page app at `frontend/app/page.tsx`. Calls the FastAPI backend via `frontend/lib/api.ts`. The `ConnectModal` handles DB connection/upload on first load; `ResultCard` renders SQL + table + chart + follow-up questions.

**Design system** — all colors are CSS custom properties defined once in `frontend/app/globals.css` (Slate neutrals + a copper/amber `--accent`, plus semantic `--success` / `--warning` / `--danger` tokens for both themes). Never hardcode a color (`rgba(...)`, hex) in a component — reference the existing `var(--...)` token, or add a new token to `globals.css` if none fits. Icons are `lucide-react`, not emoji — the UI was deliberately migrated off emoji glyphs (☀️🌙✓⚠️ etc.) because they read as unpolished; keep new UI additions consistent with that.

## Configuration

All settings live in `.env` (see `.env.example`). Key variables:

| Var | Default | Notes |
|-----|---------|-------|
| `LLM_PROVIDER` | `mock` | `groq` / `anthropic` / `mock` |
| `GROQ_API_KEY` | — | Required for free path |
| `ANTHROPIC_API_KEY` | — | Required for Anthropic path |
| `DB_PATH` | `./data/warehouse.duckdb` | TPC-H data |
| `VECTOR_DB_PATH` | `./data/vectors.duckdb` | Pre-built schema embeddings |
| `EMBEDDER` | `auto` | `auto` / `sentence-transformers` / `hash` |
| `MAX_HEAL_ATTEMPTS` | `3` | Self-heal retry limit |
| `CUBE_URL` | _(unset)_ | Enable Cube semantic layer |
| `LANGFUSE_HOST` | _(unset)_ | Enable Langfuse tracing |

## Testing notes

`conftest.py` forces `EMBEDDER=hash` and `LLM_PROVIDER=mock` via `os.environ.setdefault` — tests run fully offline with no API keys. The session-scoped `db_path` and `vector_db_path` fixtures build a small in-memory TPC-H subset. To test with a real LLM, set `LLM_PROVIDER` in your shell before running pytest (will override the `setdefault`).

`tests/test_api.py` drives the real FastAPI app end-to-end (`TestClient` → `POST /connect` → `POST /ask`) rather than calling `build_graph()` directly. Because `api.py` calls `get_llm()` itself (both directly, for the verify prompt, and indirectly via `get_compiled_agent()` → `build_graph()`), mocking it requires patching the name in *both* modules it was imported into: `monkeypatch.setattr("app.graph.get_llm", ...)` and `monkeypatch.setattr("app.api.get_llm", ...)`. Patching only one leaves the other making a real (failing, since `LLM_PROVIDER=mock` returns an empty-response `MockLLM`) call.

## Optional services

```bash
make services-up   # start Postgres, Cube, Langfuse via docker-compose
make services-down
```

After starting, set `CUBE_URL`, `LANGFUSE_HOST`, and the corresponding keys in `.env`.

## Deployment

`Dockerfile` builds a single API-only image (Python 3.11, `pip install -e ".[anthropic,embed]"`), seeds TPC-H and builds the vector index at build time, and runs `uvicorn app.api:api` on port 8000 — no Streamlit UI in the container. `render.yaml` deploys this image to Render's free tier with `LLM_PROVIDER=anthropic`; the frontend is deployed separately (e.g. Vercel) pointing `NEXT_PUBLIC_API_URL` at the Render service.
