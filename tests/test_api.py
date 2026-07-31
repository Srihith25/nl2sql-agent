"""HTTP-level tests for POST /ask, focused on the dual-SQL verify path.

These go through the real FastAPI app (/connect then /ask) exactly as a
client would, so a broken verify wiring fails a repeatable backend test
instead of only being visible through the frontend's "Verified" badge.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.llm import MockLLM

EXPLAIN_JSON = '{"explanation": "test", "follow_up_questions": []}'


def _client() -> TestClient:
    from app.api import api
    return TestClient(api)


def _connect(client: TestClient, db_path: str) -> str:
    resp = client.post("/connect", json={"db_url": f"duckdb:///{db_path}", "label": "test"})
    assert resp.status_code == 200, resp.text
    return resp.json()["session_id"]


def _patch_llm(monkeypatch, mock: MockLLM) -> None:
    # api.ask() calls get_compiled_agent() with no llm=, so build_graph resolves
    # its own get_llm(); api.ask() also calls get_llm() directly for the naive
    # verify prompt. Both names are bound at import time in their own module,
    # so both need patching for a shared mock to see every call.
    monkeypatch.setattr("app.graph.get_llm", lambda: mock)
    monkeypatch.setattr("app.api.get_llm", lambda: mock)


def test_verify_confirms_matching_second_opinion(monkeypatch, db_path: str):
    primary_sql = "SELECT r_name FROM region ORDER BY r_name"
    mock = MockLLM(responses=[
        (lambda s, u: "senior analytics engineer" in s, primary_sql),
        (lambda s, u: "concise data analyst" in s, EXPLAIN_JSON),
        (lambda s, u: "SQL expert" in s, primary_sql),  # independent verifier agrees
    ])
    _patch_llm(monkeypatch, mock)

    client = _client()
    session_id = _connect(client, db_path)
    resp = client.post(
        "/ask", json={"question": "list regions", "session_id": session_id, "verify": True}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["verified"] is True
    assert body["verify_sql"] is not None

    # Prove the second opinion actually ran as its own LLM call (distinct
    # system prompt), not a copy of the primary answer or a UI-only fake.
    naive_calls = [c for c in mock.calls if "SQL expert" in c[0]]
    assert len(naive_calls) == 1


def test_verify_flags_disagreeing_second_opinion(monkeypatch, db_path: str):
    primary_sql = "SELECT r_name FROM region ORDER BY r_name"
    disagreeing_sql = "SELECT r_name FROM region WHERE r_regionkey < 2"
    mock = MockLLM(responses=[
        (lambda s, u: "senior analytics engineer" in s, primary_sql),
        (lambda s, u: "concise data analyst" in s, EXPLAIN_JSON),
        (lambda s, u: "SQL expert" in s, disagreeing_sql),
    ])
    _patch_llm(monkeypatch, mock)

    client = _client()
    session_id = _connect(client, db_path)
    resp = client.post(
        "/ask", json={"question": "list regions", "session_id": session_id, "verify": True}
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["verified"] is False
    assert body["verify_sql"] is not None


def test_verify_off_skips_the_second_call(monkeypatch, db_path: str):
    primary_sql = "SELECT r_name FROM region ORDER BY r_name"
    mock = MockLLM(responses=[
        (lambda s, u: "senior analytics engineer" in s, primary_sql),
        (lambda s, u: "concise data analyst" in s, EXPLAIN_JSON),
        (lambda s, u: "SQL expert" in s, primary_sql),
    ])
    _patch_llm(monkeypatch, mock)

    client = _client()
    session_id = _connect(client, db_path)
    resp = client.post("/ask", json={"question": "list regions", "session_id": session_id})
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["verified"] is None
    assert body["verify_sql"] is None
    assert not any("SQL expert" in c[0] for c in mock.calls)
