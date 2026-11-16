"""
retrieval/dense.py

Neural dense file retrieval with a pretrained sentence-embedding model (default BAAI/bge-small-en-v1.5).

Each file is split into windows of WINDOW non-empty lines, prefixed with its path; every window is
embedded, and a file's score for a question is its best window's cosine similarity. This is the
"neural dense" ranker of the research benchmark and the optional neural ranking that CodeAI's chat
fuses in (via the /dense endpoints in main.py).

sentence-transformers (and torch) are optional dependencies: ``available()`` reports whether they are
installed, and every caller must work without them. An ``encoder`` can be injected for tests.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Callable, Mapping, Sequence

import numpy as np

MODEL_NAME = "BAAI/bge-small-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "
WINDOW = 40
MAX_CHARS = 1500
MAX_WINDOWS_PER_FILE = 40

Encoder = Callable[[Sequence[str]], np.ndarray]  # texts -> L2-normalised float32 matrix

_model = None


def available() -> bool:
    try:
        import sentence_transformers  # noqa: F401
    except Exception:
        return False
    return True


def default_encoder(texts: Sequence[str]) -> np.ndarray:
    global _model
    if _model is None:
        from sentence_transformers import SentenceTransformer

        _model = SentenceTransformer(MODEL_NAME, device="cpu")
        _model.max_seq_length = 256
    return _model.encode(list(texts), batch_size=64, normalize_embeddings=True, show_progress_bar=False).astype(np.float32)


def windows(path: str, text: str) -> list[str]:
    lines = [ln for ln in text.splitlines() if ln.strip()]
    out = []
    for s in range(0, max(1, len(lines)), WINDOW):
        body = "\n".join(lines[s: s + WINDOW])
        out.append(f"{path}\n{body}"[:MAX_CHARS])
        if len(out) >= MAX_WINDOWS_PER_FILE:
            break
    return out


class DenseIndex:
    """Window embeddings for a set of files; optionally cached as .npy under *cache_dir*."""

    def __init__(
        self,
        docs: Mapping[str, str],
        *,
        cache_dir: Path | None = None,
        cache_prefix: str = "index",
        encoder: Encoder | None = None,
    ) -> None:
        self.encoder = encoder or default_encoder
        self.paths = sorted(docs)
        chunks: list[str] = []
        owner: list[int] = []
        for i, p in enumerate(self.paths):
            for w in windows(p, docs[p]):
                chunks.append(w)
                owner.append(i)
        vecs = None
        cache_file = None
        if cache_dir is not None:
            key = hashlib.sha1((MODEL_NAME + "\0" + "\0".join(chunks)).encode("utf-8", "ignore")).hexdigest()[:12]
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = cache_dir / f"{cache_prefix}-{key}.npy"
            if cache_file.exists():
                vecs = np.load(cache_file)
        if vecs is None:
            vecs = self.encoder(chunks) if chunks else np.zeros((0, 1), dtype=np.float32)
            if cache_file is not None:
                np.save(cache_file, vecs)
        self.vecs = vecs
        self.owner = np.array(owner, dtype=np.int64)

    def rank_vec(self, qv: np.ndarray) -> list[str]:
        if not len(self.paths) or not len(self.owner):
            return list(self.paths)
        sims = self.vecs @ qv
        best = np.full(len(self.paths), -np.inf, dtype=np.float32)
        np.maximum.at(best, self.owner, sims)
        order = sorted(range(len(self.paths)), key=lambda i: (-float(best[i]), self.paths[i]))
        return [self.paths[i] for i in order]

    def rank(self, query: str) -> list[str]:
        return self.rank_vec(embed_queries([query], self.encoder)[0])


def embed_queries(queries: Sequence[str], encoder: Encoder | None = None) -> np.ndarray:
    return (encoder or default_encoder)([QUERY_PREFIX + q for q in queries])
