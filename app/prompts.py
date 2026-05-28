"""All prompt templates in one place. Keep these short and exact."""
from __future__ import annotations


# ---------- Phase 2: schema-grounded raw SQL ----------

GROUNDED_SYSTEM = (
    "You are a senior analytics engineer. Write a single DuckDB SQL query "
    "that answers the user's question. Rules:\n"
    "- Only use tables and columns shown in SCHEMA. Do not invent.\n"
    "- Prefer joins on the keys shown in SCHEMA.\n"
    "- Match the style of the EXAMPLES.\n"
    "- Return ONLY the SQL — no markdown fences, no explanation."
)


def grounded_user(question: str, schema: str, examples: list[tuple[str, str]]) -> str:
    if examples:
        ex_block = "\n\n".join(f"-- {q}\n{s}" for q, s in examples)
    else:
        ex_block = "(none)"
    return (
        f"SCHEMA:\n{schema}\n\n"
        f"EXAMPLES:\n{ex_block}\n\n"
        f"QUESTION: {question}\n\nSQL:"
    )


# ---------- Phase 3a: classify metric vs raw ----------

CLASSIFY_SYSTEM = (
    "You decide whether a user's analytics question is answerable using ONLY the metrics "
    "and dimensions defined in the semantic layer below. Answer with a single word: "
    "yes or no. No punctuation, no explanation."
)


def classify_user(question: str, cube_meta: str) -> str:
    return f"CUBE_META:\n{cube_meta}\n\nQUESTION: {question}\n\nAnswer:"


# ---------- Phase 3a: write a Cube query ----------

CUBE_SYSTEM = (
    "You write Cube query JSON, given a user question and the available cubes. "
    "Return ONLY a JSON object with keys among: measures, dimensions, "
    "timeDimensions, filters, order, limit. Do not include any prose or markdown."
)


def cube_user(question: str, cube_meta: str) -> str:
    return f"CUBE_META:\n{cube_meta}\n\nQUESTION: {question}\n\nJSON:"


# ---------- Phase 3b: self-healing ----------

HEAL_SYSTEM = (
    "You wrote a SQL query that failed. You will see the original question, the "
    "previous SQL, and the database error. Rewrite the SQL to fix the specific "
    "error using ONLY the schema implied by the previous attempt. Return ONLY the SQL."
)


def heal_user(question: str, prev_sql: str, error: str) -> str:
    return (
        f"QUESTION: {question}\n\n"
        f"PREVIOUS SQL:\n{prev_sql}\n\n"
        f"ERROR:\n{error}\n\n"
        f"CORRECTED SQL:"
    )


# ---------- Naive baseline (Phase 1) ----------

NAIVE_SYSTEM = (
    "You are a SQL expert. Given a user's question and a database schema, "
    "write a single DuckDB SQL query that answers it. Return ONLY the SQL — "
    "no markdown fences, no explanation."
)


def naive_user(question: str, schema_sql: str) -> str:
    return f"SCHEMA:\n{schema_sql}\n\nQUESTION: {question}\n\nSQL:"
