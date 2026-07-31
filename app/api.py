"""FastAPI endpoint exposing the agent at POST /ask."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .graph import get_compiled_agent

log = logging.getLogger(__name__)
api = FastAPI(title="nl2sql-agent", version="0.1.0")
api.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Compile the agent once at startup.
_agent = None


def _get_agent():
    global _agent
    if _agent is None:
        _agent = get_compiled_agent()
    return _agent


class AskReq(BaseModel):
    question: str


class AskResp(BaseModel):
    sql: Optional[str] = None
    cube_query: Optional[dict] = None
    rows: list = []
    chart_suggestion: dict = {}
    validation_error: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None


@api.get("/health")
def health() -> dict:
    return {"ok": True}


@api.post("/ask", response_model=AskResp)
def ask(req: AskReq) -> AskResp:
    if not req.question.strip():
        raise HTTPException(status_code=400, detail="empty question")
    try:
        state = _get_agent().invoke({"question": req.question})
    except Exception as e:  # noqa: BLE001
        log.exception("agent error")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return AskResp(
        sql=state.get("sql"),
        cube_query=state.get("cube_query"),
        rows=state.get("rows", []),
        chart_suggestion=state.get("chart_suggestion", {}),
        validation_error=state.get("validation_error"),
        attempts=int(state.get("attempts", 0)),
        error=state.get("error"),
    )
