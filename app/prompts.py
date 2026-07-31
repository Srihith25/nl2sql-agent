"""All prompt templates in one place. Keep these short and exact."""
from __future__ import annotations


# ---------- Phase 2: schema-grounded raw SQL ----------

GROUNDED_SYSTEM = (
    "You are a senior analytics engineer. Write a single DuckDB SQL query "
    "that answers the user's question. Rules:\n"
    "- Only use tables and columns shown in SCHEMA. Do not invent.\n"
    "- DATE HANDLING: Check the column type in SCHEMA before using date functions.\n"
    "  If the column is VARCHAR but holds dates (e.g. '2015-03-25'), cast it:\n"
    "    col::DATE  or  TRY_CAST(col AS DATE).\n"
    "  For year-only filters on VARCHAR date columns, LIKE is simpler and safer:\n"
    "    WHERE date_col LIKE '2015%'\n"
    "- MAX/MIN PER GROUP: For 'highest/lowest X for each Y' questions, use\n"
    "  ROW_NUMBER() OVER (PARTITION BY y_col ORDER BY x_col DESC) in a subquery,\n"
    "  then WHERE rn = 1. In the outer SELECT, name each column explicitly —\n"
    "  never use SELECT * from the subquery (it would include the rn column).\n"
    "- YEAR GROUPING: For 'per year' GROUP BY queries on VARCHAR date columns,\n"
    "  use EXTRACT(YEAR FROM date_col::DATE)::INTEGER AS year.\n"
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
    "You wrote a SQL query that failed. Fix it and return ONLY the corrected SQL.\n"
    "Rules:\n"
    "- Read the ERROR carefully and address the exact cause.\n"
    "- Check column types in SCHEMA. If a column is VARCHAR but holds dates,\n"
    "  cast before using date functions: col::DATE  or  TRY_CAST(col AS DATE).\n"
    "- Only reference tables and columns that exist in SCHEMA.\n"
    "- No markdown fences, no explanation — SQL only."
)


def heal_user(question: str, prev_sql: str, error: str, schema: str = "") -> str:
    schema_block = f"SCHEMA:\n{schema}\n\n" if schema else ""
    return (
        f"QUESTION: {question}\n\n"
        f"{schema_block}"
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
