"""
repository/graph_ir.py

Intermediate Representation (IR) & Schema Contract for CodeGraph.
Milestone 8 — provides a formal, deterministic, JSON-compatible serialization,
deserialization, and validation contract for CodeGraph without modifying M1–M7.

Canonical IR schema:
{
    "schema_version": "1.0",
    "repository": {
        "id": "repo:root",
        "name": "example"
    },
    "nodes": [
        {
            "id": "file:src/auth.js",
            "type": "file",
            "label": "auth.js",
            "metadata": {}
        }
    ],
    "edges": [
        {
            "id": "edge:file:src/auth.js->contains->symbol:src/auth.js:login:4:0",
            "type": "contains",
            "source": "file:src/auth.js",
            "target": "symbol:src/auth.js:login:4:0",
            "metadata": {}
        }
    ]
}
"""

from __future__ import annotations

from typing import Any

from .graph import CodeGraph, EdgeType, GraphEdge, GraphNode, NodeType

# Canonical schema version constant (Requirement 1)
GRAPH_IR_SCHEMA_VERSION: str = "1.0"


class GraphIRValidationError(ValueError):
    """Raised when CodeGraph IR fails schema validation."""


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_graph_ir(data: Any) -> None:
    """
    Validate that *data* strictly conforms to the CodeGraph IR schema.

    Parameters:
        data: The object to validate.

    Raises:
        GraphIRValidationError: If any schema, type, reference, or uniqueness
                               constraint is violated.
    """
    if not isinstance(data, dict):
        raise GraphIRValidationError(
            f"IR data must be a dictionary, got {type(data).__name__}"
        )

    # 1. Schema version validation
    if "schema_version" not in data:
        raise GraphIRValidationError("Missing required root field: 'schema_version'")

    schema_version = data["schema_version"]
    if not isinstance(schema_version, str):
        raise GraphIRValidationError(
            f"Root field 'schema_version' must be a string, got {type(schema_version).__name__}"
        )

    if schema_version != GRAPH_IR_SCHEMA_VERSION:
        raise GraphIRValidationError(
            f"Unsupported schema_version: '{schema_version}' (expected '{GRAPH_IR_SCHEMA_VERSION}')"
        )

    # 2. Repository information validation
    if "repository" not in data:
        raise GraphIRValidationError("Missing required root field: 'repository'")

    repo = data["repository"]
    if repo is not None:
        if not isinstance(repo, dict):
            raise GraphIRValidationError(
                f"Root field 'repository' must be an object or null, got {type(repo).__name__}"
            )
        if "id" not in repo or not isinstance(repo["id"], str) or not repo["id"].strip():
            raise GraphIRValidationError(
                "Repository object must contain a non-empty string 'id'"
            )
        if "name" not in repo or not isinstance(repo["name"], str) or not repo["name"].strip():
            raise GraphIRValidationError(
                "Repository object must contain a non-empty string 'name'"
            )

    # 3. Nodes validation
    if "nodes" not in data:
        raise GraphIRValidationError("Missing required root field: 'nodes'")

    nodes = data["nodes"]
    if not isinstance(nodes, list):
        raise GraphIRValidationError(
            f"Root field 'nodes' must be a list, got {type(nodes).__name__}"
        )

    valid_node_types = {t.value for t in NodeType}
    seen_node_ids: set[str] = set()
    found_repo_node_id: str | None = None

    for idx, node in enumerate(nodes):
        if not isinstance(node, dict):
            raise GraphIRValidationError(
                f"Node at index {idx} must be a dictionary, got {type(node).__name__}"
            )

        for req_key in ("id", "type", "label", "metadata"):
            if req_key not in node:
                raise GraphIRValidationError(
                    f"Node at index {idx} is missing required field '{req_key}'"
                )

        node_id = node["id"]
        if not isinstance(node_id, str) or not node_id.strip():
            raise GraphIRValidationError(
                f"Node at index {idx} 'id' must be a non-empty string"
            )

        if node_id in seen_node_ids:
            raise GraphIRValidationError(f"Duplicate node ID detected: '{node_id}'")
        seen_node_ids.add(node_id)

        node_type_str = node["type"]
        if not isinstance(node_type_str, str) or node_type_str not in valid_node_types:
            raise GraphIRValidationError(
                f"Node '{node_id}' has invalid type: '{node_type_str}'"
            )

        if node_type_str == NodeType.REPOSITORY.value:
            found_repo_node_id = node_id

        if not isinstance(node["label"], str):
            raise GraphIRValidationError(
                f"Node '{node_id}' field 'label' must be a string, got {type(node['label']).__name__}"
            )

        metadata = node["metadata"]
        if not isinstance(metadata, dict):
            raise GraphIRValidationError(
                f"Node '{node_id}' field 'metadata' must be an object/dict, got {type(metadata).__name__}"
            )

        for m_k, m_v in metadata.items():
            if not isinstance(m_k, str):
                raise GraphIRValidationError(
                    f"Node '{node_id}' metadata key '{m_k}' must be a string, got {type(m_k).__name__}"
                )
            if not isinstance(m_v, str):
                raise GraphIRValidationError(
                    f"Node '{node_id}' metadata value for key '{m_k}' must be a string, got {type(m_v).__name__}"
                )

    # Cross-validate repository field with repository node
    if found_repo_node_id is not None:
        if repo is None:
            raise GraphIRValidationError(
                "Root field 'repository' cannot be null when a repository node exists in nodes"
            )
        if repo["id"] != found_repo_node_id:
            raise GraphIRValidationError(
                f"Root repository id '{repo['id']}' does not match repository node id '{found_repo_node_id}'"
            )

    # 4. Edges validation
    if "edges" not in data:
        raise GraphIRValidationError("Missing required root field: 'edges'")

    edges = data["edges"]
    if not isinstance(edges, list):
        raise GraphIRValidationError(
            f"Root field 'edges' must be a list, got {type(edges).__name__}"
        )

    valid_edge_types = {t.value for t in EdgeType}
    seen_edge_ids: set[str] = set()

    for idx, edge in enumerate(edges):
        if not isinstance(edge, dict):
            raise GraphIRValidationError(
                f"Edge at index {idx} must be a dictionary, got {type(edge).__name__}"
            )

        for req_key in ("id", "type", "source", "target", "metadata"):
            if req_key not in edge:
                raise GraphIRValidationError(
                    f"Edge at index {idx} is missing required field '{req_key}'"
                )

        edge_id = edge["id"]
        if not isinstance(edge_id, str) or not edge_id.strip():
            raise GraphIRValidationError(
                f"Edge at index {idx} 'id' must be a non-empty string"
            )

        if edge_id in seen_edge_ids:
            raise GraphIRValidationError(f"Duplicate edge ID detected: '{edge_id}'")
        seen_edge_ids.add(edge_id)

        edge_type_str = edge["type"]
        if not isinstance(edge_type_str, str) or edge_type_str not in valid_edge_types:
            raise GraphIRValidationError(
                f"Edge '{edge_id}' has invalid type: '{edge_type_str}'"
            )

        available_node_ids = set(seen_node_ids)
        if repo is not None and isinstance(repo, dict) and "id" in repo and isinstance(repo["id"], str):
            available_node_ids.add(repo["id"])

        source = edge["source"]
        if not isinstance(source, str) or not source.strip():
            raise GraphIRValidationError(
                f"Edge '{edge_id}' 'source' must be a non-empty string"
            )
        if source not in available_node_ids:
            raise GraphIRValidationError(
                f"Edge '{edge_id}' source '{source}' does not exist in nodes"
            )

        target = edge["target"]
        if not isinstance(target, str) or not target.strip():
            raise GraphIRValidationError(
                f"Edge '{edge_id}' 'target' must be a non-empty string"
            )
        if target not in available_node_ids:
            raise GraphIRValidationError(
                f"Edge '{edge_id}' target '{target}' does not exist in nodes"
            )

        metadata = edge["metadata"]
        if not isinstance(metadata, dict):
            raise GraphIRValidationError(
                f"Edge '{edge_id}' field 'metadata' must be an object/dict, got {type(metadata).__name__}"
            )

        for m_k, m_v in metadata.items():
            if not isinstance(m_k, str):
                raise GraphIRValidationError(
                    f"Edge '{edge_id}' metadata key '{m_k}' must be a string, got {type(m_k).__name__}"
                )
            if not isinstance(m_v, str):
                raise GraphIRValidationError(
                    f"Edge '{edge_id}' metadata value for key '{m_k}' must be a string, got {type(m_v).__name__}"
                )


# ---------------------------------------------------------------------------
# Serialization (CodeGraph → IR)
# ---------------------------------------------------------------------------


def graph_to_ir(graph: CodeGraph) -> dict[str, Any]:
    """
    Convert an immutable M7 CodeGraph into a deterministic, JSON-compatible IR dictionary.

    Parameters:
        graph: The CodeGraph to serialize.

    Returns:
        A JSON-compatible dictionary adhering to GRAPH_IR_SCHEMA_VERSION.
    """
    # 1. Repository information
    repo_node: GraphNode | None = None
    for n in graph.nodes:
        if n.node_type == NodeType.REPOSITORY:
            repo_node = n
            break

    if repo_node is not None:
        repo_name = repo_node.get_metadata("repo_name") or repo_node.label
        repo_data: dict[str, str] | None = {
            "id": repo_node.id,
            "name": repo_name,
        }
    else:
        repo_data = None

    # 2. Nodes (sorted deterministically by ID)
    sorted_nodes = sorted(graph.nodes, key=lambda n: n.id)
    nodes_ir = [
        {
            "id": n.id,
            "type": n.node_type.value,
            "label": n.label,
            "metadata": {k: v for k, v in sorted(n.metadata)},
        }
        for n in sorted_nodes
    ]

    # 3. Edges (sorted deterministically by (source_id, edge_type, target_id, id))
    sorted_edges = sorted(
        graph.edges,
        key=lambda e: (e.source_id, e.edge_type.value, e.target_id, e.id),
    )
    edges_ir = [
        {
            "id": e.id,
            "type": e.edge_type.value,
            "source": e.source_id,
            "target": e.target_id,
            "metadata": {k: v for k, v in sorted(e.metadata)},
        }
        for e in sorted_edges
    ]

    return {
        "schema_version": GRAPH_IR_SCHEMA_VERSION,
        "repository": repo_data,
        "nodes": nodes_ir,
        "edges": edges_ir,
    }


# ---------------------------------------------------------------------------
# Deserialization (IR → CodeGraph)
# ---------------------------------------------------------------------------


def ir_to_graph(data: dict[str, Any]) -> CodeGraph:
    """
    Deserialize a CodeGraph IR dictionary into an immutable, queryable CodeGraph.

    Parameters:
        data: The IR dictionary to deserialize.

    Returns:
        An immutable CodeGraph matching M7 data models.

    Raises:
        GraphIRValidationError: If the IR fails schema validation.
    """
    validate_graph_ir(data)

    nodes_list: list[GraphNode] = []
    seen_node_ids: set[str] = set()

    for n_data in data["nodes"]:
        n_id = n_data["id"]
        seen_node_ids.add(n_id)
        node_type = NodeType(n_data["type"])
        label = n_data["label"]
        meta_tuple = tuple(
            sorted((str(k), str(v)) for k, v in n_data["metadata"].items())
        )
        nodes_list.append(
            GraphNode(
                id=n_id,
                node_type=node_type,
                label=label,
                metadata=meta_tuple,
            )
        )

    # If repository is specified in IR but omitted from nodes, synthesize it
    if data["repository"] is not None and data["repository"]["id"] not in seen_node_ids:
        repo_info = data["repository"]
        repo_node = GraphNode(
            id=repo_info["id"],
            node_type=NodeType.REPOSITORY,
            label=repo_info["name"],
            metadata=(("repo_name", repo_info["name"]),),
        )
        nodes_list.append(repo_node)

    edges_list: list[GraphEdge] = []
    for e_data in data["edges"]:
        e_id = e_data["id"]
        edge_type = EdgeType(e_data["type"])
        source_id = e_data["source"]
        target_id = e_data["target"]
        meta_tuple = tuple(
            sorted((str(k), str(v)) for k, v in e_data["metadata"].items())
        )
        edges_list.append(
            GraphEdge(
                id=e_id,
                edge_type=edge_type,
                source_id=source_id,
                target_id=target_id,
                metadata=meta_tuple,
            )
        )

    return CodeGraph(
        nodes=tuple(nodes_list),
        edges=tuple(edges_list),
    )
