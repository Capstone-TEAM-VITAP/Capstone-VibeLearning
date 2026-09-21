"""
tests/retrieval/test_embeddings.py

Comprehensive tests for Milestone 9 embedding abstraction and DeterministicEmbeddingProvider.
Covers:
  - Protocol conformity
  - Deterministic repeatability
  - SHA-256 stability across calls
  - Vector dimensions and unit normalization
  - Batch embedding and empty batches
  - Error handling (non-string inputs, invalid dimensions)
"""

from __future__ import annotations

import math
import pytest

from src.retrieval.embeddings import (
    DeterministicEmbeddingProvider,
    EmbeddingProvider,
)


class TestEmbeddingProviderProtocol:
    """Verify protocol conformance."""

    def test_isinstance_protocol_conformance(self) -> None:
        provider = DeterministicEmbeddingProvider(dimension=32)
        assert isinstance(provider, EmbeddingProvider)


class TestDeterministicEmbeddingProvider:
    """Verify vector generation, normalization, and determinism."""

    def test_positive_dimension_enforced(self) -> None:
        with pytest.raises(ValueError, match="Embedding dimension must be positive"):
            DeterministicEmbeddingProvider(dimension=0)

        with pytest.raises(ValueError, match="Embedding dimension must be positive"):
            DeterministicEmbeddingProvider(dimension=-5)

    def test_configured_dimension(self) -> None:
        p32 = DeterministicEmbeddingProvider(dimension=32)
        assert p32.dimension == 32
        vec = p32.embed_query("hello")
        assert len(vec) == 32

        p128 = DeterministicEmbeddingProvider(dimension=128)
        assert p128.dimension == 128
        vec128 = p128.embed_query("hello")
        assert len(vec128) == 128

    def test_same_text_produces_identical_vector(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        v1 = p.embed_query("function authenticate() {}")
        v2 = p.embed_query("function authenticate() {}")
        assert v1 == v2

    def test_different_text_produces_different_vectors(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        v1 = p.embed_query("function login() {}")
        v2 = p.embed_query("function logout() {}")
        assert v1 != v2

    def test_vectors_are_unit_normalized(self) -> None:
        """Every non-zero vector must have L2 norm approximately equal to 1.0."""
        p = DeterministicEmbeddingProvider(dimension=64)
        for text in ["hello", "export const x = 1;", "class User {}", ""]:
            vec = p.embed_query(text)
            norm = math.sqrt(sum(x * x for x in vec))
            assert math.isclose(norm, 1.0, rel_tol=1e-6)

    def test_batch_embedding_consistency(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        texts = ["alpha", "beta", "gamma"]

        batch_vectors = p.embed(texts)
        assert len(batch_vectors) == 3

        single_alpha = p.embed_query("alpha")
        single_beta = p.embed_query("beta")
        single_gamma = p.embed_query("gamma")

        assert batch_vectors[0] == single_alpha
        assert batch_vectors[1] == single_beta
        assert batch_vectors[2] == single_gamma

    def test_empty_batch_returns_empty_list(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        assert p.embed([]) == []

    def test_non_string_in_batch_raises_type_error(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        with pytest.raises(TypeError, match="Expected text at index 1 to be str"):
            p.embed(["valid", 12345])  # type: ignore[list-item]

    def test_non_string_in_query_raises_type_error(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        with pytest.raises(TypeError, match="Expected query to be str"):
            p.embed_query(None)  # type: ignore[arg-type]

    def test_repeated_provider_instantiation_stability(self) -> None:
        """Vectors must be identical across completely separate provider instances."""
        p1 = DeterministicEmbeddingProvider(dimension=64)
        p2 = DeterministicEmbeddingProvider(dimension=64)

        text = "const API_URL = 'http://localhost';"
        assert p1.embed_query(text) == p2.embed_query(text)

    def test_unicode_and_special_characters_support(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=32)
        v = p.embed_query("こんにちは世界 🚀 π = 3.14159")
        assert len(v) == 32
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, rel_tol=1e-6)

    def test_extremely_long_string_handling(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        long_text = "const a = 1;\n" * 5000
        v = p.embed_query(long_text)
        assert len(v) == 64
        norm = math.sqrt(sum(x * x for x in v))
        assert math.isclose(norm, 1.0, rel_tol=1e-6)

    def test_single_character_strings(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=16)
        va = p.embed_query("a")
        vb = p.embed_query("b")
        assert va != vb
        assert len(va) == 16
        assert len(vb) == 16

    def test_embed_query_matches_single_element_embed(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=32)
        t = "class RouteHandler {}"
        assert p.embed_query(t) == p.embed([t])[0]

    def test_hundred_distinct_strings_produce_distinct_vectors(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=64)
        texts = [f"function fn_{i}() {{ return {i}; }}" for i in range(100)]
        vectors = p.embed(texts)
        assert len(vectors) == 100
        # All vectors should be unique
        unique_vecs = {tuple(v) for v in vectors}
        assert len(unique_vecs) == 100

    def test_various_dimension_sizes(self) -> None:
        for dim in [1, 2, 8, 16, 128, 256]:
            p = DeterministicEmbeddingProvider(dimension=dim)
            v = p.embed_query("test text")
            assert len(v) == dim
            norm = math.sqrt(sum(x * x for x in v))
            assert math.isclose(norm, 1.0, rel_tol=1e-5)

    def test_whitespace_sensitivity(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=32)
        v1 = p.embed_query("function test() {}")
        v2 = p.embed_query("function test() { }")
        assert v1 != v2

    def test_case_sensitivity(self) -> None:
        p = DeterministicEmbeddingProvider(dimension=32)
        v1 = p.embed_query("getUser")
        v2 = p.embed_query("GetUser")
        assert v1 != v2

    def test_identical_text_cosine_similarity_is_one(self) -> None:
        from src.retrieval.index import cosine_similarity
        p = DeterministicEmbeddingProvider(dimension=32)
        v1 = p.embed_query("export const TOKEN = 'abc';")
        v2 = p.embed_query("export const TOKEN = 'abc';")
        sim = cosine_similarity(v1, v2)
        assert math.isclose(sim, 1.0, rel_tol=1e-6)

