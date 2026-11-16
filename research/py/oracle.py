"""
Independent import oracles (they never touch the Tree-sitter graph).

- JavaScript: regular expressions over comment-stripped source.
- Python: the standard-library ``ast`` module, with module names matched to files by
  dotted-path suffix. This is deliberately different from the analyzer's resolver, which
  searches ancestor directories.
"""

from __future__ import annotations

import ast
import posixpath
import re

from common import file_paths, load_ir, read_text, strip_js_comments

JS_EXT = re.compile(r"\.(jsx?|mjs|cjs)$")
JS_SKIP = re.compile(r"(^|/)(node_modules|dist|build|vendor|coverage|\.git)(/|$)|\.min\.")
IMPORT_RE = [
    re.compile(r"require\(\s*['\"](\.{1,2}/[^'\"]*)['\"]\s*\)"),
    re.compile(r"\bfrom\s+['\"](\.{1,2}/[^'\"]*)['\"]"),
    re.compile(r"\bimport\(\s*['\"](\.{1,2}/[^'\"]*)['\"]\s*\)"),
    re.compile(r"(?m)^\s*import\s+['\"](\.{1,2}/[^'\"]*)['\"]"),
]


def _js_resolve(src: str, spec: str, files: set[str]) -> str | None:
    base = posixpath.normpath(posixpath.join(posixpath.dirname(src), spec))
    for t in (base, base + ".js", base + ".jsx", base + ".mjs", base + ".cjs", base + ".json", base + "/index.js", base + "/index.jsx"):
        if t in files:
            return t
    return None


def js_import_pairs(repo: str) -> set[tuple[str, str]]:
    files = set(file_paths(load_ir(repo)))
    pairs: set[tuple[str, str]] = set()
    for rel in files:
        if not JS_EXT.search(rel) or JS_SKIP.search(rel):
            continue
        text = strip_js_comments(read_text(repo, rel))
        for rx in IMPORT_RE:
            for m in rx.finditer(text):
                t = _js_resolve(rel, m.group(1), files)
                if t and t != rel:
                    pairs.add((rel, t))
    return pairs


def _py_module_names(path: str) -> list[str]:
    """Dotted names under which *path* could be imported: every suffix of its package path."""
    stem = path[:-3] if path.endswith(".py") else path
    parts = stem.split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return [".".join(parts[i:]) for i in range(len(parts))] if parts else []


def _shared_dirs(a: str, b: str) -> int:
    n = 0
    for x, y in zip(a.split("/")[:-1], b.split("/")[:-1]):
        if x != y:
            break
        n += 1
    return n


def py_import_pairs(repo: str) -> set[tuple[str, str]]:
    files = [p for p in file_paths(load_ir(repo)) if p.endswith(".py")]
    fileset = set(files)
    by_name: dict[str, set[str]] = {}
    for p in files:
        for name in _py_module_names(p):
            by_name.setdefault(name, set()).add(p)

    def lookup_abs(dotted: str, src: str) -> str | None:
        cands = by_name.get(dotted, set()) - {src}
        if len(cands) == 1:
            return next(iter(cands))
        if len(cands) > 1:  # prefer the candidate sharing the longest directory prefix with the importer
            return max(sorted(cands), key=lambda c: _shared_dirs(src, c))
        return None

    def lookup_rel(src: str, level: int, module: str | None) -> list[str]:
        base = posixpath.dirname(src)
        for _ in range(level - 1):
            base = posixpath.dirname(base)
        parts = module.split(".") if module else []
        joined = posixpath.normpath(posixpath.join(base, *parts)) if parts else base
        joined = "" if joined == "." else joined
        out = []
        for cand in ((joined + ".py") if joined else None, posixpath.join(joined, "__init__.py") if joined else "__init__.py"):
            if cand and cand in fileset:
                out.append(cand)
        return out

    pairs: set[tuple[str, str]] = set()
    for src in files:
        text = read_text(repo, src)
        try:
            tree = ast.parse(text)
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    t = lookup_abs(alias.name, src)
                    if t and t != src:
                        pairs.add((src, t))
            elif isinstance(node, ast.ImportFrom):
                level = node.level or 0
                mod = node.module
                targets: list[str] = []
                if level:
                    targets += lookup_rel(src, level, mod)
                    for alias in node.names:  # `from . import sub`
                        sub = (mod + "." if mod else "") + alias.name
                        targets += lookup_rel(src, level, sub)
                else:
                    t = lookup_abs(mod, src) if mod else None
                    if t:
                        targets.append(t)
                    for alias in node.names:
                        if mod:
                            s = lookup_abs(mod + "." + alias.name, src)
                            if s:
                                targets.append(s)
                for t in targets:
                    if t != src:
                        pairs.add((src, t))
    return pairs


def import_pairs(repo: str, python: bool) -> set[tuple[str, str]]:
    return py_import_pairs(repo) if python else js_import_pairs(repo)


def importers(pairs: set[tuple[str, str]]) -> dict[str, set[str]]:
    out: dict[str, set[str]] = {}
    for s, t in pairs:
        out.setdefault(t, set()).add(s)
    return out


def transitive_importers(imp: dict[str, set[str]], target: str, max_depth: int = 4) -> dict[str, int]:
    dist = {target: 0}
    frontier = [target]
    for d in range(1, max_depth + 1):
        nxt = []
        for cur in frontier:
            for s in imp.get(cur, ()):
                if s not in dist:
                    dist[s] = d
                    nxt.append(s)
        frontier = nxt
    dist.pop(target)
    return dist


def py_call_triples(repo: str) -> set[tuple[str, str, str]]:
    """
    Cross-file call oracle for Python, using only ``ast``: (caller file, callee file, name) for every call
    ``name(...)`` where ``name`` was brought in by ``from M import name`` (absolute or relative), M resolves
    to a repository file, and that file defines ``name`` as a top-level function or class.
    """
    files = [p for p in file_paths(load_ir(repo)) if p.endswith(".py")]
    fileset = set(files)
    by_name: dict[str, set[str]] = {}
    for p in files:
        for name in _py_module_names(p):
            by_name.setdefault(name, set()).add(p)
    trees: dict[str, ast.Module] = {}
    for p in files:
        try:
            trees[p] = ast.parse(read_text(repo, p))
        except (SyntaxError, ValueError):
            pass
    defs = {p: {n.name for n in t.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
            for p, t in trees.items()}

    def lookup_abs(dotted: str, src: str) -> str | None:
        cands = by_name.get(dotted, set()) - {src}
        if not cands:
            return None
        return max(sorted(cands), key=lambda c: _shared_dirs(src, c))

    def lookup_rel(src: str, level: int, module: str | None) -> str | None:
        base = posixpath.dirname(src)
        for _ in range(level - 1):
            base = posixpath.dirname(base)
        joined = posixpath.normpath(posixpath.join(base, *module.split("."))) if module else base
        joined = "" if joined == "." else joined
        for cand in ((joined + ".py") if joined else None, posixpath.join(joined, "__init__.py") if joined else "__init__.py"):
            if cand and cand in fileset:
                return cand
        return None

    out: set[tuple[str, str, str]] = set()
    for src, tree in trees.items():
        alias: dict[str, tuple[str, str]] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                level = node.level or 0
                t = lookup_rel(src, level, node.module) if level else (lookup_abs(node.module, src) if node.module else None)
                if not t or t == src:
                    continue
                for a in node.names:
                    if a.name != "*" and a.name in defs.get(t, ()):
                        alias[a.asname or a.name] = (t, a.name)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in alias:
                t, name = alias[node.func.id]
                out.add((src, t, name))
    return out
