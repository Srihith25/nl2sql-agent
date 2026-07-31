.PHONY: install install-free install-paid seed index ui api test eval clean services-up services-down frontend-install frontend-dev frontend-build dev

PYTHON := .venv/bin/python

install:
	pip install -e ".[dev]"

# Free path also wants the Groq client:
install-free:
	pip install -e ".[dev,groq]"

# Paid path:
install-paid:
	pip install -e ".[dev,groq,anthropic,embed,langfuse]"

seed:
	$(PYTHON) data/seed_tpch.py

index:
	$(PYTHON) scripts/build_index.py

ui:
	$(PYTHON) -m streamlit run app/streamlit_app.py

api:
	$(PYTHON) -m uvicorn app.api:api --reload --port 8000

test:
	$(PYTHON) -m pytest -q

eval:
	$(PYTHON) eval/run_evals.py eval/tpch_25.jsonl

# Generate eval questions from any DB:  make generate-evals DB_URL=postgresql://... OUT=eval/my.jsonl
generate-evals:
	$(PYTHON) scripts/generate_evals.py --db-url "$(DB_URL)" --output "$(OUT)"

clean:
	rm -rf .pytest_cache .cache __pycache__ */__pycache__ */*/__pycache__
	rm -f data/warehouse.duckdb data/vectors.duckdb

services-up:
	docker compose up -d postgres cube langfuse \
	  langfuse-db langfuse-clickhouse langfuse-redis langfuse-minio

services-down:
	docker compose down

frontend-install:
	cd frontend && npm install

frontend-dev:
	cd frontend && npm run dev

frontend-build:
	cd frontend && npm run build

dev:
	$(PYTHON) -m uvicorn app.api:api --reload --port 8000 &
	cd frontend && npm run dev
