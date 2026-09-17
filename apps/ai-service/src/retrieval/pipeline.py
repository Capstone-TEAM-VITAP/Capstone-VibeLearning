"""
retrieval/pipeline.py

End-to-end code retrieval pipeline for Milestone 9.
Connects code chunking, embedding generation, vector indexing, similarity search,
and optional deterministic lexical/hybrid scoring into a unified API.
"""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from ..repository.graph import CodeGraph
from .chunker import CodeChunk, chunk_repository
from .context import RetrievedContext
from .embeddings import DeterministicEmbeddingProvider, EmbeddingProvider
from .index import InMemoryVectorIndex, IndexedChunk, SearchResult, VectorIndex

_TOKEN_PATTERN = re.compile(r"[A-Za-z0-9_]+")


def _tokenize(text: str) -> set[str]:
    """Tokenize text into lowercase alphanumeric identifiers."""
    return set(_TOKEN_PATTERN.findall(text.lower()))


def _compute_lexical_score(query_tokens: set[str], chunk_content: str, symbol_name: str | None) -> float:
    """
    Compute a deterministic lexical overlap score in range [0.0, 1.0].
    Uses Jaccard overlap of query tokens with code tokens.
    """
    if not query_tokens:
        return 0.0

    target_tokens = _tokenize(chunk_content)
    if symbol_name:
        target_tokens.update(_tokenize(symbol_name))

    if not target_tokens:
        return 0.0

    intersection = query_tokens.intersection(target_tokens)
    union = query_tokens.union(target_tokens)
    return len(intersection) / len(union) if union else 0.0


# ---------------------------------------------------------------------------
# Retrieval Pipeline Implementation
# ---------------------------------------------------------------------------


class RetrievalPipeline:
    """
    Coordinates repository indexing and semantic/hybrid code search.

    Pipeline:
      Source / CodeGraph → CodeChunk → EmbeddingProvider → VectorIndex → RetrievedContext
    """

    def __init__(
        self,
        embedding_provider: EmbeddingProvider,
        vector_index: VectorIndex | None = None,
        *,
        semantic_weight: float = 1.0,
        lexical_weight: float = 0.0,
    ) -> None:
        self.embedding_provider = embedding_provider
        self.vector_index: VectorIndex = (
            vector_index
            if vector_index is not None
            else InMemoryVectorIndex(dimension=embedding_provider.dimension)
        )
        self.semantic_weight = float(semantic_weight)
        self.lexical_weight = float(lexical_weight)

    def index_chunks(self, chunks: Sequence[CodeChunk]) -> int:
        """
        Embed and index a sequence of CodeChunk objects.

        Returns:
            The number of chunks successfully indexed.
        """
        if not chunks:
            return 0

        texts = [c.content for c in chunks]
        vectors = self.embedding_provider.embed(texts)

        indexed_items = [
            IndexedChunk(chunk=c, vector=tuple(v))
            for c, v in zip(chunks, vectors)
        ]
        self.vector_index.upsert(indexed_items)
        return len(indexed_items)

    def index_repository(
        self,
        graph_or_ir: CodeGraph | dict[str, Any],
        source_files: Mapping[str, str],
    ) -> int:
        """
        Extract code chunks from graph/IR and index them.

        Returns:
            The number of chunks successfully indexed.
        """
        chunks = chunk_repository(graph_or_ir, source_files)
        return self.index_chunks(chunks)

    def search(self, query: str, top_k: int = 5) -> RetrievedContext:
        """
        Execute semantic or hybrid search for *query*.

        Parameters:
            query: The search text.
            top_k: Maximum number of results to return.

        Returns:
            An immutable RetrievedContext containing the ordered results.
        """
        if not isinstance(query, str):
            raise TypeError(f"Query must be a string, got {type(query).__name__}")

        total_candidates = self.vector_index.count()
        if top_k <= 0 or total_candidates == 0:
            return RetrievedContext(
                query=query,
                results=(),
                total_candidates=total_candidates,
            )

        query_vec = self.embedding_provider.embed_query(query)
        # Search all indexed items to allow exact hybrid rescoring if enabled
        candidates = self.vector_index.search(query_vec, top_k=total_candidates)

        if self.lexical_weight > 0.0:
            query_tokens = _tokenize(query)
            rescored: list[SearchResult] = []
            for c in candidates:
                lex_score = _compute_lexical_score(query_tokens, c.content, c.symbol_id)
                combined = (
                    self.semantic_weight * c.score
                    + self.lexical_weight * lex_score
                )
                rescored.append(
                    SearchResult(
                        chunk_id=c.chunk_id,
                        score=combined,
                        path=c.path,
                        start_line=c.start_line,
                        end_line=c.end_line,
                        content=c.content,
                        symbol_id=c.symbol_id,
                        metadata=c.metadata,
                    )
                )

            # Deterministic sorting: combined score descending, then chunk_id ascending
            rescored.sort(key=lambda r: (-r.score, r.chunk_id))
            final_results = rescored[:top_k]
        else:
            final_results = candidates[:top_k]

        return RetrievedContext(
            query=query,
            results=tuple(final_results),
            total_candidates=total_candidates,
        )


def create_retrieval_pipeline(
    dimension: int = 64,
    *,
    semantic_weight: float = 1.0,
    lexical_weight: float = 0.0,
) -> RetrievalPipeline:
    """Create a default in-memory retrieval pipeline using DeterministicEmbeddingProvider."""
    provider = DeterministicEmbeddingProvider(dimension=dimension)
    return RetrievalPipeline(
        embedding_provider=provider,
        semantic_weight=semantic_weight,
        lexical_weight=lexical_weight,
    )
