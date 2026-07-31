"""FastAPI endpoint exposing the agent at POST /ask."""
from __future__ import annotations

import logging
import tempfile
from typing import Optional

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .db_adapter import execute_sql as _execute_sql
from .graph import clean_sql, get_compiled_agent
from .llm import get_llm
from .prompts import NAIVE_SYSTEM, naive_user
from .session import session_manager

log = logging.getLogger(__name__)
api = FastAPI(title="nl2sql-agent", version="0.2.0")


def _results_equal(a: list[dict], b: list[dict]) -> bool:
    """Order-independent result set comparison (same logic as the eval harness)."""
    def norm(r: dict) -> tuple:
        return tuple(sorted(
            (str(k).lower(), round(v, 4) if isinstance(v, float) else v)
            for k, v in r.items()
        ))
    def vals(r: dict) -> tuple:
        return tuple(round(v, 4) if isinstance(v, float) else v for v in r.values())

    if len(a) != len(b):
        return False
    if {norm(r) for r in a} == {norm(r) for r in b}:
        return True
    if {vals(r) for r in a} == {vals(r) for r in b}:
        return True
    # Column-subset: if a's columns are a subset of b's by name with matching values
    if a and b:
        a_keys = {k.lower() for k in next(iter(a)).keys()}
        b_keys = {k.lower() for k in next(iter(b)).keys()}
        if a_keys and a_keys.issubset(b_keys):
            def project(row: dict) -> tuple:
                return tuple(sorted(
                    (k.lower(), round(v, 4) if isinstance(v, float) else v)
                    for k, v in row.items() if k.lower() in a_keys
                ))
            if {project(r) for r in a} == {project(r) for r in b}:
                return True
    return False


api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = get_compiled_agent()
    return _agent


# ---------- Schemas ----------

class ConnectReq(BaseModel):
    db_url: str
    label: str = ""


class ConnectResp(BaseModel):
    session_id: str
    label: str
    tables: list


class AskReq(BaseModel):
    question: str
    session_id: Optional[str] = None
    verify: bool = False


class AskResp(BaseModel):
    sql: Optional[str] = None
    cube_query: Optional[dict] = None
    rows: list = []
    chart_suggestion: dict = {}
    validation_error: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None
    session_id: Optional[str] = None
    explanation: Optional[str] = None
    follow_up_questions: list = []
    verified: Optional[bool] = None
    verify_sql: Optional[str] = None


class ExecuteReq(BaseModel):
    sql: str
    session_id: Optional[str] = None


# ---------- Endpoints ----------

@api.get("/health")
def health() -> dict:
    return {"ok": True}


@api.post("/connect", response_model=ConnectResp)
def connect(req: ConnectReq) -> ConnectResp:
    """Connect to any database via a connection string."""
    try:
        session = session_manager.create_from_url(req.db_url, label=req.label)
    except Exception as e:
        log.exception("connect failed")
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ConnectResp(
        session_id=session.session_id,
        label=session.label,
        tables=session.tables,
    )


@api.post("/upload", response_model=ConnectResp)
async def upload(file: UploadFile = File(...)) -> ConnectResp:
    """Upload a file (CSV, SQLite .db, DuckDB .duckdb, Parquet) to create a session."""
    suffix = "." + (file.filename or "upload").rsplit(".", 1)[-1].lower()
    allowed = {".csv", ".db", ".sqlite", ".duckdb", ".parquet"}
    if suffix not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported file type {suffix}. Allowed: {allowed}")
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
        content = await file.read()
        tmp.write(content)
        tmp.close()
        session = session_manager.create_from_file(tmp.name, original_name=file.filename or "")
    except Exception as e:
        log.exception("upload failed")
        raise HTTPException(status_code=400, detail=str(e)) from e
    return ConnectResp(
        session_id=session.session_id,
        label=session.label,
        tables=session.tables,
    )


@api.get("/sessions")
def list_sessions() -> list:
    return session_manager.list_sessions()


@api.post("/execute")
def execute_raw(req: ExecuteReq) -> list:
    """Execute a read-only SELECT against a session's database.

    Used by the eval harness so it can run gold SQL against the same database
    the agent is connected to, without needing the raw db_url.
    """
    from .db_adapter import execute_sql as _exec, validate_sql

    if req.session_id:
        session = session_manager.get(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found or expired")
    else:
        session = session_manager.get_default()
        if session is None:
            raise HTTPException(status_code=404, detail="no default session")

    err = validate_sql(req.sql, session.db_url)
    if err:
        raise HTTPException(status_code=400, detail=f"SQL rejected: {err}")
    try:
        return _exec(req.sql, session.db_url)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) from e


@api.get("/sessions/{session_id}/schema")
def get_session_schema(session_id: str) -> dict:
    """Return schema text for a session, used by the eval-generation script."""
    session = session_manager.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="session not found or expired")
    from .db_adapter import enumerate_chunks_from_url
    chunks = enumerate_chunks_from_url(session.db_url)
    schema_text = "\n\n".join(c.body for c in chunks if c.kind == "table")
    return {"session_id": session_id, "schema": schema_text, "tables": session.tables}


@api.post("/ask", response_model=AskResp)
def ask(req: AskReq) -> AskResp:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="empty question")

    # Resolve session
    if req.session_id:
        session = session_manager.get(req.session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="session not found or expired")
    else:
        session = session_manager.get_default()

    agent = get_compiled_agent(
        retriever=session.retriever if session else None,
    )

    initial_state: dict = {"question": req.question}
    if session:
        initial_state["db_url"] = session.db_url

    try:
        state = agent.invoke(initial_state)
    except Exception as e:
        log.exception("agent error")
        raise HTTPException(status_code=500, detail=str(e)) from e

    # Optional dual-SQL verification: run a second independent LLM call and compare results
    verified: bool | None = None
    verify_sql_out: str | None = None
    if req.verify:
        if session and state.get("sql") and not state.get("error"):
            try:
                schema_ctx = session.retriever.retrieve_schema(req.question)
                verify_raw = get_llm().complete(NAIVE_SYSTEM, naive_user(req.question, schema_ctx))
                verify_sql_out = clean_sql(verify_raw)
                verify_rows = _execute_sql(verify_sql_out, session.db_url)
                verified = _results_equal(state.get("rows", []), verify_rows)
                log.info(
                    "verify ran: session=%s verified=%s primary_rows=%d verify_rows=%d verify_sql=%r",
                    session.session_id, verified, len(state.get("rows", [])), len(verify_rows), verify_sql_out,
                )
            except Exception:
                log.warning("verify requested but the second-opinion check raised", exc_info=True)
                verified = None
        else:
            log.info(
                "verify requested but skipped: session=%s has_sql=%s has_error=%s",
                bool(session), bool(state.get("sql")), bool(state.get("error")),
            )

    return AskResp(
        sql=state.get("sql"),
        cube_query=state.get("cube_query"),
        rows=state.get("rows", []),
        chart_suggestion=state.get("chart_suggestion", {}),
        validation_error=state.get("validation_error"),
        attempts=int(state.get("attempts", 0)),
        error=state.get("error"),
        session_id=session.session_id if session else None,
        explanation=state.get("explanation") or None,
        follow_up_questions=state.get("follow_up_questions") or [],
        verified=verified,
        verify_sql=verify_sql_out,
    )
