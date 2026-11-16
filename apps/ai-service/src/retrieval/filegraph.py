"""
retrieval/filegraph.py

A file-level view of the Graph IR (schema 1.0) used by structural retrieval:
nodes are repository files, edges are file-to-file dependencies lifted from
IMPORTS, CALLS and architectural DEPENDS_ON edges.

The view is a pure function of the IR dict, so it works on IR produced by the
analyzer in-process or loaded from JSON.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping

_TOKEN = re.compile(r"[A-Za-z0-9]+")
_CAMEL = re.compile(r"([a-z0-9])([A-Z])")

STOPWORDS = frozenset(
    "a an the of to in on for and or is are be it this that with as by at from which what where how "
    "does do file files when then after before into via".split()
)

# Edge kinds, in the order in which they are reported.
IMPORTS = "imports"
CALLS = "calls"
DEPENDS_ON = "depends_on"


def tokenize(text: str) -> list[str]:
    """Lowercase identifier-aware tokens (camelCase and snake_case split)."""
    spaced = _CAMEL.sub(r"\1 \2", text)
    return [t for t in (m.lower() for m in _TOKEN.findall(spaced)) if len(t) > 1]


def stem(token: str) -> str:
    """Very light suffix stripping so 'routes' / 'routing' / 'routed' meet 'route'."""
    if len(token) > 5 and token.endswith("ies"):
        token = token[:-3] + "y"
    else:
        for suffix in ("ing", "ed", "es", "s"):
            if len(token) > len(suffix) + 3 and token.endswith(suffix):
                token = token[: -len(suffix)]
                break
    if len(token) > 4 and token.endswith("e"):
        token = token[:-1]  # route / routes / routing / routed all meet at "rout"
    return token


def keywords(query: str) -> set[str]:
    """Stemmed, stopword-free query keywords."""
    return {stem(t) for t in tokenize(query) if t not in STOPWORDS}


@dataclass(frozen=True)
class FileEdge:
    source: str
    target: str
    kinds: frozenset[str]
    patterns: frozenset[str]  # "source_role->target_role" from DEPENDS_ON


@dataclass(frozen=True)
class FileGraph:
    files: tuple[str, ...]
    roles: Mapping[str, frozenset[str]]
    symbols: Mapping[str, tuple[str, ...]]  # file -> symbol names
    edges: tuple[FileEdge, ...]
    _out: Mapping[str, tuple[FileEdge, ...]] = field(repr=False, default_factory=dict)
    _in: Mapping[str, tuple[FileEdge, ...]] = field(repr=False, default_factory=dict)

    def out_edges(self, path: str) -> tuple[FileEdge, ...]:
        return self._out.get(path, ())

    def in_edges(self, path: str) -> tuple[FileEdge, ...]:
        return self._in.get(path, ())

    def has_role(self, path: str, role: str) -> bool:
        return role in self.roles.get(path, frozenset())

    def is_test(self, path: str) -> bool:
        return "test" in self.roles.get(path, frozenset()) or bool(
            re.search(r"(^|/)(tests?|__tests__|spec)(/|$)|\.(test|spec)\.|(^|/)test_[^/]*\.py$", path)
        )


def _node_path(node: Mapping[str, Any]) -> str | None:
    meta = node.get("metadata") or {}
    return meta.get("path")


def build_file_graph(ir: Mapping[str, Any]) -> FileGraph:
    """Lift the IR to file-level dependency edges (self loops dropped)."""
    nodes = {n["id"]: n for n in ir.get("nodes", [])}
    files = tuple(sorted(_node_path(n) or n["label"] for n in nodes.values() if n["type"] == "file"))
    file_set = set(files)

    roles: dict[str, set[str]] = {}
    symbols: dict[str, list[str]] = {}
    for n in nodes.values():
        p = _node_path(n)
        if not p or p not in file_set:
            continue
        if n["type"] == "file":
            continue
        meta = n.get("metadata") or {}
        if n["id"].startswith("architecture:"):
            role = meta.get("role") or n["type"]
            roles.setdefault(p, set()).add(str(role).lower())
        elif n["id"].startswith("symbol:") and meta.get("name"):
            symbols.setdefault(p, []).append(meta["name"])

    def path_of(node_id: str) -> str | None:
        n = nodes.get(node_id)
        if n is None:
            return None
        p = _node_path(n)
        return p if p in file_set else None

    acc: dict[tuple[str, str], tuple[set[str], set[str]]] = {}

    def add(u: str | None, v: str | None, kind: str, pattern: str | None = None) -> None:
        if not u or not v or u == v:
            return
        kinds, patterns = acc.setdefault((u, v), (set(), set()))
        kinds.add(kind)
        if pattern:
            patterns.add(pattern)

    for e in ir.get("edges", []):
        et = e["type"]
        if et in (IMPORTS, CALLS):
            add(path_of(e["source"]), path_of(e["target"]), et)
        elif et == DEPENDS_ON:
            meta = e.get("metadata") or {}
            pat = f'{meta.get("source_role", "")}->{meta.get("target_role", "")}'
            add(path_of(e["source"]), path_of(e["target"]), DEPENDS_ON, pat)

    edges = tuple(
        FileEdge(u, v, frozenset(k), frozenset(p)) for (u, v), (k, p) in sorted(acc.items())
    )
    out: dict[str, list[FileEdge]] = {}
    inc: dict[str, list[FileEdge]] = {}
    for fe in edges:
        out.setdefault(fe.source, []).append(fe)
        inc.setdefault(fe.target, []).append(fe)
    return FileGraph(
        files=files,
        roles={p: frozenset(r) for p, r in roles.items()},
        symbols={p: tuple(s) for p, s in symbols.items()},
        edges=edges,
        _out={p: tuple(v) for p, v in out.items()},
        _in={p: tuple(v) for p, v in inc.items()},
    )


def path_tokens(path: str) -> set[str]:
    return {stem(t) for t in tokenize(path)}


def overlap(path: str, kws: Iterable[str]) -> float:
    """Fraction of query keywords that appear among the stemmed tokens of *path*."""
    kws = set(kws)
    if not kws:
        return 0.0
    return len(path_tokens(path) & kws) / len(kws)
