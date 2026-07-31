"""In-memory session store: one session = one database connection + its vector index.

Sessions are keyed by a UUID. They live for the duration of the server process
(no persistence). A future upgrade would store the vector index in S3/R2 and
session metadata in Redis/Postgres for multi-instance deployments.
"""
from __future__ import annotations

import logging
import os
import tempfile
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .config import settings
from .db_adapter import enumerate_chunks_from_url, file_to_duckdb_url, list_tables
from .embed import get_embedder
from .retriever import Retriever, build_index, load_examples

log = logging.getLogger(__name__)

_SESSION_TTL_SECONDS = 24 * 3600  # 24 hours


@dataclass
class Session:
    session_id: str
    db_url: str
    tables: list[str]
    retriever: Retriever
    created_at: float = field(default_factory=time.time)
    label: str = ""  # human-readable name shown in the UI

    def is_expired(self) -> bool:
        return time.time() - self.created_at > _SESSION_TTL_SECONDS


class SessionManager:
    def __init__(self):
        self._sessions: dict[str, Session] = {}
        self._default_session_id: Optional[str] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_from_url(self, db_url: str, label: str = "") -> Session:
        """Build a session from a SQLAlchemy-style connection URL."""
        session_id = str(uuid.uuid4())
        retriever = self._build_retriever(db_url, session_id)
        tables = list_tables(db_url)
        session = Session(
            session_id=session_id,
            db_url=db_url,
            tables=tables,
            retriever=retriever,
            label=label or db_url.split("@")[-1],  # hide credentials
        )
        self._sessions[session_id] = session
        log.info("Created session %s for %s (%d tables)", session_id, session.label, len(tables))
        return session

    def create_from_file(self, file_path: str, original_name: str = "") -> Session:
        """Build a session from an uploaded file (CSV/SQLite/DuckDB/Parquet)."""
        db_url = file_to_duckdb_url(file_path)
        label = original_name or Path(file_path).name
        return self.create_from_url(db_url, label=label)

    def get(self, session_id: str) -> Optional[Session]:
        s = self._sessions.get(session_id)
        if s and s.is_expired():
            del self._sessions[session_id]
            return None
        return s

    def get_default(self) -> Optional[Session]:
        """Return the built-in TPC-H demo session, creating it on first call."""
        if self._default_session_id:
            s = self.get(self._default_session_id)
            if s:
                return s
        # Build the default session from the configured DuckDB warehouse.
        db_path = settings.db_path
        if not Path(db_path).exists():
            return None
        db_url = f"duckdb:///{db_path}"
        session = self._build_default_session(db_url)
        self._default_session_id = session.session_id
        return session

    def list_sessions(self) -> list[dict]:
        self._evict_expired()
        return [
            {
                "session_id": s.session_id,
                "label": s.label,
                "tables": s.tables,
                "created_at": s.created_at,
            }
            for s in self._sessions.values()
        ]

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _build_retriever(self, db_url: str, session_id: str) -> Retriever:
        embedder = get_embedder()
        chunks = enumerate_chunks_from_url(db_url)
        # Also load generic few-shot examples
        examples_path = Path(settings.vector_db_path).parent.parent / "eval" / "examples.jsonl"
        if examples_path.exists():
            chunks.extend(load_examples(str(examples_path)))

        # Use mkdtemp so the .duckdb file doesn't exist yet — DuckDB creates it fresh.
        vector_db_path = os.path.join(tempfile.mkdtemp(), f"vectors_{session_id}.duckdb")
        build_index(
            db_path=None,
            vector_db_path=vector_db_path,
            embedder=embedder,
            _chunks_override=chunks,
        )
        return Retriever(vector_db_path=vector_db_path, embedder=embedder)

    def _build_default_session(self, db_url: str) -> Session:
        """Use existing vectors.duckdb if present, otherwise build fresh."""
        session_id = str(uuid.uuid4())
        vector_path = settings.vector_db_path
        embedder = get_embedder()
        if Path(vector_path).exists():
            retriever = Retriever(vector_db_path=vector_path, embedder=embedder)
        else:
            retriever = self._build_retriever(db_url, session_id)

        tables = list_tables(db_url)
        session = Session(
            session_id=session_id,
            db_url=db_url,
            tables=tables,
            retriever=retriever,
            label="TPC-H Demo",
        )
        self._sessions[session_id] = session
        return session

    def _evict_expired(self) -> None:
        expired = [k for k, v in self._sessions.items() if v.is_expired()]
        for k in expired:
            del self._sessions[k]


# Global singleton
session_manager = SessionManager()
