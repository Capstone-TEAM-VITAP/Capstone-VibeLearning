"""
tests/retrieval/test_chunker.py

Comprehensive tests for Milestone 9 code chunking.
Covers:
  - Function, class, method, variable, constant chunks
  - File-level chunks when no symbols exist
  - Empty source handling
  - Exact line range extraction
  - Deterministic chunk IDs
  - Graph node associations (file, symbol, architecture)
  - Duplicate prevention and sorting
  - Same symbol name in different files and scopes
  - Missing source files
  - M8 IR dict input compatibility
"""

from __future__ import annotations

import dataclasses
import pytest

from src.repository.architecture import (
    ArchitecturalClassification,
    ArchitecturalLayer,
    ArchitectureRole,
    FileClassification,
    RepositoryArchitecture,
)
from src.repository.graph import (
    CodeGraph,
    NodeType,
    build_code_graph,
)
from src.repository.graph_ir import graph_to_ir
from src.repository.models import FileInfo
from src.repository.parser import Position
from src.repository.symbols import Symbol, SymbolKind
from src.retrieval.chunker import (
    CodeChunk,
    chunk_repository,
    make_chunk_id,
)


# ===========================================================================
# 1. INDIVIDUAL SYMBOL CHUNKS
# ===========================================================================


class TestIndividualSymbolChunks:
    """Verify slicing and chunk model creation for all symbol types."""

    def test_function_chunk(self) -> None:
        source = "function login(user) {\n  return user.auth();\n}\n"
        f = FileInfo("src/auth.js", "javascript", ".js", len(source))
        s = Symbol("login", SymbolKind.FUNCTION, "src/auth.js", Position(1, 0), Position(3, 1), None)
        graph = build_code_graph(files=[f], symbols=[s])

        chunks = chunk_repository(graph, {"src/auth.js": source})

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.id == "chunk:src/auth.js:login:1:3"
        assert chunk.path == "src/auth.js"
        assert chunk.symbol_name == "login"
        assert chunk.start_line == 1
        assert chunk.end_line == 3
        assert chunk.content == "function login(user) {\n  return user.auth();\n}"
        assert chunk.get_metadata("kind") == "function"
        assert chunk.get_metadata("language") == "javascript"

    def test_class_chunk(self) -> None:
        source = "// Header\nclass AuthService {\n  init() {}\n}\n"
        f = FileInfo("src/service.js", "javascript", ".js", len(source))
        s = Symbol("AuthService", SymbolKind.CLASS, "src/service.js", Position(2, 0), Position(4, 1), None)
        graph = build_code_graph(files=[f], symbols=[s])

        chunks = chunk_repository(graph, {"src/service.js": source})

        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.id == "chunk:src/service.js:AuthService:2:4"
        assert chunk.start_line == 2
        assert chunk.end_line == 4
        assert "class AuthService" in chunk.content

    def test_method_chunk(self) -> None:
        source = "class Svc {\n  authenticate(token) {\n    return true;\n  }\n}\n"
        f = FileInfo("src/svc.js", "javascript", ".js", len(source))
        cls_sym = Symbol("Svc", SymbolKind.CLASS, "src/svc.js", Position(1, 0), Position(5, 1), None)
        m_sym = Symbol("authenticate", SymbolKind.METHOD, "src/svc.js", Position(2, 2), Position(4, 3), "Svc")
        graph = build_code_graph(files=[f], symbols=[cls_sym, m_sym])

        chunks = chunk_repository(graph, {"src/svc.js": source})

        method_chunks = [c for c in chunks if c.symbol_name == "authenticate"]
        assert len(method_chunks) == 1
        mc = method_chunks[0]
        assert mc.get_metadata("parent") == "Svc"
        assert mc.start_line == 2
        assert mc.end_line == 4
        assert "authenticate(token)" in mc.content

    def test_variable_chunk(self) -> None:
        source = "let count = 0;\n"
        f = FileInfo("src/counter.js", "javascript", ".js", len(source))
        s = Symbol("count", SymbolKind.VARIABLE, "src/counter.js", Position(1, 0), Position(1, 14), None)
        graph = build_code_graph(files=[f], symbols=[s])

        chunks = chunk_repository(graph, {"src/counter.js": source})
        assert len(chunks) == 1
        assert chunks[0].symbol_name == "count"
        assert chunks[0].content == "let count = 0;"
        assert chunks[0].get_metadata("kind") == "variable"

    def test_constant_chunk(self) -> None:
        source = "const PORT = 3000;\n"
        f = FileInfo("src/config.js", "javascript", ".js", len(source))
        s = Symbol("PORT", SymbolKind.CONSTANT, "src/config.js", Position(1, 0), Position(1, 19), None)
        graph = build_code_graph(files=[f], symbols=[s])

        chunks = chunk_repository(graph, {"src/config.js": source})
        assert len(chunks) == 1
        assert chunks[0].symbol_name == "PORT"
        assert chunks[0].content == "const PORT = 3000;"
        assert chunks[0].get_metadata("kind") == "constant"


# ===========================================================================
# 2. FILE-LEVEL CHUNKS & EDGE CASES
# ===========================================================================


class TestFileLevelChunksAndEdgeCases:
    """Verify fallback file chunks, empty sources, and missing source handling."""

    def test_file_level_chunk_when_no_symbols(self) -> None:
        source = "// Config file with raw statements\nmodule.exports = { port: 8080 };\n"
        f = FileInfo("src/config.js", "javascript", ".js", len(source))
        graph = build_code_graph(files=[f], symbols=[])

        chunks = chunk_repository(graph, {"src/config.js": source})
        assert len(chunks) == 1
        chunk = chunks[0]
        assert chunk.id == "chunk:src/config.js:file:1:2"
        assert chunk.symbol_id is None
        assert chunk.symbol_name is None
        assert chunk.start_line == 1
        assert chunk.end_line == 2
        assert chunk.content == source
        assert chunk.get_metadata("kind") == "file"

    def test_empty_source_file_handling(self) -> None:
        f = FileInfo("src/empty.js", "javascript", ".js", 0)
        graph = build_code_graph(files=[f], symbols=[])

        chunks = chunk_repository(graph, {"src/empty.js": ""})
        assert len(chunks) == 1
        assert chunks[0].content == ""
        assert chunks[0].start_line == 1

    def test_missing_source_file_silently_skipped(self) -> None:
        f = FileInfo("src/missing.js", "javascript", ".js", 100)
        graph = build_code_graph(files=[f], symbols=[])

        # Source dictionary does not contain src/missing.js
        chunks = chunk_repository(graph, {})
        assert len(chunks) == 0


# ===========================================================================
# 3. GRAPH NODE ASSOCIATIONS & ARCHITECTURE
# ===========================================================================


class TestGraphContextAndMetadata:
    """Verify node_ids association and architectural role inheritance."""

    def test_chunk_node_ids_include_file_symbol_and_architecture(self) -> None:
        source = "export class UserController {}\n"
        path = "src/controllers/userController.js"
        f = FileInfo(path, "javascript", ".js", len(source))
        s = Symbol("UserController", SymbolKind.CLASS, path, Position(1, 0), Position(1, 30), None)

        classification = ArchitecturalClassification(
            path=path,
            role=ArchitectureRole.CONTROLLER,
            layer=ArchitecturalLayer.PRESENTATION,
            evidence=(),
        )
        fc = FileClassification(path, (classification,))
        arch = RepositoryArchitecture((fc,), ())

        graph = build_code_graph(files=[f], symbols=[s], architecture=arch)
        chunks = chunk_repository(graph, {path: source})

        assert len(chunks) == 1
        chunk = chunks[0]

        # Verify node_ids contains file, symbol, and architecture node IDs
        assert f"file:{path}" in chunk.node_ids
        assert f"symbol:{path}:UserController:1:0" in chunk.node_ids
        assert f"architecture:{path}:CONTROLLER" in chunk.node_ids

        # Verify metadata
        assert chunk.get_metadata("architecture_role") == "controller"
        assert chunk.get_metadata("architecture_layer") == "presentation"
        assert chunk.metadata_dict["architecture_role"] == "controller"


# ===========================================================================
# 4. IDENTITY, DETERMINISM & DUPLICATE PREVENTION
# ===========================================================================


class TestChunkIdentityAndDeterminism:
    """Verify deterministic chunk IDs, scopes, and sorted ordering."""

    def test_same_symbol_name_in_different_files_have_distinct_chunk_ids(self) -> None:
        source1 = "function login() { return 1; }\n"
        source2 = "function login() { return 2; }\n"
        f1 = FileInfo("src/a.js", "javascript", ".js", len(source1))
        f2 = FileInfo("src/b.js", "javascript", ".js", len(source2))
        s1 = Symbol("login", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(1, 31), None)
        s2 = Symbol("login", SymbolKind.FUNCTION, "src/b.js", Position(1, 0), Position(1, 31), None)

        graph = build_code_graph(files=[f1, f2], symbols=[s1, s2])
        chunks = chunk_repository(graph, {"src/a.js": source1, "src/b.js": source2})

        assert len(chunks) == 2
        assert chunks[0].id != chunks[1].id
        assert chunks[0].id == "chunk:src/a.js:login:1:1"
        assert chunks[1].id == "chunk:src/b.js:login:1:1"

    def test_same_symbol_name_in_different_scopes_same_file(self) -> None:
        source = "function fn() {\n  let temp = 1;\n}\nfunction other() {\n  let temp = 2;\n}\n"
        f = FileInfo("src/test.js", "javascript", ".js", len(source))
        s1 = Symbol("temp", SymbolKind.VARIABLE, "src/test.js", Position(2, 2), Position(2, 15), "fn")
        s2 = Symbol("temp", SymbolKind.VARIABLE, "src/test.js", Position(5, 2), Position(5, 15), "other")
        fn = Symbol("fn", SymbolKind.FUNCTION, "src/test.js", Position(1, 0), Position(3, 1), None)
        other = Symbol("other", SymbolKind.FUNCTION, "src/test.js", Position(4, 0), Position(6, 1), None)

        graph = build_code_graph(files=[f], symbols=[fn, s1, other, s2])
        chunks = chunk_repository(graph, {"src/test.js": source})

        temp_chunks = [c for c in chunks if c.symbol_name == "temp"]
        assert len(temp_chunks) == 2
        assert temp_chunks[0].id == "chunk:src/test.js:temp:2:2"
        assert temp_chunks[1].id == "chunk:src/test.js:temp:5:5"
        assert temp_chunks[0].id != temp_chunks[1].id

    def test_deterministic_sorting(self) -> None:
        source_z = "function z() {}\n"
        source_a = "function a() {}\n"
        f_z = FileInfo("src/z.js", "javascript", ".js", len(source_z))
        f_a = FileInfo("src/a.js", "javascript", ".js", len(source_a))
        s_z = Symbol("z", SymbolKind.FUNCTION, "src/z.js", Position(1, 0), Position(1, 15), None)
        s_a = Symbol("a", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(1, 15), None)

        graph = build_code_graph(files=[f_z, f_a], symbols=[s_z, s_a])
        chunks = chunk_repository(graph, {"src/z.js": source_z, "src/a.js": source_a})

        # Sorted by path first, so src/a.js precedes src/z.js
        assert chunks[0].path == "src/a.js"
        assert chunks[1].path == "src/z.js"

    def test_chunk_repository_with_m8_ir_dict(self) -> None:
        """Verify chunk_repository seamlessly accepts an M8 IR dictionary."""
        source = "const API_KEY = 'secret';\n"
        f = FileInfo("src/key.js", "javascript", ".js", len(source))
        s = Symbol("API_KEY", SymbolKind.CONSTANT, "src/key.js", Position(1, 0), Position(1, 26), None)
        graph = build_code_graph(files=[f], symbols=[s])
        ir = graph_to_ir(graph)

        chunks = chunk_repository(ir, {"src/key.js": source})
        assert len(chunks) == 1
        assert chunks[0].symbol_name == "API_KEY"
        assert chunks[0].content == "const API_KEY = 'secret';"

    def test_code_chunk_immutability(self) -> None:
        chunk = CodeChunk(
            id="c:1",
            path="a.js",
            language="javascript",
            content="var x = 1;",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name=None,
            node_ids=(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chunk.content = "mutated"  # type: ignore[misc]

    def test_make_chunk_id(self) -> None:
        cid = make_chunk_id("src/auth.js", "login", 10, 25)
        assert cid == "chunk:src/auth.js:login:10:25"

    def test_nested_function_chunks(self) -> None:
        source = (
            "function outer() {\n"
            "  function inner() {\n"
            "    return 42;\n"
            "  }\n"
            "  return inner();\n"
            "}\n"
        )
        f = FileInfo("src/nest.js", "javascript", ".js", len(source))
        outer_sym = Symbol("outer", SymbolKind.FUNCTION, "src/nest.js", Position(1, 0), Position(6, 1), None)
        inner_sym = Symbol("inner", SymbolKind.FUNCTION, "src/nest.js", Position(2, 2), Position(4, 3), "outer")

        graph = build_code_graph(files=[f], symbols=[outer_sym, inner_sym])
        chunks = chunk_repository(graph, {"src/nest.js": source})

        assert len(chunks) == 2
        chunk_names = {c.symbol_name for c in chunks}
        assert chunk_names == {"outer", "inner"}

        inner_chunk = next(c for c in chunks if c.symbol_name == "inner")
        assert inner_chunk.get_metadata("parent") == "outer"
        assert inner_chunk.start_line == 2
        assert inner_chunk.end_line == 4

    def test_multi_symbol_file_chunks(self) -> None:
        source = (
            "const A = 1;\n"
            "let b = 2;\n"
            "class C {\n"
            "  m() {}\n"
            "}\n"
        )
        f = FileInfo("src/all.js", "javascript", ".js", len(source))
        s_a = Symbol("A", SymbolKind.CONSTANT, "src/all.js", Position(1, 0), Position(1, 12), None)
        s_b = Symbol("b", SymbolKind.VARIABLE, "src/all.js", Position(2, 0), Position(2, 10), None)
        s_c = Symbol("C", SymbolKind.CLASS, "src/all.js", Position(3, 0), Position(5, 1), None)
        s_m = Symbol("m", SymbolKind.METHOD, "src/all.js", Position(4, 2), Position(4, 8), "C")

        graph = build_code_graph(files=[f], symbols=[s_a, s_b, s_c, s_m])
        chunks = chunk_repository(graph, {"src/all.js": source})

        assert len(chunks) == 4
        kinds = {c.get_metadata("kind") for c in chunks}
        assert kinds == {"constant", "variable", "class", "method"}

    def test_empty_repository_returns_empty_tuple(self) -> None:
        graph = build_code_graph(include_repo_node=False)
        chunks = chunk_repository(graph, {})
        assert chunks == ()

    def test_chunk_metadata_helpers(self) -> None:
        chunk = CodeChunk(
            id="c:test",
            path="test.js",
            language="javascript",
            content="const x = 1;",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name="x",
            node_ids=(),
            metadata=(("role", "utility"), ("env", "prod")),
        )
        assert chunk.get_metadata("role") == "utility"
        assert chunk.get_metadata("missing") is None
        assert chunk.get_metadata("missing", default="default_val") == "default_val"
        d = chunk.metadata_dict
        assert d == {"role": "utility", "env": "prod"}
        # Mutating dictionary doesn't mutate chunk
        d["role"] = "mutated"
        assert chunk.get_metadata("role") == "utility"

    def test_slice_exact_indentation_preserved(self) -> None:
        source = "function indented() {\n    const spaces = 4;\n    return spaces;\n}\n"
        f = FileInfo("src/indent.js", "javascript", ".js", len(source))
        s = Symbol("indented", SymbolKind.FUNCTION, "src/indent.js", Position(1, 0), Position(4, 1), None)
        graph = build_code_graph(files=[f], symbols=[s])

        chunks = chunk_repository(graph, {"src/indent.js": source})
        assert "    const spaces = 4;" in chunks[0].content

    def test_chunk_immutability(self) -> None:
        chunk = CodeChunk(
            id="c:freeze",
            path="frozen.js",
            language="javascript",
            content="const x = 1;",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name="x",
            node_ids=(),
            metadata=(),
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            chunk.content = "mutated"  # type: ignore[misc]

    def test_chunk_representation(self) -> None:
        chunk = CodeChunk(
            id="c:repr",
            path="repr.js",
            language="javascript",
            content="const x = 1;",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name="x",
            node_ids=(),
            metadata=(),
        )
        r = repr(chunk)
        assert "c:repr" in r
        assert "repr.js" in r

    def test_make_chunk_id_consistency(self) -> None:
        id1 = make_chunk_id("src/app.js", "main", 1, 10)
        id2 = make_chunk_id("src/app.js", "main", 1, 10)
        assert id1 == id2
        assert id1 == "chunk:src/app.js:main:1:10"

    def test_chunk_ordering_by_path_then_start_line(self) -> None:
        f1 = FileInfo("src/b.js", "javascript", ".js", 100)
        f2 = FileInfo("src/a.js", "javascript", ".js", 100)
        s_b1 = Symbol("b_fn", SymbolKind.FUNCTION, "src/b.js", Position(5, 0), Position(8, 1), None)
        s_a2 = Symbol("a_fn2", SymbolKind.FUNCTION, "src/a.js", Position(10, 0), Position(15, 1), None)
        s_a1 = Symbol("a_fn1", SymbolKind.FUNCTION, "src/a.js", Position(1, 0), Position(4, 1), None)

        source_a = "\n" * 20
        source_b = "\n" * 20

        graph = build_code_graph(files=[f1, f2], symbols=[s_b1, s_a2, s_a1])
        chunks = chunk_repository(graph, {"src/a.js": source_a, "src/b.js": source_b})

        assert [c.id for c in chunks] == [
            "chunk:src/a.js:a_fn1:1:4",
            "chunk:src/a.js:a_fn2:10:15",
            "chunk:src/b.js:b_fn:5:8",
        ]

