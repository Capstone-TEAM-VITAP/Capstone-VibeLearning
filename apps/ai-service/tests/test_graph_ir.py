"""
tests/test_graph_ir.py

Comprehensive test suite for Milestone 8 — CodeGraph IR & Schema Contract.
Covers:
  1. Schema version validation
  2. Basic serialization and deserialization
  3. Repository information handling
  4. All 21 NodeType values
  5. All 7 EdgeType values
  6. Metadata conversion and determinism
  7. Empty graph handling
  8. External and unresolved nodes
  9. Architectural integration
  10. Deterministic serialization
  11. Round-trip equality guarantee
  12. Root validation errors
  13. Node validation errors (missing fields, invalid types, bad metadata, duplicates)
  14. Edge validation errors (missing fields, invalid types, missing source/target, duplicates)
  15. Immutability of restored CodeGraph
  16. Strict JSON compatibility (json.dumps / json.loads)
  17. Large graph & randomized ordering
"""

from __future__ import annotations

import dataclasses
import json
import pytest

from src.repository.architecture import (
    ArchitecturalClassification,
    ArchitecturalLayer,
    ArchitecturalRelationship,
    ArchitectureRole,
    FileClassification,
    RepositoryArchitecture,
)
from src.repository.graph import (
    CodeGraph,
    EdgeType,
    GraphEdge,
    GraphNode,
    NodeType,
    build_code_graph,
)
from src.repository.graph_ir import (
    GRAPH_IR_SCHEMA_VERSION,
    GraphIRValidationError,
    graph_to_ir,
    ir_to_graph,
    validate_graph_ir,
)
from src.repository.models import FileInfo
from src.repository.parser import Position
from src.repository.relationships import Relationship, RelationshipKind
from src.repository.resolver import ResolutionStatus, ResolvedRelationship, SymbolId
from src.repository.symbols import Symbol, SymbolKind


# ===========================================================================
# 1. SCHEMA VERSION TESTS
# ===========================================================================


class TestSchemaVersion:
    """Verify GRAPH_IR_SCHEMA_VERSION constant and validation."""

    def test_schema_version_constant(self) -> None:
        assert GRAPH_IR_SCHEMA_VERSION == "1.0"

    def test_missing_schema_version_raises(self) -> None:
        data = {
            "repository": None,
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Missing required root field: 'schema_version'"):
            validate_graph_ir(data)

    def test_null_schema_version_raises(self) -> None:
        data = {
            "schema_version": None,
            "repository": None,
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Root field 'schema_version' must be a string"):
            validate_graph_ir(data)

    def test_non_string_schema_version_raises(self) -> None:
        data = {
            "schema_version": 1.0,
            "repository": None,
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Root field 'schema_version' must be a string"):
            validate_graph_ir(data)

    def test_unsupported_schema_version_raises(self) -> None:
        data = {
            "schema_version": "2.0",
            "repository": None,
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Unsupported schema_version: '2.0'"):
            validate_graph_ir(data)


# ===========================================================================
# 2. BASIC SERIALIZATION & DESERIALIZATION
# ===========================================================================


class TestBasicSerializationAndDeserialization:
    """Verify basic round-trip serialization and deserialization."""

    def test_basic_file_and_symbol_serialization(self) -> None:
        f = FileInfo("src/auth.js", "javascript", ".js", 1024)
        s = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(4, 0), Position(10, 1), None)
        graph = build_code_graph(files=[f], symbols=[s], repo_name="demo-app")

        ir = graph_to_ir(graph)

        assert ir["schema_version"] == "1.0"
        assert ir["repository"] == {"id": "repo:demo-app", "name": "demo-app"}
        assert len(ir["nodes"]) == 3  # repo, file, function
        assert len(ir["edges"]) == 2  # repo->file, file->function

        # Verify JSON serialization succeeds
        json_str = json.dumps(ir)
        assert isinstance(json_str, str)

        # Reconstruct graph
        restored = ir_to_graph(ir)
        assert restored == graph
        assert restored.nodes == graph.nodes
        assert restored.edges == graph.edges

    def test_deserialization_produces_identical_hash_and_queries(self) -> None:
        f = FileInfo("src/utils.js", "javascript", ".js", 200)
        c = Symbol("MAX_RETRIES", SymbolKind.CONSTANT, "src/utils.js", Position(1, 0), Position(1, 20), None)
        graph = build_code_graph(files=[f], symbols=[c])

        ir = graph_to_ir(graph)
        restored = ir_to_graph(ir)

        assert restored.get_node("symbol:src/utils.js:MAX_RETRIES:1:0") is not None
        assert restored.get_nodes_by_type(NodeType.CONSTANT) == graph.get_nodes_by_type(NodeType.CONSTANT)
        assert restored.get_outgoing_edges("file:src/utils.js") == graph.get_outgoing_edges("file:src/utils.js")


# ===========================================================================
# 3. REPOSITORY INFORMATION HANDLING
# ===========================================================================


class TestRepositoryInformation:
    """Verify repository metadata preservation and empty repo handling."""

    def test_repository_information_preserved(self) -> None:
        graph = build_code_graph(repo_name="custom-repo")
        ir = graph_to_ir(graph)

        assert ir["repository"] == {
            "id": "repo:custom-repo",
            "name": "custom-repo",
        }

    def test_graph_without_repository_node(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 50)
        graph = build_code_graph(files=[f], include_repo_node=False)

        ir = graph_to_ir(graph)
        assert ir["repository"] is None

        restored = ir_to_graph(ir)
        assert not restored.has_node("repo:root")
        assert restored == graph

    def test_repository_node_synthesized_if_omitted_from_nodes(self) -> None:
        """If repository is specified in IR but omitted from nodes list, it is synthesized."""
        ir = {
            "schema_version": "1.0",
            "repository": {
                "id": "repo:synthesized",
                "name": "synthesized-app",
            },
            "nodes": [
                {
                    "id": "file:src/main.js",
                    "type": "file",
                    "label": "main.js",
                    "metadata": {},
                }
            ],
            "edges": [
                {
                    "id": "edge:repo:synthesized->contains->file:src/main.js",
                    "type": "contains",
                    "source": "repo:synthesized",
                    "target": "file:src/main.js",
                    "metadata": {},
                }
            ],
        }

        graph = ir_to_graph(ir)
        assert graph.has_node("repo:synthesized")
        repo_node = graph.get_node("repo:synthesized")
        assert repo_node is not None
        assert repo_node.node_type == NodeType.REPOSITORY
        assert repo_node.label == "synthesized-app"

    def test_mismatched_repository_id_raises(self) -> None:
        ir = {
            "schema_version": "1.0",
            "repository": {
                "id": "repo:one",
                "name": "one",
            },
            "nodes": [
                {
                    "id": "repo:two",
                    "type": "repository",
                    "label": "two",
                    "metadata": {},
                }
            ],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Root repository id 'repo:one' does not match"):
            validate_graph_ir(ir)


# ===========================================================================
# 4. EVERY NODE TYPE SERIALIZATION & DESERIALIZATION
# ===========================================================================


class TestEveryNodeType:
    """Verify all 21 NodeType values round-trip accurately."""

    @pytest.mark.parametrize("node_type", list(NodeType))
    def test_individual_node_type_round_trip(self, node_type: NodeType) -> None:
        node = GraphNode(
            id=f"test:{node_type.value}",
            node_type=node_type,
            label=f"Label for {node_type.value}",
            metadata=(("kind", node_type.value),),
        )
        graph = CodeGraph(nodes=(node,), edges=())

        ir = graph_to_ir(graph)
        assert ir["nodes"][0]["type"] == node_type.value

        restored = ir_to_graph(ir)
        assert restored.nodes[0].node_type == node_type
        assert restored == graph

    def test_all_node_types_in_single_graph(self) -> None:
        nodes = []
        for nt in NodeType:
            nodes.append(
                GraphNode(
                    id=f"node:{nt.value}",
                    node_type=nt,
                    label=nt.value,
                    metadata=(("type", nt.value),),
                )
            )
        graph = CodeGraph(nodes=tuple(nodes), edges=())

        ir = graph_to_ir(graph)
        assert len(ir["nodes"]) == len(NodeType)

        restored = ir_to_graph(ir)
        assert restored == graph


# ===========================================================================
# 5. EVERY EDGE TYPE SERIALIZATION & DESERIALIZATION
# ===========================================================================


class TestEveryEdgeType:
    """Verify all 7 EdgeType values round-trip accurately."""

    @pytest.mark.parametrize("edge_type", list(EdgeType))
    def test_individual_edge_type_round_trip(self, edge_type: EdgeType) -> None:
        n1 = GraphNode("node:src", NodeType.FILE, "src.js")
        n2 = GraphNode("node:tgt", NodeType.FILE, "tgt.js")
        edge = GraphEdge(
            id=f"edge:{edge_type.value}",
            edge_type=edge_type,
            source_id="node:src",
            target_id="node:tgt",
            metadata=(("edge_kind", edge_type.value),),
        )
        graph = CodeGraph(nodes=(n1, n2), edges=(edge,))

        ir = graph_to_ir(graph)
        assert ir["edges"][0]["type"] == edge_type.value

        restored = ir_to_graph(ir)
        assert restored.edges[0].edge_type == edge_type
        assert restored == graph

    def test_all_edge_types_in_single_graph(self) -> None:
        n1 = GraphNode("node:a", NodeType.FILE, "a.js")
        n2 = GraphNode("node:b", NodeType.FILE, "b.js")

        edges = []
        for et in EdgeType:
            edges.append(
                GraphEdge(
                    id=f"edge:{et.value}",
                    edge_type=et,
                    source_id="node:a",
                    target_id="node:b",
                    metadata=(("kind", et.value),),
                )
            )
        graph = CodeGraph(nodes=(n1, n2), edges=tuple(edges))

        ir = graph_to_ir(graph)
        assert len(ir["edges"]) == len(EdgeType)

        restored = ir_to_graph(ir)
        assert restored == graph


# ===========================================================================
# 6. METADATA CONVERSION & DETERMINISM
# ===========================================================================


class TestMetadataConversion:
    """Verify metadata conversion between tuple of pairs and JSON dictionary."""

    def test_metadata_key_sorting(self) -> None:
        node = GraphNode(
            id="test:meta",
            node_type=NodeType.FILE,
            label="meta.js",
            metadata=(("z_key", "val_z"), ("a_key", "val_a"), ("m_key", "val_m")),
        )
        graph = CodeGraph(nodes=(node,), edges=())

        ir = graph_to_ir(graph)
        keys = list(ir["nodes"][0]["metadata"].keys())
        assert keys == ["a_key", "m_key", "z_key"]

        restored = ir_to_graph(ir)
        assert restored.nodes[0].metadata == (("a_key", "val_a"), ("m_key", "val_m"), ("z_key", "val_z"))

    def test_empty_metadata_serialized_to_empty_dict(self) -> None:
        node = GraphNode(id="test:empty", node_type=NodeType.FILE, label="empty.js", metadata=())
        graph = CodeGraph(nodes=(node,), edges=())

        ir = graph_to_ir(graph)
        assert ir["nodes"][0]["metadata"] == {}

        restored = ir_to_graph(ir)
        assert restored.nodes[0].metadata == ()


# ===========================================================================
# 7. EMPTY GRAPH HANDLING
# ===========================================================================


class TestEmptyGraph:
    """Verify empty graphs round-trip cleanly."""

    def test_empty_graph_with_default_repo(self) -> None:
        graph = build_code_graph()
        ir = graph_to_ir(graph)

        assert ir["schema_version"] == "1.0"
        assert ir["repository"] == {"id": "repo:root", "name": "root"}
        assert len(ir["nodes"]) == 1
        assert len(ir["edges"]) == 0

        restored = ir_to_graph(ir)
        assert restored == graph

    def test_completely_empty_graph_no_repo(self) -> None:
        graph = CodeGraph(nodes=(), edges=())
        ir = graph_to_ir(graph)

        assert ir["schema_version"] == "1.0"
        assert ir["repository"] is None
        assert ir["nodes"] == []
        assert ir["edges"] == []

        restored = ir_to_graph(ir)
        assert restored == graph
        assert len(restored.nodes) == 0
        assert len(restored.edges) == 0

    def test_minimal_empty_ir_deserialization(self) -> None:
        raw_ir = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [],
            "edges": [],
        }
        graph = ir_to_graph(raw_ir)
        assert len(graph.nodes) == 0
        assert len(graph.edges) == 0


# ===========================================================================
# 8. EXTERNAL AND UNRESOLVED NODES
# ===========================================================================


class TestExternalAndUnresolvedNodes:
    """Verify external and unresolved nodes serialize and deserialize faithfully."""

    def test_external_node_round_trip(self) -> None:
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
        res = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.EXTERNAL,
            target_path=None,
            target_symbol_id=None,
            notes=None,
        )
        graph = build_code_graph(files=[f], resolved_relationships=[res])

        ir = graph_to_ir(graph)
        ext_nodes = [n for n in ir["nodes"] if n["id"] == "external:express"]
        assert len(ext_nodes) == 1
        assert ext_nodes[0]["type"] == "external"

        restored = ir_to_graph(ir)
        assert restored == graph
        assert restored.has_node("external:express")

    def test_unresolved_node_round_trip(self) -> None:
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
        res = ResolvedRelationship(
            source_relationship=rel,
            status=ResolutionStatus.UNRESOLVED,
            target_path=None,
            target_symbol_id=None,
            notes=None,
        )
        graph = build_code_graph(files=[f], resolved_relationships=[res])

        ir = graph_to_ir(graph)
        unres_nodes = [n for n in ir["nodes"] if n["id"] == "unresolved:./missing.js"]
        assert len(unres_nodes) == 1
        assert unres_nodes[0]["type"] == "unresolved"

        restored = ir_to_graph(ir)
        assert restored == graph
        assert restored.has_node("unresolved:./missing.js")


# ===========================================================================
# 9. ARCHITECTURAL INTEGRATION
# ===========================================================================


class TestArchitecturalIntegration:
    """Verify architectural role nodes and depends_on edges round-trip faithfully."""

    def test_architectural_chain_round_trip(self) -> None:
        p_rt = "src/routes/authRoute.js"
        p_ctrl = "src/controllers/authController.js"
        p_svc = "src/services/authService.js"
        files = [
            FileInfo(p_rt, "javascript", ".js", 100),
            FileInfo(p_ctrl, "javascript", ".js", 100),
            FileInfo(p_svc, "javascript", ".js", 100),
        ]
        fcs = [
            FileClassification(p_rt, (ArchitecturalClassification(p_rt, ArchitectureRole.ROUTE, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification(p_ctrl, (ArchitecturalClassification(p_ctrl, ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification(p_svc, (ArchitecturalClassification(p_svc, ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
        ]
        rels = [
            ArchitecturalRelationship(p_rt, ArchitectureRole.ROUTE, p_ctrl, ArchitectureRole.CONTROLLER, "ROUTE → CONTROLLER", ()),
            ArchitecturalRelationship(p_ctrl, ArchitectureRole.CONTROLLER, p_svc, ArchitectureRole.SERVICE, "CONTROLLER → SERVICE", ()),
        ]
        arch = RepositoryArchitecture(tuple(fcs), tuple(rels))
        graph = build_code_graph(files=files, architecture=arch)

        ir = graph_to_ir(graph)
        restored = ir_to_graph(ir)

        assert restored == graph
        assert restored.has_node(f"architecture:{p_rt}:ROUTE")
        assert restored.has_node(f"architecture:{p_ctrl}:CONTROLLER")
        assert restored.has_node(f"architecture:{p_svc}:SERVICE")


# ===========================================================================
# 10. DETERMINISTIC SERIALIZATION
# ===========================================================================


class TestDeterministicSerialization:
    """Verify deterministic ordering of nodes, edges, and metadata."""

    def test_equivalent_graphs_produce_identical_ir(self) -> None:
        f1 = FileInfo("src/b.js", "javascript", ".js", 100)
        f2 = FileInfo("src/a.js", "javascript", ".js", 100)
        s1 = Symbol("fnB", SymbolKind.FUNCTION, "src/b.js", Position(1, 0), Position(5, 0), None)
        s2 = Symbol("fnA", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(5, 0), None)

        graph1 = build_code_graph(files=[f1, f2], symbols=[s1, s2])
        graph2 = build_code_graph(files=[f2, f1], symbols=[s2, s1])

        ir1 = graph_to_ir(graph1)
        ir2 = graph_to_ir(graph2)

        assert ir1 == ir2
        assert json.dumps(ir1) == json.dumps(ir2)

    def test_ir_nodes_are_sorted_by_id(self) -> None:
        f1 = FileInfo("src/z.js", "javascript", ".js", 10)
        f2 = FileInfo("src/a.js", "javascript", ".js", 10)
        graph = build_code_graph(files=[f1, f2])

        ir = graph_to_ir(graph)
        node_ids = [n["id"] for n in ir["nodes"]]
        assert node_ids == sorted(node_ids)


# ===========================================================================
# 11. ROUND-TRIP EQUALITY GUARANTEES
# ===========================================================================


class TestRoundTripEquality:
    """Verify original_graph == ir_to_graph(graph_to_ir(original_graph))."""

    def test_complex_round_trip(self) -> None:
        f1 = FileInfo("src/authController.js", "javascript", ".js", 200)
        f2 = FileInfo("src/authService.js", "javascript", ".js", 300)

        s_ctrl = Symbol("login", SymbolKind.FUNCTION, "src/authController.js", Position(2, 0), Position(8, 0), None)
        s_svc = Symbol("AuthService", SymbolKind.CLASS, "src/authService.js", Position(1, 0), Position(20, 0), None)
        s_method = Symbol("verify", SymbolKind.METHOD, "src/authService.js", Position(4, 2), Position(10, 2), "AuthService")

        imp_rel = Relationship(
            RelationshipKind.IMPORTS,
            "src/authController.js",
            Position(1, 0),
            "AuthService",
            "./authService.js",
            None,
            True,
            False,
        )
        res_imp = ResolvedRelationship(
            imp_rel,
            ResolutionStatus.RESOLVED,
            "src/authService.js",
            SymbolId("src/authService.js", "AuthService", 1, 0),
            notes=None,
        )
        call_rel = Relationship(
            RelationshipKind.CALLS,
            "src/authController.js",
            Position(5, 4),
            "authService.verify",
            None,
            None,
            False,
            False,
        )

        fcs = [
            FileClassification("src/authController.js", (ArchitecturalClassification("src/authController.js", ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification("src/authService.js", (ArchitecturalClassification("src/authService.js", ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
        ]
        arch_rel = ArchitecturalRelationship(
            "src/authController.js",
            ArchitectureRole.CONTROLLER,
            "src/authService.js",
            ArchitectureRole.SERVICE,
            "CONTROLLER → SERVICE",
            (),
        )

        arch = RepositoryArchitecture(tuple(fcs), (arch_rel,))
        original = build_code_graph(
            files=[f1, f2],
            symbols=[s_ctrl, s_svc, s_method],
            relationships=[call_rel],
            resolved_relationships=[res_imp],
            architecture=arch,
            repo_name="full-auth-app",
        )

        ir = graph_to_ir(original)
        restored = ir_to_graph(ir)

        assert restored == original
        assert restored.nodes == original.nodes
        assert restored.edges == original.edges


# ===========================================================================
# 12. ROOT VALIDATION ERRORS
# ===========================================================================


class TestRootValidationErrors:
    """Verify rejection of malformed root structures."""

    def test_non_dict_data_raises(self) -> None:
        with pytest.raises(GraphIRValidationError, match="IR data must be a dictionary"):
            validate_graph_ir(["not", "a", "dict"])

    def test_missing_repository_field_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Missing required root field: 'repository'"):
            validate_graph_ir(data)

    def test_invalid_repository_type_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": "invalid_string",
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Root field 'repository' must be an object or null"):
            validate_graph_ir(data)

    def test_repository_missing_id_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": {"name": "app"},
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Repository object must contain a non-empty string 'id'"):
            validate_graph_ir(data)

    def test_repository_missing_name_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": {"id": "repo:root"},
            "nodes": [],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Repository object must contain a non-empty string 'name'"):
            validate_graph_ir(data)

    def test_missing_nodes_field_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Missing required root field: 'nodes'"):
            validate_graph_ir(data)

    def test_non_list_nodes_field_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": "not_a_list",
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Root field 'nodes' must be a list"):
            validate_graph_ir(data)

    def test_missing_edges_field_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [],
        }
        with pytest.raises(GraphIRValidationError, match="Missing required root field: 'edges'"):
            validate_graph_ir(data)

    def test_non_list_edges_field_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [],
            "edges": {},
        }
        with pytest.raises(GraphIRValidationError, match="Root field 'edges' must be a list"):
            validate_graph_ir(data)


# ===========================================================================
# 13. NODE VALIDATION ERRORS
# ===========================================================================


class TestNodeValidationErrors:
    """Verify rejection of invalid nodes."""

    def test_node_not_a_dict_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": ["not_a_dict"],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match="Node at index 0 must be a dictionary"):
            validate_graph_ir(data)

    @pytest.mark.parametrize("missing_field", ["id", "type", "label", "metadata"])
    def test_node_missing_required_field_raises(self, missing_field: str) -> None:
        node = {"id": "node:1", "type": "file", "label": "test", "metadata": {}}
        del node[missing_field]
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [node],
            "edges": [],
        }
        with pytest.raises(GraphIRValidationError, match=f"missing required field '{missing_field}'"):
            validate_graph_ir(data)

    def test_node_empty_id_raises(self) -> None:
        node = {"id": "   ", "type": "file", "label": "test", "metadata": {}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="'id' must be a non-empty string"):
            validate_graph_ir(data)

    def test_node_invalid_type_raises(self) -> None:
        node = {"id": "node:1", "type": "invalid_type", "label": "test", "metadata": {}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="invalid type: 'invalid_type'"):
            validate_graph_ir(data)

    def test_node_non_string_label_raises(self) -> None:
        node = {"id": "node:1", "type": "file", "label": 123, "metadata": {}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="field 'label' must be a string"):
            validate_graph_ir(data)

    def test_node_non_dict_metadata_raises(self) -> None:
        node = {"id": "node:1", "type": "file", "label": "test", "metadata": ["not", "a", "dict"]}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="field 'metadata' must be an object/dict"):
            validate_graph_ir(data)

    def test_node_metadata_non_string_key_raises(self) -> None:
        node = {"id": "node:1", "type": "file", "label": "test", "metadata": {123: "val"}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="metadata key '123' must be a string"):
            validate_graph_ir(data)

    def test_node_metadata_non_string_val_raises(self) -> None:
        node = {"id": "node:1", "type": "file", "label": "test", "metadata": {"key": 456}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [node], "edges": []}
        with pytest.raises(GraphIRValidationError, match="metadata value for key 'key' must be a string"):
            validate_graph_ir(data)

    def test_duplicate_node_ids_raises(self) -> None:
        n1 = {"id": "dup:1", "type": "file", "label": "f1", "metadata": {}}
        n2 = {"id": "dup:1", "type": "file", "label": "f2", "metadata": {}}
        data = {"schema_version": "1.0", "repository": None, "nodes": [n1, n2], "edges": []}
        with pytest.raises(GraphIRValidationError, match="Duplicate node ID detected: 'dup:1'"):
            validate_graph_ir(data)


# ===========================================================================
# 14. EDGE VALIDATION ERRORS
# ===========================================================================


class TestEdgeValidationErrors:
    """Verify rejection of invalid edges."""

    def test_edge_not_a_dict_raises(self) -> None:
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [{"id": "n:1", "type": "file", "label": "f", "metadata": {}}],
            "edges": ["not_a_dict"],
        }
        with pytest.raises(GraphIRValidationError, match="Edge at index 0 must be a dictionary"):
            validate_graph_ir(data)

    @pytest.mark.parametrize("missing_field", ["id", "type", "source", "target", "metadata"])
    def test_edge_missing_required_field_raises(self, missing_field: str) -> None:
        edge = {"id": "e:1", "type": "contains", "source": "n:1", "target": "n:2", "metadata": {}}
        del edge[missing_field]
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:1", "type": "file", "label": "f1", "metadata": {}},
                {"id": "n:2", "type": "file", "label": "f2", "metadata": {}},
            ],
            "edges": [edge],
        }
        with pytest.raises(GraphIRValidationError, match=f"missing required field '{missing_field}'"):
            validate_graph_ir(data)

    def test_edge_empty_id_raises(self) -> None:
        edge = {"id": "   ", "type": "contains", "source": "n:1", "target": "n:2", "metadata": {}}
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:1", "type": "file", "label": "f1", "metadata": {}},
                {"id": "n:2", "type": "file", "label": "f2", "metadata": {}},
            ],
            "edges": [edge],
        }
        with pytest.raises(GraphIRValidationError, match="'id' must be a non-empty string"):
            validate_graph_ir(data)

    def test_edge_invalid_type_raises(self) -> None:
        edge = {"id": "e:1", "type": "invalid_edge_type", "source": "n:1", "target": "n:2", "metadata": {}}
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:1", "type": "file", "label": "f1", "metadata": {}},
                {"id": "n:2", "type": "file", "label": "f2", "metadata": {}},
            ],
            "edges": [edge],
        }
        with pytest.raises(GraphIRValidationError, match="invalid type: 'invalid_edge_type'"):
            validate_graph_ir(data)

    def test_edge_source_missing_from_nodes_raises(self) -> None:
        edge = {"id": "e:1", "type": "contains", "source": "missing:src", "target": "n:2", "metadata": {}}
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:2", "type": "file", "label": "f2", "metadata": {}},
            ],
            "edges": [edge],
        }
        with pytest.raises(GraphIRValidationError, match="source 'missing:src' does not exist in nodes"):
            validate_graph_ir(data)

    def test_edge_target_missing_from_nodes_raises(self) -> None:
        edge = {"id": "e:1", "type": "contains", "source": "n:1", "target": "missing:tgt", "metadata": {}}
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:1", "type": "file", "label": "f1", "metadata": {}},
            ],
            "edges": [edge],
        }
        with pytest.raises(GraphIRValidationError, match="target 'missing:tgt' does not exist in nodes"):
            validate_graph_ir(data)

    def test_duplicate_edge_ids_raises(self) -> None:
        e1 = {"id": "dup:e", "type": "contains", "source": "n:1", "target": "n:2", "metadata": {}}
        e2 = {"id": "dup:e", "type": "imports", "source": "n:1", "target": "n:2", "metadata": {}}
        data = {
            "schema_version": "1.0",
            "repository": None,
            "nodes": [
                {"id": "n:1", "type": "file", "label": "f1", "metadata": {}},
                {"id": "n:2", "type": "file", "label": "f2", "metadata": {}},
            ],
            "edges": [e1, e2],
        }
        with pytest.raises(GraphIRValidationError, match="Duplicate edge ID detected: 'dup:e'"):
            validate_graph_ir(data)


# ===========================================================================
# 15. IMMUTABILITY OF RESTORED CODEGRAPH
# ===========================================================================


class TestImmutability:
    """Verify that restored CodeGraph enforces immutability guarantees."""

    def test_restored_codegraph_is_frozen(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        graph = build_code_graph(files=[f])

        ir = graph_to_ir(graph)
        restored = ir_to_graph(ir)

        with pytest.raises(dataclasses.FrozenInstanceError):
            restored.nodes = ()  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            restored.nodes[0].label = "mutated"  # type: ignore[misc]

        with pytest.raises(dataclasses.FrozenInstanceError):
            restored.edges[0].target_id = "mutated"  # type: ignore[misc]

        assert isinstance(restored.nodes, tuple)
        assert isinstance(restored.edges, tuple)
        assert isinstance(restored.nodes[0].metadata, tuple)


# ===========================================================================
# 16. JSON COMPATIBILITY
# ===========================================================================


class TestJSONCompatibility:
    """Verify that IR is strictly JSON-compatible and contains only primitives."""

    def test_json_dumps_and_loads(self) -> None:
        f = FileInfo("src/service.js", "javascript", ".js", 500)
        s = Symbol("Service", SymbolKind.CLASS, "src/service.js", Position(1, 0), Position(10, 0), None)
        graph = build_code_graph(files=[f], symbols=[s])

        ir = graph_to_ir(graph)
        json_str = json.dumps(ir)
        loaded_dict = json.loads(json_str)

        restored = ir_to_graph(loaded_dict)
        assert restored == graph

    def test_no_python_enums_or_custom_objects_in_ir(self) -> None:
        f = FileInfo("src/a.js", "javascript", ".js", 100)
        graph = build_code_graph(files=[f])
        ir = graph_to_ir(graph)

        def assert_primitives_only(obj: object) -> None:
            if isinstance(obj, dict):
                for k, v in obj.items():
                    assert isinstance(k, str)
                    assert_primitives_only(v)
            elif isinstance(obj, list):
                for item in obj:
                    assert_primitives_only(item)
            else:
                assert isinstance(obj, (str, int, float, bool)) or obj is None

        assert_primitives_only(ir)


# ===========================================================================
# 17. LARGE GRAPH & RANDOMIZED ORDERING
# ===========================================================================


class TestLargeGraphAndRandomizedOrdering:
    """Verify scaling and ordering independence on larger synthetic graphs."""

    def test_fifty_nodes_and_edges(self) -> None:
        files = [FileInfo(f"src/file_{i}.js", "javascript", ".js", i * 10) for i in range(50)]
        symbols = [
            Symbol(f"func_{i}", SymbolKind.FUNCTION, f"src/file_{i}.js", Position(1, 0), Position(5, 0), None)
            for i in range(50)
        ]
        graph = build_code_graph(files=files, symbols=symbols, repo_name="scale-repo")

        ir = graph_to_ir(graph)
        assert len(ir["nodes"]) == 101  # 1 repo + 50 files + 50 functions
        assert len(ir["edges"]) == 100  # 50 repo->file + 50 file->func

        restored = ir_to_graph(ir)
        assert restored == graph

    def test_randomized_node_and_edge_order_in_ir(self) -> None:
        """Shuffled nodes and edges in IR still reconstruct identical CodeGraph."""
        import random

        files = [FileInfo(f"src/f_{i}.js", "javascript", ".js", 10) for i in range(10)]
        symbols = [
            Symbol(f"s_{i}", SymbolKind.FUNCTION, f"src/f_{i}.js", Position(1, 0), Position(3, 0), None)
            for i in range(10)
        ]
        graph = build_code_graph(files=files, symbols=symbols)
        ir = graph_to_ir(graph)

        for seed in range(5):
            r = random.Random(seed)
            shuffled_ir = dict(ir)
            shuffled_nodes = list(ir["nodes"])
            shuffled_edges = list(ir["edges"])
            r.shuffle(shuffled_nodes)
            r.shuffle(shuffled_edges)
            shuffled_ir["nodes"] = shuffled_nodes
            shuffled_ir["edges"] = shuffled_edges

            restored = ir_to_graph(shuffled_ir)
            assert restored == graph
            assert restored.nodes == graph.nodes
            assert restored.edges == graph.edges
