"""Run SELECT against DuckDB, or load a Cube query via REST."""
from __future__ import annotations

import logging
from contextlib import closing
from typing import Any

import duckdb
import httpx

from .config import settings

log = logging.getLogger(__name__)

# DuckDB ergonomic limits — guardrails against accidental scans.
_DEFAULT_ROW_LIMIT = 10_000


def run_sql(sql: str, db_path: str | None = None, row_limit: int = _DEFAULT_ROW_LIMIT) -> list[dict[str, Any]]:
    """Execute SELECT and return rows as a list of dicts. Caps result size."""
    path = db_path or settings.db_path
    with closing(duckdb.connect(path, read_only=True)) as con:
        df = con.execute(sql).fetchdf()
    if len(df) > row_limit:
        log.warning("Result truncated from %d to %d rows", len(df), row_limit)
        df = df.head(row_limit)
    return df.to_dict(orient="records")


def run_cube(cube_query: dict[str, Any]) -> list[dict[str, Any]]:
    """POST a Cube query and return its data rows. Requires CUBE_URL."""
    if not settings.cube_url:
        raise RuntimeError("CUBE_URL is not configured; cannot run Cube queries.")
    headers = {}
    if settings.cube_api_secret:
        headers["Authorization"] = settings.cube_api_secret
    resp = httpx.post(
        f"{settings.cube_url}/cubejs-api/v1/load",
        json={"query": cube_query},
        headers=headers,
        timeout=60.0,
    )
    resp.raise_for_status()
    return resp.json().get("data", [])
