"""Centralised settings loaded from environment / .env."""
from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- LLM ---
    llm_provider: Literal["groq", "anthropic", "mock"] = "mock"
    groq_api_key: str = ""
    groq_model: str = "llama-3.1-8b-instant"
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-haiku-4-5-20251001"

    # --- Data ---
    db_path: str = str(ROOT / "data" / "warehouse.duckdb")
    vector_db_path: str = str(ROOT / "data" / "vectors.duckdb")

    # --- Embedder ---
    embedder: Literal["auto", "sentence-transformers", "hash"] = "auto"
    embed_model: str = "all-MiniLM-L6-v2"

    # --- Agent ---
    max_heal_attempts: int = 3
    top_k_tables: int = 5
    top_k_columns: int = 15
    top_k_examples: int = 3

    # --- Optional services ---
    cube_url: str = ""
    cube_api_secret: str = ""
    langfuse_host: str = ""
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""


settings = Settings()
