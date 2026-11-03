"""
retrieval/lsa.py

Dense "semantic" file vectors by Latent Semantic Analysis: TF-IDF over identifier-aware
tokens followed by a truncated SVD. It captures co-occurrence (words that appear in the same
files end up near each other) without a neural model, so it runs offline and deterministically.
It is not a pretrained code-embedding model and should not be described as one.
"""

from __future__ import annotations

import math
from collections import Counter
from typing import Mapping

import numpy as np

from .filegraph import tokenize

MAX_VOCAB = 20000


def _l2(a: np.ndarray) -> np.ndarray:
    norm = np.linalg.norm(a, axis=-1, keepdims=True)
    norm[norm == 0] = 1.0
    return a / norm


class LsaIndex:
    def __init__(self, docs: Mapping[str, str], dim: int = 64) -> None:
        self.paths = sorted(docs)
        toks = [tokenize(docs[p]) + tokenize(p) for p in self.paths]
        df: Counter[str] = Counter()
        for t in toks:
            df.update(set(t))
        # Keep the most widespread terms; drop hapax terms, which carry no co-occurrence signal.
        min_df = 2 if len(self.paths) >= 20 else 1
        vocab = [w for w, c in df.most_common(MAX_VOCAB) if c >= min_df] or list(df)
        self.index = {w: i for i, w in enumerate(vocab)}
        n = len(self.paths)
        self.idf = np.array([math.log((1 + n) / (1 + df[w])) + 1.0 for w in vocab], dtype=np.float32)

        x = np.zeros((n, len(vocab)), dtype=np.float32)
        for r, t in enumerate(toks):
            for w, c in Counter(t).items():
                j = self.index.get(w)
                if j is not None:
                    x[r, j] = (1.0 + math.log(c)) * self.idf[j]
        x = _l2(x)
        k = max(1, min(dim, n - 1, len(vocab)))
        _, _, vt = np.linalg.svd(x, full_matrices=False)
        self.components = vt[:k].T.astype(np.float32)  # vocab x k
        self.doc_vecs = _l2(x @ self.components)

    def _query_vec(self, text: str) -> np.ndarray | None:
        q = np.zeros(len(self.index), dtype=np.float32)
        for w, c in Counter(tokenize(text)).items():
            j = self.index.get(w)
            if j is not None:
                q[j] = (1.0 + math.log(c)) * self.idf[j]
        if not q.any():
            return None
        return _l2(q[None, :] @ self.components)[0]

    def rank(self, query: str) -> list[str]:
        """Files by cosine similarity to *query*; files with no similarity are omitted."""
        qv = self._query_vec(query)
        if qv is None:
            return []
        sims = self.doc_vecs @ qv
        order = sorted(range(len(self.paths)), key=lambda i: (-float(sims[i]), self.paths[i]))
        return [self.paths[i] for i in order if sims[i] > 1e-6]
