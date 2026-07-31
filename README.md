# nl2sql-agent

A self-healing Natural-Language to SQL agent with schema-aware RAG, query validation, dual-SQL answer verification, and a production-style Next.js frontend. Built around DuckDB + LangGraph.

> Walks an English question through schema retrieval → SQL generation → parse + `EXPLAIN` validation → execute → chart suggestion → plain-English explanation, with up to three self-healing retries when the SQL fails, and an optional second independent LLM call to cross-check the answer.

## What you get

- **Connect any database** — Postgres, MySQL, SQLite, DuckDB via connection string, or upload a CSV / Parquet / SQLite / DuckDB file directly. Each connection becomes an isolated session with its own schema-aware vector index.
- **Schema-aware RAG**: tables, columns, sample values, and few-shot examples embedded into a DuckDB vector index per session.
- **LangGraph** state machine with a self-heal retry loop (bad SQL → error → rewrite → revalidate).
- **Validator** using `sqlglot` + DuckDB `EXPLAIN` with a SQL write-guardrail (no `INSERT`/`UPDATE`/`DELETE`/`DROP`/etc).
- **Dual-SQL verification ("Verify" mode)** — optionally runs a second, independently-prompted LLM to write its own SQL and compares results, flagging `Verified` / `Unverified` per answer.
- **Auto chart suggestion + natural-language explanation** with follow-up question chips.
- **Next.js frontend** (`frontend/`) — connect/upload modal, light & dark themes, SQL viewer with copy button, result table, chart, and session sidebar.
- **FastAPI backend** (`app/api.py`) — `/connect`, `/upload`, `/ask`, `/execute`, `/sessions`, `/health`.
- **Eval runner** with a 25-question TPC-H gold set + an execution-accuracy report, plus a script to auto-generate an eval set from any database.
- **Ships with a TPC-H demo** (8-table supply-chain schema) running in DuckDB — no external DB required to try it.
- **Optional**: Cube semantic layer, Postgres + pgvector, Langfuse observability (all wired but off-by-default).

## Quickstart

### 1. Backend

```bash
git clone https://github.com/Srihith25/nl2sql-agent.git
cd nl2sql-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate

make install-free          # pip install -e ".[dev,groq]"       (free path, Groq)
# or: make install-paid    # pip install -e ".[dev,groq,anthropic,embed,langfuse]"

cp .env.example .env
# put an API key in .env, e.g. GROQ_API_KEY=gsk_... (free, https://console.groq.com)
# or ANTHROPIC_API_KEY=sk-ant-... and LLM_PROVIDER=anthropic

make seed     # python data/seed_tpch.py      -> data/warehouse.duckdb
make index    # python scripts/build_index.py -> data/vectors.duckdb

make api      # uvicorn app.api:api --reload --port 8000
```

No API key? The test suite runs fully offline against a bundled `MockLLM`:

```bash
make test     # pytest -q — no API keys needed
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev     # http://localhost:3000 (expects the API on :8000)
```

Or start both together from the repo root:

```bash
make dev        # API on :8000 + Next.js on :3000
```

Open `http://localhost:3000`, click **"Use TPC-H demo"** in the connect modal (or paste a connection string / upload a file), and ask a question — try *"Who are the top 5 customers by revenue?"*.

There's also a lightweight Streamlit UI if you'd rather not run the Next.js frontend:

```bash
make ui         # streamlit run app/streamlit_app.py -> http://localhost:8501
```

## Connecting your own database

From the connect modal (or `POST /connect`), any SQLAlchemy-style URL works:

| Database   | Connection string example                                  |
|------------|--------------------------------------------------------------|
| PostgreSQL | `postgresql://user:password@host:5432/dbname`               |
| MySQL      | `mysql+pymysql://user:password@host:3306/dbname`             |
| SQLite     | `sqlite:///path/to/file.db`                                  |
| DuckDB     | `duckdb:///path/to/file.duckdb`                               |

Or upload a `.csv`, `.parquet`, `.sqlite`, or `.duckdb` file directly (`POST /upload`) — it's loaded into a fresh in-memory DuckDB session. Sessions are in-memory only, live for 24 hours, and are not shared across server restarts.

## Architecture

```
question ─▶ retrieve(schema, examples) ─▶ classify(metric vs raw) ─┐
                                                                   │
                              ┌────────────────────────────────────┘
                              ▼
              ┌──────────────────────┐        ┌─────────────────────┐
              │ gen_cube (semantic)  │   OR   │ gen_sql (schema RAG)│
              └──────────┬───────────┘        └─────────┬───────────┘
                         │                              ▼
                         │                      ┌──────────────┐  fail
                         │                      │   validate   │──────┐
                         │                      │ parse+EXPLAIN│      │
                         │                      └──────┬───────┘      │
                         │                             │ ok           │
                         ▼                             ▼              ▼
                  execute(cube)               execute(sql)      heal (attempts<3)
                         │                             │              │
                         └────────────┬────────────────┘              │
                                      ▼                               │
                              chart ─▶ explain, end ◀──────────────────┘
```

All SQL execution/validation routes through `app/db_adapter.py`, which is what makes the graph database-agnostic (DuckDB, SQLite, Postgres, MySQL). When `verify=true` is passed to `/ask`, a second independent LLM call runs *outside* this graph, on a naive (non-schema-tuned) prompt, and its result set is compared against the primary answer's.

## Running the eval

```bash
make eval    # python eval/run_evals.py eval/tpch_25.jsonl
```

You'll see a per-question table and a final execution-accuracy number. With the free path (Groq Llama 3.1 8B, schema RAG, 3-shot, self-heal), expect 65–75% on this set; with Claude Haiku 4.5, 80–90%.

To generate a fresh eval set against any database you've connected:

```bash
make generate-evals DB_URL=postgresql://user:pw@host/db OUT=eval/my_questions.jsonl
```

## Testing

```bash
make test                       # full suite, pytest -q, no API keys needed
pytest tests/test_graph.py -q   # LangGraph state machine + self-heal loop
pytest tests/test_api.py -q     # HTTP-level /connect + /ask, including dual-SQL verify
pytest tests/test_db_adapter.py -q  # the live validate_sql/execute_sql path
pytest -k parse_error -q        # by name pattern (matches across files)
```

`tests/test_api.py` proves the "Verify" feature actually executes an independent second LLM call server-side (not just a frontend badge) — see [`CLAUDE.md`](./CLAUDE.md) for how to check this against a live server too.

Note there are two SQL validators in this codebase: `app/db_adapter.py` (used by the live graph, covered by `tests/test_db_adapter.py`) and a separate, unused-in-production `app/validator.py` (covered by `tests/test_validator.py`). A real bug shipped once because a fix landed in the wrong one — if you're touching SQL validation/error-handling, check both.

## Configuration

Everything is driven by `.env` (see `.env.example`). The important ones:

| Var                  | Default                           | What it does                                  |
|-----------------------|-----------------------------------|-----------------------------------------------|
| `LLM_PROVIDER`        | `mock`                            | `groq`, `anthropic`, or `mock`                |
| `GROQ_API_KEY`        | _(required for free path)_        | https://console.groq.com                      |
| `GROQ_MODEL`          | `llama-3.1-8b-instant`            |                                                |
| `ANTHROPIC_API_KEY`   | _(required for Anthropic path)_   |                                                |
| `ANTHROPIC_MODEL`     | `claude-haiku-4-5-20251001`       |                                                |
| `DB_PATH`             | `./data/warehouse.duckdb`         | Default (TPC-H demo) database                 |
| `VECTOR_DB_PATH`      | `./data/vectors.duckdb`           | Pre-built schema embeddings for the demo DB   |
| `EMBEDDER`            | `auto`                            | `auto` / `sentence-transformers` / `hash`     |
| `MAX_HEAL_ATTEMPTS`   | `3`                                | Self-heal retry limit                         |
| `CUBE_URL`            | _(unset = disabled)_              | e.g. `http://localhost:4000`                  |
| `LANGFUSE_HOST`       | _(unset = disabled)_              | e.g. `http://localhost:3000`                  |

For the frontend, set `NEXT_PUBLIC_API_URL` (defaults to `http://localhost:8000`) — either in `frontend/.env.local` for local dev or as an env var on your hosting provider.

## Optional: turn on Cube + Langfuse

```bash
make services-up   # start Postgres, Cube, Langfuse via docker-compose
# then in .env:
# CUBE_URL=http://localhost:4000
# LANGFUSE_HOST=http://localhost:3000
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
make services-down
```

## Deploying to production

The backend ships as a single Docker image (`Dockerfile`) that seeds the TPC-H demo data and builds the vector index at build time, then runs `uvicorn app.api:api`. `render.yaml` deploys it to [Render](https://render.com)'s free tier as a Blueprint.

**Backend (Render):**
1. Push this repo to GitHub.
2. In the Render dashboard: **New → Blueprint**, point it at your repo — it reads `render.yaml` automatically.
3. Set the `ANTHROPIC_API_KEY` secret when prompted (the blueprint already sets `LLM_PROVIDER=anthropic` and `EMBEDDER=hash`).
4. Deploy. Note the resulting service URL (e.g. `https://nl2sql-api.onrender.com`).
5. Sanity check: `curl https://<your-service>.onrender.com/health` → `{"ok":true}`.

> **Why `EMBEDDER=hash` in production:** `sentence-transformers` pulls in `torch` (and a full unused CUDA toolkit), which OOM-crashes Render's free 512MB instance the first time a session loads an embedder. The hash embedder is deterministic but not semantic, so schema retrieval quality is lower than local dev. If retrieval quality matters more than staying on the free tier, install the `[embed]` extra and move to a plan with more RAM.
>
> **Free tier also means cold starts.** The instance spins down after ~15 minutes idle; the next request can take 30–60s to wake it, and may need a retry. This is expected, not a bug.

**Frontend (Vercel):**
1. **Add New → Project**, import the same repo. Expand the project config **before** deploying and set **Root Directory** to `frontend`. Setting this after the first deploy sometimes doesn't fully override framework detection — if you hit a `No FastAPI entrypoint found` error, delete the project and re-import with Root Directory set up front, and double-check **Settings → General → Framework Preset** reads "Next.js".
2. Add an environment variable `NEXT_PUBLIC_API_URL` = your Render backend URL from above. This is inlined at **build time** (it's a `NEXT_PUBLIC_*` var) — if you add or change it after the first build, you must redeploy for it to take effect.
3. Deploy.

The backend's CORS is currently open (`allow_origins=["*"]`) so it will accept requests from any frontend origin without extra config. See [`CLAUDE.md`](./CLAUDE.md#deployment) for more detail.

## File map

| Path                       | Purpose                                                        |
|-----------------------------|-----------------------------------------------------------------|
| `app/config.py`             | Pydantic settings loaded from `.env`                            |
| `app/llm.py`                | LLM providers: Groq, Anthropic, Mock (for tests)                |
| `app/embed.py`               | Embedder: sentence-transformers or hash fallback                |
| `app/retriever.py`          | DuckDB-backed schema/example RAG                                |
| `app/db_adapter.py`         | Multi-DB introspection, execution, validation (DuckDB/SQLite/Postgres/MySQL) |
| `app/session.py`            | In-memory session store (one session = one DB connection + vector index) |
| `app/validator.py`          | Standalone `sqlglot` + DuckDB `EXPLAIN` validator (its own test coverage; the live graph validates via `db_adapter.validate_sql`, which supports every DB backend) |
| `app/executor.py`           | Cube REST call (SQL execution goes through `db_adapter`)         |
| `app/prompts.py`            | All prompt templates                                             |
| `app/chart.py`               | Heuristic chart-type suggester                                  |
| `app/cube_meta.py`          | Optional Cube metadata loader                                    |
| `app/graph.py`               | LangGraph state machine                                          |
| `app/api.py`                 | FastAPI app: `/connect`, `/upload`, `/ask`, `/execute`, `/sessions`, `/health` |
| `app/streamlit_app.py`      | Lightweight alternative UI                                       |
| `frontend/`                  | Next.js 14 + Tailwind + Recharts frontend                        |
| `data/seed_tpch.py`         | Generates the TPC-H demo DuckDB                                  |
| `scripts/build_index.py`    | Builds the demo schema vector index                               |
| `scripts/generate_evals.py` | Auto-generates an eval set from any connected database            |
| `eval/run_evals.py`         | Execution-accuracy harness                                        |
| `eval/tpch_25.jsonl`        | 25-question TPC-H gold set                                       |
| `eval/examples.jsonl`       | Few-shot examples (question → SQL)                                |
| `cube/model/tpch.yml`       | Optional Cube semantic layer                                      |
| `docker-compose.yml`        | Optional services (Postgres + Cube + Langfuse)                    |
| `Dockerfile`                 | Production backend image (used by Render)                        |
| `render.yaml`                 | Render Blueprint for backend deployment                          |
| `tests/`                     | Pytest suite (runs without API keys)                              |

## License

MIT. See `LICENSE`.
