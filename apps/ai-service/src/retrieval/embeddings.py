"""
retrieval/embeddings.py

Embedding provider abstraction and deterministic test implementation for Milestone 9.
Provides an interface and a SHA-256-based provider that produces stable,
unit-normalized vectors without external dependencies.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol, Sequence, runtime_checkable


# ---------------------------------------------------------------------------
# Embedding Provider Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Protocol for embedding providers."""

    @property
    def dimension(self) -> int:
        """Return the fixed dimension of embedding vectors produced by this provider."""
        ...

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Compute embedding vectors for a batch of input texts."""
        ...

    def embed_query(self, query: str) -> list[float]:
        """Compute an embedding vector for a single search query."""
        ...


# ---------------------------------------------------------------------------
# Deterministic Embedding Provider
# ---------------------------------------------------------------------------


class DeterministicEmbeddingProvider:
    """
    Deterministic, offline embedding provider for tests and local development.

    Uses SHA-256 hashing to generate reproducible, unit-normalized vectors.
    Does not depend on external APIs or Python's process-randomized hash() seed.
    """

    def __init__(self, dimension: int = 64) -> None:
        if dimension <= 0:
            raise ValueError(f"Embedding dimension must be positive, got {dimension}")
        self._dimension = dimension

    @property
    def dimension(self) -> int:
        """Return the configured vector dimension."""
        return self._dimension

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """
        Compute embedding vectors for a batch of strings.

        Raises:
            TypeError: If any element in texts is not a string.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        for idx, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(
                    f"Expected text at index {idx} to be str, got {type(text).__name__}"
                )
            results.append(self._embed_single(text))
        return results

    def embed_query(self, query: str) -> list[float]:
        """
        Compute an embedding vector for a single query string.

        Raises:
            TypeError: If query is not a string.
        """
        if not isinstance(query, str):
            raise TypeError(f"Expected query to be str, got {type(query).__name__}")
        return self._embed_single(query)

    def _embed_single(self, text: str) -> list[float]:
        raw_vals: list[float] = []
        block_idx = 0

        while len(raw_vals) < self._dimension:
            hasher = hashlib.sha256()
            hasher.update(text.encode("utf-8"))
            hasher.update(block_idx.to_bytes(4, byteorder="big"))
            digest = hasher.digest()

            for b in digest:
                val = (b - 127.5) / 127.5
                raw_vals.append(val)
                if len(raw_vals) == self._dimension:
                    break
            block_idx += 1

        norm = math.sqrt(sum(x * x for x in raw_vals))
        if norm > 0.0:
            return [x / norm for x in raw_vals]
        return [0.0] * self._dimension
