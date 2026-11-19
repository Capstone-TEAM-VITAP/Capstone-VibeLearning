"""
repository/routes.py

Automatic HTTP API Endpoint Discovery, Controller Mapping, and Service/Model Tracing.
Supports Express.js routing patterns via Tree-sitter AST traversal.

Extracts:
- HTTP method (GET, POST, PUT, DELETE, PATCH, etc.)
- Route path & normalized HTTP endpoint
- Router mounting & hierarchical base path resolution
- Middleware chains (router-level & route-level)
- Controller resolution (named imports, object exports, class methods, inline)
- Service dependency tracing
- Database / Model dependency tracing
- Step-by-step Execution Flow
- Deterministic CodeGraph integration
"""

from __future__ import annotations

import logging
import posixpath
import re
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Iterable, Sequence

logger = logging.getLogger(__name__)

from .architecture import ArchitectureRole, RepositoryArchitecture
from .models import FileInfo
from .parser import Position
from .relationships import Relationship, RelationshipKind
from .resolver import ResolutionStatus, ResolvedRelationship, SymbolId
from .symbols import Symbol, SymbolKind


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MiddlewareInfo:
    """Represents a middleware function invoked in the route pipeline."""

    name: str
    source_file: str | None = None
    line: int | None = None
    column: int | None = None
    is_inline: bool = False
    status: str = "resolved"  # "resolved", "inline", "external", "unresolved"


@dataclass(frozen=True)
class ControllerInfo:
    """Represents the resolved controller handler for a route."""

    name: str
    function_name: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    start_column: int | None = None
    parameters: tuple[str, ...] = ()
    called_functions: tuple[str, ...] = ()
    status: str = "resolved"  # "resolved", "inline", "unresolved", "external"


@dataclass(frozen=True)
class ServiceDependency:
    """Represents a service called by the controller or route handler."""

    service_name: str
    method_name: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    status: str = "confirmed"  # "confirmed", "unresolved"


@dataclass(frozen=True)
class ModelDependency:
    """Represents a database model / ORM entity accessed during request handling."""

    model_name: str
    operation: str | None = None  # e.g. "findOne", "findUnique", "create", "query"
    file_path: str | None = None
    status: str = "confirmed"  # "confirmed", "inferred", "unresolved"


@dataclass(frozen=True)
class FlowStep:
    """Represents a discrete step in the request-to-database execution flow."""

    step_type: str  # "route", "middleware", "controller", "service", "model", "database"
    label: str
    file_path: str | None = None
    line: int | None = None
    description: str | None = None


@dataclass(frozen=True)
class DiscoveredRoute:
    """Complete static analysis representation of an HTTP endpoint."""

    id: str
    http_method: str
    route_path: str
    http_endpoint: str
    source_file: str
    start_line: int
    end_line: int
    start_column: int
    router_base_path: str
    controller: ControllerInfo
    middleware: tuple[MiddlewareInfo, ...] = ()
    service_dependencies: tuple[ServiceDependency, ...] = ()
    model_dependencies: tuple[ModelDependency, ...] = ()
    execution_flow: tuple[FlowStep, ...] = ()
    status: str = "resolved"  # "resolved", "unresolved", "inline", "partial"


@dataclass(frozen=True)
class RouteMapSummary:
    """Aggregated statistics for all discovered endpoints."""

    total_endpoints: int
    get_count: int
    post_count: int
    put_patch_count: int
    delete_count: int
    other_count: int
    unresolved_count: int
    controllers_count: int
    services_count: int
    models_count: int


@dataclass(frozen=True)
class RouteMapResult:
    """Top-level container for repository route intelligence."""

    routes: tuple[DiscoveredRoute, ...]
    summary: RouteMapSummary


# ---------------------------------------------------------------------------
# Tree-sitter Parser Helper
# ---------------------------------------------------------------------------


@lru_cache(maxsize=None)
def _get_js_parser() -> object:
    import tree_sitter_javascript as tsjs
    from tree_sitter import Language, Parser

    return Parser(Language(tsjs.language()))


def _node_text(node: object | None) -> str:
    if node is None:
        return ""
    raw = getattr(node, "text", None)
    return raw.decode("utf-8") if raw else ""


def _extract_string_literal(node: object | None) -> str | None:
    """Extract clean string value from a string or template_string AST node."""
    if node is None:
        return None
    ntype = getattr(node, "type", "")
    if ntype == "string":
        txt = _node_text(node)
        if (txt.startswith('"') and txt.endswith('"')) or (txt.startswith("'") and txt.endswith("'")):
            return txt[1:-1]
        return txt
    if ntype == "template_string":
        txt = _node_text(node)
        if txt.startswith("`") and txt.endswith("`"):
            return txt[1:-1]
        return txt
    return None


def normalize_endpoint_path(base_path: str, route_path: str) -> str:
    """
    Join and normalize base mount path and route path into a canonical HTTP endpoint.
    Example:
        ("/api/v1/repos", "/:id/sync") -> "/api/v1/repos/:id/sync"
        ("/api/v1", "/") -> "/api/v1"
        ("", "/") -> "/"
    """
    base = base_path.strip()
    route = route_path.strip()

    if not base:
        if not route:
            return "/"
        return "/" + route.lstrip("/") if not route.startswith("/") else route

    # Normalize base
    if not base.startswith("/"):
        base = "/" + base
    base = base.rstrip("/")

    # Normalize route
    if not route or route == "/":
        return base or "/"
    if not route.startswith("/"):
        route = "/" + route

    combined = base + route
    # Replace multiple slashes
    combined = re.sub(r"/+", "/", combined)
    if combined != "/" and combined.endswith("/"):
        combined = combined.rstrip("/")
    return combined


# ---------------------------------------------------------------------------
# AST Function / Method Parameter & Call Extractor
# ---------------------------------------------------------------------------


def _extract_parameters(fn_node: object | None) -> tuple[str, ...]:
    """Extract parameter names from a function/arrow/method AST node."""
    if fn_node is None:
        return ()
    params_node = getattr(fn_node, "child_by_field_name", lambda _: None)("parameters")
    if not params_node:
        return ()
    params: list[str] = []
    for c in getattr(params_node, "named_children", []):
        ctype = getattr(c, "type", "")
        if ctype == "identifier":
            params.append(_node_text(c))
        elif ctype == "assignment_pattern":
            left = getattr(c, "child_by_field_name", lambda _: None)("left")
            if left:
                params.append(_node_text(left))
        elif ctype == "rest_pattern":
            for r in getattr(c, "named_children", []):
                params.append(_node_text(r))
        else:
            txt = _node_text(c)
            if txt:
                params.append(txt)
    return tuple(params)


def _extract_calls_in_node(node: object | None) -> tuple[str, ...]:
    """Extract called function/method names inside a syntax node."""
    if node is None:
        return ()
    calls: list[str] = []

    def _walk(n: object) -> None:
        ntype = getattr(n, "type", "")
        if ntype == "call_expression":
            fn = getattr(n, "child_by_field_name", lambda _: None)("function")
            if fn:
                ftype = getattr(fn, "type", "")
                if ftype == "identifier":
                    calls.append(_node_text(fn))
                elif ftype == "member_expression":
                    calls.append(_node_text(fn))
        for child in getattr(n, "children", []):
            _walk(child)

    _walk(node)
    # Deduplicate preserving order
    seen: set[str] = set()
    result: list[str] = []
    for c in calls:
        if c and c not in seen:
            seen.add(c)
            result.append(c)
    return tuple(result)


# ---------------------------------------------------------------------------
# AST File Cache & Analysis Helpers
# ---------------------------------------------------------------------------


class _SourceAstCache:
    """Caches parsed Tree-sitter syntax trees for repository source files."""

    def __init__(self, repo_path: Path | None, files: Sequence[FileInfo]) -> None:
        self.repo_path = repo_path
        self.files_by_path = {f.path: f for f in files}
        self.trees: dict[str, object] = {}
        self.source_bytes: dict[str, bytes] = {}

    def get_tree(self, rel_path: str) -> object | None:
        if rel_path in self.trees:
            return self.trees[rel_path]
        if not self.repo_path:
            return None
        full_path = self.repo_path / rel_path
        if not full_path.exists() or not full_path.is_file():
            return None
        try:
            raw = full_path.read_bytes()
            parser = _get_js_parser()
            tree = parser.parse(raw)
            self.trees[rel_path] = tree
            self.source_bytes[rel_path] = raw
            return tree
        except Exception:
            return None


# ---------------------------------------------------------------------------
# Main Route Discovery & Dependency Tracing Engine
# ---------------------------------------------------------------------------


class RouteDiscoveryEngine:
    """
    Discovers Express HTTP routes and traces controllers, middleware,
    services, and database models across repository files.
    """

    SUPPORTED_HTTP_METHODS = frozenset(
        {"get", "post", "put", "delete", "patch", "options", "head", "all"}
    )
    IGNORED_CALL_OBJECTS = frozenset(
        {"req", "request", "res", "response", "client", "http", "axios", "supertest", "agent", "cache", "redis", "map", "set", "headers", "params"}
    )

    def __init__(
        self,
        files: Sequence[FileInfo],
        symbols: Sequence[Symbol],
        relationships: Sequence[Relationship],
        resolved_relationships: Sequence[ResolvedRelationship],
        architecture: RepositoryArchitecture | None = None,
        *,
        repo_path: Path | None = None,
    ) -> None:
        self.files = list(files)
        self.symbols = list(symbols)
        self.relationships = list(relationships)
        self.resolved = list(resolved_relationships)
        self.architecture = architecture
        self.repo_path = repo_path

        self.ast_cache = _SourceAstCache(repo_path, files)
        self._symbols_by_file: dict[str, list[Symbol]] = {}
        for s in symbols:
            self._symbols_by_file.setdefault(s.path, []).append(s)

        # Map file classifications
        self._roles_by_file: dict[str, set[ArchitectureRole]] = {}
        if architecture and hasattr(architecture, "file_classifications"):
            for fc in architecture.file_classifications:
                for c in fc.classifications:
                    self._roles_by_file.setdefault(c.path, set()).add(c.role)

        # Import lookups: (source_file, local_identifier) -> (target_file, target_symbol_name)
        self._imports_lookup: dict[tuple[str, str], tuple[str | None, str | None]] = {}
        self._build_imports_lookup()

    def _build_imports_lookup(self) -> None:
        for res in self.resolved:
            rel = res.source_relationship
            local_name = rel.alias or rel.target_name
            target_path = res.target_path
            tgt_sym = res.target_symbol_id.name if res.target_symbol_id else None
            if local_name:
                self._imports_lookup[(rel.source_path, local_name)] = (target_path, tgt_sym)

    def _resolve_import_target(self, file_path: str, identifier: str) -> tuple[str | None, str | None]:
        """Resolve a local identifier in file_path to its target file and symbol."""
        if (file_path, identifier) in self._imports_lookup:
            return self._imports_lookup[(file_path, identifier)]

        # Fallback: inspect raw imports in relationships
        for rel in self.relationships:
            if rel.source_path == file_path and rel.kind == RelationshipKind.IMPORTS:
                local = rel.alias or rel.target_name
                if local == identifier and rel.module_path:
                    # Resolve relative path
                    if rel.module_path.startswith("."):
                        base_dir = posixpath.dirname(file_path)
                        norm = posixpath.normpath(posixpath.join(base_dir, rel.module_path))
                        # Try extensions
                        for ext in ("", ".js", ".jsx", ".ts", ".tsx", "/index.js"):
                            cand = norm + ext
                            if any(f.path == cand for f in self.files):
                                return (cand, rel.target_name)
                    return (rel.module_path, rel.target_name)
        return (None, None)

    # -----------------------------------------------------------------------
    # Step 1: Discover Router Mounts across the repository
    # -----------------------------------------------------------------------

    def discover_router_mounts(self) -> dict[str, list[str]]:
        """
        Detect app.use('/prefix', router) mounts across all files.
        Returns mapping: file_path -> list of mounted base paths (e.g. ['/api/v1/repos']).
        """
        mount_table: dict[str, list[str]] = {}

        for fi in self.files:
            if fi.extension not in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
                continue

            tree = self.ast_cache.get_tree(fi.path)
            if not tree:
                continue

            def _find_mounts(node: object) -> None:
                ntype = getattr(node, "type", "")
                if ntype == "call_expression":
                    fn = getattr(node, "child_by_field_name", lambda _: None)("function")
                    args = getattr(node, "child_by_field_name", lambda _: None)("arguments")
                    if fn and getattr(fn, "type", "") == "member_expression" and args:
                        prop = _node_text(getattr(fn, "child_by_field_name", lambda _: None)("property"))
                        if prop == "use":
                            named_args = list(getattr(args, "named_children", []))
                            if len(named_args) >= 2:
                                prefix_str = _extract_string_literal(named_args[0])
                                target_node = named_args[1]
                                target_var = _node_text(target_node)

                                if prefix_str is not None and target_var:
                                    # Target could be an imported router variable
                                    tgt_file, _ = self._resolve_import_target(fi.path, target_var)
                                    if tgt_file:
                                        mount_table.setdefault(tgt_file, []).append(prefix_str)
                            elif len(named_args) == 1:
                                # app.use(router) without prefix
                                target_var = _node_text(named_args[0])
                                if target_var:
                                    tgt_file, _ = self._resolve_import_target(fi.path, target_var)
                                    if tgt_file:
                                        mount_table.setdefault(tgt_file, []).append("")

                for c in getattr(node, "children", []):
                    _find_mounts(c)

            _find_mounts(getattr(tree, "root_node", None))

        # Hierarchical mount expansion: e.g. /api -> /api/v1 -> /api/v1/auth
        return mount_table

    # -----------------------------------------------------------------------
    # Step 2: Extract Endpoints from Route Files
    # -----------------------------------------------------------------------

    def discover_routes(self) -> RouteMapResult:
        """Analyze all repository files and return complete RouteMapResult."""
        mounts = self.discover_router_mounts()
        routes_list: list[DiscoveredRoute] = []

        for fi in self.files:
            if fi.extension not in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"):
                continue

            tree = self.ast_cache.get_tree(fi.path)
            if not tree:
                continue

            base_prefixes = mounts.get(fi.path, [""])
            if not base_prefixes:
                base_prefixes = [""]

            file_routes = self._extract_routes_from_file(fi.path, tree, base_prefixes)
            routes_list.extend(file_routes)

        # Deduplicate routes deterministically by ID
        unique_routes: list[DiscoveredRoute] = []
        seen_ids: set[str] = set()

        # Sort routes deterministically by HTTP endpoint, method, file, and line
        for r in sorted(routes_list, key=lambda x: (x.http_endpoint, x.http_method, x.source_file, x.start_line)):
            if r.id not in seen_ids:
                seen_ids.add(r.id)
                unique_routes.append(r)

        summary = self._compute_summary(unique_routes)
        scanned_count = len([f for f in self.files if f.extension in (".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs")])
        route_files_count = len({r.source_file for r in unique_routes})
        logger.info(
            "Route discovery complete: scanned %d files, found %d route files, discovered %d endpoints, resolved %d controllers",
            scanned_count,
            route_files_count,
            len(unique_routes),
            summary.controllers_count,
        )
        return RouteMapResult(routes=tuple(unique_routes), summary=summary)

    def _extract_routes_from_file(
        self,
        file_path: str,
        tree: object,
        base_prefixes: list[str],
    ) -> list[DiscoveredRoute]:
        """Scan a single file's AST for route registrations."""
        extracted: list[DiscoveredRoute] = []
        file_level_middlewares: list[MiddlewareInfo] = []

        def _scan_node(node: object) -> None:
            ntype = getattr(node, "type", "")

            # 1. Router-level middleware: router.use(middlewareFn)
            if ntype == "call_expression":
                fn = getattr(node, "child_by_field_name", lambda _: None)("function")
                args = getattr(node, "child_by_field_name", lambda _: None)("arguments")
                if fn and getattr(fn, "type", "") == "member_expression" and args:
                    prop = _node_text(getattr(fn, "child_by_field_name", lambda _: None)("property"))
                    if prop == "use":
                        named_args = list(getattr(args, "named_children", []))
                        # If first arg is not a path string, it's a router-level middleware
                        if named_args and _extract_string_literal(named_args[0]) is None:
                            for mw_arg in named_args:
                                mw_info = self._resolve_middleware(file_path, mw_arg)
                                if mw_info:
                                    file_level_middlewares.append(mw_info)

            # 2. Direct route calls: app.get(path, ...mw, handler) or router.post(path, ...mw, handler)
            if ntype == "call_expression":
                fn = getattr(node, "child_by_field_name", lambda _: None)("function")
                args = getattr(node, "child_by_field_name", lambda _: None)("arguments")
                if fn and getattr(fn, "type", "") == "member_expression" and args:
                    obj_node = getattr(fn, "child_by_field_name", lambda _: None)("object")
                    obj_text = _node_text(obj_node).lower()
                    if obj_text in self.IGNORED_CALL_OBJECTS:
                        for c in getattr(node, "children", []):
                            _scan_node(c)
                        return

                    method_str = _node_text(getattr(fn, "child_by_field_name", lambda _: None)("property")).lower()
                    if method_str in self.SUPPORTED_HTTP_METHODS:
                        named_args = list(getattr(args, "named_children", []))
                        if named_args:
                            path_val = _extract_string_literal(named_args[0])
                            # Route path in Express should be a path string starting with "/"
                            if path_val is not None and (path_val.startswith("/") or path_val == ""):
                                mw_nodes = named_args[1:-1] if len(named_args) > 1 else []
                                handler_node = named_args[-1] if len(named_args) > 1 else None

                                start_pos = getattr(node, "start_point", None)
                                end_pos = getattr(node, "end_point", None)
                                start_line = start_pos.row + 1 if start_pos else 1
                                start_col = start_pos.column if start_pos else 0
                                end_line = end_pos.row + 1 if end_pos else start_line

                                for base_prefix in base_prefixes:
                                    endpoint = normalize_endpoint_path(base_prefix, path_val)
                                    route_id = f"route:{method_str.upper()}:{endpoint}:{file_path}:{start_line}"

                                    # Resolve middleware
                                    mw_list = list(file_level_middlewares)
                                    for m_node in mw_nodes:
                                        m_info = self._resolve_middleware(file_path, m_node)
                                        if m_info:
                                            mw_list.append(m_info)

                                    # Resolve controller
                                    controller_info = self._resolve_controller(file_path, handler_node)

                                    # Trace dependencies & flow
                                    services, models, flow = self._trace_execution_chain(
                                        method_str.upper(),
                                        endpoint,
                                        file_path,
                                        start_line,
                                        mw_list,
                                        controller_info,
                                    )

                                    # Determine route status
                                    if controller_info.status == "unresolved":
                                        r_status = "unresolved"
                                    elif controller_info.status == "inline":
                                        r_status = "inline"
                                    else:
                                        r_status = "resolved"

                                    extracted.append(
                                        DiscoveredRoute(
                                            id=route_id,
                                            http_method=method_str.upper(),
                                            route_path=path_val,
                                            http_endpoint=endpoint,
                                            source_file=file_path,
                                            start_line=start_line,
                                            end_line=end_line,
                                            start_column=start_col,
                                            router_base_path=base_prefix,
                                            controller=controller_info,
                                            middleware=tuple(mw_list),
                                            service_dependencies=tuple(services),
                                            model_dependencies=tuple(models),
                                            execution_flow=tuple(flow),
                                            status=r_status,
                                        )
                                    )

            # 3. Chained routes: router.route("/items").get(h1).post(h2)
            if ntype == "call_expression":
                chained_routes = self._try_extract_chained_routes(file_path, node, base_prefixes, file_level_middlewares)
                if chained_routes:
                    extracted.extend(chained_routes)

            for c in getattr(node, "children", []):
                _scan_node(c)

        _scan_node(getattr(tree, "root_node", None))
        return extracted

    def _try_extract_chained_routes(
        self,
        file_path: str,
        call_node: object,
        base_prefixes: list[str],
        file_middlewares: list[MiddlewareInfo],
    ) -> list[DiscoveredRoute] | None:
        """Extract chained routes like router.route('/path').get(...).post(...)"""
        methods: list[tuple[str, list[object], object]] = []
        curr = call_node
        route_path_str: str | None = None

        while curr and getattr(curr, "type", "") == "call_expression":
            fn = getattr(curr, "child_by_field_name", lambda _: None)("function")
            args = getattr(curr, "child_by_field_name", lambda _: None)("arguments")
            if fn and getattr(fn, "type", "") == "member_expression" and args:
                prop = _node_text(getattr(fn, "child_by_field_name", lambda _: None)("property")).lower()
                named_args = list(getattr(args, "named_children", []))
                if prop == "route" and named_args:
                    route_path_str = _extract_string_literal(named_args[0])
                    break
                elif prop in self.SUPPORTED_HTTP_METHODS:
                    methods.append((prop, named_args[:-1] if len(named_args) > 1 else [], named_args[-1] if named_args else None))
                obj = getattr(fn, "child_by_field_name", lambda _: None)("object")
                curr = obj
            else:
                break

        if route_path_str is None or not methods:
            return None

        results: list[DiscoveredRoute] = []
        start_pos = getattr(call_node, "start_point", None)
        end_pos = getattr(call_node, "end_point", None)
        start_line = start_pos.row + 1 if start_pos else 1
        start_col = start_pos.column if start_pos else 0
        end_line = end_pos.row + 1 if end_pos else start_line

        for m_name, mw_nodes, handler_node in methods:
            for base_prefix in base_prefixes:
                endpoint = normalize_endpoint_path(base_prefix, route_path_str)
                route_id = f"route:{m_name.upper()}:{endpoint}:{file_path}:{start_line}"

                mw_list = list(file_middlewares)
                for m_node in mw_nodes:
                    m_info = self._resolve_middleware(file_path, m_node)
                    if m_info:
                        mw_list.append(m_info)

                controller_info = self._resolve_controller(file_path, handler_node)
                services, models, flow = self._trace_execution_chain(
                    m_name.upper(), endpoint, file_path, start_line, mw_list, controller_info
                )

                results.append(
                    DiscoveredRoute(
                        id=route_id,
                        http_method=m_name.upper(),
                        route_path=route_path_str,
                        http_endpoint=endpoint,
                        source_file=file_path,
                        start_line=start_line,
                        end_line=end_line,
                        start_column=start_col,
                        router_base_path=base_prefix,
                        controller=controller_info,
                        middleware=tuple(mw_list),
                        service_dependencies=tuple(services),
                        model_dependencies=tuple(models),
                        execution_flow=tuple(flow),
                        status="resolved" if controller_info.status != "unresolved" else "unresolved",
                    )
                )

        return results

    # -----------------------------------------------------------------------
    # Step 3: Controller & Middleware Resolution
    # -----------------------------------------------------------------------

    def _resolve_middleware(self, file_path: str, node: object | None) -> MiddlewareInfo | None:
        """Resolve a middleware argument to MiddlewareInfo."""
        if node is None:
            return None

        ntype = getattr(node, "type", "")
        start_pos = getattr(node, "start_point", None)
        line = start_pos.row + 1 if start_pos else None
        col = start_pos.column if start_pos else None

        # Inline arrow or function
        if ntype in ("arrow_function", "function_expression"):
            return MiddlewareInfo(
                name="inline_middleware",
                source_file=file_path,
                line=line,
                column=col,
                is_inline=True,
                status="inline",
            )

        # Call expression e.g. validate(schema) or authLimiter()
        if ntype == "call_expression":
            fn = getattr(node, "child_by_field_name", lambda _: None)("function")
            name = _node_text(fn) or _node_text(node)
            tgt_file, _ = self._resolve_import_target(file_path, name.split(".")[0])
            return MiddlewareInfo(
                name=name,
                source_file=tgt_file or file_path,
                line=line,
                column=col,
                is_inline=False,
                status="resolved" if tgt_file else "external",
            )

        # Identifier e.g. requireAuth
        if ntype == "identifier":
            name = _node_text(node)
            tgt_file, _ = self._resolve_import_target(file_path, name)
            return MiddlewareInfo(
                name=name,
                source_file=tgt_file or file_path,
                line=line,
                column=col,
                is_inline=False,
                status="resolved" if tgt_file else "external",
            )

        # Member expression e.g. authMiddleware.requireAuth
        if ntype == "member_expression":
            name = _node_text(node)
            obj = _node_text(getattr(node, "child_by_field_name", lambda _: None)("object"))
            tgt_file, _ = self._resolve_import_target(file_path, obj)
            return MiddlewareInfo(
                name=name,
                source_file=tgt_file or file_path,
                line=line,
                column=col,
                is_inline=False,
                status="resolved" if tgt_file else "external",
            )

        # Array of middlewares
        if ntype == "array":
            name = _node_text(node)
            return MiddlewareInfo(
                name=name,
                source_file=file_path,
                line=line,
                column=col,
                is_inline=False,
                status="resolved",
            )

        return None

    def _resolve_controller(self, file_path: str, handler_node: object | None) -> ControllerInfo:
        """Resolve a route handler argument to a concrete ControllerInfo."""
        if handler_node is None:
            return ControllerInfo(
                name="unresolved",
                function_name="unresolved",
                file_path=file_path,
                status="unresolved",
            )

        ntype = getattr(handler_node, "type", "")
        start_pos = getattr(handler_node, "start_point", None)
        end_pos = getattr(handler_node, "end_point", None)
        line = start_pos.row + 1 if start_pos else None
        end_line = end_pos.row + 1 if end_pos else line
        col = start_pos.column if start_pos else None

        # Case 1: Inline function or arrow function
        if ntype in ("arrow_function", "function_expression"):
            params = _extract_parameters(handler_node)
            body = getattr(handler_node, "child_by_field_name", lambda _: None)("body")
            calls = _extract_calls_in_node(body)
            return ControllerInfo(
                name="inline",
                function_name="anonymous",
                file_path=file_path,
                start_line=line,
                end_line=end_line,
                start_column=col,
                parameters=params,
                called_functions=calls,
                status="inline",
            )

        # Case 2: Member expression: e.g. repoController.listRepos or authController.login
        if ntype == "member_expression":
            obj_name = _node_text(getattr(handler_node, "child_by_field_name", lambda _: None)("object"))
            fn_name = _node_text(getattr(handler_node, "child_by_field_name", lambda _: None)("property"))
            full_name = f"{obj_name}.{fn_name}"

            tgt_file, _ = self._resolve_import_target(file_path, obj_name)
            if tgt_file:
                # Inspect the controller file for this function
                details = self._extract_function_details_from_file(tgt_file, fn_name, obj_name)
                return ControllerInfo(
                    name=full_name,
                    function_name=fn_name,
                    file_path=tgt_file,
                    start_line=details.get("start_line"),
                    end_line=details.get("end_line"),
                    start_column=details.get("start_column"),
                    parameters=details.get("parameters", ()),
                    called_functions=details.get("called_functions", ()),
                    status="resolved",
                )
            else:
                return ControllerInfo(
                    name=full_name,
                    function_name=fn_name,
                    file_path=None,
                    status="unresolved",
                )

        # Case 3: Identifier: e.g. listRepos or handleLogin
        if ntype == "identifier":
            fn_name = _node_text(handler_node)
            # Check if imported
            tgt_file, _ = self._resolve_import_target(file_path, fn_name)
            if tgt_file:
                details = self._extract_function_details_from_file(tgt_file, fn_name)
                return ControllerInfo(
                    name=fn_name,
                    function_name=fn_name,
                    file_path=tgt_file,
                    start_line=details.get("start_line"),
                    end_line=details.get("end_line"),
                    start_column=details.get("start_column"),
                    parameters=details.get("parameters", ()),
                    called_functions=details.get("called_functions", ()),
                    status="resolved",
                )
            else:
                # Check if defined locally in the same file
                details = self._extract_function_details_from_file(file_path, fn_name)
                if details.get("start_line"):
                    return ControllerInfo(
                        name=fn_name,
                        function_name=fn_name,
                        file_path=file_path,
                        start_line=details.get("start_line"),
                        end_line=details.get("end_line"),
                        start_column=details.get("start_column"),
                        parameters=details.get("parameters", ()),
                        called_functions=details.get("called_functions", ()),
                        status="resolved",
                    )
                return ControllerInfo(
                    name=fn_name,
                    function_name=fn_name,
                    file_path=None,
                    status="unresolved",
                )

        raw_text = _node_text(handler_node)
        return ControllerInfo(
            name=raw_text or "unresolved",
            function_name=raw_text or "unresolved",
            file_path=None,
            status="unresolved",
        )

    def _extract_function_details_from_file(
        self,
        file_path: str,
        function_name: str,
        object_name: str | None = None,
    ) -> dict[str, Any]:
        """
        Locate a function definition in file_path and extract its AST details:
        parameters, line ranges, and called functions.
        Handles top-level functions, object methods (e.g. repoController = { listRepos() {} }),
        and class methods.
        """
        tree = self.ast_cache.get_tree(file_path)
        if not tree:
            # Fall back to symbols lookup if available
            syms = self._symbols_by_file.get(file_path, [])
            for s in syms:
                if s.name == function_name:
                    return {
                        "start_line": s.start.line,
                        "end_line": s.end.line,
                        "start_column": s.start.column,
                        "parameters": (),
                        "called_functions": (),
                    }
            return {}

        details: dict[str, Any] = {}

        def _search(node: object) -> bool:
            ntype = getattr(node, "type", "")

            # 1. method_definition in object literal or class
            if ntype == "method_definition":
                name_node = getattr(node, "child_by_field_name", lambda _: None)("name")
                if name_node and _node_text(name_node) == function_name:
                    sp = getattr(node, "start_point", None)
                    ep = getattr(node, "end_point", None)
                    details["start_line"] = sp.row + 1 if sp else 1
                    details["end_line"] = ep.row + 1 if ep else details["start_line"]
                    details["start_column"] = sp.column if sp else 0
                    details["parameters"] = _extract_parameters(node)
                    details["called_functions"] = _extract_calls_in_node(
                        getattr(node, "child_by_field_name", lambda _: None)("body")
                    )
                    return True

            # 2. pair in object: listRepos: async (req, res) => ...
            if ntype == "pair":
                key_node = getattr(node, "child_by_field_name", lambda _: None)("key")
                val_node = getattr(node, "child_by_field_name", lambda _: None)("value")
                if key_node and _node_text(key_node) == function_name:
                    sp = getattr(node, "start_point", None)
                    ep = getattr(node, "end_point", None)
                    details["start_line"] = sp.row + 1 if sp else 1
                    details["end_line"] = ep.row + 1 if ep else details["start_line"]
                    details["start_column"] = sp.column if sp else 0
                    if val_node and getattr(val_node, "type", "") in ("arrow_function", "function_expression"):
                        details["parameters"] = _extract_parameters(val_node)
                        details["called_functions"] = _extract_calls_in_node(
                            getattr(val_node, "child_by_field_name", lambda _: None)("body")
                        )
                    else:
                        details["parameters"] = ()
                        details["called_functions"] = ()
                    return True

            # 3. function_declaration: function listRepos(req, res) { ... }
            if ntype == "function_declaration":
                name_node = getattr(node, "child_by_field_name", lambda _: None)("name")
                if name_node and _node_text(name_node) == function_name:
                    sp = getattr(node, "start_point", None)
                    ep = getattr(node, "end_point", None)
                    details["start_line"] = sp.row + 1 if sp else 1
                    details["end_line"] = ep.row + 1 if ep else details["start_line"]
                    details["start_column"] = sp.column if sp else 0
                    details["parameters"] = _extract_parameters(node)
                    details["called_functions"] = _extract_calls_in_node(
                        getattr(node, "child_by_field_name", lambda _: None)("body")
                    )
                    return True

            # 4. variable_declarator: const listRepos = (req, res) => { ... }
            if ntype == "variable_declarator":
                name_node = getattr(node, "child_by_field_name", lambda _: None)("name")
                val_node = getattr(node, "child_by_field_name", lambda _: None)("value")
                if name_node and _node_text(name_node) == function_name and val_node:
                    sp = getattr(node, "start_point", None)
                    ep = getattr(node, "end_point", None)
                    details["start_line"] = sp.row + 1 if sp else 1
                    details["end_line"] = ep.row + 1 if ep else details["start_line"]
                    details["start_column"] = sp.column if sp else 0
                    if getattr(val_node, "type", "") in ("arrow_function", "function_expression"):
                        details["parameters"] = _extract_parameters(val_node)
                        details["called_functions"] = _extract_calls_in_node(
                            getattr(val_node, "child_by_field_name", lambda _: None)("body")
                        )
                    return True

            for c in getattr(node, "children", []):
                if _search(c):
                    return True
            return False

        _search(getattr(tree, "root_node", None))
        return details

    # -----------------------------------------------------------------------
    # Step 4: Service & Model Dependency Tracing
    # -----------------------------------------------------------------------

    def _trace_execution_chain(
        self,
        method: str,
        endpoint: str,
        route_file: str,
        route_line: int,
        middlewares: list[MiddlewareInfo],
        controller: ControllerInfo,
    ) -> tuple[list[ServiceDependency], list[ModelDependency], list[FlowStep]]:
        """
        Trace the full execution chain:
        Route -> Middleware(s) -> Controller -> Service -> Model -> Database
        """
        services: list[ServiceDependency] = []
        models: list[ModelDependency] = []
        flow: list[FlowStep] = []

        # 1. Route step
        flow.append(
            FlowStep(
                step_type="route",
                label=f"{method} {endpoint}",
                file_path=route_file,
                line=route_line,
                description="HTTP Request Entrypoint",
            )
        )

        # 2. Middleware steps
        for mw in middlewares:
            flow.append(
                FlowStep(
                    step_type="middleware",
                    label=mw.name,
                    file_path=mw.source_file,
                    line=mw.line,
                    description="Request Pipeline Middleware",
                )
            )

        # 3. Controller step
        ctrl_label = controller.name if controller.name != "inline" else "inline handler"
        flow.append(
            FlowStep(
                step_type="controller",
                label=ctrl_label,
                file_path=controller.file_path or route_file,
                line=controller.start_line,
                description="HTTP Request Controller Handler",
            )
        )

        # 4. Trace calls inside controller to services & models
        ctrl_file = controller.file_path or route_file
        called_fns = controller.called_functions

        for call_str in called_fns:
            # Check for service calls (e.g. repoService.connectRepo or authService.authenticate)
            parts = call_str.split(".")
            base_obj = parts[0]
            method_called = parts[1] if len(parts) > 1 else None

            # Resolve base_obj in ctrl_file imports
            target_file, _ = self._resolve_import_target(ctrl_file, base_obj)

            is_service = False
            if target_file:
                roles = self._roles_by_file.get(target_file, set())
                if ArchitectureRole.SERVICE in roles or "service" in target_file.lower():
                    is_service = True
            elif "service" in base_obj.lower():
                is_service = True

            if is_service:
                svc_dep = ServiceDependency(
                    service_name=base_obj,
                    method_name=method_called,
                    file_path=target_file,
                    status="confirmed" if target_file else "unresolved",
                )
                if svc_dep not in services:
                    services.append(svc_dep)
                    flow.append(
                        FlowStep(
                            step_type="service",
                            label=f"{base_obj}.{method_called}()" if method_called else base_obj,
                            file_path=target_file,
                            description="Business Logic Service Execution",
                        )
                    )

                    # Now trace inside this service method for model/database operations
                    if target_file and method_called:
                        svc_details = self._extract_function_details_from_file(
                            target_file, method_called, base_obj
                        )
                        svc_calls = svc_details.get("called_functions", ())
                        for svc_call in svc_calls:
                            m_dep = self._detect_model_dependency(target_file, svc_call)
                            if m_dep and m_dep not in models:
                                models.append(m_dep)
                                flow.append(
                                    FlowStep(
                                        step_type="model",
                                        label=f"{m_dep.model_name}.{m_dep.operation}()" if m_dep.operation else m_dep.model_name,
                                        file_path=m_dep.file_path,
                                        description="Database / ORM Data Access",
                                    )
                                )

            # Also check direct model calls from controller
            m_dep = self._detect_model_dependency(ctrl_file, call_str)
            if m_dep and m_dep not in models:
                models.append(m_dep)
                flow.append(
                    FlowStep(
                        step_type="model",
                        label=f"{m_dep.model_name}.{m_dep.operation}()" if m_dep.operation else m_dep.model_name,
                        file_path=m_dep.file_path,
                        description="Database / ORM Data Access",
                    )
                )

        # 5. Database step if any model or database access was detected
        if models or any("db" in c.lower() or "query" in c.lower() for c in called_fns):
            flow.append(
                FlowStep(
                    step_type="database",
                    label="Database Query Execution",
                    description="PostgreSQL / Persistent Storage Transaction",
                )
            )

        return services, models, flow

    def _detect_model_dependency(self, file_path: str, call_str: str) -> ModelDependency | None:
        """Detect if call_str represents a database/model/repository access."""
        parts = call_str.split(".")
        base_obj = parts[0]
        raw_op = parts[1] if len(parts) > 1 else None
        operation = raw_op.split("(")[0] if raw_op else None

        # Prisma or generic db client: e.g. prisma.user.findUnique or db.orm.public.AnalysisJob
        if base_obj.lower() in ("prisma", "db", "pool", "knex", "orm"):
            model_target = parts[1] if len(parts) > 2 else base_obj
            op = parts[-1].split("(")[0] if len(parts) > 1 else "query"
            return ModelDependency(
                model_name=model_target,
                operation=op,
                file_path=None,
                status="confirmed",
            )

        # Repository / Model files: e.g. repositoryRepository.findByUserAndUrl or User.findOne
        target_file, _ = self._resolve_import_target(file_path, base_obj)
        if target_file:
            roles = self._roles_by_file.get(target_file, set())
            if ArchitectureRole.SERVICE in roles or "service" in target_file.lower():
                return None
            if (
                ArchitectureRole.MODEL in roles
                or ArchitectureRole.REPOSITORY in roles
                or ArchitectureRole.ENTITY in roles
                or "model" in target_file.lower()
                or "repositor" in target_file.lower()
            ):
                return ModelDependency(
                    model_name=base_obj,
                    operation=operation,
                    file_path=target_file,
                    status="confirmed",
                )
        elif (
            "repository" in base_obj.lower()
            or "model" in base_obj.lower()
            or (base_obj[0].isupper() and operation in ("find", "findOne", "findById", "create", "update", "delete", "where"))
        ):
            if "service" in base_obj.lower():
                return None
            return ModelDependency(
                model_name=base_obj,
                operation=operation,
                file_path=target_file,
                status="confirmed" if target_file else "inferred",
            )

        return None

    # -----------------------------------------------------------------------
    # Step 5: Summary Computation
    # -----------------------------------------------------------------------

    def _compute_summary(self, routes: Sequence[DiscoveredRoute]) -> RouteMapSummary:
        """Calculate aggregate counts across all discovered endpoints."""
        get_c = sum(1 for r in routes if r.http_method == "GET")
        post_c = sum(1 for r in routes if r.http_method == "POST")
        put_patch_c = sum(1 for r in routes if r.http_method in ("PUT", "PATCH"))
        del_c = sum(1 for r in routes if r.http_method == "DELETE")
        other_c = sum(1 for r in routes if r.http_method not in ("GET", "POST", "PUT", "PATCH", "DELETE"))
        unres_c = sum(1 for r in routes if r.status == "unresolved")

        ctrls = {r.controller.name for r in routes if r.controller.name not in ("unresolved", "inline")}
        svcs = {s.service_name for r in routes for s in r.service_dependencies}
        mdls = {m.model_name for r in routes for m in r.model_dependencies}

        return RouteMapSummary(
            total_endpoints=len(routes),
            get_count=get_c,
            post_count=post_c,
            put_patch_count=put_patch_c,
            delete_count=del_c,
            other_count=other_c,
            unresolved_count=unres_c,
            controllers_count=len(ctrls),
            services_count=len(svcs),
            models_count=len(mdls),
        )


# ---------------------------------------------------------------------------
# Public Helper
# ---------------------------------------------------------------------------


def discover_routes(
    files: Sequence[FileInfo],
    symbols: Sequence[Symbol],
    relationships: Sequence[Relationship],
    resolved_relationships: Sequence[ResolvedRelationship],
    architecture: RepositoryArchitecture | None = None,
    *,
    repo_path: Path | None = None,
) -> RouteMapResult:
    """Analyze repository and return discovered HTTP routes and summary."""
    engine = RouteDiscoveryEngine(
        files=files,
        symbols=symbols,
        relationships=relationships,
        resolved_relationships=resolved_relationships,
        architecture=architecture,
        repo_path=repo_path,
    )
    return engine.discover_routes()
