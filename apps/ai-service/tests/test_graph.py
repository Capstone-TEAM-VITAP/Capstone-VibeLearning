"""
tests/test_graph.py

Comprehensive tests for Milestone 7 — CodeGraph Construction.
Covers:
  1. Node creation (repository, file, function, class, method, variable, constant)
  2. Containment hierarchy (repo → file, file → symbol, class → method, nested symbols)
  3. Relationships (imports, exports, references, calls)
  4. Cross-file resolution (resolved import, resolved symbol target, external, unresolved)
  5. Architectural integration (roles, route → controller, controller → service,
     service → repository, repository → model)
  6. Identity (same name in different files/scopes, deterministic IDs, uniqueness)
  7. Validation (invalid edge, missing target, duplicate nodes, invalid parent, unknown file)
  8. Determinism (shuffled inputs produce identical graphs, sorted ordering)
  9. Immutability (frozen dataclass enforcement, tuples)
  10. Queries (get_node, get_nodes_by_type, incoming/outgoing edges, neighbors)
  11. Empty input (empty repository handling)
  12. End-to-end pipeline integration
"""

from __future__ import annotations

import dataclasses
import pytest

from src.repository.architecture import (
    ArchitecturalClassification,
    ArchitecturalLayer,
    ArchitecturalRelationship,
    ArchitectureRole,
    EvidenceItem,
    FileClassification,
    RepositoryArchitecture,
)
from src.repository.graph import (
    CodeGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    GraphValidationError,
    NodeType,
    build_code_graph,
    get_incoming_edges,
    get_node,
    get_nodes_by_type,
    get_outgoing_edges,
    make_arch_node_id,
    make_edge_id,
    make_external_node_id,
    make_file_node_id,
    make_repo_node_id,
    make_symbol_node_id,
    make_unresolved_node_id,
)
from src.repository.models import FileInfo
from src.repository.parser import Position
from src.repository.relationships import Relationship, RelationshipKind
from src.repository.resolver import ResolutionStatus, ResolvedRelationship, SymbolId
from src.repository.symbols import Symbol, SymbolKind


# ===========================================================================
# 1. NODE CREATION TESTS
# ===========================================================================


class TestNodeCreation:
    """Verify nodes are created for repository, files, and all symbol kinds."""

    def test_repository_root_node_created(self) -> None:
        graph = build_code_graph(repo_name="my-app")
        repo_node = graph.get_node("repo:my-app")
        assert repo_node is not None
        assert repo_node.node_type == NodeType.REPOSITORY
        assert repo_node.label == "my-app"
        assert repo_node.get_metadata("repo_name") == "my-app"

    def test_file_node_created_with_metadata(self) -> None:
        file_info = FileInfo(
            path="src/auth.js", language="javascript", extension=".js", size=1024
        )
        graph = build_code_graph(files=[file_info])

        file_node = graph.get_node("file:src/auth.js")
        assert file_node is not None
        assert file_node.node_type == NodeType.FILE
        assert file_node.label == "auth.js"
        assert file_node.get_metadata("language") == "javascript"
        assert file_node.get_metadata("extension") == ".js"
        assert file_node.get_metadata("size") == "1024"
        assert file_node.get_metadata("path") == "src/auth.js"

    def test_function_symbol_node_created(self) -> None:
        f = FileInfo("src/auth.js", "javascript", ".js", 100)
        s = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(4, 0), Position(10, 1), None)
        graph = build_code_graph(files=[f], symbols=[s])

        node = graph.get_node("symbol:src/auth.js:login:4:0")
        assert node is not None
        assert node.node_type == NodeType.FUNCTION
        assert node.label == "login"
        assert node.get_metadata("name") == "login"
        assert node.get_metadata("kind") == "function"
        assert node.get_metadata("start_line") == "4"
        assert node.get_metadata("start_col") == "0"

    def test_class_symbol_node_created(self) -> None:
        f = FileInfo("src/service.js", "javascript", ".js", 100)
        s = Symbol("UserService", SymbolKind.CLASS, "src/service.js", Position(1, 0), Position(20, 1), None)
        graph = build_code_graph(files=[f], symbols=[s])

        node = graph.get_node("symbol:src/service.js:UserService:1:0")
        assert node is not None
        assert node.node_type == NodeType.CLASS
        assert node.label == "UserService"

    def test_method_symbol_node_created(self) -> None:
        f = FileInfo("src/service.js", "javascript", ".js", 100)
        cls_sym = Symbol("UserService", SymbolKind.CLASS, "src/service.js", Position(1, 0), Position(20, 1), None)
        m_sym = Symbol("getUser", SymbolKind.METHOD, "src/service.js", Position(5, 2), Position(10, 3), "UserService")
        graph = build_code_graph(files=[f], symbols=[cls_sym, m_sym])

        node = graph.get_node("symbol:src/service.js:getUser:5:2")
        assert node is not None
        assert node.node_type == NodeType.METHOD
        assert node.label == "getUser"
        assert node.get_metadata("parent") == "UserService"

    def test_variable_symbol_node_created(self) -> None:
        f = FileInfo("src/utils.js", "javascript", ".js", 100)
        s = Symbol("count", SymbolKind.VARIABLE, "src/utils.js", Position(2, 4), Position(2, 14), None)
        graph = build_code_graph(files=[f], symbols=[s])

        node = graph.get_node("symbol:src/utils.js:count:2:4")
        assert node is not None
        assert node.node_type == NodeType.VARIABLE
        assert node.label == "count"

    def test_constant_symbol_node_created(self) -> None:
        f = FileInfo("src/config.js", "javascript", ".js", 100)
        s = Symbol("API_PORT", SymbolKind.CONSTANT, "src/config.js", Position(1, 0), Position(1, 20), None)
        graph = build_code_graph(files=[f], symbols=[s])

        node = graph.get_node("symbol:src/config.js:API_PORT:1:0")
        assert node is not None
        assert node.node_type == NodeType.CONSTANT
        assert node.label == "API_PORT"


# ===========================================================================
# 2. CONTAINMENT HIERARCHY TESTS
# ===========================================================================


class TestContainmentHierarchy:
    """Verify repository → file, file → symbol, and symbol → child symbol containment."""

    def test_repository_contains_files(self) -> None:
        f1 = FileInfo("src/a.js", "javascript", ".js", 10)
        f2 = FileInfo("src/b.js", "javascript", ".js", 20)
        graph = build_code_graph(files=[f1, f2], repo_name="demo")

        edges = graph.get_outgoing_edges("repo:demo")
        contained_targets = {e.target_id for e in edges if e.edge_type == EdgeType.CONTAINS}
        assert contained_targets == {"file:src/a.js", "file:src/b.js"}

    def test_file_contains_top_level_symbols(self) -> None:
        f = FileInfo("src/auth.js", "javascript", ".js", 100)
        s1 = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(1, 0), Position(5, 0), None)
        s2 = Symbol("logout", SymbolKind.FUNCTION, "src/auth.js", Position(6, 0), Position(10, 0), None)
        graph = build_code_graph(files=[f], symbols=[s1, s2])

        edges = graph.get_outgoing_edges("file:src/auth.js")
        contained = [e for e in edges if e.edge_type == EdgeType.CONTAINS]
        contained_ids = {e.target_id for e in contained}
        assert contained_ids == {
            "symbol:src/auth.js:login:1:0",
            "symbol:src/auth.js:logout:6:0",
        }

    def test_class_contains_method(self) -> None:
        f = FileInfo("src/service.js", "javascript", ".js", 100)
        cls_sym = Symbol("AuthService", SymbolKind.CLASS, "src/service.js", Position(1, 0), Position(20, 0), None)
        m_sym = Symbol("validate", SymbolKind.METHOD, "src/service.js", Position(5, 2), Position(10, 2), "AuthService")
        graph = build_code_graph(files=[f], symbols=[cls_sym, m_sym])

        class_edges = graph.get_outgoing_edges("symbol:src/service.js:AuthService:1:0")
        method_contains = [e for e in class_edges if e.edge_type == EdgeType.CONTAINS]
        assert len(method_contains) == 1
        assert method_contains[0].target_id == "symbol:src/service.js:validate:5:2"

        # The file contains the class, but NOT directly the method
        file_edges = graph.get_outgoing_edges("file:src/service.js")
        file_contains = [e for e in file_edges if e.edge_type == EdgeType.CONTAINS]
        assert len(file_contains) == 1
        assert file_contains[0].target_id == "symbol:src/service.js:AuthService:1:0"

    def test_nested_symbols_hierarchy(self) -> None:
        """Outer function contains inner function, which contains a variable."""
        f = FileInfo("src/nested.js", "javascript", ".js", 100)
        outer = Symbol("outer", SymbolKind.FUNCTION, "src/nested.js", Position(1, 0), Position(15, 0), None)
        inner = Symbol("inner", SymbolKind.FUNCTION, "src/nested.js", Position(3, 2), Position(12, 2), "outer")
        var_x = Symbol("x", SymbolKind.VARIABLE, "src/nested.js", Position(5, 4), Position(5, 12), "inner")
        graph = build_code_graph(files=[f], symbols=[outer, inner, var_x])

        outer_edges = graph.get_outgoing_edges("symbol:src/nested.js:outer:1:0")
        assert any(e.target_id == "symbol:src/nested.js:inner:3:2" and e.edge_type == EdgeType.CONTAINS for e in outer_edges)

        inner_edges = graph.get_outgoing_edges("symbol:src/nested.js:inner:3:2")
        assert any(e.target_id == "symbol:src/nested.js:x:5:4" and e.edge_type == EdgeType.CONTAINS for e in inner_edges)


# ===========================================================================
# 3. RELATIONSHIPS (M4 / M5)
# ===========================================================================


class TestRelationshipEdges:
    """Verify IMPORTS, EXPORTS, CALLS, and REFERENCES edges."""

    def test_exports_relationship(self) -> None:
        f = FileInfo("src/auth.js", "javascript", ".js", 100)
        s = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(2, 0), Position(6, 0), None)
        exp_rel = Relationship(
            kind=RelationshipKind.EXPORTS,
            source_path="src/auth.js",
            source_position=Position(8, 0),
            target_name="login",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        graph = build_code_graph(files=[f], symbols=[s], relationships=[exp_rel])

        file_edges = graph.get_outgoing_edges("file:src/auth.js")
        export_edges = [e for e in file_edges if e.edge_type == EdgeType.EXPORTS]
        assert len(export_edges) == 1
        assert export_edges[0].target_id == "symbol:src/auth.js:login:2:0"
        assert export_edges[0].get_metadata("target_name") == "login"

    def test_intra_file_function_call(self) -> None:
        f = FileInfo("src/app.js", "javascript", ".js", 100)
        helper = Symbol("helper", SymbolKind.FUNCTION, "src/app.js", Position(1, 0), Position(5, 0), None)
        main = Symbol("main", SymbolKind.FUNCTION, "src/app.js", Position(7, 0), Position(12, 0), None)
        call_rel = Relationship(
            kind=RelationshipKind.CALLS,
            source_path="src/app.js",
            source_position=Position(9, 4),
            target_name="helper",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        graph = build_code_graph(files=[f], symbols=[helper, main], relationships=[call_rel])

        main_edges = graph.get_outgoing_edges("symbol:src/app.js:main:7:0")
        call_edges = [e for e in main_edges if e.edge_type == EdgeType.CALLS]
        assert len(call_edges) == 1
        assert call_edges[0].target_id == "symbol:src/app.js:helper:1:0"

    def test_intra_file_reference(self) -> None:
        f = FileInfo("src/config.js", "javascript", ".js", 100)
        c = Symbol("DEFAULT_PORT", SymbolKind.CONSTANT, "src/config.js", Position(1, 0), Position(1, 25), None)
        fn = Symbol("getPort", SymbolKind.FUNCTION, "src/config.js", Position(3, 0), Position(6, 0), None)
        ref_rel = Relationship(
            kind=RelationshipKind.REFERENCES,
            source_path="src/config.js",
            source_position=Position(4, 8),
            target_name="DEFAULT_PORT",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        graph = build_code_graph(files=[f], symbols=[c, fn], relationships=[ref_rel])

        fn_edges = graph.get_outgoing_edges("symbol:src/config.js:getPort:3:0")
        ref_edges = [e for e in fn_edges if e.edge_type == EdgeType.REFERENCES]
        assert len(ref_edges) == 1
        assert ref_edges[0].target_id == "symbol:src/config.js:DEFAULT_PORT:1:0"

    def test_cross_file_call_via_import(self) -> None:
        """Calling an imported function creates a CALLS edge from caller to target symbol."""
        f_app = FileInfo("src/app.js", "javascript", ".js", 100)
        f_auth = FileInfo("src/auth.js", "javascript", ".js", 100)

        main_sym = Symbol("main", SymbolKind.FUNCTION, "src/app.js", Position(3, 0), Position(8, 0), None)
        auth_sym = Symbol("authenticate", SymbolKind.FUNCTION, "src/auth.js", Position(2, 0), Position(7, 0), None)

        import_rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/app.js",
            source_position=Position(1, 0),
            target_name="authenticate",
            module_path="./auth.js",
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        res_import = ResolvedRelationship(
            source_relationship=import_rel,
            status=ResolutionStatus.RESOLVED,
            target_path="src/auth.js",
            target_symbol_id=SymbolId("src/auth.js", "authenticate", 2, 0),
            notes=None,
        )
        call_rel = Relationship(
            kind=RelationshipKind.CALLS,
            source_path="src/app.js",
            source_position=Position(5, 4),
            target_name="authenticate",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )

        graph = build_code_graph(
            files=[f_app, f_auth],
            symbols=[main_sym, auth_sym],
            relationships=[call_rel],
            resolved_relationships=[res_import],
        )

        main_edges = graph.get_outgoing_edges("symbol:src/app.js:main:3:0")
        calls = [e for e in main_edges if e.edge_type == EdgeType.CALLS]
        assert len(calls) == 1
        assert calls[0].target_id == "symbol:src/auth.js:authenticate:2:0"


# ===========================================================================
# 4. CROSS-FILE RESOLUTION (M5)
# ===========================================================================


class TestResolutionNodesAndEdges:
    """Verify resolved symbol targets, cross-file imports, external & unresolved nodes."""

    def test_resolved_cross_file_import_both_symbol_and_file_edges(self) -> None:
        f_app = FileInfo("src/app.js", "javascript", ".js", 100)
        f_auth = FileInfo("src/auth.js", "javascript", ".js", 100)
        sym_login = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(4, 0), Position(10, 1), None)

        rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/app.js",
            source_position=Position(1, 0),
            target_name="login",
            module_path="./auth.js",
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        resolved = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED,
            target_path="src/auth.js",
            target_symbol_id=SymbolId("src/auth.js", "login", 4, 0),
            notes=None,
        )

        graph = build_code_graph(
            files=[f_app, f_auth],
            symbols=[sym_login],
            resolved_relationships=[resolved],
        )

        app_edges = graph.get_outgoing_edges("file:src/app.js")
        import_edges = [e for e in app_edges if e.edge_type == EdgeType.IMPORTS]

        # Should have import edge to target symbol AND import edge to target file
        targets = {e.target_id for e in import_edges}
        assert "symbol:src/auth.js:login:4:0" in targets
        assert "file:src/auth.js" in targets

    def test_resolved_file_without_symbol(self) -> None:
        """Side-effect or namespace import produces file-level import edge."""
        f_app = FileInfo("src/app.js", "javascript", ".js", 100)
        f_init = FileInfo("src/startup.js", "javascript", ".js", 50)

        rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/app.js",
            source_position=Position(1, 0),
            target_name="",
            module_path="./startup.js",
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        resolved = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.RESOLVED_FILE,
            target_path="src/startup.js",
            target_symbol_id=None,
            notes=None,
        )

        graph = build_code_graph(
            files=[f_app, f_init],
            resolved_relationships=[resolved],
        )

        app_edges = graph.get_outgoing_edges("file:src/app.js")
        import_edges = [e for e in app_edges if e.edge_type == EdgeType.IMPORTS]
        assert len(import_edges) == 1
        assert import_edges[0].target_id == "file:src/startup.js"

    def test_external_dependency_creates_external_node(self) -> None:
        """External packages like 'express' become NodeType.EXTERNAL, NOT a fake file."""
        f = FileInfo("src/server.js", "javascript", ".js", 100)
        rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/server.js",
            source_position=Position(1, 0),
            target_name="express",
            module_path="express",
            alias=None,
            is_default=True,
            is_namespace=False,
        )
        resolved = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.EXTERNAL,
            target_path=None,
            target_symbol_id=None,
            notes=None,
        )

        graph = build_code_graph(files=[f], resolved_relationships=[resolved])

        ext_node = graph.get_node("external:express")
        assert ext_node is not None
        assert ext_node.node_type == NodeType.EXTERNAL
        assert ext_node.label == "express"
        assert ext_node.get_metadata("status") == "external"

        # Edge from server.js to external node
        edges = graph.get_outgoing_edges("file:src/server.js")
        import_edges = [e for e in edges if e.edge_type == EdgeType.IMPORTS]
        assert len(import_edges) == 1
        assert import_edges[0].target_id == "external:express"
        assert import_edges[0].get_metadata("status") == "external"

    def test_unresolved_import_creates_unresolved_node(self) -> None:
        """Missing relative imports remain NodeType.UNRESOLVED."""
        f = FileInfo("src/app.js", "javascript", ".js", 100)
        rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/app.js",
            source_position=Position(1, 0),
            target_name="missing",
            module_path="./missing.js",
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        resolved = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.UNRESOLVED,
            target_path=None,
            target_symbol_id=None,
            notes=None,
        )

        graph = build_code_graph(files=[f], resolved_relationships=[resolved])

        unres_node = graph.get_node("unresolved:./missing.js")
        assert unres_node is not None
        assert unres_node.node_type == NodeType.UNRESOLVED
        assert unres_node.label == "./missing.js"
        assert unres_node.get_metadata("status") == "unresolved"

        # Edge from app.js to unresolved node
        edges = graph.get_outgoing_edges("file:src/app.js")
        import_edges = [e for e in edges if e.edge_type == EdgeType.IMPORTS]
        assert len(import_edges) == 1
        assert import_edges[0].target_id == "unresolved:./missing.js"


# ===========================================================================
# 5. ARCHITECTURAL INTEGRATION (M6)
# ===========================================================================


class TestArchitecturalIntegration:
    """Verify architectural role nodes, classified_as edges, and dependency chains."""

    def test_file_classified_as_role_node(self) -> None:
        f = FileInfo("src/services/authService.js", "javascript", ".js", 100)
        classification = ArchitecturalClassification(
            path="src/services/authService.js",
            role=ArchitectureRole.SERVICE,
            layer=ArchitecturalLayer.APPLICATION,
            evidence=(EvidenceItem("Service suffix", "path"),),
        )
        fc = FileClassification("src/services/authService.js", (classification,))
        arch = RepositoryArchitecture((fc,), ())

        graph = build_code_graph(files=[f], architecture=arch)

        arch_node = graph.get_node("architecture:src/services/authService.js:SERVICE")
        assert arch_node is not None
        assert arch_node.node_type == NodeType.SERVICE
        assert arch_node.get_metadata("layer") == "application"

        # CLASSIFIED_AS edge from file to architecture node
        file_edges = graph.get_outgoing_edges("file:src/services/authService.js")
        class_edges = [e for e in file_edges if e.edge_type == EdgeType.CLASSIFIED_AS]
        assert len(class_edges) == 1
        assert class_edges[0].target_id == "architecture:src/services/authService.js:SERVICE"

    def test_architectural_relationship_chain(self) -> None:
        """
        Verify: ROUTE → CONTROLLER → SERVICE → REPOSITORY → MODEL
        Each link has a DEPENDS_ON edge between architecture nodes.
        """
        paths = {
            "route": "src/routes/authRoutes.js",
            "controller": "src/controllers/authController.js",
            "service": "src/services/authService.js",
            "repo": "src/repositories/userRepository.js",
            "model": "src/models/userModel.js",
        }
        files = [FileInfo(p, "javascript", ".js", 100) for p in paths.values()]

        classes = [
            FileClassification(
                paths["route"],
                (ArchitecturalClassification(paths["route"], ArchitectureRole.ROUTE, ArchitecturalLayer.PRESENTATION, ()),),
            ),
            FileClassification(
                paths["controller"],
                (ArchitecturalClassification(paths["controller"], ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),),
            ),
            FileClassification(
                paths["service"],
                (ArchitecturalClassification(paths["service"], ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),),
            ),
            FileClassification(
                paths["repo"],
                (ArchitecturalClassification(paths["repo"], ArchitectureRole.REPOSITORY, ArchitecturalLayer.DATA, ()),),
            ),
            FileClassification(
                paths["model"],
                (ArchitecturalClassification(paths["model"], ArchitectureRole.MODEL, ArchitecturalLayer.DOMAIN, ()),),
            ),
        ]

        rels = [
            ArchitecturalRelationship(
                source_path=paths["route"],
                source_role=ArchitectureRole.ROUTE,
                target_path=paths["controller"],
                target_role=ArchitectureRole.CONTROLLER,
                pattern="ROUTE → CONTROLLER",
                evidence=(),
            ),
            ArchitecturalRelationship(
                source_path=paths["controller"],
                source_role=ArchitectureRole.CONTROLLER,
                target_path=paths["service"],
                target_role=ArchitectureRole.SERVICE,
                pattern="CONTROLLER → SERVICE",
                evidence=(),
            ),
            ArchitecturalRelationship(
                source_path=paths["service"],
                source_role=ArchitectureRole.SERVICE,
                target_path=paths["repo"],
                target_role=ArchitectureRole.REPOSITORY,
                pattern="SERVICE → REPOSITORY",
                evidence=(),
            ),
            ArchitecturalRelationship(
                source_path=paths["repo"],
                source_role=ArchitectureRole.REPOSITORY,
                target_path=paths["model"],
                target_role=ArchitectureRole.MODEL,
                pattern="REPOSITORY → MODEL",
                evidence=(),
            ),
        ]

        arch = RepositoryArchitecture(tuple(classes), tuple(rels))
        graph = build_code_graph(files=files, architecture=arch)

        # 1. Route → Controller
        route_node_id = "architecture:src/routes/authRoutes.js:ROUTE"
        ctrl_node_id = "architecture:src/controllers/authController.js:CONTROLLER"
        edges = [e for e in graph.get_outgoing_edges(route_node_id) if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(edges) == 1
        assert edges[0].target_id == ctrl_node_id
        assert edges[0].get_metadata("pattern") == "ROUTE → CONTROLLER"

        # 2. Controller → Service
        service_node_id = "architecture:src/services/authService.js:SERVICE"
        edges = [e for e in graph.get_outgoing_edges(ctrl_node_id) if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(edges) == 1
        assert edges[0].target_id == service_node_id

        # 3. Service → Repository
        repo_node_id = "architecture:src/repositories/userRepository.js:REPOSITORY"
        edges = [e for e in graph.get_outgoing_edges(service_node_id) if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(edges) == 1
        assert edges[0].target_id == repo_node_id

        # 4. Repository → Model
        model_node_id = "architecture:src/models/userModel.js:MODEL"
        edges = [e for e in graph.get_outgoing_edges(repo_node_id) if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(edges) == 1
        assert edges[0].target_id == model_node_id

    def test_file_with_multiple_architectural_roles(self) -> None:
        """A test file that tests a controller can be classified as both TEST and CONTROLLER."""
        p = "src/tests/authController.test.js"
        f = FileInfo(p, "javascript", ".js", 100)
        c1 = ArchitecturalClassification(p, ArchitectureRole.TEST, ArchitecturalLayer.TESTING, ())
        c2 = ArchitecturalClassification(p, ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ())
        fc = FileClassification(p, (c1, c2))
        arch = RepositoryArchitecture((fc,), ())

        graph = build_code_graph(files=[f], architecture=arch)

        t_node = graph.get_node(f"architecture:{p}:TEST")
        c_node = graph.get_node(f"architecture:{p}:CONTROLLER")
        assert t_node is not None and t_node.node_type == NodeType.TEST
        assert c_node is not None and c_node.node_type == NodeType.CONTROLLER

        file_edges = graph.get_outgoing_edges(f"file:{p}")
        classified = [e for e in file_edges if e.edge_type == EdgeType.CLASSIFIED_AS]
        assert len(classified) == 2


# ===========================================================================
# 6. NODE IDENTITY & DETERMINISM
# ===========================================================================


class TestNodeIdentity:
    """Verify deterministic IDs and distinct identities for same-named symbols."""

    def test_same_symbol_name_in_different_files(self) -> None:
        f1 = FileInfo("src/auth.js", "javascript", ".js", 100)
        f2 = FileInfo("src/admin.js", "javascript", ".js", 100)

        s1 = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(4, 0), Position(10, 1), None)
        s2 = Symbol("login", SymbolKind.FUNCTION, "src/admin.js", Position(4, 0), Position(10, 1), None)

        graph = build_code_graph(files=[f1, f2], symbols=[s1, s2])

        n1 = graph.get_node("symbol:src/auth.js:login:4:0")
        n2 = graph.get_node("symbol:src/admin.js:login:4:0")
        assert n1 is not None and n2 is not None
        assert n1.id != n2.id

    def test_same_symbol_name_in_different_scopes_same_file(self) -> None:
        f = FileInfo("src/app.js", "javascript", ".js", 100)
        s1 = Symbol("temp", SymbolKind.VARIABLE, "src/app.js", Position(5, 2), Position(5, 10), None)
        s2 = Symbol("temp", SymbolKind.VARIABLE, "src/app.js", Position(15, 2), Position(15, 10), None)

        graph = build_code_graph(files=[f], symbols=[s1, s2])

        n1 = graph.get_node("symbol:src/app.js:temp:5:2")
        n2 = graph.get_node("symbol:src/app.js:temp:15:2")
        assert n1 is not None and n2 is not None
        assert n1.id != n2.id

    def test_deterministic_id_generation(self) -> None:
        id1 = make_symbol_node_id("src/a.js", "login", 4, 0)
        id2 = make_symbol_node_id("src/a.js", "login", 4, 0)
        assert id1 == id2 == "symbol:src/a.js:login:4:0"

        id3 = make_file_node_id("src/a.js")
        assert id3 == "file:src/a.js"

        id4 = make_arch_node_id("src/a.js", ArchitectureRole.SERVICE)
        assert id4 == "architecture:src/a.js:SERVICE"

        id5 = make_external_node_id("express")
        assert id5 == "external:express"

        id6 = make_unresolved_node_id("./missing.js")
        assert id6 == "unresolved:./missing.js"


# ===========================================================================
# 7. VALIDATION TESTS
# ===========================================================================


class TestGraphValidation:
    """Verify construction-time checks for invalid edges, missing targets, duplicates, and bad parents."""

    def test_missing_edge_source_raises(self) -> None:
        node = GraphNode("file:src/a.js", NodeType.FILE, "a.js")
        edge = GraphEdge("edge:bad->imports->file:src/a.js", EdgeType.IMPORTS, "bad:src/ghost.js", "file:src/a.js")
        with pytest.raises(GraphValidationError, match="Edge source not found"):
            CodeGraph(nodes=(node,), edges=(edge,))

    def test_missing_edge_target_raises(self) -> None:
        node = GraphNode("file:src/a.js", NodeType.FILE, "a.js")
        edge = GraphEdge("edge:file:src/a.js->imports->bad", EdgeType.IMPORTS, "file:src/a.js", "bad:target")
        with pytest.raises(GraphValidationError, match="Edge target not found"):
            CodeGraph(nodes=(node,), edges=(edge,))

    def test_duplicate_file_detected_in_builder(self) -> None:
        f1 = FileInfo("src/a.js", "javascript", ".js", 100)
        f2 = FileInfo("src/a.js", "javascript", ".js", 200)
        with pytest.raises(GraphValidationError, match="Duplicate file path detected"):
            build_code_graph(files=[f1, f2])

    def test_duplicate_symbol_detected_in_builder(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        s1 = Symbol("fn", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(5, 0), None)
        s2 = Symbol("fn", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(5, 0), None)
        with pytest.raises(GraphValidationError, match="Duplicate symbol node ID detected"):
            build_code_graph(files=[f], symbols=[s1, s2])

    def test_invalid_parent_detected(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        s = Symbol("orphanMethod", SymbolKind.METHOD, "src/a.js", Position(5, 2), Position(10, 2), "NonExistentParent")
        with pytest.raises(GraphValidationError, match="Parent symbol 'NonExistentParent' not found"):
            build_code_graph(files=[f], symbols=[s])

    def test_symbol_belongs_to_unknown_file(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        s = Symbol("fn", SymbolKind.FUNCTION, "src/unknown.js", Position(1, 0), Position(5, 0), None)
        with pytest.raises(GraphValidationError, match="belongs to unknown file"):
            build_code_graph(files=[f], symbols=[s])


# ===========================================================================
# 8. DETERMINISM TESTS
# ===========================================================================


class TestGraphDeterminism:
    """Verify identical CodeGraph output regardless of input ordering."""

    def test_shuffled_files_and_symbols_produce_identical_graph(self) -> None:
        f1 = FileInfo("src/z.js", "javascript", ".js", 100)
        f2 = FileInfo("src/a.js", "javascript", ".js", 200)
        f3 = FileInfo("src/m.js", "javascript", ".js", 150)

        s1 = Symbol("zFunc", SymbolKind.FUNCTION, "src/z.js", Position(1, 0), Position(5, 0), None)
        s2 = Symbol("aFunc", SymbolKind.FUNCTION, "src/a.js", Position(2, 0), Position(6, 0), None)
        s3 = Symbol("mFunc", SymbolKind.FUNCTION, "src/m.js", Position(3, 0), Position(7, 0), None)

        graph1 = build_code_graph(files=[f1, f2, f3], symbols=[s1, s2, s3])
        graph2 = build_code_graph(files=[f3, f1, f2], symbols=[s3, s1, s2])

        assert graph1.nodes == graph2.nodes
        assert graph1.edges == graph2.edges
        assert graph1 == graph2

    def test_nodes_are_sorted_by_id(self) -> None:
        f1 = FileInfo("src/b.js", "javascript", ".js", 10)
        f2 = FileInfo("src/a.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f1, f2])

        node_ids = [n.id for n in graph.nodes]
        assert node_ids == sorted(node_ids)

    def test_edges_are_sorted_deterministically(self) -> None:
        f1 = FileInfo("src/b.js", "javascript", ".js", 10)
        f2 = FileInfo("src/a.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f1, f2])

        edge_keys = [(e.source_id, e.edge_type.value, e.target_id, e.id) for e in graph.edges]
        assert edge_keys == sorted(edge_keys)


# ===========================================================================
# 9. IMMUTABILITY TESTS
# ===========================================================================


class TestImmutability:
    """Verify graph models and collections cannot be mutated."""

    def test_graph_node_is_frozen(self) -> None:
        node = GraphNode("test:id", NodeType.FILE, "test")
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.label = "mutated"  # type: ignore[misc]

    def test_graph_edge_is_frozen(self) -> None:
        edge = GraphEdge("edge:1", EdgeType.CONTAINS, "a", "b")
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.target_id = "mutated"  # type: ignore[misc]

    def test_code_graph_is_frozen(self) -> None:
        graph = build_code_graph()
        with pytest.raises(dataclasses.FrozenInstanceError):
            graph.nodes = ()  # type: ignore[misc]

    def test_nodes_and_edges_are_tuples(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f])
        assert isinstance(graph.nodes, tuple)
        assert isinstance(graph.edges, tuple)


# ===========================================================================
# 10. GRAPH QUERY HELPERS
# ===========================================================================


class TestGraphQueries:
    """Verify get_node, get_nodes_by_type, outgoing/incoming edges, neighbors."""

    def test_get_node_existing_and_missing(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f])

        assert graph.get_node("file:src/a.js") is not None
        assert get_node(graph, "file:src/a.js") is not None
        assert graph.get_node("non_existent") is None
        assert get_node(graph, "non_existent") is None

    def test_get_nodes_by_type(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 10)
        s1 = Symbol("f1", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(3, 0), None)
        s2 = Symbol("f2", SymbolKind.FUNCTION, "src/a.js", Position(4, 0), Position(6, 0), None)
        s3 = Symbol("PORT", SymbolKind.CONSTANT, "src/a.js", Position(7, 0), Position(7, 10), None)
        graph = build_code_graph(files=[f], symbols=[s1, s2, s3])

        fn_nodes = graph.get_nodes_by_type(NodeType.FUNCTION)
        assert len(fn_nodes) == 2
        assert {n.label for n in fn_nodes} == {"f1", "f2"}

        const_nodes = get_nodes_by_type(graph, NodeType.CONSTANT)
        assert len(const_nodes) == 1
        assert const_nodes[0].label == "PORT"

        empty_nodes = graph.get_nodes_by_type(NodeType.HOOK)
        assert empty_nodes == ()

    def test_incoming_and_outgoing_edges(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 10)
        s = Symbol("f1", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(3, 0), None)
        graph = build_code_graph(files=[f], symbols=[s], repo_name="repo")

        # repo contains file, file contains symbol
        repo_out = graph.get_outgoing_edges("repo:repo")
        assert any(e.target_id == "file:src/a.js" for e in repo_out)

        file_in = graph.get_incoming_edges("file:src/a.js")
        assert any(e.source_id == "repo:repo" for e in file_in)

        file_out = get_outgoing_edges(graph, "file:src/a.js")
        assert any(e.target_id == "symbol:src/a.js:f1:1:0" for e in file_out)

        sym_in = get_incoming_edges(graph, "symbol:src/a.js:f1:1:0")
        assert any(e.source_id == "file:src/a.js" for e in sym_in)

    def test_get_neighbors(self) -> None:
        f1 = FileInfo("src/a.js", "javascript", ".js", 10)
        f2 = FileInfo("src/b.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f1, f2], repo_name="repo")

        neighbors = graph.get_neighbors("repo:repo", direction="outgoing")
        assert len(neighbors) == 2
        assert {n.id for n in neighbors} == {"file:src/a.js", "file:src/b.js"}

        in_neighbors = graph.get_neighbors("file:src/a.js", direction="incoming")
        assert len(in_neighbors) == 1
        assert in_neighbors[0].id == "repo:repo"


# ===========================================================================
# 11. EMPTY INPUT HANDLING
# ===========================================================================


class TestEmptyInput:
    """Verify empty repositories produce valid graphs."""

    def test_empty_repository(self) -> None:
        graph = build_code_graph([], [], [], [], None)
        assert len(graph.nodes) == 1  # root repo node
        assert graph.nodes[0].node_type == NodeType.REPOSITORY
        assert len(graph.edges) == 0

    def test_none_inputs_handled(self) -> None:
        graph = build_code_graph()
        assert len(graph.nodes) == 1
        assert graph.has_node("repo:root")
        assert len(graph.edges) == 0


# ===========================================================================
# 12. END-TO-END PIPELINE INTEGRATION
# ===========================================================================


class TestEndToEndPipeline:
    """Run full pipeline: files → symbols → relationships → resolver → architecture → CodeGraph."""

    def test_full_synthetic_repository(self) -> None:
        # 1. Files
        files = [
            FileInfo("src/routes/authRoute.js", "javascript", ".js", 120),
            FileInfo("src/controllers/authController.js", "javascript", ".js", 250),
            FileInfo("src/services/authService.js", "javascript", ".js", 400),
        ]

        # 2. Symbols
        symbols = [
            Symbol("handleLogin", SymbolKind.FUNCTION, "src/controllers/authController.js", Position(5, 0), Position(12, 0), None),
            Symbol("AuthService", SymbolKind.CLASS, "src/services/authService.js", Position(2, 0), Position(25, 0), None),
            Symbol("validateCredentials", SymbolKind.METHOD, "src/services/authService.js", Position(5, 2), Position(10, 2), "AuthService"),
        ]

        # 3. Import from controller to service
        import_rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/controllers/authController.js",
            source_position=Position(1, 0),
            target_name="validateCredentials",
            module_path="../services/authService.js",
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        resolved_import = ResolvedRelationship(
            source_relationship=import_rel,
            status=ResolutionStatus.RESOLVED,
            target_path="src/services/authService.js",
            target_symbol_id=SymbolId("src/services/authService.js", "validateCredentials", 5, 2),
            notes=None,
        )

        # 4. External import to express
        express_rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/routes/authRoute.js",
            source_position=Position(1, 0),
            target_name="express",
            module_path="express",
            alias=None,
            is_default=True,
            is_namespace=False,
        )
        resolved_express = ResolvedRelationship(
            source_relationship=express_rel,
            status=ResolutionStatus.EXTERNAL,
            target_path=None,
            target_symbol_id=None,
            notes=None,
        )

        # 5. Method call inside controller to validateCredentials
        call_rel = Relationship(
            kind=RelationshipKind.CALLS,
            source_path="src/controllers/authController.js",
            source_position=Position(8, 4),
            target_name="validateCredentials",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )

        # 6. Architecture classifications
        fcs = [
            FileClassification("src/routes/authRoute.js", (ArchitecturalClassification("src/routes/authRoute.js", ArchitectureRole.ROUTE, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification("src/controllers/authController.js", (ArchitecturalClassification("src/controllers/authController.js", ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification("src/services/authService.js", (ArchitecturalClassification("src/services/authService.js", ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
        ]
        arch_rel = ArchitecturalRelationship(
            source_path="src/controllers/authController.js",
            source_role=ArchitectureRole.CONTROLLER,
            target_path="src/services/authService.js",
            target_role=ArchitectureRole.SERVICE,
            pattern="CONTROLLER → SERVICE",
            evidence=(),
        )
        arch = RepositoryArchitecture(tuple(fcs), (arch_rel,))

        # 7. Build graph
        graph = build_code_graph(
            files=files,
            symbols=symbols,
            relationships=[call_rel],
            resolved_relationships=[resolved_import, resolved_express],
            architecture=arch,
            repo_name="auth-system",
        )

        # Assertions
        assert graph.has_node("repo:auth-system")
        assert graph.has_node("external:express")
        assert graph.has_node("architecture:src/controllers/authController.js:CONTROLLER")
        assert graph.has_node("architecture:src/services/authService.js:SERVICE")

        # Verify call edge from handleLogin to validateCredentials
        hl_edges = graph.get_outgoing_edges("symbol:src/controllers/authController.js:handleLogin:5:0")
        call_edges = [e for e in hl_edges if e.edge_type == EdgeType.CALLS]
        assert len(call_edges) == 1
        assert call_edges[0].target_id == "symbol:src/services/authService.js:validateCredentials:5:2"

        # Verify architectural dependency
        ctrl_arch_id = "architecture:src/controllers/authController.js:CONTROLLER"
        svc_arch_id = "architecture:src/services/authService.js:SERVICE"
        arch_edges = [e for e in graph.get_outgoing_edges(ctrl_arch_id) if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(arch_edges) == 1
        assert arch_edges[0].target_id == svc_arch_id

    def test_full_pipeline_with_real_ast_and_symbols(self) -> None:
        """
        Execute full real pipeline from M1 scanner to M6 architecture to M7 graph
        using actual JavaScript source code strings.
        """
        from src.repository.symbols import extract_symbols
        from src.repository.relationships import extract_relationships
        from src.repository.resolver import resolve_imports
        from src.repository.architecture import classify_repository

        # Realistic multi-file JavaScript project
        code_service = """
export class UserService {
  findUserById(id) {
    return { id, name: "Alice" };
  }
}
"""
        code_controller = """
import { UserService } from "../services/userService.js";

export function getUser(req, res) {
  const service = new UserService();
  return service.findUserById(req.params.id);
}
"""
        code_routes = """
import express from "express";
import { getUser } from "../controllers/userController.js";

const router = express.Router();
router.get("/users/:id", getUser);
export default router;
"""

        f_service = FileInfo("src/services/userService.js", "javascript", ".js", len(code_service))
        f_controller = FileInfo("src/controllers/userController.js", "javascript", ".js", len(code_controller))
        f_routes = FileInfo("src/routes/userRoutes.js", "javascript", ".js", len(code_routes))
        files = [f_service, f_controller, f_routes]

        # Extract symbols (M3)
        symbols_svc = extract_symbols(f_service.path, f_service.language, code_service)
        symbols_ctrl = extract_symbols(f_controller.path, f_controller.language, code_controller)
        symbols_rt = extract_symbols(f_routes.path, f_routes.language, code_routes)
        all_symbols = symbols_svc + symbols_ctrl + symbols_rt

        # Extract relationships (M4)
        rels_svc = extract_relationships(f_service.path, f_service.language, code_service)
        rels_ctrl = extract_relationships(f_controller.path, f_controller.language, code_controller)
        rels_rt = extract_relationships(f_routes.path, f_routes.language, code_routes)
        all_rels = rels_svc + rels_ctrl + rels_rt

        # Resolve imports (M5)
        resolved_imports = resolve_imports(files, all_symbols, all_rels)

        # Detect architecture (M6)
        architecture = classify_repository(files, all_symbols, all_rels, resolved_imports)

        # Build CodeGraph (M7)
        graph = build_code_graph(
            files=files,
            symbols=all_symbols,
            relationships=all_rels,
            resolved_relationships=resolved_imports,
            architecture=architecture,
            repo_name="real-pipeline-app",
        )

        # 1. Verify structure
        assert graph.has_node("repo:real-pipeline-app")
        assert graph.has_node("file:src/services/userService.js")
        assert graph.has_node("file:src/controllers/userController.js")
        assert graph.has_node("file:src/routes/userRoutes.js")
        assert graph.has_node("external:express")

        # 2. Verify resolved import edge exists
        rt_edges = graph.get_outgoing_edges("file:src/routes/userRoutes.js")
        assert any(e.edge_type == EdgeType.IMPORTS and e.target_id == "file:src/controllers/userController.js" for e in rt_edges)
        assert any(e.edge_type == EdgeType.IMPORTS and e.target_id == "external:express" for e in rt_edges)

        # 3. Verify architectural roles detected and mapped
        assert graph.has_node("architecture:src/routes/userRoutes.js:ROUTE")
        assert graph.has_node("architecture:src/controllers/userController.js:CONTROLLER")
        assert graph.has_node("architecture:src/services/userService.js:SERVICE")

        # 4. Verify architectural dependency: ROUTE → CONTROLLER
        route_arch_edges = graph.get_outgoing_edges("architecture:src/routes/userRoutes.js:ROUTE")
        assert any(
            e.edge_type == EdgeType.DEPENDS_ON and e.target_id == "architecture:src/controllers/userController.js:CONTROLLER"
            for e in route_arch_edges
        )


# ===========================================================================
# 13. ADDITIONAL EDGE CASES & COVERAGE
# ===========================================================================


class TestAdditionalCoverage:
    """Extra test cases for all architectural roles, unreliably identified calls, and shared nodes."""

    def test_all_architectural_role_types_created(self) -> None:
        """Every ArchitectureRole enum value can be represented as a NodeType."""
        roles_to_test = [
            (ArchitectureRole.ROUTE, NodeType.ROUTE),
            (ArchitectureRole.CONTROLLER, NodeType.CONTROLLER),
            (ArchitectureRole.SERVICE, NodeType.SERVICE),
            (ArchitectureRole.REPOSITORY, NodeType.REPOSITORY_ROLE),
            (ArchitectureRole.MODEL, NodeType.MODEL),
            (ArchitectureRole.ENTITY, NodeType.ENTITY),
            (ArchitectureRole.COMPONENT, NodeType.COMPONENT),
            (ArchitectureRole.HOOK, NodeType.HOOK),
            (ArchitectureRole.MIDDLEWARE, NodeType.MIDDLEWARE),
            (ArchitectureRole.UTILITY, NodeType.UTILITY),
            (ArchitectureRole.CONFIG, NodeType.CONFIG),
            (ArchitectureRole.ENTRYPOINT, NodeType.ENTRYPOINT),
            (ArchitectureRole.TEST, NodeType.TEST),
            (ArchitectureRole.UNKNOWN, NodeType.UNKNOWN),
        ]

        files = []
        classifications = []
        for role, expected_node_type in roles_to_test:
            path = f"src/test_{role.value}.js"
            f = FileInfo(path, "javascript", ".js", 50)
            files.append(f)
            c = ArchitecturalClassification(path, role, ArchitecturalLayer.UNKNOWN, ())
            classifications.append(FileClassification(path, (c,)))

        arch = RepositoryArchitecture(tuple(classifications), ())
        graph = build_code_graph(files=files, architecture=arch)

        for role, expected_node_type in roles_to_test:
            path = f"src/test_{role.value}.js"
            node_id = make_arch_node_id(path, role)
            node = graph.get_node(node_id)
            assert node is not None
            assert node.node_type == expected_node_type

    def test_multiple_files_share_same_external_node(self) -> None:
        """If 3 files import 'react', only ONE external:react node is created."""
        f1 = FileInfo("src/comp1.js", "javascript", ".js", 100)
        f2 = FileInfo("src/comp2.js", "javascript", ".js", 100)
        f3 = FileInfo("src/comp3.js", "javascript", ".js", 100)

        rels = []
        for f in (f1, f2, f3):
            r = Relationship(RelationshipKind.IMPORTS, f.path, Position(1, 0), "react", "react", None, True, False)
            res = ResolvedRelationship(r, ResolutionStatus.EXTERNAL, None, None, notes=None)
            rels.append(res)

        graph = build_code_graph(files=[f1, f2, f3], resolved_relationships=rels)

        react_nodes = [n for n in graph.nodes if n.id == "external:react"]
        assert len(react_nodes) == 1

        # All 3 files have outgoing edges to external:react
        incoming_to_react = graph.get_incoming_edges("external:react")
        assert len(incoming_to_react) == 3
        sources = {e.source_id for e in incoming_to_react}
        assert sources == {"file:src/comp1.js", "file:src/comp2.js", "file:src/comp3.js"}

    def test_unidentified_call_creates_no_edge(self) -> None:
        """Calls to undefined functions (e.g. console.log, global) do NOT create edges."""
        f = FileInfo("src/app.js", "javascript", ".js", 100)
        call_rel = Relationship(
            kind=RelationshipKind.CALLS,
            source_path="src/app.js",
            source_position=Position(5, 4),
            target_name="console.log",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        graph = build_code_graph(files=[f], relationships=[call_rel])

        # No CALLS edges should have been created
        calls = [e for e in graph.edges if e.edge_type == EdgeType.CALLS]
        assert len(calls) == 0

    def test_unidentified_reference_creates_no_edge(self) -> None:
        """References to undefined identifiers do NOT create edges."""
        f = FileInfo("src/app.js", "javascript", ".js", 100)
        ref_rel = Relationship(
            kind=RelationshipKind.REFERENCES,
            source_path="src/app.js",
            source_position=Position(5, 4),
            target_name="window.location",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )
        graph = build_code_graph(files=[f], relationships=[ref_rel])

        refs = [e for e in graph.edges if e.edge_type == EdgeType.REFERENCES]
        assert len(refs) == 0

    def test_dotted_method_call_on_imported_object(self) -> None:
        """Calling authService.authenticate() resolves to method in authService.js."""
        f_ctrl = FileInfo("src/authController.js", "javascript", ".js", 100)
        f_svc = FileInfo("src/authService.js", "javascript", ".js", 100)

        ctrl_fn = Symbol("login", SymbolKind.FUNCTION, "src/authController.js", Position(3, 0), Position(8, 0), None)
        svc_cls = Symbol("AuthService", SymbolKind.CLASS, "src/authService.js", Position(1, 0), Position(10, 0), None)
        svc_method = Symbol("authenticate", SymbolKind.METHOD, "src/authService.js", Position(4, 2), Position(7, 2), "AuthService")

        import_rel = Relationship(
            kind=RelationshipKind.IMPORTS,
            source_path="src/authController.js",
            source_position=Position(1, 0),
            target_name="authService",
            module_path="./authService.js",
            alias=None,
            is_default=True,
            is_namespace=False,
        )
        resolved_import = ResolvedRelationship(
            source_relationship=import_rel,
            status=ResolutionStatus.RESOLVED,
            target_path="src/authService.js",
            target_symbol_id=SymbolId("src/authService.js", "AuthService", 1, 0),
            notes=None,
        )

        call_rel = Relationship(
            kind=RelationshipKind.CALLS,
            source_path="src/authController.js",
            source_position=Position(5, 4),
            target_name="authService.authenticate",
            module_path=None,
            alias=None,
            is_default=False,
            is_namespace=False,
        )

        graph = build_code_graph(
            files=[f_ctrl, f_svc],
            symbols=[ctrl_fn, svc_cls, svc_method],
            relationships=[call_rel],
            resolved_relationships=[resolved_import],
        )

        call_edges = [e for e in graph.edges if e.edge_type == EdgeType.CALLS]
        assert len(call_edges) == 1
        assert call_edges[0].source_id == "symbol:src/authController.js:login:3:0"
        assert call_edges[0].target_id == "symbol:src/authService.js:authenticate:4:2"

    def test_direct_codegraph_instantiation_validation(self) -> None:
        """Instantiating CodeGraph directly validates duplicate node IDs."""
        n1 = GraphNode("dup:id", NodeType.FILE, "a.js")
        n2 = GraphNode("dup:id", NodeType.FILE, "b.js")
        with pytest.raises(GraphValidationError, match="Duplicate node ID in CodeGraph"):
            CodeGraph(nodes=(n1, n2), edges=())

    def test_metadata_dict_property_and_get_metadata_default(self) -> None:
        node = GraphNode("test:1", NodeType.FILE, "label", metadata=(("a", "1"), ("b", "2")))
        assert node.get_metadata("a") == "1"
        assert node.get_metadata("c") is None
        assert node.get_metadata("c", default="def") == "def"
        d = node.metadata_dict
        assert d == {"a": "1", "b": "2"}
        # Mutating the returned dict does not mutate node.metadata
        d["a"] = "mutated"
        assert node.get_metadata("a") == "1"

    def test_repeated_random_shuffle_determinism(self) -> None:
        """Build graph with 10 random permutations of the input; all outputs must be identical."""
        import random

        files = [FileInfo(f"src/f{i}.js", "javascript", ".js", i * 10) for i in range(10)]
        symbols = [
            Symbol(f"fn{i}", SymbolKind.FUNCTION, f"src/f{i}.js", Position(1, 0), Position(5, 0), None)
            for i in range(10)
        ]

        baseline = build_code_graph(files=files, symbols=symbols)

        for seed in range(10):
            r = random.Random(seed)
            shuffled_files = list(files)
            shuffled_symbols = list(symbols)
            r.shuffle(shuffled_files)
            r.shuffle(shuffled_symbols)

            g = build_code_graph(files=shuffled_files, symbols=shuffled_symbols)
            assert g == baseline
            assert g.nodes == baseline.nodes
            assert g.edges == baseline.edges


# ===========================================================================
# 14. INDIVIDUAL ARCHITECTURAL TRANSITIONS (M6 -> M7)
# ===========================================================================


class TestIndividualArchitectureTransitions:
    """Explicitly verify each architectural transition pair requested in Milestone 7."""

    def test_route_to_controller_transition(self) -> None:
        p_rt = "src/routes/authRoute.js"
        p_ctrl = "src/controllers/authController.js"
        files = [FileInfo(p_rt, "javascript", ".js", 100), FileInfo(p_ctrl, "javascript", ".js", 100)]
        fcs = [
            FileClassification(p_rt, (ArchitecturalClassification(p_rt, ArchitectureRole.ROUTE, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification(p_ctrl, (ArchitecturalClassification(p_ctrl, ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
        ]
        rel = ArchitecturalRelationship(p_rt, ArchitectureRole.ROUTE, p_ctrl, ArchitectureRole.CONTROLLER, "ROUTE → CONTROLLER", ())
        graph = build_code_graph(files=files, architecture=RepositoryArchitecture(tuple(fcs), (rel,)))

        edges = graph.get_outgoing_edges(f"architecture:{p_rt}:ROUTE")
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(dep_edges) == 1
        assert dep_edges[0].target_id == f"architecture:{p_ctrl}:CONTROLLER"

    def test_controller_to_service_transition(self) -> None:
        p_ctrl = "src/controllers/authController.js"
        p_svc = "src/services/authService.js"
        files = [FileInfo(p_ctrl, "javascript", ".js", 100), FileInfo(p_svc, "javascript", ".js", 100)]
        fcs = [
            FileClassification(p_ctrl, (ArchitecturalClassification(p_ctrl, ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification(p_svc, (ArchitecturalClassification(p_svc, ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
        ]
        rel = ArchitecturalRelationship(p_ctrl, ArchitectureRole.CONTROLLER, p_svc, ArchitectureRole.SERVICE, "CONTROLLER → SERVICE", ())
        graph = build_code_graph(files=files, architecture=RepositoryArchitecture(tuple(fcs), (rel,)))

        edges = graph.get_outgoing_edges(f"architecture:{p_ctrl}:CONTROLLER")
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(dep_edges) == 1
        assert dep_edges[0].target_id == f"architecture:{p_svc}:SERVICE"

    def test_service_to_repository_transition(self) -> None:
        p_svc = "src/services/authService.js"
        p_repo = "src/repositories/userRepository.js"
        files = [FileInfo(p_svc, "javascript", ".js", 100), FileInfo(p_repo, "javascript", ".js", 100)]
        fcs = [
            FileClassification(p_svc, (ArchitecturalClassification(p_svc, ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
            FileClassification(p_repo, (ArchitecturalClassification(p_repo, ArchitectureRole.REPOSITORY, ArchitecturalLayer.DATA, ()),)),
        ]
        rel = ArchitecturalRelationship(p_svc, ArchitectureRole.SERVICE, p_repo, ArchitectureRole.REPOSITORY, "SERVICE → REPOSITORY", ())
        graph = build_code_graph(files=files, architecture=RepositoryArchitecture(tuple(fcs), (rel,)))

        edges = graph.get_outgoing_edges(f"architecture:{p_svc}:SERVICE")
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(dep_edges) == 1
        assert dep_edges[0].target_id == f"architecture:{p_repo}:REPOSITORY"

    def test_repository_to_model_transition(self) -> None:
        p_repo = "src/repositories/userRepository.js"
        p_model = "src/models/userModel.js"
        files = [FileInfo(p_repo, "javascript", ".js", 100), FileInfo(p_model, "javascript", ".js", 100)]
        fcs = [
            FileClassification(p_repo, (ArchitecturalClassification(p_repo, ArchitectureRole.REPOSITORY, ArchitecturalLayer.DATA, ()),)),
            FileClassification(p_model, (ArchitecturalClassification(p_model, ArchitectureRole.MODEL, ArchitecturalLayer.DOMAIN, ()),)),
        ]
        rel = ArchitecturalRelationship(p_repo, ArchitectureRole.REPOSITORY, p_model, ArchitectureRole.MODEL, "REPOSITORY → MODEL", ())
        graph = build_code_graph(files=files, architecture=RepositoryArchitecture(tuple(fcs), (rel,)))

        edges = graph.get_outgoing_edges(f"architecture:{p_repo}:REPOSITORY")
        dep_edges = [e for e in edges if e.edge_type == EdgeType.DEPENDS_ON]
        assert len(dep_edges) == 1
        assert dep_edges[0].target_id == f"architecture:{p_model}:MODEL"


# ===========================================================================
# 15. DETAILED IMMUTABILITY AND VALIDATION CHECKS
# ===========================================================================


class TestDetailedImmutabilityAndValidation:
    """Verify attribute freezing, collection immutability, and edge case validations."""

    def test_cannot_mutate_node_attributes(self) -> None:
        node = GraphNode("id:1", NodeType.FILE, "file.js", metadata=(("k", "v"),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.id = "new:id"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.node_type = NodeType.SERVICE  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            node.metadata = ()  # type: ignore[misc]

    def test_cannot_mutate_edge_attributes(self) -> None:
        edge = GraphEdge("edge:1", EdgeType.CONTAINS, "a", "b", metadata=(("k", "v"),))
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.id = "new:edge"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.edge_type = EdgeType.CALLS  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.source_id = "new:a"  # type: ignore[misc]
        with pytest.raises(dataclasses.FrozenInstanceError):
            edge.target_id = "new:b"  # type: ignore[misc]

    def test_cannot_mutate_graph_nodes_tuple(self) -> None:
        graph = build_code_graph()
        with pytest.raises(TypeError):
            graph.nodes[0] = GraphNode("new", NodeType.FILE, "new")  # type: ignore[index]
        assert not hasattr(graph.nodes, "append")
        assert not hasattr(graph.edges, "append")

    def test_leaf_node_has_no_outgoing_edges(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        s = Symbol("leaf", SymbolKind.VARIABLE, "src/a.js", Position(1, 0), Position(1, 10), None)
        graph = build_code_graph(files=[f], symbols=[s])

        outgoing = graph.get_outgoing_edges("symbol:src/a.js:leaf:1:0")
        assert outgoing == ()

    def test_root_node_has_no_incoming_edges(self) -> None:
        graph = build_code_graph(repo_name="root-repo")
        incoming = graph.get_incoming_edges("repo:root-repo")
        assert incoming == ()

    def test_include_repo_node_false(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        graph = build_code_graph(files=[f], include_repo_node=False)
        assert not graph.has_node("repo:root")
        assert len(graph.nodes) == 1
        assert graph.nodes[0].id == "file:src/a.js"
        assert len(graph.edges) == 0

    def test_edge_id_with_and_without_position(self) -> None:
        id_no_pos = make_edge_id("a", EdgeType.CALLS, "b")
        assert id_no_pos == "edge:a->calls->b"

        id_with_pos = make_edge_id("a", EdgeType.CALLS, "b", line=12, column=4)
        assert id_with_pos == "edge:a->calls->b@12:4"


