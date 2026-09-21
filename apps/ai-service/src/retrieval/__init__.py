"""
retrieval package for Milestone 9 — Semantic Code Index & Retrieval Foundation.
"""

from .chunker import CodeChunk, chunk_repository, make_chunk_id
from .context import RetrievedContext
from .embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from .index import (
    InMemoryVectorIndex,
    IndexedChunk,
    SearchResult,
    VectorIndex,
    cosine_similarity,
)
from .pipeline import RetrievalPipeline, create_retrieval_pipeline

__all__ = [
    "CodeChunk",
    "chunk_repository",
    "make_chunk_id",
    "RetrievedContext",
    "EmbeddingProvider",
    "DeterministicEmbeddingProvider",
    "VectorIndex",
    "IndexedChunk",
    "SearchResult",
    "InMemoryVectorIndex",
    "cosine_similarity",
    "RetrievalPipeline",
    "create_retrieval_pipeline",
]
