"""DuckDB-backed schema + few-shot retriever.

Storage model: a single DuckDB file (`vectors.duckdb` by default) with one table:

    schema_chunks(id BIGINT, kind TEXT, ref TEXT, body TEXT, embedding DOUBLE[])

`kind` is one of: 'table' | 'column' | 'example'.
At query time we load all rows into numpy, dot against the query embedding
(cosine since vectors are normalised) and return the top-k.

This is intentionally simple — a few thousand vectors fit comfortably in RAM
and Python is fast enough for portfolio-scale workloads. Swap in pgvector + HNSW
when you outgrow this; see scripts/build_index.py for the conversion path.
"""
from __future__ import annotations

import json
import logging
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional

import duckdb
import numpy as np

from .config import settings
from .embed import Embedder, get_embedder

log = logging.getLogger(__name__)

EXAMPLE_SEP = "\n===SQL===\n"


@dataclass
class Chunk:
    kind: str
    ref: str
    body: str


# ---------- Schema introspection (build-time) ----------

def describe_table(con: duckdb.DuckDBPyConnection, table: str) -> str:
    rows = con.execute(f"DESCRIBE {table}").fetchall()
    sample_df = con.execute(f"SELECT * FROM {table} LIMIT 3").fetchdf()
    sample = sample_df.to_dict(orient="records")
    lines = [f"TABLE {table}"]
    for r in rows:
        name, dtype = r[0], r[1]
        lines.append(f"  - {name}: {dtype}")
    lines.append(f"  sample_rows={sample}")
    return "\n".join(lines)


def describe_column(con: duckdb.DuckDBPyConnection, table: str, col: str, dtype: str) -> str:
    try:
        samples = con.execute(f'SELECT DISTINCT "{col}" FROM "{table}" LIMIT 5').fetchall()
    except duckdb.Error:
        samples = []
    return f"COLUMN {table}.{col} ({dtype}) sample_values={[s[0] for s in samples]}"


def enumerate_chunks(con: duckdb.DuckDBPyConnection) -> list[Chunk]:
    chunks: list[Chunk] = []
    tables = [r[0] for r in con.execute("SHOW TABLES").fetchall()]
    for t in tables:
        chunks.append(Chunk("table", t, describe_table(con, t)))
        for r in con.execute(f"DESCRIBE {t}").fetchall():
            name, dtype = r[0], r[1]
            chunks.append(Chunk("column", f"{t}.{name}", describe_column(con, t, name, dtype)))
    return chunks


def load_examples(path: str | Path) -> list[Chunk]:
    """Load few-shot examples from a JSONL with {question, sql} lines."""
    p = Path(path)
    if not p.exists():
        return []
    out: list[Chunk] = []
    for i, line in enumerate(p.read_text().splitlines()):
        if not line.strip():
            continue
        rec = json.loads(line)
        body = f"{rec['question']}{EXAMPLE_SEP}{rec['sql']}"
        out.append(Chunk("example", f"q{i}", body))
    return out


# ---------- Index build ----------

def build_index(
    db_path: str | None = None,
    vector_db_path: str | None = None,
    examples_path: str | Path | None = None,
    embedder: Embedder | None = None,
) -> int:
    """Build (or rebuild) the schema-chunks index. Returns the chunk count."""
    db_path = db_path or settings.db_path
    vector_db_path = vector_db_path or settings.vector_db_path
    embedder = embedder or get_embedder()

    if not Path(db_path).exists():
        raise FileNotFoundError(f"Data warehouse not found at {db_path}. Run data/seed_tpch.py first.")

    with closing(duckdb.connect(db_path, read_only=True)) as data_con:
        chunks = enumerate_chunks(data_con)
    if examples_path:
        chunks.extend(load_examples(examples_path))

    bodies = [c.body for c in chunks]
    embeds = embedder.encode(bodies)
    log.info("Embedded %d chunks (dim=%d)", len(bodies), embeds.shape[1])

    Path(vector_db_path).parent.mkdir(parents=True, exist_ok=True)
    with closing(duckdb.connect(vector_db_path)) as vcon:
        vcon.execute("DROP TABLE IF EXISTS schema_chunks")
        vcon.execute(
            """
            CREATE TABLE schema_chunks (
              id BIGINT,
              kind TEXT,
              ref TEXT,
              body TEXT,
              embedding DOUBLE[]
            )
            """
        )
        rows = [
            (i, c.kind, c.ref, c.body, embeds[i].astype(float).tolist())
            for i, c in enumerate(chunks)
        ]
        vcon.executemany(
            "INSERT INTO schema_chunks VALUES (?, ?, ?, ?, ?)",
            rows,
        )

    return len(chunks)


# ---------- Query-time retriever ----------

@dataclass
class RetrievedChunk:
    kind: str
    ref: str
    body: str
    score: float


class Retriever:
    def __init__(
        self,
        vector_db_path: Optional[str] = None,
        embedder: Optional[Embedder] = None,
    ):
        self.vector_db_path = vector_db_path or settings.vector_db_path
        self.embedder = embedder or get_embedder()
        self._kinds: np.ndarray | None = None
        self._refs: np.ndarray | None = None
        self._bodies: np.ndarray | None = None
        self._embeds: np.ndarray | None = None
        self._load()

    def _load(self) -> None:
        if not Path(self.vector_db_path).exists():
            log.warning("Vector DB not found at %s; retriever will return empty results.", self.vector_db_path)
            return
        with closing(duckdb.connect(self.vector_db_path, read_only=True)) as vcon:
            rows = vcon.execute("SELECT kind, ref, body, embedding FROM schema_chunks").fetchall()
        if not rows:
            return
        self._kinds = np.array([r[0] for r in rows])
        self._refs = np.array([r[1] for r in rows])
        self._bodies = np.array([r[2] for r in rows])
        self._embeds = np.array([r[3] for r in rows], dtype=np.float32)
        # Re-normalise (defensive — embedders may not have)
        norms = np.linalg.norm(self._embeds, axis=1, keepdims=True) + 1e-8
        self._embeds = self._embeds / norms

    def _topk(self, qv: np.ndarray, kind_filter: Iterable[str] | None, k: int) -> list[RetrievedChunk]:
        if self._embeds is None or len(self._embeds) == 0:
            return []
        sims = self._embeds @ qv
        mask = (
            np.isin(self._kinds, list(kind_filter))
            if kind_filter is not None
            else np.ones_like(sims, dtype=bool)
        )
        idxs = np.where(mask)[0]
        if len(idxs) == 0:
            return []
        order = idxs[np.argsort(-sims[idxs])][:k]
        return [
            RetrievedChunk(
                kind=str(self._kinds[i]),
                ref=str(self._refs[i]),
                body=str(self._bodies[i]),
                score=float(sims[i]),
            )
            for i in order
        ]

    def retrieve_schema(self, question: str, k_tables: int | None = None, k_cols: int | None = None) -> str:
        qv = self.embedder.encode([question])[0]
        qv = qv / (np.linalg.norm(qv) + 1e-8)
        tables = self._topk(qv, {"table"}, k_tables or settings.top_k_tables)
        cols = self._topk(qv, {"column"}, k_cols or settings.top_k_columns)
        return "\n\n".join(c.body for c in tables + cols)

    def retrieve_examples(self, question: str, k: int | None = None) -> list[tuple[str, str]]:
        qv = self.embedder.encode([question])[0]
        qv = qv / (np.linalg.norm(qv) + 1e-8)
        ex = self._topk(qv, {"example"}, k or settings.top_k_examples)
        out: list[tuple[str, str]] = []
        for c in ex:
            if EXAMPLE_SEP in c.body:
                q, s = c.body.split(EXAMPLE_SEP, 1)
                out.append((q, s))
        return out
