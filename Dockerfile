FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install -e ".[anthropic,embed]"

COPY . .

# Seed data and build the vector index at image build time
RUN python data/seed_tpch.py && python scripts/build_index.py

EXPOSE 8000

CMD ["uvicorn", "app.api:api", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
