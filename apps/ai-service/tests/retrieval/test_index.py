"""
tests/retrieval/test_index.py

Comprehensive tests for Milestone 9 in-memory vector index and cosine similarity.
Covers:
  - Cosine similarity: identical, orthogonal, opposite, zero vectors, precision
  - Dimension mismatch handling
  - Upsert and replace semantics
  - Top-k limits, zero top-k, exceeding candidate count
  - Deterministic tie-breaking (score descending, chunk_id ascending)
  - Metadata preservation in SearchResult
"""

from __future__ import annotations

import math
import pytest

from src.retrieval.chunker import CodeChunk
from src.retrieval.index import (
    InMemoryVectorIndex,
    IndexedChunk,
    VectorIndex,
    cosine_similarity,
)


def _make_dummy_chunk(chunk_id: str, content: str = "code") -> CodeChunk:
    return CodeChunk(
        id=chunk_id,
        path="src/test.js",
        language="javascript",
        content=content,
        start_line=1,
        end_line=5,
        symbol_id=f"sym:{chunk_id}",
        symbol_name=chunk_id,
        node_ids=(f"node:{chunk_id}",),
        metadata=(("key", chunk_id),),
    )


# ===========================================================================
# 1. COSINE SIMILARITY MATH TESTS
# ===========================================================================


class TestCosineSimilarityMath:
    """Verify safe cosine similarity math across all edge cases."""

    def test_identical_vectors_similarity_is_one(self) -> None:
        v = [1.0, 2.0, 3.0]
        assert math.isclose(cosine_similarity(v, v), 1.0, rel_tol=1e-6)

    def test_orthogonal_vectors_similarity_is_zero(self) -> None:
        v1 = [1.0, 0.0]
        v2 = [0.0, 1.0]
        assert math.isclose(cosine_similarity(v1, v2), 0.0, abs_tol=1e-9)

    def test_opposite_vectors_similarity_is_negative_one(self) -> None:
        v1 = [1.0, 2.0]
        v2 = [-1.0, -2.0]
        assert math.isclose(cosine_similarity(v1, v2), -1.0, rel_tol=1e-6)

    def test_zero_vector_returns_zero(self) -> None:
        v1 = [0.0, 0.0, 0.0]
        v2 = [1.0, 2.0, 3.0]
        assert cosine_similarity(v1, v2) == 0.0
        assert cosine_similarity(v1, v1) == 0.0

    def test_dimension_mismatch_raises_value_error(self) -> None:
        v1 = [1.0, 2.0]
        v2 = [1.0, 2.0, 3.0]
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            cosine_similarity(v1, v2)

    def test_similarity_clamped_within_bounds(self) -> None:
        v = [1.0, 1.0, 1.0]
        sim = cosine_similarity(v, v)
        assert -1.0 <= sim <= 1.0


# ===========================================================================
# 2. VECTOR INDEX BEHAVIOR & PROTOCOL
# ===========================================================================


class TestInMemoryVectorIndex:
    """Verify upsert, replacement, search, top-k, and deterministic ties."""

    def test_isinstance_protocol_conformance(self) -> None:
        idx = InMemoryVectorIndex(dimension=4)
        assert isinstance(idx, VectorIndex)

    def test_empty_index_behavior(self) -> None:
        idx = InMemoryVectorIndex(dimension=4)
        assert idx.count() == 0
        results = idx.search([1.0, 0.0, 0.0, 0.0], top_k=5)
        assert results == []

    def test_upsert_and_count(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        c1 = _make_dummy_chunk("c1")
        c2 = _make_dummy_chunk("c2")

        idx.upsert(
            [
                IndexedChunk(chunk=c1, vector=(1.0, 0.0)),
                IndexedChunk(chunk=c2, vector=(0.0, 1.0)),
            ]
        )
        assert idx.count() == 2

    def test_upsert_replaces_existing_chunk_id(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        c1_old = _make_dummy_chunk("c1", content="old code")
        c1_new = _make_dummy_chunk("c1", content="new code")

        idx.upsert([IndexedChunk(chunk=c1_old, vector=(1.0, 0.0))])
        assert idx.count() == 1

        idx.upsert([IndexedChunk(chunk=c1_new, vector=(0.0, 1.0))])
        assert idx.count() == 1

        results = idx.search([0.0, 1.0], top_k=1)
        assert len(results) == 1
        assert results[0].content == "new code"
        assert math.isclose(results[0].score, 1.0, rel_tol=1e-6)

    def test_upsert_dimension_mismatch_raises(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        c1 = _make_dummy_chunk("c1")
        with pytest.raises(ValueError, match="Vector dimension mismatch"):
            idx.upsert([IndexedChunk(chunk=c1, vector=(1.0, 2.0, 3.0))])

    def test_search_dimension_mismatch_raises(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c1"), vector=(1.0, 0.0))])

        with pytest.raises(ValueError, match="Query vector dimension mismatch"):
            idx.search([1.0, 2.0, 3.0], top_k=5)

    def test_top_k_limiting_and_zero_top_k(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        for i in range(10):
            idx.upsert([IndexedChunk(chunk=_make_dummy_chunk(f"c{i}"), vector=(1.0, float(i)))])

        assert len(idx.search([1.0, 0.0], top_k=3)) == 3
        assert len(idx.search([1.0, 0.0], top_k=0)) == 0
        assert len(idx.search([1.0, 0.0], top_k=-2)) == 0
        assert len(idx.search([1.0, 0.0], top_k=50)) == 10

    def test_deterministic_tie_breaking_order(self) -> None:
        """Chunks with identical similarity scores must be sorted by chunk_id ascending."""
        idx = InMemoryVectorIndex(dimension=2)
        # All three chunks have identical vector (1.0, 0.0) -> identical similarity score 1.0
        c_z = _make_dummy_chunk("chunk_z")
        c_a = _make_dummy_chunk("chunk_a")
        c_m = _make_dummy_chunk("chunk_m")

        idx.upsert(
            [
                IndexedChunk(chunk=c_z, vector=(1.0, 0.0)),
                IndexedChunk(chunk=c_a, vector=(1.0, 0.0)),
                IndexedChunk(chunk=c_m, vector=(1.0, 0.0)),
            ]
        )

        results = idx.search([1.0, 0.0], top_k=5)
        assert len(results) == 3
        # Scores identical
        assert math.isclose(results[0].score, results[1].score)
        assert math.isclose(results[1].score, results[2].score)
        # IDs sorted alphabetically ascending
        assert [r.chunk_id for r in results] == ["chunk_a", "chunk_m", "chunk_z"]

    def test_search_result_preserves_metadata(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        c = CodeChunk(
            id="c:meta",
            path="src/auth.js",
            language="javascript",
            content="function login() {}",
            start_line=10,
            end_line=15,
            symbol_id="sym:auth:1",
            symbol_name="login",
            node_ids=("node:1", "node:2"),
            metadata=(("role", "controller"),),
        )
        idx.upsert([IndexedChunk(chunk=c, vector=(1.0, 0.0))])

        results = idx.search([1.0, 0.0], top_k=1)
        assert len(results) == 1
        res = results[0]
        assert res.chunk_id == "c:meta"
        assert res.path == "src/auth.js"
        assert res.start_line == 10
        assert res.end_line == 15
        assert res.symbol_id == "sym:auth:1"
        assert res.metadata == (("role", "controller"),)

    def test_search_result_immutability(self) -> None:
        import dataclasses
        c = _make_dummy_chunk("c1")
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=c, vector=(1.0, 0.0))])
        res = idx.search([1.0, 0.0], top_k=1)[0]

        with pytest.raises(dataclasses.FrozenInstanceError):
            res.score = 0.5  # type: ignore[misc]

    def test_indexed_chunk_immutability(self) -> None:
        import dataclasses
        c = _make_dummy_chunk("c1")
        item = IndexedChunk(chunk=c, vector=(1.0, 0.0))

        with pytest.raises(dataclasses.FrozenInstanceError):
            item.vector = (0.0, 1.0)  # type: ignore[misc]

    def test_negative_similarities_ranked_properly(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        c_pos = _make_dummy_chunk("pos")
        c_orth = _make_dummy_chunk("orth")
        c_neg = _make_dummy_chunk("neg")

        idx.upsert([
            IndexedChunk(chunk=c_pos, vector=(1.0, 0.0)),
            IndexedChunk(chunk=c_orth, vector=(0.0, 1.0)),
            IndexedChunk(chunk=c_neg, vector=(-1.0, 0.0)),
        ])

        results = idx.search([1.0, 0.0], top_k=3)
        assert [r.chunk_id for r in results] == ["pos", "orth", "neg"]
        assert math.isclose(results[0].score, 1.0)
        assert math.isclose(results[1].score, 0.0)
        assert math.isclose(results[2].score, -1.0)

    def test_dimension_inferred_from_first_upsert_when_none(self) -> None:
        idx = InMemoryVectorIndex()
        assert idx.dimension is None
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c1"), vector=(1.0, 2.0, 3.0))])
        assert idx.dimension == 3

    def test_multiple_sequential_upserts(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c1"), vector=(1.0, 0.0))])
        assert idx.count() == 1
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c2"), vector=(0.0, 1.0))])
        assert idx.count() == 2
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c3"), vector=(1.0, 1.0))])
        assert idx.count() == 3

    def test_empty_upsert_list_does_nothing(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([])
        assert idx.count() == 0

    def test_upsert_with_zero_vector(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c_zero"), vector=(0.0, 0.0))])
        assert idx.count() == 1
        results = idx.search([1.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].score == 0.0

    def test_search_with_zero_vector(self) -> None:
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=_make_dummy_chunk("c1"), vector=(1.0, 0.0))])
        results = idx.search([0.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0].score == 0.0

    def test_search_result_representation(self) -> None:
        c = _make_dummy_chunk("c1")
        idx = InMemoryVectorIndex(dimension=2)
        idx.upsert([IndexedChunk(chunk=c, vector=(1.0, 0.0))])
        res = idx.search([1.0, 0.0], top_k=1)[0]
        rep = repr(res)
        assert "chunk_id='c1'" in rep
        assert "score=" in rep

    def test_indexed_chunk_representation(self) -> None:
        c = _make_dummy_chunk("c1")
        item = IndexedChunk(chunk=c, vector=(1.0, 0.0))
        rep = repr(item)
        assert "c1" in rep

