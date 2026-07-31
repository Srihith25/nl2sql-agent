"""LangGraph state machine for the NL→SQL agent.

The graph has eight nodes:

    retrieve  → classify ──┬─► gen_cube   → execute_cube ─► chart → END
                          └─► gen_sql    → validate ─┬─► execute_sql ─► chart → END
                                                     └─► heal (loop ≤ N) → validate
                                                                 │
                                                              (≥ N tries)
                                                                 ▼
                                                                chart → END

`get_compiled_agent()` returns a compiled graph using the configured LLM.
Tests use `build_graph(llm=..., retriever=...)` to inject mocks.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Literal, Optional, TypedDict

from langgraph.graph import END, StateGraph

from .chart import suggest_chart
from .config import settings
from .cube_meta import fetch_cube_meta
from .db_adapter import execute_sql as adapter_execute, validate_sql as adapter_validate
from .executor import run_cube
from .llm import LLM, get_llm
from .prompts import (
    CLASSIFY_SYSTEM,
    CUBE_SYSTEM,
    GROUNDED_SYSTEM,
    HEAL_SYSTEM,
    classify_user,
    cube_user,
    grounded_user,
    heal_user,
)
from .retriever import Retriever

log = logging.getLogger(__name__)


# ---------- State ----------

class AgentState(TypedDict, total=False):
    question: str
    db_url: str                      # set by API layer from the active session
    schema_context: str
    examples: list[tuple[str, str]]
    cube_meta: str
    route: Literal["metric", "raw"]
    cube_query: dict
    sql: str
    validation_error: Optional[str]
    rows: list[dict]
    attempts: int
    chart_suggestion: dict
    error: Optional[str]
    explanation: str
    follow_up_questions: list[str]


# ---------- Helpers ----------

_SQL_FENCE = re.compile(r"^```(?:sql)?\s*|\s*```\s*$", re.MULTILINE)


def clean_sql(s: str) -> str:
    s = _SQL_FENCE.sub("", s or "").strip()
    return s


def _safe_json(s: str) -> dict | None:
    s = s.strip()
    # Strip surrounding ```json fences
    s = re.sub(r"^```(?:json)?\s*|\s*```\s*$", "", s, flags=re.MULTILINE).strip()
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        return None


# ---------- Graph factory ----------

def build_graph(
    llm: Optional[LLM] = None,
    retriever: Optional[Retriever] = None,
    cube_meta: Optional[str] = None,
    db_path: Optional[str] = None,
):
    """Construct (without compiling) the agent graph.

    Pass `llm` and `retriever` to inject mocks for tests.
    """
    llm = llm or get_llm()
    retriever = retriever or Retriever()
    # Resolve cube meta once. Tests can pass an explicit empty string.
    if cube_meta is None:
        cube_meta = fetch_cube_meta()
    db = db_path or settings.db_path

    def n_retrieve(state: AgentState) -> AgentState:
        q = state["question"]
        return {
            "schema_context": retriever.retrieve_schema(q),
            "examples": retriever.retrieve_examples(q),
            "cube_meta": cube_meta,
            "attempts": 0,
        }

    def n_classify(state: AgentState) -> AgentState:
        if not cube_meta:
            return {"route": "raw"}
        label = llm.complete(CLASSIFY_SYSTEM, classify_user(state["question"], cube_meta))
        return {"route": "metric" if label.strip().lower().startswith("y") else "raw"}

    def n_gen_cube(state: AgentState) -> AgentState:
        raw = llm.complete(CUBE_SYSTEM, cube_user(state["question"], cube_meta))
        parsed = _safe_json(raw) or {}
        return {"cube_query": parsed}

    def n_gen_sql(state: AgentState) -> AgentState:
        out = llm.complete(
            GROUNDED_SYSTEM,
            grounded_user(state["question"], state.get("schema_context", ""), state.get("examples", [])),
        )
        return {"sql": clean_sql(out)}

    def _effective_url(state: AgentState) -> str:
        # state["db_url"] is already a full URL (duckdb:/// or postgres:// etc.)
        # db is a plain file path — wrap it so adapter functions can parse it uniformly.
        return state.get("db_url") or f"duckdb:///{db}"

    def n_validate(state: AgentState) -> AgentState:
        err = adapter_validate(state.get("sql", ""), _effective_url(state))
        return {"validation_error": err}

    def n_execute_sql(state: AgentState) -> AgentState:
        try:
            rows = adapter_execute(state["sql"], _effective_url(state))
            return {"rows": rows, "error": None}
        except Exception as e:  # noqa: BLE001
            log.exception("execute_sql failed")
            return {"rows": [], "error": f"execute failed: {e}"}

    def n_execute_cube(state: AgentState) -> AgentState:
        try:
            rows = run_cube(state.get("cube_query", {}))
            return {"rows": rows, "error": None}
        except Exception as e:  # noqa: BLE001
            log.exception("execute_cube failed")
            return {"rows": [], "error": f"cube failed: {e}"}

    def n_heal(state: AgentState) -> AgentState:
        new_sql = llm.complete(
            HEAL_SYSTEM,
            heal_user(
                state["question"],
                state.get("sql", ""),
                state.get("validation_error") or "",
                state.get("schema_context", ""),
            ),
        )
        return {
            "sql": clean_sql(new_sql),
            "attempts": int(state.get("attempts", 0)) + 1,
        }

    def n_chart(state: AgentState) -> AgentState:
        return {"chart_suggestion": suggest_chart(state.get("rows", []))}

    _EXPLAIN_SYSTEM = (
        "You are a concise data analyst. Given a question and its SQL result, respond with "
        "valid JSON only — no prose, no markdown fences — in this exact shape:\n"
        '{"explanation": "<1-2 sentence plain-English insight>", '
        '"follow_up_questions": ["<q1>", "<q2>", "<q3>"]}\n'
        "The follow-up questions must be natural continuations a non-technical user would actually ask next."
    )

    def n_explain(state: AgentState) -> AgentState:
        rows = state.get("rows", [])
        if not rows or state.get("error"):
            return {"explanation": "", "follow_up_questions": []}
        sample = rows[:6]
        user_msg = (
            f'Question: "{state.get("question", "")}"\n'
            f"SQL: {state.get('sql', '')}\n"
            f"Returned {len(rows)} row(s). Sample data: {json.dumps(sample, default=str)}"
        )
        try:
            raw = llm.complete(_EXPLAIN_SYSTEM, user_msg)
            parsed = _safe_json(raw) or {}
            return {
                "explanation": parsed.get("explanation", ""),
                "follow_up_questions": parsed.get("follow_up_questions", [])[:4],
            }
        except Exception:  # noqa: BLE001
            log.warning("n_explain failed — skipping", exc_info=True)
            return {"explanation": "", "follow_up_questions": []}

    g = StateGraph(AgentState)
    for name, fn in [
        ("retrieve", n_retrieve),
        ("classify", n_classify),
        ("gen_cube", n_gen_cube),
        ("gen_sql", n_gen_sql),
        ("validate", n_validate),
        ("execute_sql", n_execute_sql),
        ("execute_cube", n_execute_cube),
        ("heal", n_heal),
        ("chart", n_chart),
        ("explain", n_explain),
    ]:
        g.add_node(name, fn)

    g.set_entry_point("retrieve")
    g.add_edge("retrieve", "classify")
    g.add_conditional_edges(
        "classify",
        lambda s: s.get("route", "raw"),
        {"metric": "gen_cube", "raw": "gen_sql"},
    )
    g.add_edge("gen_cube", "execute_cube")
    g.add_edge("gen_sql", "validate")
    g.add_conditional_edges(
        "validate",
        lambda s: (
            "execute_sql"
            if not s.get("validation_error")
            else ("heal" if int(s.get("attempts", 0)) < settings.max_heal_attempts else "chart")
        ),
        {"execute_sql": "execute_sql", "heal": "heal", "chart": "chart"},
    )
    g.add_edge("heal", "validate")
    g.add_edge("execute_sql", "chart")
    g.add_edge("execute_cube", "chart")
    g.add_edge("chart", "explain")
    g.add_edge("explain", END)
    return g


def get_compiled_agent(
    llm: Optional[LLM] = None,
    retriever: Optional[Retriever] = None,
    cube_meta: Optional[str] = None,
    db_path: Optional[str] = None,
):
    return build_graph(llm=llm, retriever=retriever, cube_meta=cube_meta, db_path=db_path).compile()


def run_question(question: str, **kwargs: Any) -> AgentState:
    agent = get_compiled_agent(**kwargs)
    return agent.invoke({"question": question})
