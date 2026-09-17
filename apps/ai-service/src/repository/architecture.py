"""
repository/architecture.py

Deterministic, evidence-based architectural detection.
Milestone 6 — classifies repository files into architectural roles using
evidence gathered from M1 (FileInfo), M3 (Symbol), M4 (Relationship), and
M5 (ResolvedRelationship).

Design principles
-----------------
1.  Pure deterministic inference — no LLM, no regex-primary, no random values.
2.  Evidence is explicit and verifiable — every item corresponds to an actual
    observation from the repository data.
3.  Multiple roles per file are supported; a file may legitimately be TEST
    and CONTROLLER at the same time.
4.  UNKNOWN is a valid and honest result when no evidence matches.
5.  Path-based evidence, extension evidence, symbol evidence, call evidence,
    and import evidence are detected and stored separately so tests can
    verify each source independently.
6.  Architectural relationships (e.g. ROUTE → CONTROLLER) are inferred only
    from actual resolved import relationships combined with role classifications,
    never from naming alone.

Public API
----------
classify_file(file, symbols, relationships, resolved) -> FileClassification
classify_repository(files, symbols, relationships, resolved) -> RepositoryArchitecture

Deferred to M7+
---------------
- Final CodeGraph construction
- Graph persistence / visualisation
- LLM semantic enrichment
- RAG / embeddings / Qdrant
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from .models import FileInfo
from .relationships import Relationship, RelationshipKind
from .resolver import ResolvedRelationship, ResolutionStatus
from .symbols import Symbol, SymbolKind

# ---------------------------------------------------------------------------
# Architectural role
# ---------------------------------------------------------------------------


class ArchitectureRole(str, Enum):
    """
    Architectural role of a file or symbol.

    Each value describes the dominant responsibility of the artifact within
    the application's architecture.
    """

    CONTROLLER = "controller"    # handles HTTP requests, delegates to services
    SERVICE = "service"          # encapsulates business logic
    REPOSITORY = "repository"    # data access layer (database queries)
    ROUTE = "route"              # URL routing / path registration
    MODEL = "model"              # data model / ORM schema
    ENTITY = "entity"            # domain entity / value object
    COMPONENT = "component"      # UI component (React / Vue / etc.)
    HOOK = "hook"                # reusable stateful logic (React hooks)
    MIDDLEWARE = "middleware"     # request / response pipeline function
    UTILITY = "utility"          # shared helper / pure-function utilities
    CONFIG = "config"            # configuration / environment settings
    ENTRYPOINT = "entrypoint"    # application boot / server start
    TEST = "test"                # automated test file
    UNKNOWN = "unknown"          # insufficient evidence to classify


# ---------------------------------------------------------------------------
# Architectural layer
# ---------------------------------------------------------------------------


class ArchitecturalLayer(str, Enum):
    """
    Broad application layer that an architectural role belongs to.

    Layers are coarser-grained groupings for visualisation and pattern
    detection; they are NOT enforced constraints.
    """

    PRESENTATION = "presentation"    # routes, controllers, UI components, hooks
    APPLICATION = "application"      # services, use-cases
    DOMAIN = "domain"                # models, entities, domain logic
    DATA = "data"                    # repositories, database adapters
    INFRASTRUCTURE = "infrastructure" # config, middleware, utilities, entrypoints
    TESTING = "testing"              # test files
    UNKNOWN = "unknown"              # no layer determined


# ---------------------------------------------------------------------------
# Role → Layer mapping
# ---------------------------------------------------------------------------

_ROLE_TO_LAYER: dict[ArchitectureRole, ArchitecturalLayer] = {
    ArchitectureRole.CONTROLLER: ArchitecturalLayer.PRESENTATION,
    ArchitectureRole.ROUTE: ArchitecturalLayer.PRESENTATION,
    ArchitectureRole.COMPONENT: ArchitecturalLayer.PRESENTATION,
    ArchitectureRole.HOOK: ArchitecturalLayer.PRESENTATION,
    ArchitectureRole.SERVICE: ArchitecturalLayer.APPLICATION,
    ArchitectureRole.MODEL: ArchitecturalLayer.DOMAIN,
    ArchitectureRole.ENTITY: ArchitecturalLayer.DOMAIN,
    ArchitectureRole.REPOSITORY: ArchitecturalLayer.DATA,
    ArchitectureRole.MIDDLEWARE: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitectureRole.CONFIG: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitectureRole.UTILITY: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitectureRole.ENTRYPOINT: ArchitecturalLayer.INFRASTRUCTURE,
    ArchitectureRole.TEST: ArchitecturalLayer.TESTING,
    ArchitectureRole.UNKNOWN: ArchitecturalLayer.UNKNOWN,
}


def _role_to_layer(role: ArchitectureRole) -> ArchitecturalLayer:
    """Return the architectural layer for a given role."""
    return _ROLE_TO_LAYER.get(role, ArchitecturalLayer.UNKNOWN)


# ---------------------------------------------------------------------------
# Evidence model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EvidenceItem:
    """
    A single, verifiable piece of evidence that contributed to an
    architectural classification.

    Every ``EvidenceItem`` corresponds to an actual observation extracted
    from the repository data — nothing is fabricated.

    Attributes
    ----------
    description:
        Human-readable statement of what was observed.
        Example: ``"filename contains 'controller'"``
    category:
        Source of this evidence:
        ``"path"``      — from filename stem or directory segment
        ``"extension"`` — from the file extension (.jsx, .tsx, …)
        ``"symbol"``    — from an M3-extracted Symbol name
        ``"call"``      — from an M4 CALLS relationship
        ``"import"``    — from M4 IMPORTS / M5 ResolvedRelationship
    """

    description: str
    category: str


# ---------------------------------------------------------------------------
# Classification models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ArchitecturalClassification:
    """
    A single architectural role assignment for a file.

    A file may have more than one ``ArchitecturalClassification`` (e.g.
    ``TEST`` + ``CONTROLLER`` for a controller test file).

    Attributes
    ----------
    path:
        Repository-relative POSIX path of the classified file.
    role:
        The assigned architectural role.
    layer:
        The broad architectural layer derived from the role.
    evidence:
        Tuple of ``EvidenceItem`` objects that justify this classification.
        Empty only when role is ``UNKNOWN``.
    """

    path: str
    role: ArchitectureRole
    layer: ArchitecturalLayer
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class FileClassification:
    """
    All architectural classifications for a single file.

    Attributes
    ----------
    path:
        Repository-relative POSIX path of the file.
    classifications:
        Tuple of ``ArchitecturalClassification`` objects — one per detected
        role.  Contains exactly one ``UNKNOWN`` classification when no
        evidence matches any known role.
    """

    path: str
    classifications: tuple[ArchitecturalClassification, ...]


@dataclass(frozen=True)
class ArchitecturalRelationship:
    """
    A detected architectural relationship between two classified files.

    Only emitted when an actual resolved import exists AND both files have
    matching role classifications — never inferred from naming alone.

    Attributes
    ----------
    source_path:
        File that imports from ``target_path``.
    source_role:
        Architectural role of the source file relevant to this relationship.
    target_path:
        File being imported.
    target_role:
        Architectural role of the target file relevant to this relationship.
    pattern:
        Human-readable description of the architectural pattern.
        Example: ``"ROUTE → CONTROLLER"``
    evidence:
        Tuple of ``EvidenceItem`` objects that justify this relationship.
    """

    source_path: str
    source_role: ArchitectureRole
    target_path: str
    target_role: ArchitectureRole
    pattern: str
    evidence: tuple[EvidenceItem, ...]


@dataclass(frozen=True)
class RepositoryArchitecture:
    """
    Complete architectural view of a repository.

    Attributes
    ----------
    file_classifications:
        Tuple of ``FileClassification`` objects, one per repository file,
        sorted deterministically by path.
    architectural_relationships:
        Detected architectural relationships sorted deterministically by
        (source_path, target_path, pattern).
    """

    file_classifications: tuple[FileClassification, ...]
    architectural_relationships: tuple[ArchitecturalRelationship, ...]


# ---------------------------------------------------------------------------
# Detection data tables
# ---------------------------------------------------------------------------

# filename stem substring → role (first matching keyword wins per role)
_STEM_CHECKS: list[tuple[ArchitectureRole, tuple[str, ...]]] = [
    (ArchitectureRole.TEST,       ("test", "spec")),
    (ArchitectureRole.CONTROLLER, ("controller", "controllers", "ctrl")),
    (ArchitectureRole.SERVICE,    ("service", "services", "svc")),
    (ArchitectureRole.REPOSITORY, ("repository", "repositories", "repo")),
    (ArchitectureRole.ROUTE,      ("route", "routes", "router")),
    (ArchitectureRole.MODEL,      ("model", "models", "schema", "schemas")),
    (ArchitectureRole.ENTITY,     ("entity", "entities")),
    (ArchitectureRole.MIDDLEWARE, ("middleware",)),
    (ArchitectureRole.CONFIG,     ("config", "configuration", "settings")),
    (ArchitectureRole.UTILITY,    ("util", "utils", "utility", "utilities", "helper", "helpers")),
    (ArchitectureRole.COMPONENT,  ("component", "components")),
]

# lowercase directory segment → role (first matching segment wins per role)
_SEGMENT_CHECKS: list[tuple[ArchitectureRole, frozenset[str]]] = [
    (ArchitectureRole.TEST,       frozenset({"__tests__", "tests", "test", "spec", "specs", "__spec__"})),
    (ArchitectureRole.HOOK,       frozenset({"hooks", "hook"})),
    (ArchitectureRole.CONTROLLER, frozenset({"controllers", "controller"})),
    (ArchitectureRole.SERVICE,    frozenset({"services", "service"})),
    (ArchitectureRole.REPOSITORY, frozenset({"repositories", "repository", "repos", "repo", "dal"})),
    (ArchitectureRole.ROUTE,      frozenset({"routes", "route"})),
    (ArchitectureRole.MODEL,      frozenset({"models", "model", "schemas"})),
    (ArchitectureRole.ENTITY,     frozenset({"entities", "entity"})),
    (ArchitectureRole.MIDDLEWARE, frozenset({"middleware", "middlewares"})),
    (ArchitectureRole.CONFIG,     frozenset({"config", "configuration", "settings", "configs"})),
    (ArchitectureRole.UTILITY,    frozenset({"utils", "util", "helpers", "helper", "lib", "utilities", "common"})),
    (ArchitectureRole.COMPONENT,  frozenset({"components", "component", "pages", "views", "screens", "ui"})),
]

# ENTRYPOINT: stem must be exactly one of these (lowercase)
_ENTRYPOINT_STEMS: frozenset[str] = frozenset({"index", "main", "server", "app"})

# Express route registration callees (M4 CALLS target_name)
_EXPRESS_ROUTE_CALLEES: frozenset[str] = frozenset({
    "router.get", "router.post", "router.put", "router.delete",
    "router.patch", "router.use", "router.all",
    "app.get",    "app.post",    "app.put",    "app.delete",
    "app.patch",  "app.use",     "app.all",
})

# React hook callees (from M4 CALLS)
_REACT_HOOK_CALLEES: frozenset[str] = frozenset({
    "useState", "useEffect", "useCallback", "useMemo",
    "useRef", "useContext", "useReducer", "useLayoutEffect",
    "useId", "useTransition", "useDeferredValue",
})

# Database operation callee prefixes → REPOSITORY evidence
_DB_CALLEE_PREFIXES: tuple[str, ...] = (
    "prisma.", "db.", "knex.", "sequelize.",
    "mongoose.connection.", "pool.", "client.",
)

# Database operation callee suffixes → REPOSITORY evidence
_DB_CALLEE_SUFFIXES: tuple[str, ...] = (
    ".findMany", ".findById", ".findOne", ".findAll", ".findBy",
    ".findByPk", ".findAndCountAll",
    ".createMany", ".create", ".save",
    ".updateMany", ".update",
    ".deleteMany", ".delete", ".destroy",
    ".query", ".execute", ".raw",
)

# Model-creation callees → MODEL evidence
_MODEL_CREATION_CALLEES: frozenset[str] = frozenset({
    "mongoose.model",
})

# External module patterns → (module_path_exact, role, description)
_EXTERNAL_IMPORT_PATTERNS: list[tuple[str, ArchitectureRole, str]] = [
    ("react",          ArchitectureRole.COMPONENT, "imports 'react'"),
    ("react",          ArchitectureRole.HOOK,      "imports 'react'"),
    ("react-dom",      ArchitectureRole.COMPONENT, "imports 'react-dom'"),
    ("express",        ArchitectureRole.ROUTE,     "imports 'express'"),
    ("mongoose",       ArchitectureRole.MODEL,      "imports 'mongoose'"),
    ("mongoose",       ArchitectureRole.REPOSITORY, "imports 'mongoose'"),
    ("@prisma/client", ArchitectureRole.REPOSITORY, "imports '@prisma/client'"),
]

# Architectural relationship patterns: (source_role, target_role, pattern_label)
_ARCH_PATTERNS: list[tuple[ArchitectureRole, ArchitectureRole, str]] = [
    (ArchitectureRole.ROUTE,      ArchitectureRole.CONTROLLER, "ROUTE → CONTROLLER"),
    (ArchitectureRole.CONTROLLER, ArchitectureRole.SERVICE,    "CONTROLLER → SERVICE"),
    (ArchitectureRole.SERVICE,    ArchitectureRole.REPOSITORY, "SERVICE → REPOSITORY"),
    (ArchitectureRole.REPOSITORY, ArchitectureRole.MODEL,      "REPOSITORY → MODEL"),
    (ArchitectureRole.SERVICE,    ArchitectureRole.MODEL,      "SERVICE → MODEL"),
    (ArchitectureRole.COMPONENT,  ArchitectureRole.HOOK,       "COMPONENT → HOOK"),
    (ArchitectureRole.COMPONENT,  ArchitectureRole.SERVICE,    "COMPONENT → SERVICE"),
    (ArchitectureRole.MIDDLEWARE, ArchitectureRole.SERVICE,    "MIDDLEWARE → SERVICE"),
]


# ---------------------------------------------------------------------------
# Path utilities
# ---------------------------------------------------------------------------


def _file_decompose(path: str) -> tuple[str, str, str, list[str]]:
    """
    Decompose a repository file path into its constituent parts.

    Returns
    -------
    stem_raw:   basename without the final extension, preserving original case.
                e.g. ``"authController.test"`` for ``"src/authController.test.js"``
    stem:       ``stem_raw`` lowercased.
    ext:        Final extension, lowercased. e.g. ``".js"``
    segments:   Lowercased directory segments (empty list for root files).
                e.g. ``["src", "controllers"]``
    """
    basename = posixpath.basename(path)
    dirname = posixpath.dirname(path)
    stem_raw, ext = posixpath.splitext(basename)
    segments = [s.lower() for s in dirname.split("/") if s]
    return stem_raw, stem_raw.lower(), ext.lower(), segments


def _is_hook_name(raw_stem: str) -> bool:
    """
    Return True if *raw_stem* follows the React hook naming convention.

    A hook name starts with ``"use"`` and is followed by an uppercase letter
    or nothing else (the exact string ``"use"`` is excluded as it's too generic).

    Examples: ``"useAuth"`` → True, ``"useState"`` → True,
              ``"useful"`` → False, ``"use"`` → False.
    """
    if len(raw_stem) <= 3:
        return False
    return raw_stem.startswith("use") and raw_stem[3].isupper()


# ---------------------------------------------------------------------------
# Detection: file path and extension
# ---------------------------------------------------------------------------


def _detect_by_path(file: FileInfo) -> dict[ArchitectureRole, list[EvidenceItem]]:
    """
    Derive architectural role evidence purely from the file path and extension.

    No file content is examined here.  Uses filename stem substring matching,
    path segment membership, and extension checks.
    """
    stem_raw, stem, ext, segments = _file_decompose(file.path)
    evidence: dict[ArchitectureRole, list[EvidenceItem]] = {}

    # Deduplication helper (same description → add only once per role)
    seen: dict[ArchitectureRole, set[str]] = {}

    def add(role: ArchitectureRole, desc: str, cat: str = "path") -> None:
        bucket = seen.setdefault(role, set())
        if desc not in bucket:
            bucket.add(desc)
            evidence.setdefault(role, []).append(EvidenceItem(description=desc, category=cat))

    # --- Extension-based evidence ---
    if ext in {".jsx", ".tsx"}:
        add(ArchitectureRole.COMPONENT, f"JSX/TSX file extension ({ext!r})", "extension")

    # --- Special stem cases ---
    # ENTRYPOINT: stem is exactly one of the recognised entry filenames
    if stem in _ENTRYPOINT_STEMS:
        add(ArchitectureRole.ENTRYPOINT, f"filename is {stem!r} (common application entrypoint)")

    # HOOK: stem follows React hook naming convention (useXxx)
    if _is_hook_name(stem_raw):
        add(ArchitectureRole.HOOK, "filename follows React hook naming convention (use*)")

    # --- General stem keyword matching ---
    for role, keywords in _STEM_CHECKS:
        for kw in keywords:
            if kw in stem:
                add(role, f"filename contains {kw!r}")
                break  # one stem match per role is sufficient

    # --- General segment keyword matching ---
    for role, segment_set in _SEGMENT_CHECKS:
        for seg in segments:
            if seg in segment_set:
                add(role, f"in {seg!r} directory")
                break  # one segment match per role is sufficient

    return evidence


# ---------------------------------------------------------------------------
# Detection: M3 symbols
# ---------------------------------------------------------------------------


def _detect_by_symbols(
    file: FileInfo,
    symbols: list[Symbol],
) -> dict[ArchitectureRole, list[EvidenceItem]]:
    """
    Derive architectural role evidence from the M3-extracted symbols of *file*.

    Checks symbol naming conventions to identify hooks, controllers, services,
    repositories, models, and React components.
    """
    evidence: dict[ArchitectureRole, list[EvidenceItem]] = {}
    seen: dict[ArchitectureRole, set[str]] = {}

    def add(role: ArchitectureRole, desc: str) -> None:
        bucket = seen.setdefault(role, set())
        if desc not in bucket:
            bucket.add(desc)
            evidence.setdefault(role, []).append(EvidenceItem(description=desc, category="symbol"))

    _callable = {SymbolKind.FUNCTION, SymbolKind.CLASS, SymbolKind.METHOD}

    for sym in symbols:
        name = sym.name
        name_lower = name.lower()

        # React hook naming convention: function named useXxx
        if sym.kind in {SymbolKind.FUNCTION} and _is_hook_name(name):
            add(ArchitectureRole.HOOK, f"symbol {name!r} follows React hook naming (use*)")

        # Controller naming convention
        if sym.kind in _callable and name_lower.endswith("controller"):
            add(ArchitectureRole.CONTROLLER, f"symbol {name!r} follows controller naming convention")

        # Service naming convention
        if sym.kind in _callable and name_lower.endswith("service"):
            add(ArchitectureRole.SERVICE, f"symbol {name!r} follows service naming convention")

        # Repository naming convention
        if sym.kind in _callable and name_lower.endswith("repository"):
            add(ArchitectureRole.REPOSITORY, f"symbol {name!r} follows repository naming convention")

        # Model / schema naming convention
        if sym.kind in _callable and (
            name_lower.endswith("model") or name_lower.endswith("schema")
        ):
            add(ArchitectureRole.MODEL, f"symbol {name!r} follows model/schema naming convention")

        # React component: capitalized name in a JSX/TSX file
        if (
            sym.kind in {SymbolKind.FUNCTION, SymbolKind.CLASS}
            and name
            and name[0].isupper()
            and file.extension in {".jsx", ".tsx"}
        ):
            add(ArchitectureRole.COMPONENT, f"symbol {name!r} is a capitalized component identifier")

    return evidence


# ---------------------------------------------------------------------------
# Detection: M4 CALLS relationships
# ---------------------------------------------------------------------------


def _detect_by_calls(
    file: FileInfo,
    relationships: list[Relationship],
) -> dict[ArchitectureRole, list[EvidenceItem]]:
    """
    Derive architectural role evidence from M4 CALLS relationships of *file*.

    Detects Express route registration, React hook calls, and database
    operation patterns.
    """
    evidence: dict[ArchitectureRole, list[EvidenceItem]] = {}
    seen: dict[ArchitectureRole, set[str]] = {}

    def add(role: ArchitectureRole, desc: str) -> None:
        bucket = seen.setdefault(role, set())
        if desc not in bucket:
            bucket.add(desc)
            evidence.setdefault(role, []).append(EvidenceItem(description=desc, category="call"))

    for rel in relationships:
        if rel.kind != RelationshipKind.CALLS:
            continue

        callee = rel.target_name

        # Express route registration
        if callee in _EXPRESS_ROUTE_CALLEES:
            add(ArchitectureRole.ROUTE, f"calls {callee!r} — Express route registration")

        # React hook usage (component or hook file)
        if callee in _REACT_HOOK_CALLEES:
            add(ArchitectureRole.COMPONENT, f"calls {callee!r} — React hook usage")

        # Database operations — prefix match
        for prefix in _DB_CALLEE_PREFIXES:
            if callee.startswith(prefix):
                add(ArchitectureRole.REPOSITORY, f"calls {callee!r} — database operation")
                break

        # Database operations — suffix match
        for suffix in _DB_CALLEE_SUFFIXES:
            if callee.endswith(suffix):
                add(ArchitectureRole.REPOSITORY, f"calls {callee!r} — database query pattern")
                break

        # Model creation
        if callee in _MODEL_CREATION_CALLEES:
            add(ArchitectureRole.MODEL, f"calls {callee!r} — model definition")

    return evidence


# ---------------------------------------------------------------------------
# Detection: M5 ResolvedRelationship (import patterns)
# ---------------------------------------------------------------------------


def _detect_by_imports(
    file: FileInfo,
    resolved: list[ResolvedRelationship],
) -> dict[ArchitectureRole, list[EvidenceItem]]:
    """
    Derive architectural role evidence from M5 resolved import relationships.

    Only examines imports with ``status == EXTERNAL`` to detect well-known
    npm packages that imply specific roles.  Local imports are not used here
    (cross-file role inference happens at repository level).
    """
    evidence: dict[ArchitectureRole, list[EvidenceItem]] = {}
    seen: dict[ArchitectureRole, set[str]] = {}

    def add(role: ArchitectureRole, desc: str) -> None:
        bucket = seen.setdefault(role, set())
        if desc not in bucket:
            bucket.add(desc)
            evidence.setdefault(role, []).append(EvidenceItem(description=desc, category="import"))

    for rr in resolved:
        if rr.status != ResolutionStatus.EXTERNAL:
            continue
        module_path = rr.source_relationship.module_path or ""
        for mod, role, desc in _EXTERNAL_IMPORT_PATTERNS:
            if module_path == mod:
                add(role, desc)

    return evidence


# ---------------------------------------------------------------------------
# Classification assembly
# ---------------------------------------------------------------------------


def _merge_evidence(
    *sources: dict[ArchitectureRole, list[EvidenceItem]],
) -> dict[ArchitectureRole, list[EvidenceItem]]:
    """Merge multiple evidence dicts (from different detection sources)."""
    merged: dict[ArchitectureRole, list[EvidenceItem]] = {}
    seen: dict[ArchitectureRole, set[str]] = {}

    for src in sources:
        for role, items in src.items():
            bucket = seen.setdefault(role, set())
            for item in items:
                if item.description not in bucket:
                    bucket.add(item.description)
                    merged.setdefault(role, []).append(item)

    return merged


def _build_file_classification(
    file: FileInfo,
    role_evidence: dict[ArchitectureRole, list[EvidenceItem]],
) -> FileClassification:
    """
    Convert a role → evidence mapping into an immutable ``FileClassification``.

    If *role_evidence* is empty, a single ``UNKNOWN`` classification is
    returned.  Otherwise, one ``ArchitecturalClassification`` is created per
    role, sorted by role value for determinism.
    """
    if not role_evidence:
        return FileClassification(
            path=file.path,
            classifications=(
                ArchitecturalClassification(
                    path=file.path,
                    role=ArchitectureRole.UNKNOWN,
                    layer=ArchitecturalLayer.UNKNOWN,
                    evidence=(),
                ),
            ),
        )

    classifications = tuple(
        sorted(
            (
                ArchitecturalClassification(
                    path=file.path,
                    role=role,
                    layer=_role_to_layer(role),
                    evidence=tuple(items),
                )
                for role, items in role_evidence.items()
            ),
            key=lambda c: c.role.value,
        )
    )
    return FileClassification(path=file.path, classifications=classifications)


# ---------------------------------------------------------------------------
# Architectural relationship detection
# ---------------------------------------------------------------------------


def _detect_architectural_relationships(
    file_classifs: list[FileClassification],
    resolved: list[ResolvedRelationship],
) -> list[ArchitecturalRelationship]:
    """
    Detect architectural relationships (e.g. ROUTE → CONTROLLER) by joining
    role classifications with actual resolved import relationships.

    A relationship is emitted only when:
    - A resolved import from file A to file B exists (RESOLVED or RESOLVED_FILE).
    - File A has role X and file B has role Y.
    - (X, Y) matches a known architectural pattern.

    This strictly avoids fabricating relationships based on naming alone.
    """
    # Build path → set[ArchitectureRole] from classifications
    path_roles: dict[str, set[ArchitectureRole]] = {}
    for fc in file_classifs:
        path_roles[fc.path] = {c.role for c in fc.classifications}

    results: list[ArchitecturalRelationship] = []
    # Deduplicate: (source_path, target_path, pattern) → already emitted
    seen_keys: set[tuple[str, str, str]] = set()

    for rr in resolved:
        if rr.target_path is None:
            continue
        if rr.status not in {ResolutionStatus.RESOLVED, ResolutionStatus.RESOLVED_FILE}:
            continue

        src_path = rr.source_relationship.source_path
        tgt_path = rr.target_path

        src_roles = path_roles.get(src_path, set())
        tgt_roles = path_roles.get(tgt_path, set())

        for src_role, tgt_role, pattern in _ARCH_PATTERNS:
            if src_role not in src_roles or tgt_role not in tgt_roles:
                continue
            key = (src_path, tgt_path, pattern)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            evidence = (
                EvidenceItem(
                    description=(
                        f"{src_path!r} imports {tgt_path!r} "
                        f"(module: {rr.source_relationship.module_path!r})"
                    ),
                    category="import",
                ),
                EvidenceItem(
                    description=(
                        f"source classified as {src_role.value.upper()}, "
                        f"target classified as {tgt_role.value.upper()}"
                    ),
                    category="classification",
                ),
            )
            results.append(
                ArchitecturalRelationship(
                    source_path=src_path,
                    source_role=src_role,
                    target_path=tgt_path,
                    target_role=tgt_role,
                    pattern=pattern,
                    evidence=evidence,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def classify_file(
    file: FileInfo,
    symbols: list[Symbol] | None = None,
    relationships: list[Relationship] | None = None,
    resolved: list[ResolvedRelationship] | None = None,
) -> FileClassification:
    """
    Classify a single file into architectural roles.

    Runs all four detection passes (path, symbols, calls, imports) and
    merges their evidence.  Returns a ``FileClassification`` with one
    ``ArchitecturalClassification`` per detected role, or a single
    ``UNKNOWN`` classification when no evidence was found.

    Parameters
    ----------
    file:
        ``FileInfo`` from the M1 scanner.
    symbols:
        M3 symbols extracted from this file (defaults to ``[]``).
    relationships:
        M4 relationships where ``source_path == file.path``
        (defaults to ``[]``).
    resolved:
        M5 resolved relationships where source file is this file
        (defaults to ``[]``).
    """
    symbols = symbols or []
    relationships = relationships or []
    resolved = resolved or []

    role_evidence = _merge_evidence(
        _detect_by_path(file),
        _detect_by_symbols(file, symbols),
        _detect_by_calls(file, relationships),
        _detect_by_imports(file, resolved),
    )

    return _build_file_classification(file, role_evidence)


def classify_repository(
    files: list[FileInfo],
    symbols: list[Symbol] | None = None,
    relationships: list[Relationship] | None = None,
    resolved: list[ResolvedRelationship] | None = None,
) -> RepositoryArchitecture:
    """
    Classify all files in a repository and detect architectural patterns.

    Builds per-file indexes from the provided data, classifies each file,
    then detects inter-file architectural relationships from the resolved
    import graph.

    Parameters
    ----------
    files:
        All ``FileInfo`` objects from the M1 scanner.
    symbols:
        All ``Symbol`` objects from M3 (across all files).
    relationships:
        All ``Relationship`` objects from M4 (across all files).
    resolved:
        All ``ResolvedRelationship`` objects from M5.

    Returns
    -------
    RepositoryArchitecture
        Fully classified repository sorted deterministically.
    """
    symbols = symbols or []
    relationships = relationships or []
    resolved = resolved or []

    # --- Build per-file indexes ---
    file_symbols: dict[str, list[Symbol]] = {}
    for sym in symbols:
        file_symbols.setdefault(sym.path, []).append(sym)

    file_relationships: dict[str, list[Relationship]] = {}
    for rel in relationships:
        file_relationships.setdefault(rel.source_path, []).append(rel)

    file_resolved: dict[str, list[ResolvedRelationship]] = {}
    for rr in resolved:
        src = rr.source_relationship.source_path
        file_resolved.setdefault(src, []).append(rr)

    # --- Classify each file ---
    file_classifs: list[FileClassification] = []
    for fi in files:
        fc = classify_file(
            file=fi,
            symbols=file_symbols.get(fi.path, []),
            relationships=file_relationships.get(fi.path, []),
            resolved=file_resolved.get(fi.path, []),
        )
        file_classifs.append(fc)

    # --- Detect architectural relationships ---
    arch_rels = _detect_architectural_relationships(file_classifs, resolved)

    # --- Sort deterministically ---
    file_classifs.sort(key=lambda fc: fc.path)
    arch_rels.sort(key=lambda ar: (ar.source_path, ar.target_path, ar.pattern))

    return RepositoryArchitecture(
        file_classifications=tuple(file_classifs),
        architectural_relationships=tuple(arch_rels),
    )
