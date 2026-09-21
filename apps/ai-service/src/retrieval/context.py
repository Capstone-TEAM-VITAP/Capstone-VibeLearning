"""
retrieval/context.py

RetrievedContext contract model for Milestone 9.
Defines the immutable container returned by semantic search and consumed by
downstream CodeAI modules (AI Software Assistant, Code Review, Verification).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from .index import SearchResult


@dataclass(frozen=True)
class RetrievedContext:
    """
    Immutable retrieval context returned by the retrieval pipeline.

    Attributes:
        query:            The search query string.
        results:          Deterministic tuple of top-k SearchResult objects.
        total_candidates: Total number of candidate chunks evaluated in the index.
    """

    query: str
    results: tuple[SearchResult, ...]
    total_candidates: int

    def __len__(self) -> int:
        """Return the number of retrieved search results."""
        return len(self.results)

    def __iter__(self) -> Iterator[SearchResult]:
        """Iterate over retrieved search results."""
        return iter(self.results)

    @property
    def top_result(self) -> SearchResult | None:
        """Return the highest-scoring search result, or None if empty."""
        return self.results[0] if self.results else None

    @property
    def paths(self) -> tuple[str, ...]:
        """Return distinct file paths represented across retrieved results."""
        seen = []
        for r in self.results:
            if r.path not in seen:
                seen.append(r.path)
        return tuple(seen)
