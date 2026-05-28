"""Embedding providers.

We default to sentence-transformers/all-MiniLM-L6-v2 (~80MB, 384-dim, CPU OK).
If sentence-transformers is not installed, we fall back to a deterministic hash
embedder so tests can run with zero downloads. The hash embedder is fine for
tests but lacks semantic value, so the agent will retrieve poorly with it.
"""
from __future__ import annotations

import hashlib
import logging
from typing import Protocol

import numpy as np

from .config import settings

log = logging.getLogger(__name__)


class Embedder(Protocol):
    dim: int
    def encode(self, texts: list[str]) -> np.ndarray: ...


# ---------- Hash fallback ----------

class HashEmbedder:
    """Deterministic, zero-dependency embedder. Not semantic; for tests only.

    Each text is hashed to a fixed-length unit vector. Identical inputs always
    map to the same vector. Different inputs get pseudo-orthogonal vectors.
    """

    dim: int = 256

    def encode(self, texts: list[str]) -> np.ndarray:
        out = []
        for t in texts:
            # 64 bytes from sha512 → 16 floats; repeat to reach self.dim
            seed = hashlib.sha512(t.encode("utf-8")).digest()
            buf = (seed * ((self.dim * 4 // len(seed)) + 1))[: self.dim * 4]
            arr = np.frombuffer(buf, dtype=np.uint32).astype(np.float32)
            arr = arr / (2**32 - 1) * 2.0 - 1.0
            arr = arr / (np.linalg.norm(arr) + 1e-8)
            out.append(arr)
        return np.stack(out)


# ---------- Real (sentence-transformers) ----------

class STEmbedder:
    def __init__(self, model_name: str | None = None):
        from sentence_transformers import SentenceTransformer  # type: ignore

        self.model_name = model_name or settings.embed_model
        self.model = SentenceTransformer(self.model_name)
        # Probe dim
        self.dim = int(self.model.get_sentence_embedding_dimension())

    def encode(self, texts: list[str]) -> np.ndarray:
        return self.model.encode(
            texts,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        ).astype(np.float32)


# ---------- Factory ----------

def get_embedder() -> Embedder:
    choice = settings.embedder
    if choice == "hash":
        return HashEmbedder()
    if choice == "sentence-transformers":
        return STEmbedder()
    # auto
    try:
        return STEmbedder()
    except Exception as e:  # noqa: BLE001
        log.warning(
            "sentence-transformers unavailable (%s); falling back to HashEmbedder. "
            "Run `pip install -e '.[embed]'` for real semantic retrieval.",
            type(e).__name__,
        )
        return HashEmbedder()
