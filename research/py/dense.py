"""
Neural dense ranker for the research harness: a thin wrapper around the product implementation in
apps/ai-service/src/retrieval/dense.py, so the benchmark measures exactly the code CodeAI runs.
Embeddings are cached per repository and text condition in research/out/emb_cache (git-ignored).
Needs the research/.venv-emb environment (sentence-transformers + torch).
"""

from __future__ import annotations

from typing import Mapping

import numpy as np

from common import RESEARCH
from src.retrieval import dense as _dense

MODEL_NAME = _dense.MODEL_NAME
CACHE = RESEARCH / "out" / "emb_cache"


class DenseIndex(_dense.DenseIndex):
    def __init__(self, repo: str, tag: str, docs: Mapping[str, str]) -> None:
        super().__init__(docs, cache_dir=CACHE, cache_prefix=f"{repo}-{tag}")


def embed_queries(queries: list[str]) -> np.ndarray:
    return _dense.embed_queries(queries)
