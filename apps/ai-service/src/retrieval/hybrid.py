"""
retrieval/hybrid.py

File-level retrieval used by the research benchmark: lexical (BM25), dense (LSA), structural
(graph) and their Reciprocal Rank Fusion.

The structural ranker is query-aware in one simple way: if the query names a file and asks who
imports / depends on it / is affected by it, files are ranked by reverse-dependency distance from
that file; otherwise files are ranked by how well their path and symbol names match the query,
with a decaying bonus for neighbours of strong matches.
"""

from __future__ import annotations

import math
import re
from collections import Counter, deque
from typing import Mapping, Sequence

from .filegraph import FileGraph, build_file_graph, keywords, path_tokens, stem, tokenize
from .lsa import LsaIndex

RRF_K0 = 60
RRF_WEIGHTS = {"vector": 0.55, "graph": 0.45}
REVERSE_INTENT = re.compile(
    r"\b(import|imports|imported|depend|depends|dependent|dependency|dependencies|affect|affected|"
    r"impact|impacted|break|breaks|use|uses|used|require|requires)\b",
    re.IGNORECASE,
)
MAX_REVERSE_DEPTH = 4

_STOP = frozenset(
    "a an the of to in on for and or is are be it this that with as by at from which what where how does do file files".split()
)


class Bm25Index:
    def __init__(self, docs: Mapping[str, str], k1: float = 1.2, b: float = 0.75) -> None:
        self.k1, self.b = k1, b
        self.paths = sorted(docs)
        self.tf: dict[str, Counter[str]] = {}
        self.len: dict[str, int] = {}
        df: Counter[str] = Counter()
        for p in self.paths:
            toks = tokenize(docs[p]) + 2 * tokenize(p)
            self.tf[p] = Counter(toks)
            self.len[p] = len(toks)
            df.update(self.tf[p].keys())
        self.df = df
        self.n = len(self.paths)
        self.avg = sum(self.len.values()) / max(1, self.n)

    def rank(self, query: str) -> list[str]:
        q = [t for t in tokenize(query) if t not in _STOP]
        scored = []
        for p in self.paths:
            s = 0.0
            for t in q:
                f = self.tf[p].get(t)
                if not f:
                    continue
                idf = math.log(1 + (self.n - self.df[t] + 0.5) / (self.df[t] + 0.5))
                s += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * self.len[p] / self.avg))
            if s > 0:
                scored.append((-s, p))
        scored.sort()
        return [p for _, p in scored]


def rrf(rankings: Mapping[str, Sequence[str]], weights: Mapping[str, float] | None = None, k0: int = RRF_K0) -> list[str]:
    """Weighted Reciprocal Rank Fusion; ties broken by path."""
    score: dict[str, float] = {}
    for name, ranked in rankings.items():
        w = (weights or {}).get(name, 1.0)
        for i, p in enumerate(ranked):
            score[p] = score.get(p, 0.0) + w / (k0 + i + 1)
    return [p for p, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))]


def _find_named_file(fg: FileGraph, query: str) -> str | None:
    """A file whose full path (preferred) or unique basename appears verbatim in the query."""
    q = query.lower()
    hits = [p for p in fg.files if p.lower() in q]
    if hits:
        return max(hits, key=len)
    by_base: dict[str, list[str]] = {}
    for p in fg.files:
        by_base.setdefault(p.rsplit("/", 1)[-1].lower(), []).append(p)
    named = [ps[0] for b, ps in by_base.items() if len(ps) == 1 and "." in b and b in q]
    return max(named, key=len) if named else None


def graph_rank(fg: FileGraph, query: str) -> list[str]:
    named = _find_named_file(fg, query)
    if named and REVERSE_INTENT.search(query):
        dist = {named: 0}
        dq = deque([named])
        while dq:
            cur = dq.popleft()
            if dist[cur] >= MAX_REVERSE_DEPTH:
                continue
            for e in fg.in_edges(cur):
                if e.source not in dist:
                    dist[e.source] = dist[cur] + 1
                    dq.append(e.source)
        return sorted((p for p in dist if p != named), key=lambda p: (dist[p], p))

    kws = keywords(query)
    if not kws:
        return []
    seed: dict[str, float] = {}
    for p in fg.files:
        toks = set(path_tokens(p))
        for name in fg.symbols.get(p, ()):
            toks |= {stem(t) for t in tokenize(name)}
        hit = len(toks & kws) / len(kws)
        if hit > 0:
            seed[p] = hit
    score = dict(seed)
    for p, s in seed.items():
        for e in fg.out_edges(p):
            score[e.target] = max(score.get(e.target, 0.0), 0.5 * s)
        for e in fg.in_edges(p):
            score[e.source] = max(score.get(e.source, 0.0), 0.5 * s)
    return [p for p, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))]


def relevance_from_ranking(ranked: Sequence[str], top_n: int = 10) -> dict[str, float]:
    """
    Turn a ranked file list into relevance scores in (0, 1] for the pruner: reciprocal rank,
    zero beyond *top_n*. Rank 1 scores 1.0, rank 2 scores 0.5, and so on.
    """
    return {p: 1.0 / (i + 1) for i, p in enumerate(ranked[:top_n])}


class RepoRetriever:
    """Builds every ranker once for a repository (IR plus file texts)."""

    def __init__(self, ir: Mapping, texts: Mapping[str, str], lsa_dim: int = 64) -> None:
        self.fg = build_file_graph(ir)
        docs = {p: texts.get(p, "") for p in self.fg.files}
        self.bm25 = Bm25Index(docs)
        self.lsa = LsaIndex(docs, dim=lsa_dim)

    def rankings(self, query: str) -> dict[str, list[str]]:
        vec = self.lsa.rank(query)
        graph = graph_rank(self.fg, query)
        lex = self.bm25.rank(query)
        return {
            "bm25": lex,
            "vector": vec,
            "graph": graph,
            "hybrid": rrf({"vector": vec, "graph": graph}, RRF_WEIGHTS),
            "hybrid+bm25": rrf({"bm25": lex, "vector": vec, "graph": graph}),
        }
