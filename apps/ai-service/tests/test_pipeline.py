"""
tests/test_pipeline.py

Comprehensive test suite for Person 1 Repository Intelligence End-to-End Pipeline.
Validates orchestration of M1–M8 into an immutable, deterministic result.

Tests include all 22 required items:
1. Missing repository path
2. Repository path points to a file
3. Empty repository
4. Small JavaScript repository
5. Multiple files
6. File scanning integration
7. Symbol extraction integration
8. Relationship extraction integration
9. Cross-file resolution integration
10. Architecture integration
11. CodeGraph generation
12. Graph IR generation
13. Repository name handling
14. Explicit repo_name
15. Automatic repo_name
16. Deterministic repeated analysis
17. Ignored directories
18. Unsupported files
19. Nested directories
20. Malformed source handling where supported
21. Result model immutability
22. IR validation
Plus the Section 9 representative multi-layer end-to-end repository test.
"""

from __future__ import annotations

import sys
from dataclasses import FrozenInstanceError
from pathlib import Path
from typing import Any

import pytest

# Ensure src/ is on python path
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from repository.architecture import ArchitectureRole
from repository.graph import EdgeType, NodeType
from repository.graph_ir import GRAPH_IR_SCHEMA_VERSION, validate_graph_ir
from repository.pipeline import (
    RepositoryAnalysisError,
    RepositoryAnalysisResult,
    analyze_repository,
)
from repository.resolver import ResolutionStatus


# ===========================================================================
# 1. Missing repository path
# ===========================================================================


def test_1_missing_repository_path(tmp_path: Path) -> None:
    missing_dir = tmp_path / "non_existent_folder"
    with pytest.raises(RepositoryAnalysisError, match="does not exist"):
        analyze_repository(missing_dir)


# ===========================================================================
# 2. Repository path points to a file
# ===========================================================================


def test_2_repository_path_points_to_a_file(tmp_path: Path) -> None:
    file_path = tmp_path / "not_a_dir.js"
    file_path.write_text("console.log(1);", encoding="utf-8")
    with pytest.raises(RepositoryAnalysisError, match="not a directory"):
        analyze_repository(file_path)


# ===========================================================================
# 3. Empty repository
# ===========================================================================


def test_3_empty_repository(tmp_path: Path) -> None:
    empty_repo = tmp_path / "empty_repo"
    empty_repo.mkdir()

    result = analyze_repository(empty_repo)
    assert isinstance(result, RepositoryAnalysisResult)
    assert result.repository_name == "empty_repo"
    assert len(result.files) == 0
    assert len(result.symbols) == 0
    assert len(result.relationships) == 0
    assert len(result.resolved_relationships) == 0
    assert len(result.architecture.file_classifications) == 0
    assert len(result.graph.nodes) == 1
    assert result.graph.nodes[0].node_type == NodeType.REPOSITORY
    assert len(result.graph.edges) == 0
    validate_graph_ir(result.ir)


# ===========================================================================
# 4. Small JavaScript repository
# ===========================================================================


def test_4_small_javascript_repository(tmp_path: Path) -> None:
    repo = tmp_path / "small_js_repo"
    repo.mkdir()
    (repo / "math.js").write_text(
        """
export function square(n) {
    return n * n;
}
""",
        encoding="utf-8",
    )

    result = analyze_repository(repo)
    assert len(result.files) == 1
    assert result.files[0].path == "math.js"
    assert any(s.name == "square" for s in result.symbols)
    assert any(r.target_name == "square" for r in result.relationships)


# ===========================================================================
# 5. Multiple files
# ===========================================================================


def test_5_multiple_files(tmp_path: Path) -> None:
    repo = tmp_path / "multi_files_repo"
    repo.mkdir()
    (repo / "a.js").write_text("export const A = 1;", encoding="utf-8")
    (repo / "b.js").write_text("export const B = 2;", encoding="utf-8")
    (repo / "c.js").write_text("export const C = 3;", encoding="utf-8")

    result = analyze_repository(repo)
    assert len(result.files) == 3
    paths = {f.path for f in result.files}
    assert paths == {"a.js", "b.js", "c.js"}


# ===========================================================================
# 6. File scanning integration
# ===========================================================================


def test_6_file_scanning_integration(tmp_path: Path) -> None:
    repo = tmp_path / "scan_repo"
    repo.mkdir()
    (repo / "main.js").write_text("console.log('main');", encoding="utf-8")
    (repo / "util.js").write_text("console.log('util');", encoding="utf-8")

    result = analyze_repository(repo)
    assert len(result.files) == 2
    for fi in result.files:
        assert fi.language == "javascript"
        assert fi.extension == ".js"
        assert fi.size > 0


# ===========================================================================
# 7. Symbol extraction integration
# ===========================================================================


def test_7_symbol_extraction_integration(tmp_path: Path) -> None:
    repo = tmp_path / "symbol_repo"
    repo.mkdir()
    (repo / "service.js").write_text(
        """
export class UserService {
    getUser(id) {
        return id;
    }
}
export const DEFAULT_USER = "guest";
""",
        encoding="utf-8",
    )

    result = analyze_repository(repo)
    sym_map = {s.name: s for s in result.symbols}
    assert "UserService" in sym_map
    assert "getUser" in sym_map
    assert "DEFAULT_USER" in sym_map
    assert sym_map["getUser"].parent == "UserService"


# ===========================================================================
# 8. Relationship extraction integration
# ===========================================================================


def test_8_relationship_extraction_integration(tmp_path: Path) -> None:
    repo = tmp_path / "rel_repo"
    repo.mkdir()
    (repo / "index.js").write_text(
        """
import { helper } from "./helper.js";

function run() {
    helper();
}
export { run };
""",
        encoding="utf-8",
    )

    result = analyze_repository(repo)
    kinds = {r.kind.value for r in result.relationships}
    assert "imports" in kinds
    assert "calls" in kinds
    assert "exports" in kinds


# ===========================================================================
# 9. Cross-file resolution integration
# ===========================================================================


def test_9_cross_file_resolution_integration(tmp_path: Path) -> None:
    repo = tmp_path / "cross_repo"
    repo.mkdir()
    (repo / "source.js").write_text(
        "export function add(a, b) { return a + b; }", encoding="utf-8"
    )
    (repo / "consumer.js").write_text(
        """
import { add } from "./source.js";
function exec() { return add(1, 2); }
export { exec };
""",
        encoding="utf-8",
    )

    result = analyze_repository(repo)
    resolved = result.resolved_relationships
    assert len(resolved) >= 1
    res_import = next(
        r for r in resolved if r.source_relationship.target_name == "add"
    )
    assert res_import.status == ResolutionStatus.RESOLVED
    assert res_import.target_path == "source.js"
    assert res_import.target_symbol_id is not None
    assert res_import.target_symbol_id.name == "add"


# ===========================================================================
# 10. Architecture integration
# ===========================================================================


def test_10_architecture_integration(tmp_path: Path) -> None:
    repo = tmp_path / "arch_repo"
    repo.mkdir()
    src = repo / "src"
    src.mkdir()
    (src / "userController.js").write_text(
        "export function handleReq() {}", encoding="utf-8"
    )
    (src / "userService.js").write_text(
        "export function findUser() {}", encoding="utf-8"
    )

    result = analyze_repository(repo)
    classifs = {
        fc.path: [c.role for c in fc.classifications]
        for fc in result.architecture.file_classifications
    }
    assert "src/userController.js" in classifs
    assert ArchitectureRole.CONTROLLER in classifs["src/userController.js"]
    assert "src/userService.js" in classifs
    assert ArchitectureRole.SERVICE in classifs["src/userService.js"]


# ===========================================================================
# 11. CodeGraph generation
# ===========================================================================


def test_11_codegraph_generation(tmp_path: Path) -> None:
    repo = tmp_path / "graph_repo"
    repo.mkdir()
    (repo / "fileA.js").write_text("export function funcA() {}", encoding="utf-8")

    result = analyze_repository(repo)
    graph = result.graph
    assert graph is not None
    node_ids = {n.id for n in graph.nodes}
    assert "repo:graph_repo" in node_ids
    assert "file:fileA.js" in node_ids
    assert any("funcA" in nid for nid in node_ids)


# ===========================================================================
# 12. Graph IR generation
# ===========================================================================


def test_12_graph_ir_generation(tmp_path: Path) -> None:
    repo = tmp_path / "ir_repo"
    repo.mkdir()
    (repo / "mod.js").write_text("export const NUM = 42;", encoding="utf-8")

    result = analyze_repository(repo)
    ir = result.ir
    assert isinstance(ir, dict)
    assert ir["schema_version"] == GRAPH_IR_SCHEMA_VERSION
    assert "repository" in ir
    assert "nodes" in ir
    assert "edges" in ir
    assert ir["repository"]["name"] == "ir_repo"


# ===========================================================================
# 13. Repository name handling
# ===========================================================================


def test_13_repository_name_handling(tmp_path: Path) -> None:
    repo = tmp_path / "my_test_repo"
    repo.mkdir()

    # Derived
    res_default = analyze_repository(repo)
    assert res_default.repository_name == "my_test_repo"

    # Explicit
    res_custom = analyze_repository(repo, repo_name="custom_override")
    assert res_custom.repository_name == "custom_override"


# ===========================================================================
# 14. Explicit repo_name
# ===========================================================================


def test_14_explicit_repo_name(tmp_path: Path) -> None:
    repo = tmp_path / "dir_name_ignored"
    repo.mkdir()

    result = analyze_repository(repo, repo_name="ExplicitProjectName")
    assert result.repository_name == "ExplicitProjectName"
    assert result.graph.get_node("repo:ExplicitProjectName") is not None
    assert result.ir["repository"]["name"] == "ExplicitProjectName"


# ===========================================================================
# 15. Automatic repo_name
# ===========================================================================


def test_15_automatic_repo_name(tmp_path: Path) -> None:
    repo = tmp_path / "auto_repo_123"
    repo.mkdir()

    result = analyze_repository(repo)
    assert result.repository_name == "auto_repo_123"
    assert result.graph.get_node("repo:auto_repo_123") is not None


# ===========================================================================
# 16. Deterministic repeated analysis
# ===========================================================================


def test_16_deterministic_repeated_analysis(tmp_path: Path) -> None:
    repo = tmp_path / "determinism_repo"
    repo.mkdir()
    (repo / "z.js").write_text("export function zeta() { return 1; }", encoding="utf-8")
    (repo / "a.js").write_text("export function alpha() { return 2; }", encoding="utf-8")
    (repo / "m.js").write_text(
        """
import { zeta } from "./z.js";
import { alpha } from "./a.js";
function mid() { return zeta() + alpha(); }
export { mid };
""",
        encoding="utf-8",
    )

    r1 = analyze_repository(repo)
    r2 = analyze_repository(repo)

    assert [f.path for f in r1.files] == [f.path for f in r2.files]
    assert [s.name for s in r1.symbols] == [s.name for s in r2.symbols]
    assert [r.target_name for r in r1.relationships] == [
        r.target_name for r in r2.relationships
    ]
    assert [rr.status for rr in r1.resolved_relationships] == [
        rr.status for rr in r2.resolved_relationships
    ]
    assert [n.id for n in r1.graph.nodes] == [n.id for n in r2.graph.nodes]
    assert [e.id for e in r1.graph.edges] == [e.id for e in r2.graph.edges]
    assert r1.ir == r2.ir


# ===========================================================================
# 17. Ignored directories
# ===========================================================================


def test_17_ignored_directories(tmp_path: Path) -> None:
    repo = tmp_path / "ignore_dirs_repo"
    repo.mkdir()
    (repo / "app.js").write_text("export const x = 1;", encoding="utf-8")

    node_modules = repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "pkg.js").write_text("console.log('ignored');", encoding="utf-8")

    dist = repo / "dist"
    dist.mkdir()
    (dist / "bundle.js").write_text("console.log('ignored');", encoding="utf-8")

    result = analyze_repository(repo)
    paths = [f.path for f in result.files]
    assert paths == ["app.js"]
    assert not any("node_modules" in p for p in paths)
    assert not any("dist" in p for p in paths)


# ===========================================================================
# 18. Unsupported files
# ===========================================================================


def test_18_unsupported_files(tmp_path: Path) -> None:
    repo = tmp_path / "unsupported_repo"
    repo.mkdir()
    (repo / "index.js").write_text("export function main() {}", encoding="utf-8")
    (repo / "README.md").write_text("# Documentation", encoding="utf-8")
    (repo / "config.json").write_text('{"port": 8080}', encoding="utf-8")
    (repo / "styles.css").write_text("body { margin: 0; }", encoding="utf-8")

    result = analyze_repository(repo)
    paths = [f.path for f in result.files]
    assert "index.js" in paths
    assert "README.md" in paths
    assert "config.json" in paths
    assert "styles.css" in paths

    # Symbols extracted only from supported JS files
    for s in result.symbols:
        assert s.path == "index.js"


# ===========================================================================
# 19. Nested directories
# ===========================================================================


def test_19_nested_directories(tmp_path: Path) -> None:
    repo = tmp_path / "nested_repo"
    repo.mkdir()
    deep_dir = repo / "src" / "api" / "v1" / "endpoints"
    deep_dir.mkdir(parents=True)
    (deep_dir / "users.js").write_text(
        "export function getUsers() {}", encoding="utf-8"
    )

    result = analyze_repository(repo)
    assert len(result.files) == 1
    assert result.files[0].path == "src/api/v1/endpoints/users.js"
    assert result.symbols[0].path == "src/api/v1/endpoints/users.js"


# ===========================================================================
# 20. Malformed source handling where supported
# ===========================================================================


def test_20_malformed_source_handling(tmp_path: Path) -> None:
    repo = tmp_path / "malformed_source_repo"
    repo.mkdir()
    (repo / "broken.js").write_text(
        """
function beforeError() { return 1; }
const @@@ invalid syntax ;;;
function afterError() { return 2; }
""",
        encoding="utf-8",
    )

    result = analyze_repository(repo)
    sym_names = {s.name for s in result.symbols}
    assert "beforeError" in sym_names
    assert "afterError" in sym_names
    validate_graph_ir(result.ir)


# ===========================================================================
# 21. Result model immutability
# ===========================================================================


def test_21_result_model_immutability(tmp_path: Path) -> None:
    repo = tmp_path / "immut_repo"
    repo.mkdir()
    (repo / "a.js").write_text("export const A = 1;", encoding="utf-8")

    result = analyze_repository(repo)
    assert isinstance(result.files, tuple)
    assert isinstance(result.symbols, tuple)
    assert isinstance(result.relationships, tuple)
    assert isinstance(result.resolved_relationships, tuple)

    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.repository_name = "mutated"  # type: ignore[misc]

    with pytest.raises((FrozenInstanceError, AttributeError)):
        result.files = ()  # type: ignore[misc]


# ===========================================================================
# 22. IR validation
# ===========================================================================


def test_22_ir_validation(tmp_path: Path) -> None:
    repo = tmp_path / "ir_val_repo"
    repo.mkdir()
    (repo / "test.js").write_text("export function hello() {}", encoding="utf-8")

    result = analyze_repository(repo)
    validate_graph_ir(result.ir)
    assert result.ir["schema_version"] == "1.0"
    assert "repository" in result.ir
    assert "nodes" in result.ir
    assert "edges" in result.ir


# ===========================================================================
# Section 9: Complete Multi-Layer End-to-End Test Case
# ===========================================================================


def test_end_to_end_sample_repo(tmp_path: Path) -> None:
    """
    Creates the representative repository structure specified in Section 9:
    sample-repo/
        src/
            routes/
                auth.js
            controllers/
                authController.js
            services/
                authService.js
            models/
                User.js
        node_modules/
            ignored.js
        dist/
            ignored.js
    """
    sample_repo = tmp_path / "sample-repo"
    sample_repo.mkdir()

    # Directories
    src_dir = sample_repo / "src"
    routes_dir = src_dir / "routes"
    controllers_dir = src_dir / "controllers"
    services_dir = src_dir / "services"
    models_dir = src_dir / "models"

    for d in (routes_dir, controllers_dir, services_dir, models_dir):
        d.mkdir(parents=True)

    # Ignored directories
    node_modules = sample_repo / "node_modules"
    node_modules.mkdir()
    (node_modules / "ignored.js").write_text(
        "module.exports = {};", encoding="utf-8"
    )

    dist_dir = sample_repo / "dist"
    dist_dir.mkdir()
    (dist_dir / "ignored.js").write_text(
        "console.log('dist');", encoding="utf-8"
    )

    # 1. models/User.js
    (models_dir / "User.js").write_text(
        """
export class User {
    constructor(username, email) {
        this.username = username;
        this.email = email;
    }
}
""",
        encoding="utf-8",
    )

    # 2. services/authService.js
    (services_dir / "authService.js").write_text(
        """
import { User } from "../models/User.js";

function helper() {
    return true;
}

export class AuthService {
    createUser(username, email) {
        return new User(username, email);
    }
}

function validateCredentials(username, password) {
    helper();
    return true;
}
export { validateCredentials };
""",
        encoding="utf-8",
    )

    # 3. controllers/authController.js
    (controllers_dir / "authController.js").write_text(
        """
import { AuthService, validateCredentials } from "../services/authService.js";

function handleLogin(req, res) {
    validateCredentials(req.username, req.password);
    return res;
}
export { handleLogin };
""",
        encoding="utf-8",
    )

    # 4. routes/auth.js
    (routes_dir / "auth.js").write_text(
        """
import { handleLogin } from "../controllers/authController.js";

function setupAuthRoutes(app) {
    handleLogin(null, null);
    app.post("/login", handleLogin);
}
export { setupAuthRoutes };
""",
        encoding="utf-8",
    )

    # Run analysis
    result = analyze_repository(sample_repo)

    # Verify ignored files do not appear
    file_paths = [f.path for f in result.files]
    assert "node_modules/ignored.js" not in file_paths
    assert "dist/ignored.js" not in file_paths
    assert len(file_paths) == 4
    assert "src/models/User.js" in file_paths
    assert "src/services/authService.js" in file_paths
    assert "src/controllers/authController.js" in file_paths
    assert "src/routes/auth.js" in file_paths

    # Verify symbols
    sym_names = {s.name for s in result.symbols}
    assert "User" in sym_names
    assert "AuthService" in sym_names
    assert "createUser" in sym_names
    assert "validateCredentials" in sym_names
    assert "handleLogin" in sym_names
    assert "setupAuthRoutes" in sym_names

    # Verify relationships
    rel_target_names = {r.target_name for r in result.relationships}
    assert "User" in rel_target_names
    assert "AuthService" in rel_target_names
    assert "validateCredentials" in rel_target_names
    assert "handleLogin" in rel_target_names

    # Verify resolved relationships
    resolved_statuses = {rr.status for rr in result.resolved_relationships}
    assert ResolutionStatus.RESOLVED in resolved_statuses

    # Verify architecture classifications
    classifications = {
        fc.path: [c.role for c in fc.classifications]
        for fc in result.architecture.file_classifications
    }
    assert ArchitectureRole.MODEL in classifications["src/models/User.js"]
    assert ArchitectureRole.SERVICE in classifications["src/services/authService.js"]
    assert ArchitectureRole.CONTROLLER in classifications["src/controllers/authController.js"]
    assert ArchitectureRole.ROUTE in classifications["src/routes/auth.js"]

    # Verify CodeGraph has FILE, FUNCTION/CLASS nodes, IMPORTS, and CALLS edges
    node_types = {n.node_type for n in result.graph.nodes}
    assert NodeType.FILE in node_types
    assert NodeType.CLASS in node_types
    assert NodeType.FUNCTION in node_types
    assert NodeType.METHOD in node_types

    edge_types = {e.edge_type for e in result.graph.edges}
    assert EdgeType.IMPORTS in edge_types
    assert EdgeType.CALLS in edge_types
    assert EdgeType.CONTAINS in edge_types
    assert EdgeType.CLASSIFIED_AS in edge_types
    assert EdgeType.DEPENDS_ON in edge_types

    # Verify IR structure
    assert result.ir["schema_version"] == "1.0"
    assert result.ir["repository"]["name"] == "sample-repo"
    assert len(result.ir["nodes"]) == len(result.graph.nodes)
    assert len(result.ir["edges"]) == len(result.graph.edges)

    # Validate IR strictly against canonical schema contract
    validate_graph_ir(result.ir)
