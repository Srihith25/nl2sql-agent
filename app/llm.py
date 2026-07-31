"""LLM provider abstraction.

Three providers:
  * groq      — free tier, llama-3.1-8b-instant by default
  * anthropic — paid, claude-haiku-4-5 by default
  * mock      — used by the test suite; takes a list of canned responses

Usage:
    from app.llm import get_llm
    llm = get_llm()
    text = llm.complete(system="You are ...", user="Write SQL for ...")
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Callable, Optional, Protocol

from .config import settings

log = logging.getLogger(__name__)


class LLM(Protocol):
    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str: ...


# ---------- Groq ----------

class GroqLLM:
    def __init__(self, model: Optional[str] = None):
        try:
            from groq import Groq  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "groq package not installed. Run: pip install -e '.[groq]'"
            ) from e
        if not settings.groq_api_key:
            raise RuntimeError("GROQ_API_KEY is not set in .env")
        self.client = Groq(api_key=settings.groq_api_key)
        self.model = model or settings.groq_model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        r = self.client.chat.completions.create(
            model=self.model,
            temperature=0,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        return r.choices[0].message.content or ""


# ---------- Anthropic ----------

class ClaudeLLM:
    def __init__(self, model: Optional[str] = None):
        try:
            from anthropic import Anthropic  # type: ignore
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "anthropic package not installed. Run: pip install -e '.[anthropic]'"
            ) from e
        if not settings.anthropic_api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set in .env")
        self.client = Anthropic(api_key=settings.anthropic_api_key)
        self.model = model or settings.anthropic_model

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        r = self.client.messages.create(
            model=self.model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        # Anthropic returns a list of content blocks; the first should be text.
        return r.content[0].text  # type: ignore[attr-defined]


# ---------- Mock (deterministic, for tests) ----------

@dataclass
class MockLLM:
    """A scripted LLM. Each call uses the first response whose predicate matches.

    Examples
    --------
    >>> mock = MockLLM(responses=[
    ...     (lambda s, u: "Is this question" in s, "yes"),
    ...     (lambda s, u: "Write a single" in s, "SELECT 1"),
    ... ])
    """

    responses: list[tuple[Callable[[str, str], bool], str]] = field(default_factory=list)
    fallback: str = ""
    calls: list[tuple[str, str]] = field(default_factory=list)

    def complete(self, system: str, user: str, max_tokens: int = 1024) -> str:
        self.calls.append((system, user))
        for predicate, response in self.responses:
            if predicate(system, user):
                return response
        return self.fallback


# ---------- Factory ----------

def get_llm(provider: Optional[str] = None) -> LLM:
    provider = provider or settings.llm_provider
    if provider == "groq":
        return GroqLLM()
    if provider == "anthropic":
        return ClaudeLLM()
    if provider == "mock":
        log.warning("Using MockLLM with no scripted responses (returns empty string).")
        return MockLLM()
    raise ValueError(f"Unknown LLM provider: {provider}")
