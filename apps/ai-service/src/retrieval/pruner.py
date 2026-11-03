"""
retrieval/pruner.py

Query-conditioned Graph Path Pruning over the file-level dependency graph.

Problem: a question such as "trace repository creation from a GitHub URL" is
answered by a short chain of files (route → controller → service → …). Expanding
the graph outward from matching files (k-hop BFS) returns every neighbour,
including middleware, loggers and shared utilities, so the useful chain is
buried. The pruner scores each file-to-file edge against the query and an
architectural layer hierarchy, then selects a small connected set of edges.

All weights are fixed constants chosen before any benchmark was run; they are
not fitted to data. ``use_roles`` and ``use_continuity`` switch off the two
structural components so their contribution can be measured.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from .filegraph import (
    CALLS,
    DEPENDS_ON,
    IMPORTS,
    FileEdge,
    FileGraph,
    keywords,
    overlap,
)

# Architectural layers, outermost first. An edge from layer i to layer i+1 is
# "downstream flow" in a layered application.
LAYER = {"route": 0, "controller": 1, "service": 2, "repository": 3, "model": 3}

KIND_BONUS = {DEPENDS_ON: 2.0, CALLS: 1.5, IMPORTS: 0.5}
OVERLAP_WEIGHT = 1.5
HIERARCHY_BONUS = 3.0
BOTH_ENDS_BONUS = 5.0  # route -> controller where both ends match the query
PRIMARY_BONUS = 4.5    # controller -> service, controller reached from a matching route
SECONDARY_BONUS = 2.5  # controller -> service, controller itself matches the query
CONTINUITY_BONUS = 2.0
SCORE_THRESHOLD = 2.0
DEFAULT_K_MAX = 3


@dataclass(frozen=True)
class ScoredEdge:
    source: str
    target: str
    score: float

    @property
    def pair(self) -> tuple[str, str]:
        return (self.source, self.target)


def _layers(fg: FileGraph, path: str) -> set[int]:
    return {LAYER[r] for r in fg.roles.get(path, ()) if r in LAYER}


def _is_downstream(fg: FileGraph, e: FileEdge, src_layer: int | None = None) -> bool:
    """True if some role of the source sits exactly one layer above some role of the target."""
    for pattern in e.patterns:
        a, _, b = pattern.partition("->")
        if a in LAYER and b in LAYER and LAYER[b] == LAYER[a] + 1:
            if src_layer is None or LAYER[a] == src_layer:
                return True
    lu, lv = _layers(fg, e.source), _layers(fg, e.target)
    return any(
        (src_layer is None or a == src_layer) and b == a + 1 for a in lu for b in lv
    )


def score_edges(
    fg: FileGraph,
    query: str,
    *,
    use_roles: bool = True,
    relevance: Mapping[str, float] | None = None,
) -> list[ScoredEdge]:
    """
    Score every non-test dependency edge for *query*; best first, threshold applied.

    By default a file is relevant to the extent that its path shares words with the query.
    Pass *relevance* (file path -> score in [0, 1], e.g. from a retrieval ranking) to judge
    relevance by file content instead; files absent from the mapping count as 0.
    """
    kws = keywords(query)
    if not kws and not relevance:
        return []

    edges = [e for e in fg.edges if not fg.is_test(e.source) and not fg.is_test(e.target)]
    if relevance is not None:
        ov = {p: float(relevance.get(p, 0.0)) for e in edges for p in (e.source, e.target)}
    else:
        ov = {p: overlap(p, kws) for e in edges for p in (e.source, e.target)}

    # Controllers reached from a matching route (primary) or matching themselves (secondary).
    primary: set[str] = set()
    secondary: set[str] = set()
    if use_roles:
        for e in edges:
            if _is_downstream(fg, e, src_layer=LAYER["route"]) and fg.has_role(e.target, "controller"):
                if ov[e.source] > 0:
                    primary.add(e.target)
                elif ov[e.target] > 0:
                    secondary.add(e.target)

    out: list[ScoredEdge] = []
    for e in edges:
        base = OVERLAP_WEIGHT * ov[e.source] + OVERLAP_WEIGHT * ov[e.target]
        if base <= 0:
            continue  # nothing about this edge relates to the query
        s = base + max(KIND_BONUS.get(k, 0.0) for k in e.kinds)
        if use_roles and _is_downstream(fg, e):
            s += HIERARCHY_BONUS
            if _is_downstream(fg, e, src_layer=LAYER["route"]) and ov[e.source] > 0 and ov[e.target] > 0:
                s += BOTH_ENDS_BONUS
            elif _is_downstream(fg, e, src_layer=LAYER["controller"]):
                if e.source in primary:
                    s += PRIMARY_BONUS
                elif e.source in secondary:
                    s += SECONDARY_BONUS
        if s >= SCORE_THRESHOLD:
            out.append(ScoredEdge(e.source, e.target, round(s, 6)))
    out.sort(key=lambda x: (-x.score, x.source, x.target))
    return out


def prune(
    fg: FileGraph,
    query: str,
    k_max: int = DEFAULT_K_MAX,
    *,
    use_roles: bool = True,
    use_continuity: bool = True,
    relevance: Mapping[str, float] | None = None,
) -> list[ScoredEdge]:
    """Return at most *k_max* edges forming the most query-relevant, connected flow."""
    candidates = score_edges(fg, query, use_roles=use_roles, relevance=relevance)
    selected: list[ScoredEdge] = []
    remaining = list(candidates)
    while remaining and len(selected) < k_max:
        starts = {s.source for s in selected}
        ends = {s.target for s in selected}
        chosen_pairs = {s.pair for s in selected}

        def adjusted(c: ScoredEdge) -> float:
            if use_continuity and selected and (c.source in ends or c.target in starts):
                return c.score + CONTINUITY_BONUS
            return c.score

        remaining.sort(key=lambda c: (-adjusted(c), c.source, c.target))
        pick = remaining.pop(0)
        if (pick.target, pick.source) in chosen_pairs:
            continue  # would close a two-node cycle
        selected.append(pick)
    return selected


def bfs_edges(fg: FileGraph, query: str, hops: int = 2, n_seeds: int = 3) -> list[tuple[str, str]]:
    """
    Unpruned baseline: expand outgoing edges up to *hops* from the *n_seeds* files whose
    paths best match the query, and return every edge traversed.
    """
    kws = keywords(query)
    ranked = sorted(
        (p for p in fg.files if not fg.is_test(p) and overlap(p, kws) > 0),
        key=lambda p: (-overlap(p, kws), p),
    )[:n_seeds]
    seen_edges: dict[tuple[str, str], None] = {}
    frontier = list(ranked)
    visited = set(frontier)
    for _ in range(hops):
        nxt: list[str] = []
        for p in frontier:
            for e in fg.out_edges(p):
                seen_edges.setdefault((e.source, e.target), None)
                if e.target not in visited:
                    visited.add(e.target)
                    nxt.append(e.target)
        frontier = nxt
    return list(seen_edges)


def top_overlap_edges(fg: FileGraph, query: str, k_max: int = DEFAULT_K_MAX) -> list[tuple[str, str]]:
    """Baseline without structure: the *k_max* edges whose endpoints best match the query words."""
    kws = keywords(query)
    scored = []
    for e in fg.edges:
        if fg.is_test(e.source) or fg.is_test(e.target):
            continue
        s = overlap(e.source, kws) + overlap(e.target, kws)
        if s > 0:
            scored.append((-s, e.source, e.target))
    scored.sort()
    return [(u, v) for _, u, v in scored[:k_max]]


def top_relevance_edges(
    fg: FileGraph, relevance: Mapping[str, float], k_max: int = DEFAULT_K_MAX
) -> list[tuple[str, str]]:
    """Content-aware baseline without structure: edges whose endpoints have the highest summed relevance."""
    scored = []
    for e in fg.edges:
        if fg.is_test(e.source) or fg.is_test(e.target):
            continue
        s = relevance.get(e.source, 0.0) + relevance.get(e.target, 0.0)
        if s > 0:
            scored.append((-s, e.source, e.target))
    scored.sort()
    return [(u, v) for _, u, v in scored[:k_max]]
