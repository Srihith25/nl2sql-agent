FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# No [embed] extra: sentence-transformers pulls in torch (+ a full CUDA toolkit
# it never uses here), which OOMs on Render's free 512MB instance the first
# time a session loads an embedder. EMBEDDER=hash (set in render.yaml) never
# touches that code path; get_embedder()'s "auto" mode also falls back to the
# hash embedder if sentence-transformers isn't installed, so this is safe
# even if EMBEDDER is ever unset.
RUN pip install -e ".[anthropic]"

COPY . .

# Seed data and build the vector index at image build time
RUN python data/seed_tpch.py && python scripts/build_index.py

EXPOSE 8000

CMD ["uvicorn", "app.api:api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
