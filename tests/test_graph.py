"""End-to-end agent test using a scripted MockLLM.

These tests exercise the FULL LangGraph state machine including:
  * retrieve → classify → gen_sql → validate → execute → chart
  * validate-failure → heal → validate → execute (the self-heal path)

No external API calls. No real embedder.
"""
from __future__ import annotations

from app.embed import HashEmbedder
from app.graph import build_graph
from app.llm import MockLLM
from app.retriever import Retriever


def _retriever(vector_db_path: str) -> Retriever:
    return Retriever(vector_db_path=vector_db_path, embedder=HashEmbedder())


def test_happy_path(db_path: str, vector_db_path: str):
    """A good SQL on the first try → execute → chart → done."""
    sql = "SELECT COUNT(*) AS n FROM orders"
    llm = MockLLM(responses=[
        (lambda s, u: "single DuckDB SQL" in s, sql),
    ])
    agent = build_graph(
        llm=llm,
        retriever=_retriever(vector_db_path),
        cube_meta="",          # disable metric route
        db_path=db_path,
    ).compile()

    state = agent.invoke({"question": "how many orders?"})
    assert state["sql"].strip().startswith("SELECT COUNT(*)")
    assert state["validation_error"] is None
    assert state["rows"] == [{"n": 4}]
    assert state.get("attempts", 0) == 0


def test_self_healing(db_path: str, vector_db_path: str):
    """First SQL references a missing column; heal fixes it on attempt 1."""
    bad = "SELECT no_such_col FROM orders"
    good = "SELECT COUNT(*) AS n FROM orders"

    llm = MockLLM(responses=[
        # First gen_sql -> bad. The HEAL prompt does NOT contain "single"; gen_sql does.
        (lambda s, u: "single DuckDB SQL" in s, bad),
        # heal -> good. HEAL user message always contains "CORRECTED SQL:".
        (lambda s, u: "CORRECTED SQL:" in u, good),
    ])
    agent = build_graph(
        llm=llm,
        retriever=_retriever(vector_db_path),
        cube_meta="",
        db_path=db_path,
    ).compile()

    state = agent.invoke({"question": "count orders"})
    assert state.get("attempts", 0) == 1
    assert state["sql"].strip() == good
    assert state["rows"] == [{"n": 4}]


def test_heal_gives_up_after_max(db_path: str, vector_db_path: str):
    """After MAX heal attempts, the agent ends gracefully with no rows."""
    llm = MockLLM(responses=[
        # Every call returns broken SQL.
        (lambda s, u: True, "SELECT no_such_col FROM orders"),
    ])
    agent = build_graph(
        llm=llm,
        retriever=_retriever(vector_db_path),
        cube_meta="",
        db_path=db_path,
    ).compile()

    state = agent.invoke({"question": "count orders"})
    # We tried MAX_HEAL_ATTEMPTS times (3 by default) and then ended.
    assert state.get("rows", []) == []
    assert state.get("validation_error") is not None
    assert state.get("attempts", 0) >= 3


def test_chart_suggestion_bar(db_path: str, vector_db_path: str):
    sql = "SELECT o_orderstatus, COUNT(*) AS n FROM orders GROUP BY o_orderstatus"
    llm = MockLLM(responses=[(lambda s, u: "single DuckDB SQL" in s, sql)])
    agent = build_graph(
        llm=llm,
        retriever=_retriever(vector_db_path),
        cube_meta="",
        db_path=db_path,
    ).compile()
    state = agent.invoke({"question": "orders by status"})
    assert state["chart_suggestion"].get("type") == "bar"
    assert state["chart_suggestion"]["x"] == "o_orderstatus"
    assert state["chart_suggestion"]["y"] == "n"


def test_strips_markdown_fences(db_path: str, vector_db_path: str):
    fenced = "```sql\nSELECT COUNT(*) AS n FROM orders\n```"
    llm = MockLLM(responses=[(lambda s, u: True, fenced)])
    agent = build_graph(
        llm=llm,
        retriever=_retriever(vector_db_path),
        cube_meta="",
        db_path=db_path,
    ).compile()
    state = agent.invoke({"question": "count"})
    assert "```" not in state["sql"]
    assert state["rows"] == [{"n": 4}]
