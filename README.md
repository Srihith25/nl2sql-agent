# nl2sql-agent

A self-healing Natural-Language to SQL agent with optional semantic-layer governance, schema-aware RAG, query validation, and observability. Built around DuckDB + LangGraph + Cube + Langfuse.

> Walks an English question through schema retrieval → SQL generation → parse + EXPLAIN validation → execute → chart suggestion, with up to three self-healing retries when the SQL fails.

## What you get

- A working agent over **TPC-H** (8-table supply-chain schema) running in DuckDB — no Postgres or Docker required for the first run.
- **Schema-aware RAG**: tables, columns, and few-shot examples embedded into a DuckDB vector index.
- **LangGraph** state machine with retry/heal loop.
- **Validator** using `sqlglot` + DuckDB `EXPLAIN` with a SQL-write guardrail.
- **Streamlit UI** with SQL display, result table, and auto-suggested chart.
- **FastAPI** `/ask` endpoint for programmatic access.
- **Eval runner** with a 25-question TPC-H gold set + an execution-accuracy report.
- **Optional**: Cube semantic layer, Postgres + pgvector, Langfuse observability (all wired but off-by-default).

## Quickstart (5 minutes, free path)

```bash
git clone https://github.com/<you>/nl2sql-agent.git
cd nl2sql-agent
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e .

cp .env.example .env
# put your free Groq key into .env  -> GROQ_API_KEY=gsk_...
# (sign up at https://console.groq.com -- the free tier is generous)

python data/seed_tpch.py            # generates a ~10 MB TPC-H DuckDB
python scripts/build_index.py       # embeds the schema into the DuckDB vector store

streamlit run app/streamlit_app.py  # open http://localhost:8501
```

No API key? You can still run the test suite end-to-end with the bundled `MockLLM`:

```bash
pytest -q
```

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
                              suggest_chart, end ◀────────────────────┘
```

Every node is checkpointed by LangGraph and (optionally) traced into Langfuse.

## File map

| Path                       | Purpose                                                   |
|----------------------------|-----------------------------------------------------------|
| `app/config.py`            | Pydantic settings loaded from `.env`                      |
| `app/llm.py`               | LLM providers: Groq, Anthropic, Mock (for tests)          |
| `app/embed.py`             | Embedder: sentence-transformers or hash fallback          |
| `app/retriever.py`         | DuckDB-backed schema/example RAG                          |
| `app/validator.py`         | `sqlglot` parse + DuckDB `EXPLAIN` + write guardrail      |
| `app/executor.py`          | Safe SQL run + optional Cube REST call                    |
| `app/prompts.py`           | All prompt templates                                      |
| `app/chart.py`             | Heuristic chart-type suggester                            |
| `app/cube_meta.py`         | Optional Cube metadata loader                             |
| `app/graph.py`             | LangGraph state machine                                   |
| `app/api.py`               | FastAPI `/ask` endpoint                                   |
| `app/streamlit_app.py`     | The UI                                                    |
| `data/seed_tpch.py`        | Generates the TPC-H DuckDB                                |
| `scripts/build_index.py`   | Builds the schema-chunks vector index                     |
| `scripts/phase1_demo.py`   | Minimal naive-prompt baseline (for the eval comparison)   |
| `eval/run_evals.py`        | Execution-accuracy harness                                |
| `eval/tpch_25.jsonl`       | 25-question TPC-H gold set                                |
| `eval/examples.jsonl`      | Few-shot examples (question → SQL)                        |
| `cube/model/tpch.yml`      | Optional Cube semantic layer                              |
| `docker-compose.yml`       | Optional services (Postgres + Cube + Langfuse)            |
| `Dockerfile`               | App image                                                 |
| `tests/`                   | Pytest suite (runs without API keys)                      |

## Configuration

Everything is driven by `.env`. See `.env.example` for the full list. The important ones:

| Var                  | Default                           | What it does                                  |
|----------------------|-----------------------------------|-----------------------------------------------|
| `LLM_PROVIDER`       | `groq`                            | `groq`, `anthropic`, or `mock`                |
| `GROQ_API_KEY`       | _(required for free path)_        | https://console.groq.com                      |
| `ANTHROPIC_API_KEY`  | _(optional)_                      | For Claude Haiku 4.5                          |
| `DB_PATH`            | `./data/warehouse.duckdb`         | Where the TPC-H data lives                    |
| `VECTOR_DB_PATH`     | `./data/vectors.duckdb`           | Where embeddings live (DuckDB by default)     |
| `EMBEDDER`           | `auto`                            | `auto` / `sentence-transformers` / `hash`     |
| `CUBE_URL`           | _(unset = disabled)_              | e.g. `http://localhost:4000`                  |
| `LANGFUSE_HOST`      | _(unset = disabled)_              | e.g. `http://localhost:3000`                  |
| `MAX_HEAL_ATTEMPTS`  | `3`                               | How many self-heal retries before giving up   |

## Running the eval

```bash
python eval/run_evals.py eval/tpch_25.jsonl
```

You will see a per-question table and a final execution-accuracy number. With the free path (Groq Llama 3.1 8B, schema RAG, 3-shot, self-heal), expect 65–75% on this set; with Claude Haiku 4.5, 80–90%.

## Optional: turn on Cube + Langfuse

```bash
docker compose up -d postgres cube langfuse \
  langfuse-db langfuse-clickhouse langfuse-redis langfuse-minio
# then in .env:
# CUBE_URL=http://localhost:4000
# LANGFUSE_HOST=http://localhost:3000
# LANGFUSE_PUBLIC_KEY=pk-lf-...
# LANGFUSE_SECRET_KEY=sk-lf-...
```

## License

MIT. See `LICENSE`.
