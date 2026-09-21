"""
retrieval/chunker.py

Structural code chunking for Milestone 9.
Extracts immutable, deterministic CodeChunk objects from CodeGraph / CodeGraph IR
and repository source files.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from ..repository.graph import CodeGraph, NodeType
from ..repository.graph_ir import ir_to_graph

_SYMBOL_NODE_TYPES: frozenset[NodeType] = frozenset(
    {
        NodeType.FUNCTION,
        NodeType.CLASS,
        NodeType.METHOD,
        NodeType.VARIABLE,
        NodeType.CONSTANT,
    }
)


# ---------------------------------------------------------------------------
# Immutable CodeChunk Model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CodeChunk:
    """
    An immutable chunk of code mapped to structural graph context.

    Attributes:
        id:          Deterministic chunk identifier.
        path:        Repository-relative POSIX path.
        language:    Programming/markup language (e.g. 'javascript').
        content:     Sliced source code text for this chunk.
        start_line:  1-indexed starting line in source.
        end_line:    1-indexed ending line in source (inclusive).
        symbol_id:   ID of corresponding M7 symbol node, or None if file-level.
        symbol_name: Identifier name of symbol, or None if file-level.
        node_ids:    Associated graph node IDs (file, symbol, architecture, etc.).
        metadata:    Sorted key-value metadata pairs.
    """

    id: str
    path: str
    language: str
    content: str
    start_line: int
    end_line: int
    symbol_id: str | None
    symbol_name: str | None
    node_ids: tuple[str, ...]
    metadata: tuple[tuple[str, str], ...] = ()

    def get_metadata(self, key: str, default: str | None = None) -> str | None:
        """Return the value for metadata *key*, or *default* if not found."""
        for k, v in self.metadata:
            if k == key:
                return v
        return default

    @property
    def metadata_dict(self) -> dict[str, str]:
        """Return metadata as a dictionary view."""
        return dict(self.metadata)


# ---------------------------------------------------------------------------
# Deterministic Identity Helpers
# ---------------------------------------------------------------------------


def make_chunk_id(
    path: str, symbol_or_scope: str, start_line: int, end_line: int
) -> str:
    """Return deterministic ID for a code chunk."""
    return f"chunk:{path}:{symbol_or_scope}:{start_line}:{end_line}"


def _slice_lines(source_text: str, start_line: int, end_line: int) -> str:
    """Slice lines from *source_text* using 1-indexed line numbers (inclusive)."""
    lines = source_text.splitlines()
    if not lines:
        return ""
    start_idx = max(0, start_line - 1)
    end_idx = min(len(lines), end_line)
    if start_idx >= end_idx:
        # Fallback if range is invalid or out-of-bounds
        return lines[start_idx] if start_idx < len(lines) else ""
    return "\n".join(lines[start_idx:end_idx])


# ---------------------------------------------------------------------------
# Repository Chunking
# ---------------------------------------------------------------------------


def chunk_repository(
    graph_or_ir: CodeGraph | dict[str, Any],
    source_files: Mapping[str, str],
) -> tuple[CodeChunk, ...]:
    """
    Extract deterministic CodeChunk objects from CodeGraph or IR and source texts.

    Parameters:
        graph_or_ir:  An M7 CodeGraph or an M8 IR dictionary.
        source_files: Mapping from repository-relative path to full file content.

    Returns:
        A deterministically-sorted tuple of immutable CodeChunk objects.
    """
    if isinstance(graph_or_ir, dict):
        graph = ir_to_graph(graph_or_ir)
    else:
        graph = graph_or_ir

    chunks_dict: dict[str, CodeChunk] = {}

    # Index nodes by file path
    file_nodes = [n for n in graph.nodes if n.node_type == NodeType.FILE]

    for file_node in file_nodes:
        path = file_node.get_metadata("path") or file_node.id.removeprefix("file:")
        if path not in source_files:
            continue

        source_text = source_files[path]
        language = file_node.get_metadata("language") or "javascript"
        file_lines = source_text.splitlines()
        total_lines = len(file_lines)

        # Collect architectural roles for this file
        arch_nodes = [
            n for n in graph.nodes if n.id.startswith(f"architecture:{path}:")
        ]
        arch_node_ids = tuple(sorted(n.id for n in arch_nodes))

        # Collect symbol nodes belonging to this file
        file_symbol_nodes = [
            n
            for n in graph.nodes
            if n.node_type in _SYMBOL_NODE_TYPES
            and (
                n.get_metadata("path") == path
                or n.id.startswith(f"symbol:{path}:")
            )
        ]

        if file_symbol_nodes:
            for s_node in file_symbol_nodes:
                s_name = s_node.get_metadata("name") or s_node.label
                try:
                    s_start = int(s_node.get_metadata("start_line", "1"))
                except ValueError:
                    s_start = 1
                try:
                    s_end = int(s_node.get_metadata("end_line", str(s_start)))
                except ValueError:
                    s_end = s_start

                content = _slice_lines(source_text, s_start, s_end)
                chunk_id = make_chunk_id(path, s_name, s_start, s_end)

                # Assemble node associations
                node_ids = tuple(
                    sorted(set((s_node.id, file_node.id) + arch_node_ids))
                )

                # Assemble metadata
                meta: dict[str, str] = {
                    "kind": s_node.node_type.value,
                    "language": language,
                    "path": path,
                    "symbol_name": s_name,
                }
                parent = s_node.get_metadata("parent")
                if parent:
                    meta["parent"] = parent

                for an in arch_nodes:
                    role = an.get_metadata("role")
                    layer = an.get_metadata("layer")
                    if role:
                        meta["architecture_role"] = role
                    if layer:
                        meta["architecture_layer"] = layer

                meta_tuple = tuple(sorted(meta.items()))

                chunk = CodeChunk(
                    id=chunk_id,
                    path=path,
                    language=language,
                    content=content,
                    start_line=s_start,
                    end_line=s_end,
                    symbol_id=s_node.id,
                    symbol_name=s_name,
                    node_ids=node_ids,
                    metadata=meta_tuple,
                )
                chunks_dict[chunk_id] = chunk

        else:
            # File-level chunk when no symbols are present
            start_line = 1
            end_line = max(1, total_lines)
            content = source_text
            chunk_id = make_chunk_id(path, "file", start_line, end_line)
            node_ids = tuple(sorted(set((file_node.id,) + arch_node_ids)))

            meta = {
                "kind": "file",
                "language": language,
                "path": path,
            }
            for an in arch_nodes:
                role = an.get_metadata("role")
                layer = an.get_metadata("layer")
                if role:
                    meta["architecture_role"] = role
                if layer:
                    meta["architecture_layer"] = layer

            meta_tuple = tuple(sorted(meta.items()))

            chunk = CodeChunk(
                id=chunk_id,
                path=path,
                language=language,
                content=content,
                start_line=start_line,
                end_line=end_line,
                symbol_id=None,
                symbol_name=None,
                node_ids=node_ids,
                metadata=meta_tuple,
            )
            chunks_dict[chunk_id] = chunk

    # Deterministic sorting of all chunks
    sorted_chunks = sorted(
        chunks_dict.values(),
        key=lambda c: (c.path, c.start_line, c.end_line, c.id),
    )
    return tuple(sorted_chunks)
