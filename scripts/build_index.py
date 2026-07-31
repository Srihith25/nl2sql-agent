"""Build the schema-chunks vector index from the warehouse DuckDB."""
from __future__ import annotations

import logging
import pathlib
import sys

from app.config import settings
from app.retriever import build_index

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

ROOT = pathlib.Path(__file__).resolve().parent.parent


def main() -> int:
    examples = ROOT / "eval" / "examples.jsonl"
    n = build_index(
        db_path=settings.db_path,
        vector_db_path=settings.vector_db_path,
        examples_path=examples if examples.exists() else None,
    )
    print(f"[index] built {n} chunks at {settings.vector_db_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
