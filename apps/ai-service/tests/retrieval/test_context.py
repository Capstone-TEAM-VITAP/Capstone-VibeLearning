"""
tests/retrieval/test_context.py

Comprehensive tests for Milestone 9 RetrievedContext model.
Covers:
  - Context creation and query preservation
  - Immutable fields and frozen behavior
  - Result ordering and tuple immutability
  - Empty context handling
  - Helper properties: top_result, paths, len, iteration
"""

from __future__ import annotations

import dataclasses
import pytest

from src.retrieval.context import RetrievedContext
from src.retrieval.index import SearchResult


def _make_dummy_result(chunk_id: str, path: str = "src/test.js", score: float = 0.9) -> SearchResult:
    return SearchResult(
        chunk_id=chunk_id,
        score=score,
        path=path,
        start_line=1,
        end_line=5,
        content="code snippet",
        symbol_id=f"sym:{chunk_id}",
        metadata=(("id", chunk_id),),
    )


class TestRetrievedContext:
    """Verify RetrievedContext contract."""

    def test_creation_and_field_preservation(self) -> None:
        r1 = _make_dummy_result("c1", path="src/auth.js", score=0.95)
        r2 = _make_dummy_result("c2", path="src/user.js", score=0.80)
        ctx = RetrievedContext(
            query="find authentication method",
            results=(r1, r2),
            total_candidates=10,
        )

        assert ctx.query == "find authentication method"
        assert ctx.total_candidates == 10
        assert len(ctx) == 2
        assert ctx.results == (r1, r2)
        assert ctx.top_result == r1
        assert ctx.paths == ("src/auth.js", "src/user.js")

    def test_empty_context(self) -> None:
        ctx = RetrievedContext(
            query="no matches",
            results=(),
            total_candidates=0,
        )
        assert len(ctx) == 0
        assert ctx.top_result is None
        assert ctx.paths == ()
        assert list(ctx) == []

    def test_context_is_immutable(self) -> None:
        r = _make_dummy_result("c1")
        ctx = RetrievedContext(query="query", results=(r,), total_candidates=1)

        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.query = "new query"  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.total_candidates = 5  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            ctx.results = ()  # type: ignore[misc]

        assert isinstance(ctx.results, tuple)

    def test_iteration_over_results(self) -> None:
        r1 = _make_dummy_result("c1")
        r2 = _make_dummy_result("c2")
        ctx = RetrievedContext(query="q", results=(r1, r2), total_candidates=2)

        items = [item.chunk_id for item in ctx]
        assert items == ["c1", "c2"]

    def test_paths_deduplication(self) -> None:
        r1 = _make_dummy_result("c1", path="src/auth.js")
        r2 = _make_dummy_result("c2", path="src/auth.js")
        r3 = _make_dummy_result("c3", path="src/user.js")
        ctx = RetrievedContext(query="q", results=(r1, r2, r3), total_candidates=3)

        assert ctx.paths == ("src/auth.js", "src/user.js")

    def test_total_candidates_independent_of_top_k(self) -> None:
        r1 = _make_dummy_result("c1")
        ctx = RetrievedContext(query="q", results=(r1,), total_candidates=100)
        assert len(ctx) == 1
        assert ctx.total_candidates == 100

    def test_indexing_results(self) -> None:
        r1 = _make_dummy_result("c1", score=0.9)
        r2 = _make_dummy_result("c2", score=0.8)
        ctx = RetrievedContext(query="q", results=(r1, r2), total_candidates=2)
        assert ctx.results[0].chunk_id == "c1"
        assert ctx.results[1].chunk_id == "c2"

    def test_context_representation(self) -> None:
        r1 = _make_dummy_result("c1", score=0.9)
        ctx = RetrievedContext(query="query_abc", results=(r1,), total_candidates=5)
        r_str = repr(ctx)
        assert "query_abc" in r_str
        assert "total_candidates=5" in r_str

    def test_paths_empty_when_no_results(self) -> None:
        ctx = RetrievedContext(query="empty", results=(), total_candidates=0)
        assert ctx.paths == ()

    def test_top_result_is_first_result(self) -> None:
        r1 = _make_dummy_result("first", score=0.99)
        r2 = _make_dummy_result("second", score=0.50)
        ctx = RetrievedContext(query="top", results=(r1, r2), total_candidates=2)
        assert ctx.top_result is not None
        assert ctx.top_result.chunk_id == "first"

    def test_preserves_score_order(self) -> None:
        r1 = _make_dummy_result("c1", score=0.9)
        r2 = _make_dummy_result("c2", score=0.7)
        r3 = _make_dummy_result("c3", score=0.4)
        ctx = RetrievedContext(query="order", results=(r1, r2, r3), total_candidates=10)
        scores = [r.score for r in ctx]
        assert scores == [0.9, 0.7, 0.4]

    def test_slice_results(self) -> None:
        r1 = _make_dummy_result("c1", score=0.9)
        r2 = _make_dummy_result("c2", score=0.8)
        r3 = _make_dummy_result("c3", score=0.7)
        ctx = RetrievedContext(query="slice", results=(r1, r2, r3), total_candidates=3)
        sliced = ctx.results[:2]
        assert len(sliced) == 2
        assert sliced[0].chunk_id == "c1"
        assert sliced[1].chunk_id == "c2"

