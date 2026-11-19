"""
repository/graph.py

Unified in-memory CodeGraph construction for repository intelligence.
Milestone 7 — converts deterministic facts from M1–M6 into an immutable,
queryable, deterministically-ordered graph representation.

Pipeline:
  M1 FileInfo                  → FILE nodes
  M3 Symbol                    → FUNCTION, CLASS, METHOD, VARIABLE, CONSTANT nodes
  M4 / M5 Relationships        → CONTAINS, IMPORTS, EXPORTS, CALLS, REFERENCES edges
  M6 Architecture              → Architectural role nodes & DEPENDS_ON edges
  External / Unresolved imports → EXTERNAL & UNRESOLVED nodes

Design principles:
1. Pure static analysis facts — NO LLM, NO invented relationships.
2. Immutability: frozen dataclasses with tuples for all collections.
3. Determinism: stable IDs, sorted nodes and edges, independent of hash seeds.
4. Validation: construction-time integrity checks for nodes, edges, and parents.
5. In-memory: no graph database, no Neo4j, no Qdrant/Redis dependencies.
"""

from __future__ import annotations

import posixpath
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence

from .architecture import (
    ArchitecturalClassification,
    ArchitecturalRelationship,
    ArchitectureRole,
    FileClassification,
    RepositoryArchitecture,
)
from .models import FileInfo
from .parser import Position
from .relationships import Relationship, RelationshipKind
from .resolver import ResolutionStatus, ResolvedRelationship, SymbolId
from .symbols import Symbol, SymbolKind


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GraphValidationError(ValueError):
    """Raised when construction-time graph validation fails."""


# ---------------------------------------------------------------------------
# Node and Edge Type Enums
# ---------------------------------------------------------------------------


class NodeType(str, Enum):
    """Semantic category of a CodeGraph node."""

    REPOSITORY = "repository"
    FILE = "file"

    # Symbols (from M3)
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    VARIABLE = "variable"
    CONSTANT = "constant"

    # Architectural roles (from M6)
    ROUTE = "route"
    CONTROLLER = "controller"
    SERVICE = "service"
    REPOSITORY_ROLE = "repository_role"
    MODEL = "model"
    ENTITY = "entity"
    COMPONENT = "component"
    HOOK = "hook"
    MIDDLEWARE = "middleware"
    UTILITY = "utility"
    CONFIG = "config"
    ENTRYPOINT = "entrypoint"
    TEST = "test"
    UNKNOWN = "unknown"

    # External & Unresolved dependencies
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"

    # API & Route Map extensions
    API_ENDPOINT = "api_endpoint"
    DATABASE_MODEL = "database_model"


class EdgeType(str, Enum):
    """Semantic category of a CodeGraph directed edge."""

    CONTAINS = "contains"
    IMPORTS = "imports"
    EXPORTS = "exports"
    CALLS = "calls"
    REFERENCES = "references"
    CLASSIFIED_AS = "classified_as"
    DEPENDS_ON = "depends_on"

    # API & Route Map extensions
    ROUTES_TO = "routes_to"
    HANDLED_BY = "handled_by"
    USES_MIDDLEWARE = "uses_middleware"
    CALLS_SERVICE = "calls_service"
    ACCESSES_MODEL = "accesses_model"


# Mappings from prior milestone models to NodeType
_SYMBOL_KIND_TO_NODE_TYPE: dict[SymbolKind, NodeType] = {
    SymbolKind.FUNCTION: NodeType.FUNCTION,
    SymbolKind.CLASS: NodeType.CLASS,
    SymbolKind.METHOD: NodeType.METHOD,
    SymbolKind.VARIABLE: NodeType.VARIABLE,
    SymbolKind.CONSTANT: NodeType.CONSTANT,
}

_ROLE_TO_NODE_TYPE: dict[ArchitectureRole, NodeType] = {
    ArchitectureRole.CONTROLLER: NodeType.CONTROLLER,
    ArchitectureRole.SERVICE: NodeType.SERVICE,
    ArchitectureRole.REPOSITORY: NodeType.REPOSITORY_ROLE,
    ArchitectureRole.ROUTE: NodeType.ROUTE,
    ArchitectureRole.MODEL: NodeType.MODEL,
    ArchitectureRole.ENTITY: NodeType.ENTITY,
    ArchitectureRole.COMPONENT: NodeType.COMPONENT,
    ArchitectureRole.HOOK: NodeType.HOOK,
    ArchitectureRole.MIDDLEWARE: NodeType.MIDDLEWARE,
    ArchitectureRole.UTILITY: NodeType.UTILITY,
    ArchitectureRole.CONFIG: NodeType.CONFIG,
    ArchitectureRole.ENTRYPOINT: NodeType.ENTRYPOINT,
    ArchitectureRole.TEST: NodeType.TEST,
    ArchitectureRole.UNKNOWN: NodeType.UNKNOWN,
}


# ---------------------------------------------------------------------------
# Node ID Generation Helpers (Deterministic)
# ---------------------------------------------------------------------------


def make_repo_node_id(repo_name: str = "root") -> str:
    """Return deterministic ID for repository root node."""
    return f"repo:{repo_name}"


def make_file_node_id(path: str) -> str:
    """Return deterministic ID for a file node."""
    return f"file:{path}"


def make_symbol_node_id(path: str, name: str, line: int, column: int) -> str:
    """Return deterministic ID for a symbol node."""
    return f"symbol:{path}:{name}:{line}:{column}"


def make_arch_node_id(path: str, role: ArchitectureRole | str) -> str:
    """Return deterministic ID for an architectural role node."""
    role_str = role.value if isinstance(role, ArchitectureRole) else str(role)
    return f"architecture:{path}:{role_str.upper()}"


def make_external_node_id(module_path: str) -> str:
    """Return deterministic ID for an external dependency node."""
    return f"external:{module_path}"


def make_unresolved_node_id(module_path: str) -> str:
    """Return deterministic ID for an unresolved reference node."""
    return f"unresolved:{module_path}"


def make_api_endpoint_node_id(method: str, path: str) -> str:
    """Return deterministic ID for an API endpoint node."""
    norm_path = "/" + path.strip("/") if path.strip("/") else "/"
    return f"endpoint:{method.upper()}:{norm_path}"


def make_database_model_node_id(model_name: str, path: str | None = None) -> str:
    """Return deterministic ID for a database model node."""
    if path:
        return f"db_model:{path}:{model_name}"
    return f"db_model:{model_name}"


def make_edge_id(
    source_id: str,
    edge_type: EdgeType,
    target_id: str,
    line: int | None = None,
    column: int | None = None,
) -> str:
    """Return deterministic unique ID for a directed edge."""
    base = f"edge:{source_id}->{edge_type.value}->{target_id}"
    if line is not None and column is not None:
        return f"{base}@{line}:{column}"
    return base


# ---------------------------------------------------------------------------
# Immutable Graph Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GraphNode:
    """
    An immutable node in the CodeGraph.

    Attributes:
        id:        Stable, deterministic, unique identifier.
        node_type: Semantic category (FILE, FUNCTION, SERVICE, etc.).
        label:     Human-readable display name.
        metadata:  Sorted key-value pairs representing node attributes.
    """

    id: str
    node_type: NodeType
    label: str
    metadata: tuple[tuple[str, str], ...] = ()

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        """Look up a metadata property by key."""
        for k, v in self.metadata:
            if k == key:
                return v
        return default

    @property
    def metadata_dict(self) -> dict[str, str]:
        """Return metadata as a dictionary view."""
        return dict(self.metadata)


@dataclass(frozen=True)
class GraphEdge:
    """
    An immutable directed edge in the CodeGraph.

    Attributes:
        id:        Deterministic unique identifier.
        edge_type: Semantic category (CONTAINS, IMPORTS, CALLS, etc.).
        source_id: ID of the originating node.
        target_id: ID of the destination node.
        metadata:  Sorted key-value pairs representing edge attributes.
    """

    id: str
    edge_type: EdgeType
    source_id: str
    target_id: str
    metadata: tuple[tuple[str, str], ...] = ()

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        """Look up an edge metadata property by key."""
        for k, v in self.metadata:
            if k == key:
                return v
        return default

    @property
    def metadata_dict(self) -> dict[str, str]:
        """Return metadata as a dictionary view."""
        return dict(self.metadata)


@dataclass(frozen=True)
class CodeGraph:
    """
    An immutable, deterministic in-memory code graph.

    Contains all nodes and edges from repository analysis, sorted deterministically
    with fast internal lookup indexes for $O(1)$ read-only queries.
    """

    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    _node_index: dict[str, GraphNode] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )
    _type_index: dict[NodeType, tuple[GraphNode, ...]] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )
    _outgoing_index: dict[str, tuple[GraphEdge, ...]] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )
    _incoming_index: dict[str, tuple[GraphEdge, ...]] = field(
        default_factory=dict, compare=False, hash=False, repr=False
    )

    def __post_init__(self) -> None:
        # 1. Sort nodes deterministically by id
        sorted_nodes = tuple(sorted(self.nodes, key=lambda n: n.id))
        object.__setattr__(self, "nodes", sorted_nodes)

        # 2. Validate node uniqueness and build node index
        node_idx: dict[str, GraphNode] = {}
        type_acc: dict[NodeType, list[GraphNode]] = {}
        for node in sorted_nodes:
            if node.id in node_idx:
                raise GraphValidationError(f"Duplicate node ID in CodeGraph: '{node.id}'")
            node_idx[node.id] = node
            type_acc.setdefault(node.node_type, []).append(node)

        # 3. Sort edges deterministically by (source_id, edge_type, target_id, id)
        sorted_edges = tuple(
            sorted(
                self.edges,
                key=lambda e: (e.source_id, e.edge_type.value, e.target_id, e.id),
            )
        )
        object.__setattr__(self, "edges", sorted_edges)

        # 4. Validate edge integrity and build adjacency indexes
        out_acc: dict[str, list[GraphEdge]] = {}
        in_acc: dict[str, list[GraphEdge]] = {}
        for edge in sorted_edges:
            if edge.source_id not in node_idx:
                raise GraphValidationError(
                    f"Edge source not found in graph nodes: '{edge.source_id}' (edge id: '{edge.id}')"
                )
            if edge.target_id not in node_idx:
                raise GraphValidationError(
                    f"Edge target not found in graph nodes: '{edge.target_id}' (edge id: '{edge.id}')"
                )
            out_acc.setdefault(edge.source_id, []).append(edge)
            in_acc.setdefault(edge.target_id, []).append(edge)

        # 5. Populate immutable index fields
        object.__setattr__(self, "_node_index", node_idx)
        object.__setattr__(
            self,
            "_type_index",
            {k: tuple(v) for k, v in type_acc.items()},
        )
        object.__setattr__(
            self,
            "_outgoing_index",
            {k: tuple(v) for k, v in out_acc.items()},
        )
        object.__setattr__(
            self,
            "_incoming_index",
            {k: tuple(v) for k, v in in_acc.items()},
        )

    # -----------------------------------------------------------------------
    # Read-Only Query Methods
    # -----------------------------------------------------------------------

    def get_node(self, node_id: str) -> GraphNode | None:
        """Return the GraphNode with matching ID, or None if not found."""
        return self._node_index.get(node_id)

    def has_node(self, node_id: str) -> bool:
        """Return True if a node with this ID exists in the graph."""
        return node_id in self._node_index

    def get_nodes_by_type(self, node_type: NodeType) -> tuple[GraphNode, ...]:
        """Return all nodes of the specified NodeType."""
        return self._type_index.get(node_type, ())

    def get_outgoing_edges(self, node_id: str) -> tuple[GraphEdge, ...]:
        """Return all directed edges originating from node_id."""
        return self._outgoing_index.get(node_id, ())

    def get_incoming_edges(self, node_id: str) -> tuple[GraphEdge, ...]:
        """Return all directed edges terminating at node_id."""
        return self._incoming_index.get(node_id, ())

    def get_neighbors(
        self, node_id: str, direction: str = "outgoing"
    ) -> tuple[GraphNode, ...]:
        """
        Return neighbor nodes in the specified direction ('outgoing', 'incoming', or 'both').
        """
        result_ids: list[str] = []
        if direction in ("outgoing", "both"):
            for e in self.get_outgoing_edges(node_id):
                if e.target_id not in result_ids:
                    result_ids.append(e.target_id)
        if direction in ("incoming", "both"):
            for e in self.get_incoming_edges(node_id):
                if e.source_id not in result_ids:
                    result_ids.append(e.source_id)

        return tuple(
            self._node_index[nid]
            for nid in sorted(result_ids)
            if nid in self._node_index
        )


# ---------------------------------------------------------------------------
# Standalone Read-Only Query Helpers
# ---------------------------------------------------------------------------


def get_node(graph: CodeGraph, node_id: str) -> GraphNode | None:
    """Return the node with the given ID from the graph, or None."""
    return graph.get_node(node_id)


def get_nodes_by_type(graph: CodeGraph, node_type: NodeType) -> tuple[GraphNode, ...]:
    """Return all nodes matching node_type from the graph."""
    return graph.get_nodes_by_type(node_type)


def get_outgoing_edges(graph: CodeGraph, node_id: str) -> tuple[GraphEdge, ...]:
    """Return all outgoing edges from the node with the given ID."""
    return graph.get_outgoing_edges(node_id)


def get_incoming_edges(graph: CodeGraph, node_id: str) -> tuple[GraphEdge, ...]:
    """Return all incoming edges pointing to the node with the given ID."""
    return graph.get_incoming_edges(node_id)


# ---------------------------------------------------------------------------
# Graph Construction Implementation
# ---------------------------------------------------------------------------


def _to_sorted_metadata(data: dict[str, Any] | Iterable[tuple[str, Any]]) -> tuple[tuple[str, str], ...]:
    """Normalize and deterministically sort key-value metadata pairs."""
    items = data.items() if isinstance(data, dict) else data
    return tuple(sorted((str(k), str(v)) for k, v in items if v is not None))


def build_code_graph(
    files: Sequence[FileInfo] | None = None,
    symbols: Sequence[Symbol] | None = None,
    relationships: Sequence[Relationship] | None = None,
    resolved_relationships: Sequence[ResolvedRelationship] | None = None,
    architecture: RepositoryArchitecture | Sequence[FileClassification] | None = None,
    *,
    repo_name: str = "root",
    include_repo_node: bool = True,
    validate: bool = True,
    routes: Any = None,
) -> CodeGraph:
    """
    Construct an immutable, deterministic CodeGraph from M1–M6 analysis outputs.

    Parameters:
        files:                   Discovered FileInfo objects from M1.
        symbols:                 Extracted Symbol objects from M3.
        relationships:           Raw Relationship objects from M4.
        resolved_relationships:  Resolved import relationships from M5.
        architecture:            RepositoryArchitecture or FileClassifications from M6.
        repo_name:               Name of the repository root node.
        include_repo_node:       Whether to add the root REPOSITORY node.
        validate:                Whether to perform construction-time validation.

    Returns:
        An immutable CodeGraph with deterministic node and edge orderings.

    Raises:
        GraphValidationError: If structural or reference validation fails.
    """
    files_list = list(files or [])
    symbols_list = list(symbols or [])
    rels_list = list(relationships or [])
    resolved_list = list(resolved_relationships or [])

    nodes_map: dict[str, GraphNode] = {}
    edges_map: dict[str, GraphEdge] = {}

    def add_node(node: GraphNode) -> None:
        if node.id in nodes_map:
            existing = nodes_map[node.id]
            if existing != node:
                raise GraphValidationError(
                    f"Conflicting duplicate node ID detected: '{node.id}'"
                )
            return
        nodes_map[node.id] = node

    def add_edge(edge: GraphEdge) -> None:
        edges_map[edge.id] = edge

    # -----------------------------------------------------------------------
    # 1. Root Repository Node
    # -----------------------------------------------------------------------
    repo_node_id = make_repo_node_id(repo_name)
    if include_repo_node:
        repo_node = GraphNode(
            id=repo_node_id,
            node_type=NodeType.REPOSITORY,
            label=repo_name,
            metadata=(("repo_name", repo_name),),
        )
        add_node(repo_node)

    # -----------------------------------------------------------------------
    # 2. File Nodes & Repo Containment
    # -----------------------------------------------------------------------
    known_file_paths: set[str] = set()
    for file_info in files_list:
        if file_info.path in known_file_paths:
            raise GraphValidationError(f"Duplicate file path detected: '{file_info.path}'")
        known_file_paths.add(file_info.path)

        file_id = make_file_node_id(file_info.path)
        meta = _to_sorted_metadata(
            {
                "extension": file_info.extension,
                "language": file_info.language,
                "path": file_info.path,
                "size": file_info.size,
            }
        )
        file_node = GraphNode(
            id=file_id,
            node_type=NodeType.FILE,
            label=posixpath.basename(file_info.path),
            metadata=meta,
        )
        add_node(file_node)

        if include_repo_node:
            edge_id = make_edge_id(repo_node_id, EdgeType.CONTAINS, file_id)
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.CONTAINS,
                    source_id=repo_node_id,
                    target_id=file_id,
                )
            )

    # -----------------------------------------------------------------------
    # 3. Symbol Nodes & Containment Hierarchy
    # -----------------------------------------------------------------------
    # Index symbols by path and name for containment and call resolution
    symbols_by_file: dict[str, list[Symbol]] = {}
    symbol_node_id_lookup: dict[tuple[str, str, int, int], str] = {}

    for sym in symbols_list:
        if validate and files_list and sym.path not in known_file_paths:
            raise GraphValidationError(
                f"Symbol '{sym.name}' belongs to unknown file: '{sym.path}'"
            )

        sym_id = make_symbol_node_id(
            sym.path, sym.name, sym.start.line, sym.start.column
        )
        if sym_id in nodes_map:
            raise GraphValidationError(f"Duplicate symbol node ID detected: '{sym_id}'")

        node_type = _SYMBOL_KIND_TO_NODE_TYPE.get(sym.kind, NodeType.UNKNOWN)
        meta_dict: dict[str, Any] = {
            "end_col": sym.end.column,
            "end_line": sym.end.line,
            "kind": sym.kind.value,
            "name": sym.name,
            "path": sym.path,
            "start_col": sym.start.column,
            "start_line": sym.start.line,
        }
        if sym.parent:
            meta_dict["parent"] = sym.parent

        sym_node = GraphNode(
            id=sym_id,
            node_type=node_type,
            label=sym.name,
            metadata=_to_sorted_metadata(meta_dict),
        )
        add_node(sym_node)
        symbols_by_file.setdefault(sym.path, []).append(sym)
        symbol_node_id_lookup[(sym.path, sym.name, sym.start.line, sym.start.column)] = sym_id

    # Build containment edges for symbols
    for sym in symbols_list:
        child_id = make_symbol_node_id(
            sym.path, sym.name, sym.start.line, sym.start.column
        )
        if sym.parent is None:
            # Contained directly by the file
            file_id = make_file_node_id(sym.path)
            if file_id in nodes_map:
                edge_id = make_edge_id(file_id, EdgeType.CONTAINS, child_id)
                add_edge(
                    GraphEdge(
                        id=edge_id,
                        edge_type=EdgeType.CONTAINS,
                        source_id=file_id,
                        target_id=child_id,
                    )
                )
        else:
            # Contained by parent symbol in the same file
            file_syms = symbols_by_file.get(sym.path, [])
            candidates = [s for s in file_syms if s.name == sym.parent]

            if not candidates:
                if validate:
                    raise GraphValidationError(
                        f"Parent symbol '{sym.parent}' not found for symbol '{sym.name}' in '{sym.path}'"
                    )
                continue

            # If multiple symbols match parent name, find enclosing scope
            parent_sym = candidates[0]
            if len(candidates) > 1:
                enclosing = [
                    s
                    for s in candidates
                    if (s.start.line < sym.start.line or (s.start.line == sym.start.line and s.start.column <= sym.start.column))
                    and (sym.end.line < s.end.line or (sym.end.line == s.end.line and sym.end.column <= s.end.column))
                ]
                if enclosing:
                    parent_sym = enclosing[0]

            parent_id = make_symbol_node_id(
                parent_sym.path,
                parent_sym.name,
                parent_sym.start.line,
                parent_sym.start.column,
            )
            edge_id = make_edge_id(parent_id, EdgeType.CONTAINS, child_id)
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.CONTAINS,
                    source_id=parent_id,
                    target_id=child_id,
                )
            )

    # -----------------------------------------------------------------------
    # 4. Resolved Imports (M5)
    # -----------------------------------------------------------------------
    # Track cross-file import mappings for call and reference resolution
    imported_symbols_by_file: dict[str, dict[str, SymbolId]] = {}

    for res in resolved_list:
        src_rel = res.source_relationship
        src_file_id = make_file_node_id(src_rel.source_path)

        if res.status == ResolutionStatus.RESOLVED and res.target_symbol_id:
            # 1. Edge from source file to target symbol
            tgt_sym = res.target_symbol_id
            tgt_sym_id = make_symbol_node_id(
                tgt_sym.path, tgt_sym.name, tgt_sym.line, tgt_sym.column
            )
            edge_id = make_edge_id(
                src_file_id,
                EdgeType.IMPORTS,
                tgt_sym_id,
                src_rel.source_position.line,
                src_rel.source_position.column,
            )
            meta = _to_sorted_metadata(
                {
                    "alias": src_rel.alias,
                    "is_default": src_rel.is_default,
                    "module_path": src_rel.module_path,
                    "status": res.status.value,
                    "target_name": src_rel.target_name,
                    "target_path": res.target_path,
                }
            )
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.IMPORTS,
                    source_id=src_file_id,
                    target_id=tgt_sym_id,
                    metadata=meta,
                )
            )

            # 2. Also ensure a resolved cross-file import edge exists
            if res.target_path:
                tgt_file_id = make_file_node_id(res.target_path)
                file_edge_id = make_edge_id(
                    src_file_id,
                    EdgeType.IMPORTS,
                    tgt_file_id,
                )
                if file_edge_id not in edges_map:
                    add_edge(
                        GraphEdge(
                            id=file_edge_id,
                            edge_type=EdgeType.IMPORTS,
                            source_id=src_file_id,
                            target_id=tgt_file_id,
                            metadata=_to_sorted_metadata(
                                {"status": "resolved", "target_path": res.target_path}
                            ),
                        )
                    )

            # Register in imported symbol lookup for calls/references
            import_name = src_rel.alias or src_rel.target_name
            if import_name:
                imported_symbols_by_file.setdefault(src_rel.source_path, {})[import_name] = tgt_sym

        elif res.status == ResolutionStatus.RESOLVED_FILE and res.target_path:
            tgt_file_id = make_file_node_id(res.target_path)
            edge_id = make_edge_id(
                src_file_id,
                EdgeType.IMPORTS,
                tgt_file_id,
                src_rel.source_position.line,
                src_rel.source_position.column,
            )
            meta = _to_sorted_metadata(
                {
                    "is_default": src_rel.is_default,
                    "is_namespace": src_rel.is_namespace,
                    "module_path": src_rel.module_path,
                    "status": res.status.value,
                    "target_path": res.target_path,
                }
            )
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.IMPORTS,
                    source_id=src_file_id,
                    target_id=tgt_file_id,
                    metadata=meta,
                )
            )

        elif res.status == ResolutionStatus.EXTERNAL:
            module_name = src_rel.module_path or src_rel.target_name
            ext_id = make_external_node_id(module_name)
            if ext_id not in nodes_map:
                add_node(
                    GraphNode(
                        id=ext_id,
                        node_type=NodeType.EXTERNAL,
                        label=module_name,
                        metadata=_to_sorted_metadata(
                            {"module_path": module_name, "status": "external"}
                        ),
                    )
                )
            edge_id = make_edge_id(
                src_file_id,
                EdgeType.IMPORTS,
                ext_id,
                src_rel.source_position.line,
                src_rel.source_position.column,
            )
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.IMPORTS,
                    source_id=src_file_id,
                    target_id=ext_id,
                    metadata=_to_sorted_metadata(
                        {
                            "module_path": module_name,
                            "status": "external",
                            "target_name": src_rel.target_name,
                        }
                    ),
                )
            )

        elif res.status == ResolutionStatus.UNRESOLVED:
            module_name = src_rel.module_path or src_rel.target_name
            unres_id = make_unresolved_node_id(module_name)
            if unres_id not in nodes_map:
                add_node(
                    GraphNode(
                        id=unres_id,
                        node_type=NodeType.UNRESOLVED,
                        label=module_name,
                        metadata=_to_sorted_metadata(
                            {"module_path": module_name, "status": "unresolved"}
                        ),
                    )
                )
            edge_id = make_edge_id(
                src_file_id,
                EdgeType.IMPORTS,
                unres_id,
                src_rel.source_position.line,
                src_rel.source_position.column,
            )
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.IMPORTS,
                    source_id=src_file_id,
                    target_id=unres_id,
                    metadata=_to_sorted_metadata(
                        {
                            "module_path": module_name,
                            "status": "unresolved",
                            "target_name": src_rel.target_name,
                        }
                    ),
                )
            )

    # -----------------------------------------------------------------------
    # 5. Raw Relationships (EXPORTS, CALLS, REFERENCES) (M4)
    # -----------------------------------------------------------------------
    def find_enclosing_symbol_id(path: str, pos: Position) -> str:
        file_syms = symbols_by_file.get(path, [])
        enclosing = [
            s
            for s in file_syms
            if (s.start.line < pos.line or (s.start.line == pos.line and s.start.column <= pos.column))
            and (pos.line < s.end.line or (pos.line == s.end.line and pos.column <= s.end.column))
        ]
        if enclosing:
            # Deepest enclosing symbol (highest start line/col)
            deepest = sorted(
                enclosing,
                key=lambda s: (s.start.line, s.start.column),
                reverse=True,
            )[0]
            return make_symbol_node_id(
                deepest.path, deepest.name, deepest.start.line, deepest.start.column
            )
        return make_file_node_id(path)

    for rel in rels_list:
        src_file_id = make_file_node_id(rel.source_path)

        if rel.kind == RelationshipKind.EXPORTS:
            # Find the symbol in the same file that is being exported
            file_syms = symbols_by_file.get(rel.source_path, [])
            matching_syms = [s for s in file_syms if s.name == rel.target_name]
            if matching_syms:
                tgt_sym = matching_syms[0]
                tgt_sym_id = make_symbol_node_id(
                    tgt_sym.path, tgt_sym.name, tgt_sym.start.line, tgt_sym.start.column
                )
                edge_id = make_edge_id(
                    src_file_id,
                    EdgeType.EXPORTS,
                    tgt_sym_id,
                    rel.source_position.line,
                    rel.source_position.column,
                )
                add_edge(
                    GraphEdge(
                        id=edge_id,
                        edge_type=EdgeType.EXPORTS,
                        source_id=src_file_id,
                        target_id=tgt_sym_id,
                        metadata=_to_sorted_metadata(
                            {
                                "alias": rel.alias,
                                "is_default": rel.is_default,
                                "target_name": rel.target_name,
                            }
                        ),
                    )
                )

        elif rel.kind in (RelationshipKind.CALLS, RelationshipKind.REFERENCES):
            # Determine source node (enclosing symbol or file)
            src_node_id = find_enclosing_symbol_id(rel.source_path, rel.source_position)

            # Resolve target symbol deterministically
            target_node_id: str | None = None
            target_name = rel.target_name

            # Case A: intra-file symbol
            file_syms = symbols_by_file.get(rel.source_path, [])
            matching_local = [s for s in file_syms if s.name == target_name]
            if matching_local:
                lsym = matching_local[0]
                target_node_id = make_symbol_node_id(
                    lsym.path, lsym.name, lsym.start.line, lsym.start.column
                )

            # Case B: imported symbol
            if target_node_id is None:
                file_imports = imported_symbols_by_file.get(rel.source_path, {})
                if target_name in file_imports:
                    isym = file_imports[target_name]
                    target_node_id = make_symbol_node_id(
                        isym.path, isym.name, isym.line, isym.column
                    )

            # Case C: object method call (e.g. authService.authenticateUser)
            if target_node_id is None and "." in target_name:
                parts = target_name.split(".", 1)
                obj_name, method_name = parts[0], parts[1]
                file_imports = imported_symbols_by_file.get(rel.source_path, {})
                if obj_name in file_imports:
                    target_file_path = file_imports[obj_name].path
                    target_file_syms = symbols_by_file.get(target_file_path, [])
                    matching_methods = [
                        s for s in target_file_syms if s.name == method_name
                    ]
                    if matching_methods:
                        msym = matching_methods[0]
                        target_node_id = make_symbol_node_id(
                            msym.path, msym.name, msym.start.line, msym.start.column
                        )

            # Only create edge if the target can be reliably identified
            if target_node_id is not None and target_node_id in nodes_map:
                edge_type = (
                    EdgeType.CALLS
                    if rel.kind == RelationshipKind.CALLS
                    else EdgeType.REFERENCES
                )
                edge_id = make_edge_id(
                    src_node_id,
                    edge_type,
                    target_node_id,
                    rel.source_position.line,
                    rel.source_position.column,
                )
                add_edge(
                    GraphEdge(
                        id=edge_id,
                        edge_type=edge_type,
                        source_id=src_node_id,
                        target_id=target_node_id,
                        metadata=_to_sorted_metadata({"target_name": target_name}),
                    )
                )

    # -----------------------------------------------------------------------
    # 6. Architectural Integration (M6)
    # -----------------------------------------------------------------------
    file_classifications: Sequence[FileClassification] = ()
    arch_relationships: Sequence[ArchitecturalRelationship] = ()

    if isinstance(architecture, RepositoryArchitecture):
        file_classifications = architecture.file_classifications
        arch_relationships = architecture.architectural_relationships
    elif architecture is not None:
        file_classifications = list(architecture)

    for fc in file_classifications:
        for classification in fc.classifications:
            arch_node_id = make_arch_node_id(classification.path, classification.role)
            node_type = _ROLE_TO_NODE_TYPE.get(
                classification.role, NodeType.UNKNOWN
            )
            label = f"{posixpath.basename(classification.path)} ({classification.role.value.upper()})"
            meta = _to_sorted_metadata(
                {
                    "layer": classification.layer.value,
                    "path": classification.path,
                    "role": classification.role.value,
                }
            )
            add_node(
                GraphNode(
                    id=arch_node_id,
                    node_type=node_type,
                    label=label,
                    metadata=meta,
                )
            )

            file_id = make_file_node_id(classification.path)
            if file_id in nodes_map:
                class_edge_id = make_edge_id(
                    file_id, EdgeType.CLASSIFIED_AS, arch_node_id
                )
                add_edge(
                    GraphEdge(
                        id=class_edge_id,
                        edge_type=EdgeType.CLASSIFIED_AS,
                        source_id=file_id,
                        target_id=arch_node_id,
                        metadata=_to_sorted_metadata(
                            {
                                "layer": classification.layer.value,
                                "role": classification.role.value,
                            }
                        ),
                    )
                )

    for ar in arch_relationships:
        src_arch_id = make_arch_node_id(ar.source_path, ar.source_role)
        tgt_arch_id = make_arch_node_id(ar.target_path, ar.target_role)

        if src_arch_id in nodes_map and tgt_arch_id in nodes_map:
            edge_id = make_edge_id(src_arch_id, EdgeType.DEPENDS_ON, tgt_arch_id)
            add_edge(
                GraphEdge(
                    id=edge_id,
                    edge_type=EdgeType.DEPENDS_ON,
                    source_id=src_arch_id,
                    target_id=tgt_arch_id,
                    metadata=_to_sorted_metadata(
                        {
                            "pattern": ar.pattern,
                            "source_role": ar.source_role.value,
                            "target_role": ar.target_role.value,
                        }
                    ),
                )
            )

        src_file_id = make_file_node_id(ar.source_path)
        tgt_file_id = make_file_node_id(ar.target_path)
        if src_file_id in nodes_map and tgt_file_id in nodes_map:
            file_dep_id = make_edge_id(
                src_file_id, EdgeType.DEPENDS_ON, tgt_file_id
            )
            if file_dep_id not in edges_map:
                add_edge(
                    GraphEdge(
                        id=file_dep_id,
                        edge_type=EdgeType.DEPENDS_ON,
                        source_id=src_file_id,
                        target_id=tgt_file_id,
                        metadata=_to_sorted_metadata(
                            {
                                "pattern": ar.pattern,
                                "source_role": ar.source_role.value,
                                "target_role": ar.target_role.value,
                            }
                        ),
                    )
                )

    # -----------------------------------------------------------------------
    # 7. API & Route Map Integration (Section 5)
    # -----------------------------------------------------------------------
    routes_list_to_add: Sequence[Any] = ()
    if routes is not None:
        if hasattr(routes, "routes"):
            routes_list_to_add = routes.routes
        elif isinstance(routes, (list, tuple)):
            routes_list_to_add = routes

    for r in routes_list_to_add:
        # 1. API_ENDPOINT Node
        ep_id = make_api_endpoint_node_id(r.http_method, r.http_endpoint)
        if ep_id not in nodes_map:
            add_node(
                GraphNode(
                    id=ep_id,
                    node_type=NodeType.API_ENDPOINT,
                    label=f"{r.http_method} {r.http_endpoint}",
                    metadata=_to_sorted_metadata(
                        {
                            "endpoint": r.http_endpoint,
                            "method": r.http_method,
                            "path": r.route_path,
                            "source_file": r.source_file,
                            "start_line": r.start_line,
                            "status": r.status,
                        }
                    ),
                )
            )

        # 2. Edge: Route source file -> API_ENDPOINT (ROUTES_TO)
        src_file_id = make_file_node_id(r.source_file)
        if src_file_id in nodes_map:
            routes_to_edge_id = make_edge_id(
                src_file_id, EdgeType.ROUTES_TO, ep_id, r.start_line, r.start_column
            )
            if routes_to_edge_id not in edges_map:
                add_edge(
                    GraphEdge(
                        id=routes_to_edge_id,
                        edge_type=EdgeType.ROUTES_TO,
                        source_id=src_file_id,
                        target_id=ep_id,
                        metadata=_to_sorted_metadata(
                            {"method": r.http_method, "endpoint": r.http_endpoint}
                        ),
                    )
                )

        # 3. Controller node & HANDLED_BY edge
        ctrl_node_id = None
        if r.controller and r.controller.name != "unresolved":
            if r.controller.file_path and r.controller.start_line:
                cand_sym_id = make_symbol_node_id(
                    r.controller.file_path,
                    r.controller.function_name,
                    r.controller.start_line,
                    r.controller.start_column or 0,
                )
                if cand_sym_id in nodes_map:
                    ctrl_node_id = cand_sym_id

            if not ctrl_node_id:
                ctrl_node_id = f"controller:{r.controller.file_path or r.source_file}:{r.controller.name}"
                if ctrl_node_id not in nodes_map:
                    add_node(
                        GraphNode(
                            id=ctrl_node_id,
                            node_type=NodeType.CONTROLLER,
                            label=r.controller.name,
                            metadata=_to_sorted_metadata(
                                {
                                    "file_path": r.controller.file_path or r.source_file,
                                    "function_name": r.controller.function_name,
                                    "name": r.controller.name,
                                    "status": r.controller.status,
                                }
                            ),
                        )
                    )

            handled_by_edge_id = make_edge_id(ep_id, EdgeType.HANDLED_BY, ctrl_node_id)
            if handled_by_edge_id not in edges_map:
                add_edge(
                    GraphEdge(
                        id=handled_by_edge_id,
                        edge_type=EdgeType.HANDLED_BY,
                        source_id=ep_id,
                        target_id=ctrl_node_id,
                        metadata=_to_sorted_metadata({"controller": r.controller.name}),
                    )
                )

        # 4. Middleware nodes & USES_MIDDLEWARE edges
        for mw in r.middleware:
            mw_node_id = f"middleware:{mw.source_file or 'inline'}:{mw.name}"
            if mw_node_id not in nodes_map:
                add_node(
                    GraphNode(
                        id=mw_node_id,
                        node_type=NodeType.MIDDLEWARE,
                        label=mw.name,
                        metadata=_to_sorted_metadata(
                            {
                                "is_inline": mw.is_inline,
                                "name": mw.name,
                                "source_file": mw.source_file or r.source_file,
                                "status": mw.status,
                            }
                        ),
                    )
                )
            mw_edge_id = make_edge_id(ep_id, EdgeType.USES_MIDDLEWARE, mw_node_id)
            if mw_edge_id not in edges_map:
                add_edge(
                    GraphEdge(
                        id=mw_edge_id,
                        edge_type=EdgeType.USES_MIDDLEWARE,
                        source_id=ep_id,
                        target_id=mw_node_id,
                        metadata=_to_sorted_metadata({"middleware": mw.name}),
                    )
                )

        # 5. Service nodes & CALLS_SERVICE edges (from controller)
        if ctrl_node_id:
            for svc in r.service_dependencies:
                svc_node_id = f"service:{svc.file_path or 'unresolved'}:{svc.service_name}"
                if svc_node_id not in nodes_map:
                    add_node(
                        GraphNode(
                            id=svc_node_id,
                            node_type=NodeType.SERVICE,
                            label=svc.service_name,
                            metadata=_to_sorted_metadata(
                                {
                                    "file_path": svc.file_path or "",
                                    "service_name": svc.service_name,
                                    "status": svc.status,
                                }
                            ),
                        )
                    )
                svc_edge_id = make_edge_id(ctrl_node_id, EdgeType.CALLS_SERVICE, svc_node_id)
                if svc_edge_id not in edges_map:
                    add_edge(
                        GraphEdge(
                            id=svc_edge_id,
                            edge_type=EdgeType.CALLS_SERVICE,
                            source_id=ctrl_node_id,
                            target_id=svc_node_id,
                            metadata=_to_sorted_metadata(
                                {
                                    "method": svc.method_name or "",
                                    "service": svc.service_name,
                                }
                            ),
                        )
                    )

                # 6. Model nodes & ACCESSES_MODEL edges (from service)
                for mdl in r.model_dependencies:
                    mdl_node_id = make_database_model_node_id(mdl.model_name, mdl.file_path)
                    if mdl_node_id not in nodes_map:
                        add_node(
                            GraphNode(
                                id=mdl_node_id,
                                node_type=NodeType.DATABASE_MODEL,
                                label=mdl.model_name,
                                metadata=_to_sorted_metadata(
                                    {
                                        "file_path": mdl.file_path or "",
                                        "model_name": mdl.model_name,
                                        "operation": mdl.operation or "",
                                        "status": mdl.status,
                                    }
                                ),
                            )
                        )
                    mdl_edge_id = make_edge_id(svc_node_id, EdgeType.ACCESSES_MODEL, mdl_node_id)
                    if mdl_edge_id not in edges_map:
                        add_edge(
                            GraphEdge(
                                id=mdl_edge_id,
                                edge_type=EdgeType.ACCESSES_MODEL,
                                source_id=svc_node_id,
                                target_id=mdl_node_id,
                                metadata=_to_sorted_metadata(
                                    {
                                        "model": mdl.model_name,
                                        "operation": mdl.operation or "",
                                    }
                                ),
                            )
                        )

    # -----------------------------------------------------------------------
    # 8. Final Validation & CodeGraph Construction
    # -----------------------------------------------------------------------
    return CodeGraph(
        nodes=tuple(nodes_map.values()),
        edges=tuple(edges_map.values()),
    )
