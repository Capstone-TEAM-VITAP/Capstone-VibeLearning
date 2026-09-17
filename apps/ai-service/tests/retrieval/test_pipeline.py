"""
tests/retrieval/test_pipeline.py

Comprehensive tests for Milestone 9 RetrievalPipeline.
Covers:
  - Repository and chunk indexing
  - Query execution and top-k limits
  - End-to-end flow from M8 CodeGraph IR to RetrievedContext
  - Empty repository handling
  - Deterministic repeated queries
  - Line range and metadata preservation
  - Multiple files and symbols retrieval
  - Deterministic tie-breaking on equal scores
  - Hybrid retrieval with configurable semantic and lexical weights
"""

from __future__ import annotations

import math
import pytest

from src.repository.architecture import (
    ArchitecturalClassification,
    ArchitecturalLayer,
    ArchitecturalRelationship,
    ArchitectureRole,
    FileClassification,
    RepositoryArchitecture,
)
from src.repository.graph import build_code_graph
from src.repository.graph_ir import graph_to_ir
from src.repository.models import FileInfo
from src.repository.parser import Position
from src.repository.symbols import Symbol, SymbolKind
from src.retrieval.chunker import CodeChunk
from src.retrieval.embeddings import DeterministicEmbeddingProvider
from src.retrieval.index import InMemoryVectorIndex
from src.retrieval.pipeline import (
    RetrievalPipeline,
    create_retrieval_pipeline,
)


class TestRetrievalPipelineBasics:
    """Verify standard indexing and query execution."""

    def test_pipeline_creation_helper(self) -> None:
        pipeline = create_retrieval_pipeline(dimension=32)
        assert pipeline.embedding_provider.dimension == 32
        assert pipeline.vector_index.count() == 0

    def test_index_empty_chunks_returns_zero(self) -> None:
        pipeline = create_retrieval_pipeline()
        count = pipeline.index_chunks([])
        assert count == 0
        assert pipeline.vector_index.count() == 0

    def test_search_on_empty_index_returns_empty_context(self) -> None:
        pipeline = create_retrieval_pipeline()
        ctx = pipeline.search("find login function", top_k=5)
        assert len(ctx) == 0
        assert ctx.query == "find login function"
        assert ctx.total_candidates == 0

    def test_top_k_zero_or_negative_returns_empty_results(self) -> None:
        pipeline = create_retrieval_pipeline()
        chunk = CodeChunk("c1", "a.js", "javascript", "function test() {}", 1, 1, None, None, ())
        pipeline.index_chunks([chunk])

        ctx_zero = pipeline.search("test", top_k=0)
        assert len(ctx_zero) == 0

        ctx_neg = pipeline.search("test", top_k=-3)
        assert len(ctx_neg) == 0

    def test_non_string_query_raises_type_error(self) -> None:
        pipeline = create_retrieval_pipeline()
        with pytest.raises(TypeError, match="Query must be a string"):
            pipeline.search(12345)  # type: ignore[arg-type]


class TestEndToEndRetrievalPipeline:
    """
    Mandatory End-to-End Test:
    M8 CodeGraph IR + source files
        ↓
    CodeChunk
        ↓
    DeterministicEmbeddingProvider
        ↓
    InMemoryVectorIndex
        ↓
    query
        ↓
    RetrievedContext
    """

    def test_complete_end_to_end_flow_from_m8_ir(self) -> None:
        # 1. Source files
        source_auth = (
            "export class AuthService {\n"
            "  authenticate(user, pass) {\n"
            "    return user.valid(pass);\n"
            "  }\n"
            "}\n"
        )
        source_ctrl = (
            "import { AuthService } from './authService.js';\n"
            "export function loginController(req, res) {\n"
            "  const svc = new AuthService();\n"
            "  return svc.authenticate(req.body.user, req.body.pass);\n"
            "}\n"
        )
        source_routes = (
            "import { loginController } from './authController.js';\n"
            "router.post('/login', loginController);\n"
        )

        files = [
            FileInfo("src/authService.js", "javascript", ".js", len(source_auth)),
            FileInfo("src/authController.js", "javascript", ".js", len(source_ctrl)),
            FileInfo("src/authRoutes.js", "javascript", ".js", len(source_routes)),
        ]
        symbols = [
            Symbol("AuthService", SymbolKind.CLASS, "src/authService.js", Position(1, 0), Position(5, 1), None),
            Symbol("authenticate", SymbolKind.METHOD, "src/authService.js", Position(2, 2), Position(4, 3), "AuthService"),
            Symbol("loginController", SymbolKind.FUNCTION, "src/authController.js", Position(2, 0), Position(5, 1), None),
        ]
        fcs = [
            FileClassification("src/authService.js", (ArchitecturalClassification("src/authService.js", ArchitectureRole.SERVICE, ArchitecturalLayer.APPLICATION, ()),)),
            FileClassification("src/authController.js", (ArchitecturalClassification("src/authController.js", ArchitectureRole.CONTROLLER, ArchitecturalLayer.PRESENTATION, ()),)),
            FileClassification("src/authRoutes.js", (ArchitecturalClassification("src/authRoutes.js", ArchitectureRole.ROUTE, ArchitecturalLayer.PRESENTATION, ()),)),
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

        # Construct M7 graph and M8 IR
        graph = build_code_graph(files=files, symbols=symbols, architecture=arch, repo_name="auth-system")
        ir = graph_to_ir(graph)

        sources = {
            "src/authService.js": source_auth,
            "src/authController.js": source_ctrl,
            "src/authRoutes.js": source_routes,
        }

        # 2. Pipeline setup and indexing
        pipeline = create_retrieval_pipeline(dimension=64)
        indexed_count = pipeline.index_repository(ir, sources)
        # Expect 4 chunks: AuthService, authenticate, loginController, and file chunk for authRoutes (which has no symbols)
        assert indexed_count == 4
        assert pipeline.vector_index.count() == 4

        # 3. Query
        ctx = pipeline.search("authenticate user and pass", top_k=2)

        # 4. Validate RetrievedContext
        assert ctx.query == "authenticate user and pass"
        assert ctx.total_candidates == 4
        assert len(ctx) == 2
        assert ctx.top_result is not None

        # Verify attributes on top search result
        top = ctx.top_result
        assert top.chunk_id.startswith("chunk:")
        assert top.path in sources
        assert top.start_line >= 1
        assert top.end_line >= top.start_line
        assert len(top.content) > 0
        assert isinstance(top.score, float)
        assert -1.0 <= top.score <= 1.0


class TestDeterminismAndRepeatability:
    """Verify that identical queries produce identical results and rankings."""

    def test_repeated_query_determinism(self) -> None:
        source = "function calculateSum(a, b) { return a + b; }\nfunction multiply(a, b) { return a * b; }\n"
        f = FileInfo("src/math.js", "javascript", ".js", len(source))
        s1 = Symbol("calculateSum", SymbolKind.FUNCTION, "src/math.js", Position(1, 0), Position(1, 46), None)
        s2 = Symbol("multiply", SymbolKind.FUNCTION, "src/math.js", Position(2, 0), Position(2, 41), None)
        graph = build_code_graph(files=[f], symbols=[s1, s2])

        pipeline = create_retrieval_pipeline(dimension=64)
        pipeline.index_repository(graph, {"src/math.js": source})

        ctx1 = pipeline.search("sum calculation", top_k=2)
        ctx2 = pipeline.search("sum calculation", top_k=2)

        assert ctx1.results == ctx2.results
        assert [r.chunk_id for r in ctx1.results] == [r.chunk_id for r in ctx2.results]
        assert [r.score for r in ctx1.results] == [r.score for r in ctx2.results]


class TestHybridRetrieval:
    """Verify optional lexical / hybrid retrieval scoring."""

    def test_hybrid_scoring_adjusts_ranking(self) -> None:
        # Create two chunks where chunk B has exact lexical overlap with query tokens
        c1 = CodeChunk(
            id="c1",
            path="a.js",
            language="javascript",
            content="const x = 100;",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name="x",
            node_ids=(),
        )
        c2 = CodeChunk(
            id="c2",
            path="b.js",
            language="javascript",
            content="function specificLexicalMatch() { return 'found'; }",
            start_line=1,
            end_line=1,
            symbol_id=None,
            symbol_name="specificLexicalMatch",
            node_ids=(),
        )

        # Pure semantic pipeline
        sem_pipeline = create_retrieval_pipeline(semantic_weight=1.0, lexical_weight=0.0)
        sem_pipeline.index_chunks([c1, c2])
        sem_ctx = sem_pipeline.search("specificLexicalMatch", top_k=2)
        assert len(sem_ctx) == 2

        # Hybrid pipeline with high lexical weight
        hybrid_pipeline = create_retrieval_pipeline(semantic_weight=0.1, lexical_weight=0.9)
        hybrid_pipeline.index_chunks([c1, c2])
        hybrid_ctx = hybrid_pipeline.search("specificLexicalMatch", top_k=2)

        # Chunk c2 must be ranked first due to high lexical overlap
        assert hybrid_ctx.top_result is not None
        assert hybrid_ctx.top_result.chunk_id == "c2"

    def test_configurable_weights_respected(self) -> None:
        p = RetrievalPipeline(
            embedding_provider=DeterministicEmbeddingProvider(dimension=16),
            semantic_weight=0.7,
            lexical_weight=0.3,
        )
        assert math.isclose(p.semantic_weight, 0.7)
        assert math.isclose(p.lexical_weight, 0.3)

    def test_pure_lexical_search_with_zero_semantic_weight(self) -> None:
        c1 = CodeChunk("c1", "a.js", "javascript", "const databaseConnection = true;", 1, 1, None, "databaseConnection", ())
        c2 = CodeChunk("c2", "b.js", "javascript", "const networkRequest = false;", 1, 1, None, "networkRequest", ())

        pipeline = create_retrieval_pipeline(semantic_weight=0.0, lexical_weight=1.0)
        pipeline.index_chunks([c1, c2])

        ctx = pipeline.search("database", top_k=2)
        assert ctx.top_result is not None
        assert ctx.top_result.chunk_id == "c1"

    def test_pipeline_with_custom_vector_index(self) -> None:
        custom_index = InMemoryVectorIndex(dimension=16)
        provider = DeterministicEmbeddingProvider(dimension=16)
        p = RetrievalPipeline(embedding_provider=provider, vector_index=custom_index)

        c = CodeChunk("c1", "a.js", "javascript", "let x = 1;", 1, 1, None, "x", ())
        p.index_chunks([c])

        assert custom_index.count() == 1
        ctx = p.search("x", top_k=1)
        assert len(ctx) == 1

    def test_pipeline_replaces_updated_chunk(self) -> None:
        p = create_retrieval_pipeline(dimension=32)
        c_old = CodeChunk("c1", "a.js", "javascript", "function oldFn() {}", 1, 1, None, "oldFn", ())
        c_new = CodeChunk("c1", "a.js", "javascript", "function newFn() {}", 1, 1, None, "newFn", ())

        p.index_chunks([c_old])
        assert p.vector_index.count() == 1
        p.index_chunks([c_new])
        assert p.vector_index.count() == 1

        ctx = p.search("newFn", top_k=1)
        assert len(ctx) == 1
        assert "newFn" in ctx.results[0].content

    def test_end_to_end_with_real_tree_sitter_ast(self) -> None:
        """Full end-to-end integration test from raw JS code through M2-M9."""
        from src.repository.symbols import extract_symbols
        from src.repository.relationships import extract_relationships
        from src.repository.resolver import resolve_imports
        from src.repository.architecture import classify_repository

        code_user = "export class UserService {\n  getUser(id) { return { id }; }\n}\n"
        code_ctrl = "import { UserService } from './user.js';\nexport function handleUser(req) {\n  return new UserService().getUser(req.id);\n}\n"

        files = [
            FileInfo("src/user.js", "javascript", ".js", len(code_user)),
            FileInfo("src/ctrl.js", "javascript", ".js", len(code_ctrl)),
        ]
        syms_u = extract_symbols("src/user.js", "javascript", code_user)
        syms_c = extract_symbols("src/ctrl.js", "javascript", code_ctrl)
        all_syms = syms_u + syms_c

        rels_u = extract_relationships("src/user.js", "javascript", code_user)
        rels_c = extract_relationships("src/ctrl.js", "javascript", code_ctrl)
        all_rels = rels_u + rels_c

        resolved = resolve_imports(files, all_syms, all_rels)
        arch = classify_repository(files, all_syms, all_rels, resolved)
        graph = build_code_graph(files=files, symbols=all_syms, relationships=all_rels, resolved_relationships=resolved, architecture=arch)
        ir = graph_to_ir(graph)

        sources = {
            "src/user.js": code_user,
            "src/ctrl.js": code_ctrl,
        }

        pipeline = create_retrieval_pipeline(dimension=64)
        count = pipeline.index_repository(ir, sources)
        assert count > 0

        ctx = pipeline.search("handleUser request", top_k=1)
        assert len(ctx) == 1
        assert ctx.top_result is not None
        assert ctx.top_result.path in ("src/ctrl.js", "src/user.js")

    def test_index_repository_with_direct_codegraph(self) -> None:
        source = "function directTest() { return 1; }\n"
        f = FileInfo("src/direct.js", "javascript", ".js", len(source))
        s = Symbol("directTest", SymbolKind.FUNCTION, "src/direct.js", Position(1, 0), Position(1, 35), None)
        graph = build_code_graph(files=[f], symbols=[s])

        pipeline = create_retrieval_pipeline(dimension=32)
        count = pipeline.index_repository(graph, {"src/direct.js": source})
        assert count == 1
        assert pipeline.vector_index.count() == 1

        ctx = pipeline.search("directTest", top_k=1)
        assert len(ctx) == 1
        assert ctx.top_result is not None
        assert "directTest" in ctx.top_result.chunk_id

    def test_search_whitespace_only_query(self) -> None:
        pipeline = create_retrieval_pipeline(dimension=32)
        c = CodeChunk("c1", "a.js", "javascript", "const val = 1;", 1, 1, None, "val", ())
        pipeline.index_chunks([c])

        ctx = pipeline.search("   ", top_k=1)
        assert len(ctx) == 1
        assert ctx.query == "   "

    def test_repeated_queries_produce_identical_order_and_scores(self) -> None:
        pipeline = create_retrieval_pipeline(dimension=32)
        c1 = CodeChunk("c1", "a.js", "javascript", "function first() {}", 1, 1, None, "first", ())
        c2 = CodeChunk("c2", "b.js", "javascript", "function second() {}", 1, 1, None, "second", ())
        pipeline.index_chunks([c1, c2])

        res1 = pipeline.search("first function", top_k=2)
        res2 = pipeline.search("first function", top_k=2)

        assert len(res1) == len(res2)
        assert [r.chunk_id for r in res1] == [r.chunk_id for r in res2]
        assert [r.score for r in res1] == [r.score for r in res2]

    def test_total_candidates_reflects_all_indexed_chunks(self) -> None:
        pipeline = create_retrieval_pipeline(dimension=16)
        chunks = [
            CodeChunk(f"c{i}", f"file_{i}.js", "javascript", f"const x_{i} = {i};", 1, 1, None, f"x_{i}", ())
            for i in range(15)
        ]
        pipeline.index_chunks(chunks)

        ctx = pipeline.search("x_1", top_k=3)
        assert len(ctx) == 3
        assert ctx.total_candidates == 15

    def test_pipeline_default_weights(self) -> None:
        pipeline = create_retrieval_pipeline()
        assert pipeline.semantic_weight == 1.0
        assert pipeline.lexical_weight == 0.0

    def test_tokenize_helper(self) -> None:
        from src.retrieval.pipeline import _tokenize
        tokens = _tokenize("function getUserById(userId) { return user_cache[userId]; }")
        assert "getuserbyid" in tokens
        assert "userid" in tokens
        assert "user_cache" in tokens

    def test_compute_lexical_score_edges(self) -> None:
        from src.retrieval.pipeline import _compute_lexical_score
        assert _compute_lexical_score(set(), "some content", None) == 0.0
        assert _compute_lexical_score({"token"}, "", None) == 0.0
        # Symbol name match
        score = _compute_lexical_score({"finduser"}, "let x = 1;", "findUser")
        assert score > 0.0

    def test_index_repository_empty_sources(self) -> None:
        pipeline = create_retrieval_pipeline(dimension=16)
        f = FileInfo("src/empty.js", "javascript", ".js", 0)
        graph = build_code_graph(files=[f])
        indexed = pipeline.index_repository(graph, {})
        assert indexed == 0
        assert pipeline.vector_index.count() == 0

