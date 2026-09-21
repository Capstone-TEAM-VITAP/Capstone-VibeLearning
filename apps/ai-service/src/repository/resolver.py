"""
repository/resolver.py

Cross-file relationship resolution for JavaScript repositories.
Milestone 5 — resolves raw M4 import/export facts into actual
file + symbol references within the repository.

Cross-module scope
------------------
M5 resolves IMPORTS relationships extracted by M4 into concrete
repository facts:

  BEFORE:
    app.js → IMPORTS("login")  module_path="./auth.js"

  AFTER:
    ResolvedRelationship(
        status=RESOLVED,
        target_path="src/auth.js",
        target_symbol_id=SymbolId("src/auth.js", "login", line=3, col=0),
    )

Public API
----------
resolve_imports(files, symbols, relationships) -> list[ResolvedRelationship]
    Build internal indexes and resolve all IMPORTS relationships.

RepositoryIndex
    Pre-computed lookup tables. Can be reused across multiple resolve calls.

Design principles
-----------------
1.  Pure deterministic computation — no filesystem scanning, no LLM.
2.  All data comes from M1 (FileInfo), M3 (Symbol), M4 (Relationship).
3.  External npm packages are marked EXTERNAL (not failed).
4.  Missing local modules are UNRESOLVED (not crashed).
5.  Circular re-export chains are detected and terminated cleanly.
6.  Symbol identity includes (path, name, line, column) so that duplicate
    names in different files are never confused.
7.  Repository boundary protection: paths normalised to escape the root
    are rejected as UNRESOLVED.

Deferred to M6+
---------------
- npm / node_modules resolution
- TypeScript tsconfig path aliases
- Webpack / Vite aliases
- Final CodeGraph construction
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from enum import Enum
from typing import Iterator

from .models import FileInfo
from .parser import Position
from .relationships import Relationship, RelationshipKind
from .symbols import Symbol, SymbolKind

# ---------------------------------------------------------------------------
# Symbol identity — stable cross-file reference
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SymbolId:
    """
    A stable, globally-unique identifier for a code symbol.

    Using the symbol *name* alone is insufficient: two files can both define
    ``login()``.  ``SymbolId`` includes the file path and source position so
    that two symbols with the same name in different files (or at different
    locations in the same file) are never confused.

    Attributes
    ----------
    path:
        Repository-relative POSIX path of the file that declares this symbol.
        Example: ``"src/auth/login.js"``
    name:
        The identifier text of the symbol.  Example: ``"login"``
    line:
        1-indexed source line of the symbol's declaration start.
    column:
        0-indexed source column of the symbol's declaration start.
    """

    path: str
    name: str
    line: int
    column: int


# ---------------------------------------------------------------------------
# Resolution status
# ---------------------------------------------------------------------------


class ResolutionStatus(str, Enum):
    """
    Outcome of attempting to resolve a single IMPORTS relationship.

    RESOLVED
        The import was resolved to a specific symbol in a specific file.
        Both ``target_path`` and ``target_symbol_id`` are populated.

    RESOLVED_FILE
        The import's target file was found, but no specific symbol could be
        matched (side-effect imports, namespace imports, or exports whose
        symbol declaration was not found).  ``target_path`` is populated;
        ``target_symbol_id`` is ``None``.

    EXTERNAL
        The module specifier is an external (npm) package or Node.js built-in
        that is intentionally outside the repository.  Neither ``target_path``
        nor ``target_symbol_id`` is populated.

    UNRESOLVED
        The module specifier looks like a relative import but no matching file
        was found in the repository index, OR the path would escape the repo
        root.  Neither field is populated.
    """

    RESOLVED = "resolved"
    RESOLVED_FILE = "resolved_file"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


# ---------------------------------------------------------------------------
# Resolved relationship model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ResolvedRelationship:
    """
    The result of resolving a single IMPORTS ``Relationship``.

    Attributes
    ----------
    source_relationship:
        The original M4 ``Relationship`` that was resolved.
    status:
        Outcome of the resolution attempt.
    target_path:
        Repository-relative POSIX path of the resolved target file.
        Populated for RESOLVED and RESOLVED_FILE; ``None`` otherwise.
    target_symbol_id:
        Stable identity of the specific symbol being imported.
        Populated for RESOLVED only; ``None`` for all other statuses.
    notes:
        Human-readable explanation for non-RESOLVED outcomes, or
        additional context (e.g. which alias was used).  ``None`` when
        no extra context is needed.
    """

    source_relationship: Relationship
    status: ResolutionStatus
    target_path: str | None
    target_symbol_id: SymbolId | None
    notes: str | None


# ---------------------------------------------------------------------------
# Repository index — pre-computed fast lookup tables
# ---------------------------------------------------------------------------

# Maximum re-export chain depth before declaring a cycle / giving up.
_MAX_REEXPORT_DEPTH: int = 10

# File extensions tried when the import path omits the extension.
_CANDIDATE_EXTENSIONS: tuple[str, ...] = (".js", ".jsx", ".ts", ".tsx", ".mjs")
_INDEX_FILES: tuple[str, ...] = (
    "/index.js",
    "/index.jsx",
    "/index.ts",
    "/index.tsx",
)


class RepositoryIndex:
    """
    Pre-computed lookup tables for the repository.

    Build once, query many times.  All mutations happen in ``__init__``;
    after construction the index is effectively read-only.

    Parameters
    ----------
    files:
        All ``FileInfo`` objects from the M1 scanner.
    symbols:
        All ``Symbol`` objects extracted by the M3 symbol extractor.
    relationships:
        All ``Relationship`` objects extracted by the M4 relationship
        extractor.
    """

    def __init__(
        self,
        files: list[FileInfo],
        symbols: list[Symbol],
        relationships: list[Relationship],
    ) -> None:
        # --- File index ---
        # path → FileInfo
        self._files: dict[str, FileInfo] = {f.path: f for f in files}

        # --- Symbol index ---
        # path → [Symbol, ...]
        self._symbols_by_file: dict[str, list[Symbol]] = {}
        # (path, name) → [Symbol, ...]  (list: same name can appear in multiple scopes)
        self._symbols_by_file_name: dict[tuple[str, str], list[Symbol]] = {}

        for sym in symbols:
            self._symbols_by_file.setdefault(sym.path, []).append(sym)
            key = (sym.path, sym.name)
            self._symbols_by_file_name.setdefault(key, []).append(sym)

        # --- Relationship indexes ---
        # path → [Relationship, ...]  (EXPORTS from that file)
        self._exports_by_file: dict[str, list[Relationship]] = {}
        # path → [Relationship, ...]  (IMPORTS from that file)
        self._imports_by_file: dict[str, list[Relationship]] = {}

        for rel in relationships:
            if rel.kind == RelationshipKind.EXPORTS:
                self._exports_by_file.setdefault(rel.source_path, []).append(rel)
            elif rel.kind == RelationshipKind.IMPORTS:
                self._imports_by_file.setdefault(rel.source_path, []).append(rel)

    # ------------------------------------------------------------------
    # File queries
    # ------------------------------------------------------------------

    def has_file(self, path: str) -> bool:
        """Return True if *path* is known in the repository."""
        return path in self._files

    @property
    def files_by_path(self) -> dict[str, FileInfo]:
        """Mapping of all repository file paths → ``FileInfo``."""
        return self._files

    # ------------------------------------------------------------------
    # Symbol queries
    # ------------------------------------------------------------------

    def get_symbols_for_file(self, path: str) -> list[Symbol]:
        """All symbols declared in *path* (from M3)."""
        return self._symbols_by_file.get(path, [])

    def get_symbols_by_name(self, path: str, name: str) -> list[Symbol]:
        """
        All symbols named *name* in *path*.

        Returns a list because the same name may appear in multiple
        scopes (e.g. ``function login`` at top level and a nested
        ``function login`` inside a class method).
        """
        return self._symbols_by_file_name.get((path, name), [])

    # ------------------------------------------------------------------
    # Relationship queries
    # ------------------------------------------------------------------

    def get_exports(self, path: str) -> list[Relationship]:
        """All EXPORTS relationships declared in *path* (from M4)."""
        return self._exports_by_file.get(path, [])

    def get_reexport_sources(self, path: str) -> list[str]:
        """
        Return the raw module specifiers for ``export * from "..."``
        statements in *path*.

        In the M4 model these appear as EXPORTS relationships with
        ``target_name="*"`` and a non-null ``module_path``.
        """
        return [
            rel.module_path
            for rel in self._exports_by_file.get(path, [])
            if rel.target_name == "*" and rel.module_path is not None
        ]

    def get_named_reexport_sources(self, path: str, name: str) -> list[str]:
        """
        Return raw module specifiers for ``export { <name> } from "..."``
        in *path*.

        NOTE: In the current M4 representation, named re-exports produce
        an EXPORTS(name, module_path=None) AND an EXPORTS("*", module_path=X)
        as separate relationships.  This helper identifies potential named
        re-export sources by returning all ``export *`` sources, since we
        cannot distinguish which names came from which source without further
        analysis.
        """
        return self.get_reexport_sources(path)

    def get_imports(self, path: str) -> list[Relationship]:
        """All IMPORTS relationships declared in *path* (from M4)."""
        return self._imports_by_file.get(path, [])


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


def _is_external(module_path: str) -> bool:
    """
    Return True if *module_path* refers to an external (npm / built-in) module.

    External modules do not start with ``.`` or ``..``.
    """
    return not (
        module_path == "."
        or module_path.startswith("./")
        or module_path.startswith("../")
    )


def _is_safe_path(normalized: str) -> bool:
    """
    Return True if a normalised POSIX path stays within the repository root.

    Any path that starts with ``..`` would escape the root and is rejected.
    """
    return not (normalized.startswith("..") or normalized == "..")


def _resolve_module_path(
    source_file: str,
    module_path: str,
    files_by_path: dict[str, FileInfo],
) -> str | None:
    """
    Resolve a relative *module_path* from *source_file* to an actual
    repository file path, or ``None`` if not found.

    Algorithm
    ---------
    1. Compute base directory from *source_file*.
    2. Normalise: ``posixpath.normpath(base_dir / module_path)``.
    3. Reject paths that would escape the repository root (start with ``..``).
    4. Try exact match in the file index.
    5. Try appending each of ``.js``, ``.jsx``, ``.ts``, ``.tsx``, ``.mjs``.
    6. Try ``/index.js``, ``/index.jsx``, ``/index.ts``, ``/index.tsx``.
    7. Return ``None`` if nothing matched.

    This function is deterministic and does not touch the filesystem.
    """
    src_dir = posixpath.dirname(source_file)
    # posixpath.join("", "./auth.js") == "./auth.js", normpath handles it
    raw = posixpath.join(src_dir, module_path) if src_dir else module_path
    candidate = posixpath.normpath(raw)

    # Security: reject any path that escapes the repository root
    if not _is_safe_path(candidate):
        return None

    # 1. Exact match
    if candidate in files_by_path:
        return candidate

    # 2. Try common extensions
    for ext in _CANDIDATE_EXTENSIONS:
        with_ext = candidate + ext
        if with_ext in files_by_path:
            return with_ext

    # 3. Try directory index files
    for idx in _INDEX_FILES:
        with_idx = candidate + idx
        if with_idx in files_by_path:
            return with_idx

    return None


# ---------------------------------------------------------------------------
# Symbol resolution helpers
# ---------------------------------------------------------------------------


def _best_symbol(candidates: list[Symbol]) -> Symbol:
    """
    From a list of candidate symbols with the same name, return the one
    most likely to be a top-level (exported) symbol.

    Preference order:
    1. ``parent is None``  (top-level declaration)
    2. First in source order
    """
    top_level = [s for s in candidates if s.parent is None]
    pool = top_level or candidates
    return min(pool, key=lambda s: (s.start.line, s.start.column))


def _find_local_symbol(
    name: str,
    file_path: str,
    index: RepositoryIndex,
) -> Symbol | None:
    """
    Return the best local ``Symbol`` named *name* in *file_path*, or
    ``None`` if no matching symbol exists.
    """
    candidates = index.get_symbols_by_name(file_path, name)
    return _best_symbol(candidates) if candidates else None


def _symbol_to_id(sym: Symbol) -> SymbolId:
    """Convert a ``Symbol`` to its stable ``SymbolId``."""
    return SymbolId(
        path=sym.path,
        name=sym.name,
        line=sym.start.line,
        column=sym.start.column,
    )


def _resolve_named_export(
    name: str,
    file_path: str,
    index: RepositoryIndex,
    visited: frozenset[str],
    depth: int = 0,
) -> Symbol | None:
    """
    Resolve the exported symbol named *name* from *file_path*.

    Follows ``export * from "..."`` re-export chains up to
    ``_MAX_REEXPORT_DEPTH`` levels.  Uses *visited* (a frozenset of
    file paths already traversed) to detect and break cycles.

    Parameters
    ----------
    name:
        The original exported name (NOT the local alias).
    file_path:
        Repository-relative POSIX path of the file to search.
    index:
        Pre-computed repository index.
    visited:
        Set of file paths already visited in this resolution chain
        (cycle protection).
    depth:
        Current recursion depth.
    """
    if depth > _MAX_REEXPORT_DEPTH or file_path in visited:
        return None

    visited = visited | {file_path}

    # --- 1. Direct symbol lookup in this file ---
    sym = _find_local_symbol(name, file_path, index)
    if sym is not None:
        return sym

    # --- 2. Follow re-export sources ---
    # In the M4 model, "export { x } from './y'" and "export * from './y'"
    # both create an EXPORTS("*", module_path="./y") marker. We try each
    # re-export source recursively to find the named symbol.
    for src_module in index.get_reexport_sources(file_path):
        resolved_src = _resolve_module_path(
            file_path, src_module, index.files_by_path
        )
        if resolved_src is None:
            continue
        sym = _resolve_named_export(name, resolved_src, index, visited, depth + 1)
        if sym is not None:
            return sym

    return None


def _resolve_default_export(
    file_path: str,
    index: RepositoryIndex,
) -> Symbol | None:
    """
    Find the symbol corresponding to the default export of *file_path*.

    Looks for EXPORTS relationships with ``is_default=True`` and then
    resolves the ``target_name`` to a local symbol.  Returns ``None`` if
    no matching symbol is found.
    """
    for rel in index.get_exports(file_path):
        if rel.is_default and rel.target_name:
            sym = _find_local_symbol(rel.target_name, file_path, index)
            if sym is not None:
                return sym
    return None


# ---------------------------------------------------------------------------
# Single-relationship resolution
# ---------------------------------------------------------------------------


def _resolve_single_import(
    rel: Relationship,
    index: RepositoryIndex,
) -> ResolvedRelationship:
    """
    Produce a ``ResolvedRelationship`` for one IMPORTS *rel*.

    Decision tree:
    1. No module_path        → UNRESOLVED
    2. External module path  → EXTERNAL
    3. Path not in index     → UNRESOLVED  (includes repo-escape paths)
    4. Side-effect import    → RESOLVED_FILE
    5. Namespace import      → RESOLVED_FILE
    6. Default import        → RESOLVED if default symbol found, else RESOLVED_FILE
    7. Named import          → RESOLVED if symbol found (with re-export chain),
                               else RESOLVED_FILE
    """
    module_path = rel.module_path

    # --- Guard: missing module path ---
    if module_path is None:
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.UNRESOLVED,
            target_path=None,
            target_symbol_id=None,
            notes="No module path on relationship",
        )

    # --- External dependency ---
    if _is_external(module_path):
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.EXTERNAL,
            target_path=None,
            target_symbol_id=None,
            notes=f"External dependency: {module_path!r}",
        )

    # --- Resolve path ---
    target_path = _resolve_module_path(
        rel.source_path, module_path, index.files_by_path
    )
    if target_path is None:
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.UNRESOLVED,
            target_path=None,
            target_symbol_id=None,
            notes=f"Module not found in repository: {module_path!r}",
        )

    # --- Side-effect import (no binding) ---
    if rel.target_name == "":
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED_FILE,
            target_path=target_path,
            target_symbol_id=None,
            notes="Side-effect import (no binding)",
        )

    # --- Namespace import (import * as ns) ---
    if rel.is_namespace:
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED_FILE,
            target_path=target_path,
            target_symbol_id=None,
            notes=f"Namespace import — module resolved to {target_path!r}",
        )

    # --- Default import ---
    if rel.is_default:
        sym = _resolve_default_export(target_path, index)
        if sym is not None:
            return ResolvedRelationship(
                source_relationship=rel,
                status=ResolutionStatus.RESOLVED,
                target_path=target_path,
                target_symbol_id=_symbol_to_id(sym),
                notes=None,
            )
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED_FILE,
            target_path=target_path,
            target_symbol_id=None,
            notes="Default export declaration not found in target file",
        )

    # --- Named import ---
    # Use target_name (the original exported identifier), not alias
    original_name = rel.target_name
    sym = _resolve_named_export(original_name, target_path, index, frozenset())
    if sym is not None:
        return ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED,
            target_path=target_path,
            target_symbol_id=_symbol_to_id(sym),
            notes=(
                f"Resolved via alias {rel.alias!r}" if rel.alias else None
            ),
        )
    return ResolvedRelationship(
        source_relationship=rel,
        status=ResolutionStatus.RESOLVED_FILE,
        target_path=target_path,
        target_symbol_id=None,
        notes=f"Symbol {original_name!r} not found in {target_path!r}",
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def resolve_imports(
    files: list[FileInfo],
    symbols: list[Symbol],
    relationships: list[Relationship],
) -> list[ResolvedRelationship]:
    """
    Resolve all IMPORTS relationships into concrete repository references.

    Builds a ``RepositoryIndex`` from the provided data and resolves each
    IMPORTS relationship in *relationships*.  Non-IMPORTS relationships
    (EXPORTS, CALLS, REFERENCES) are ignored — they are already file-local.

    The returned list is sorted deterministically by:
      (source_path, source_position.line, source_position.column, target_name)

    Parameters
    ----------
    files:
        All ``FileInfo`` objects from the M1 scanner for the repository.
    symbols:
        All ``Symbol`` objects from the M3 extractor.
    relationships:
        All ``Relationship`` objects from the M4 extractor.

    Returns
    -------
    list[ResolvedRelationship]
        One entry per IMPORTS relationship, regardless of whether it could
        be resolved.  External and missing modules are represented with the
        appropriate ``ResolutionStatus``.
    """
    index = RepositoryIndex(files, symbols, relationships)

    results: list[ResolvedRelationship] = []
    for rel in relationships:
        if rel.kind != RelationshipKind.IMPORTS:
            continue
        results.append(_resolve_single_import(rel, index))

    # Deterministic sort
    results.sort(
        key=lambda r: (
            r.source_relationship.source_path,
            r.source_relationship.source_position.line,
            r.source_relationship.source_position.column,
            r.source_relationship.target_name,
        )
    )
    return results
