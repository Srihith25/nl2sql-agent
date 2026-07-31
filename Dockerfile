FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

RUN apt-get update \
 && apt-get install -y --no-install-recommends build-essential libpq-dev curl ca-certificates \
 && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
RUN pip install -e ".[groq,embed]"

COPY . .

EXPOSE 8000 8501

# Default command: API + UI in the same container.
CMD ["bash", "-lc", \
     "uvicorn app.api:api --host 0.0.0.0 --port 8000 & \
      streamlit run app/streamlit_app.py --server.port 8501 --server.address 0.0.0.0"]
