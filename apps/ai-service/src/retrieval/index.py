"""
retrieval/index.py

Vector index abstraction and in-memory implementation for Milestone 9.
Provides deterministic similarity search over code chunks using safe cosine similarity.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol, Sequence, runtime_checkable

from .chunker import CodeChunk


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IndexedChunk:
    """
    An immutable pair of a CodeChunk and its embedding vector.

    Attributes:
        chunk:  The source CodeChunk.
        vector: The embedding vector as an immutable tuple of floats.
    """

    chunk: CodeChunk
    vector: tuple[float, ...]


@dataclass(frozen=True)
class SearchResult:
    """
    An immutable search result returned by the vector index.

    Attributes:
        chunk_id:   Identifier of the matching chunk.
        score:      Similarity score in range [-1.0, 1.0].
        path:       Repository-relative file path.
        start_line: Starting line in source code.
        end_line:   Ending line in source code.
        content:    Code content snippet.
        symbol_id:  Associated symbol ID, or None.
        metadata:   Metadata tuple associated with the chunk.
    """

    chunk_id: str
    score: float
    path: str
    start_line: int
    end_line: int
    content: str
    symbol_id: str | None
    metadata: tuple[tuple[str, str], ...] = ()


# ---------------------------------------------------------------------------
# Cosine Similarity Calculation
# ---------------------------------------------------------------------------


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """
    Compute safe cosine similarity between two vectors.

    Handles zero vectors, unit vectors, and numerical precision limits.

    Raises:
        ValueError: If vector dimensions do not match.
    """
    if len(a) != len(b):
        raise ValueError(
            f"Vector dimension mismatch: vector A has length {len(a)}, vector B has length {len(b)}"
        )

    dot = 0.0
    norm_a = 0.0
    norm_b = 0.0

    for x, y in zip(a, b):
        dot += x * y
        norm_a += x * x
        norm_b += y * y

    if norm_a <= 0.0 or norm_b <= 0.0:
        return 0.0

    sim = dot / (math.sqrt(norm_a) * math.sqrt(norm_b))
    return max(-1.0, min(1.0, sim))


# ---------------------------------------------------------------------------
# Vector Index Protocol
# ---------------------------------------------------------------------------


@runtime_checkable
class VectorIndex(Protocol):
    """Protocol for vector indexes."""

    def upsert(self, items: Sequence[IndexedChunk]) -> None:
        """Insert or replace indexed chunks."""
        ...

    def search(
        self,
        vector: Sequence[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Search for top_k nearest chunks to vector."""
        ...

    def count(self) -> int:
        """Return the number of indexed chunks."""
        ...


# ---------------------------------------------------------------------------
# In-Memory Vector Index Implementation
# ---------------------------------------------------------------------------


class InMemoryVectorIndex:
    """
    An in-memory, deterministic vector index for code retrieval.

    Supports upserting, replacing, and cosine similarity search.
    Results with equal scores are ordered deterministically by chunk_id ascending.
    """

    def __init__(self, dimension: int | None = None) -> None:
        self._dimension = dimension
        self._items: dict[str, IndexedChunk] = {}

    @property
    def dimension(self) -> int | None:
        """Return the expected vector dimension, or None if not yet set."""
        return self._dimension

    def count(self) -> int:
        """Return the number of indexed items."""
        return len(self._items)

    def upsert(self, items: Sequence[IndexedChunk]) -> None:
        """
        Insert or replace indexed chunks in the index.

        Raises:
            ValueError: If an item's vector length does not match index dimension.
        """
        for item in items:
            vec_len = len(item.vector)
            if self._dimension is None:
                self._dimension = vec_len
            elif vec_len != self._dimension:
                raise ValueError(
                    f"Vector dimension mismatch for chunk '{item.chunk.id}': "
                    f"expected {self._dimension}, got {vec_len}"
                )
            self._items[item.chunk.id] = item

    def search(
        self,
        vector: Sequence[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """
        Search for top_k most similar items to query vector.

        Results are sorted by score descending, then chunk_id ascending.

        Raises:
            ValueError: If query vector dimension does not match index dimension.
        """
        if top_k <= 0 or not self._items:
            return []

        if self._dimension is not None and len(vector) != self._dimension:
            raise ValueError(
                f"Query vector dimension mismatch: expected {self._dimension}, got {len(vector)}"
            )

        scored_results: list[SearchResult] = []
        for chunk_id, indexed_chunk in self._items.items():
            sim = cosine_similarity(vector, indexed_chunk.vector)
            chunk = indexed_chunk.chunk
            scored_results.append(
                SearchResult(
                    chunk_id=chunk.id,
                    score=sim,
                    path=chunk.path,
                    start_line=chunk.start_line,
                    end_line=chunk.end_line,
                    content=chunk.content,
                    symbol_id=chunk.symbol_id,
                    metadata=chunk.metadata,
                )
            )

        # Deterministic ordering: score descending, then chunk_id ascending
        scored_results.sort(key=lambda r: (-r.score, r.chunk_id))
        return scored_results[:top_k]
