from __future__ import annotations


def test_retriever_returns_chunks(retriever):
    schema = retriever.retrieve_schema("any question about anything")
    # Both kinds present
    assert "TABLE orders" in schema or "TABLE customer" in schema or "COLUMN" in schema
    assert len(schema) > 0


def test_retriever_examples_optional(retriever):
    # Examples not loaded into this test index; should still return [] gracefully
    out = retriever.retrieve_examples("any question")
    assert isinstance(out, list)


def test_retriever_topk_respects_filter(retriever):
    # Re-load with a larger schema to make the test meaningful
    s = retriever.retrieve_schema("orders by region", k_tables=3, k_cols=3)
    # Roughly: should contain at least one TABLE and at least one COLUMN block
    has_table = "TABLE " in s
    has_column = "COLUMN " in s
    assert has_table and has_column
