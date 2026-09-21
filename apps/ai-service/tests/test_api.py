"""
tests/test_api.py

API endpoint test suite for AI Service FastAPI application.
Validates POST /analyze, request validation, error handling, and Graph IR contract.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from starlette.testclient import TestClient

# Ensure src/ is on python path
_SRC = Path(__file__).parent.parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from main import app
from repository.graph_ir import validate_graph_ir

client = TestClient(app)


@pytest.fixture(autouse=True)
def configure_default_analysis_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Set CODEAI_ANALYSIS_ROOT to tmp_path by default for test isolation."""
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(tmp_path))


# ===========================================================================
# Health Check
# ===========================================================================


def test_health_check() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


# ===========================================================================
# 13. POST /analyze success
# ===========================================================================


def test_13_post_analyze_success(tmp_path: Path) -> None:
    repo = tmp_path / "sample_api_repo"
    repo.mkdir()
    (repo / "index.js").write_text("export function greet() { return 'hi'; }", encoding="utf-8")

    response = client.post(
        "/analyze",
        json={"repository_path": str(repo)},
    )
    assert response.status_code == 200
    data = response.json()
    assert "repository_name" in data
    assert data["repository_name"] == "sample_api_repo"
    assert "ir" in data
    assert data["ir"]["schema_version"] == "1.0"
    assert len(data["ir"]["nodes"]) >= 1


# ===========================================================================
# 14. Missing repository path
# ===========================================================================


def test_14_missing_repository_path() -> None:
    # Omitted field
    response = client.post("/analyze", json={})
    assert response.status_code == 422

    # Empty string
    response_empty = client.post("/analyze", json={"repository_path": "   "})
    assert response_empty.status_code == 400
    assert "repository_path is required" in response_empty.json()["detail"]


# ===========================================================================
# 15. Invalid / Non-existent repository path
# ===========================================================================


def test_15_invalid_repository_path(tmp_path: Path) -> None:
    bad_path = tmp_path / "does_not_exist_xyz"
    response = client.post(
        "/analyze",
        json={"repository_path": str(bad_path)},
    )
    assert response.status_code == 404
    assert "does not exist" in response.json()["detail"]


# ===========================================================================
# 16. Repository path pointing to a file
# ===========================================================================


def test_16_repository_path_pointing_to_a_file(tmp_path: Path) -> None:
    file_path = tmp_path / "file.js"
    file_path.write_text("export const x = 1;", encoding="utf-8")

    response = client.post(
        "/analyze",
        json={"repository_path": str(file_path)},
    )
    assert response.status_code == 400
    assert "not a directory" in response.json()["detail"]


# ===========================================================================
# 17. Explicit repo name
# ===========================================================================


def test_17_explicit_repo_name(tmp_path: Path) -> None:
    repo = tmp_path / "actual_dir_name"
    repo.mkdir()
    (repo / "app.js").write_text("export const PORT = 3000;", encoding="utf-8")

    response = client.post(
        "/analyze",
        json={
            "repository_path": str(repo),
            "repo_name": "custom-explicit-name",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repository_name"] == "custom-explicit-name"
    assert data["ir"]["repository"]["name"] == "custom-explicit-name"


# ===========================================================================
# 18. Graph IR validation
# ===========================================================================


def test_18_graph_ir_validation(tmp_path: Path) -> None:
    repo = tmp_path / "valid_ir_repo"
    repo.mkdir()
    (repo / "calc.js").write_text(
        """
export function add(a, b) {
    return a + b;
}
""",
        encoding="utf-8",
    )

    response = client.post(
        "/analyze",
        json={"repository_path": str(repo)},
    )
    assert response.status_code == 200
    ir = response.json()["ir"]

    # Strictly validates against M8 schema contract
    validate_graph_ir(ir)
    assert ir["schema_version"] == "1.0"
    assert "repository" in ir
    assert "nodes" in ir
    assert "edges" in ir


# ===========================================================================
# 19. Error response behavior
# ===========================================================================


def test_19_error_response_behavior() -> None:
    # Malformed JSON body
    response = client.post(
        "/analyze",
        content="not-json",
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert "detail" in response.json()


# ===========================================================================
# 20. Repository inside CODEAI_ANALYSIS_ROOT succeeds
# ===========================================================================


def test_20_repository_inside_root_succeeds(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "trusted_root"
    root.mkdir()
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(root))

    repo = root / "valid_project"
    repo.mkdir()
    (repo / "index.js").write_text("export const answer = 42;", encoding="utf-8")

    response = client.post(
        "/analyze",
        json={"repository_path": str(repo)},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["repository_name"] == "valid_project"
    assert data["ir"]["schema_version"] == "1.0"


# ===========================================================================
# 21. Repository outside root rejected
# ===========================================================================


def test_21_repository_outside_root_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "trusted_root"
    root.mkdir()
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(root))

    outside_repo = tmp_path / "outside_project"
    outside_repo.mkdir()
    (outside_repo / "index.js").write_text("export const secret = 'key';", encoding="utf-8")

    response = client.post(
        "/analyze",
        json={"repository_path": str(outside_repo)},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "outside the trusted analysis root" in detail
    assert str(outside_repo) not in detail


# ===========================================================================
# 22. ../ traversal rejected
# ===========================================================================


def test_22_traversal_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "trusted_root"
    root.mkdir()
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(root))

    # Relative ../ traversal
    response_rel = client.post(
        "/analyze",
        json={"repository_path": "../traversal_escape"},
    )
    assert response_rel.status_code == 400
    assert "outside the trusted analysis root" in response_rel.json()["detail"]
    assert "../traversal_escape" not in response_rel.json()["detail"]

    # Absolute traversal path
    traversal_path = str(root / ".." / "other_dir")
    response_abs = client.post(
        "/analyze",
        json={"repository_path": traversal_path},
    )
    assert response_abs.status_code == 400
    assert "outside the trusted analysis root" in response_abs.json()["detail"]
    assert traversal_path not in response_abs.json()["detail"]


# ===========================================================================
# 23. Symlink root escape rejected where supported
# ===========================================================================


def test_23_symlink_root_escape_rejected_where_supported(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "trusted_root"
    root.mkdir()
    outside_target = tmp_path / "outside_target"
    outside_target.mkdir()
    (outside_target / "secret.js").write_text("export const pass = '123';", encoding="utf-8")

    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(root))

    symlink_dir = root / "escape_link"
    try:
        symlink_dir.symlink_to(outside_target, target_is_directory=True)
    except OSError:
        pytest.skip("Symlink creation not supported in current environment/permissions")

    response = client.post(
        "/analyze",
        json={"repository_path": str(symlink_dir)},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "outside the trusted analysis root" in detail
    assert str(outside_target) not in detail


# ===========================================================================
# 24. Invalid path errors contain no filesystem path
# ===========================================================================


def test_24_invalid_path_errors_contain_no_filesystem_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "trusted_root"
    root.mkdir()
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(root))

    # 1. Nonexistent directory inside root
    non_existent = root / "does_not_exist_abc"
    resp_404 = client.post(
        "/analyze",
        json={"repository_path": str(non_existent)},
    )
    assert resp_404.status_code == 404
    detail_404 = resp_404.json()["detail"]
    assert detail_404 == "Repository path does not exist"
    assert str(non_existent) not in detail_404

    # 2. File instead of directory inside root
    file_path = root / "just_a_file.js"
    file_path.write_text("console.log(1);", encoding="utf-8")
    resp_file = client.post(
        "/analyze",
        json={"repository_path": str(file_path)},
    )
    assert resp_file.status_code == 400
    detail_file = resp_file.json()["detail"]
    assert detail_file == "Repository path is not a directory"
    assert str(file_path) not in detail_file


# ===========================================================================
# 25. Missing CODEAI_ANALYSIS_ROOT raises 500
# ===========================================================================


def test_25_missing_codeai_analysis_root_raises_500(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("CODEAI_ANALYSIS_ROOT", raising=False)
    response = client.post(
        "/analyze",
        json={"repository_path": "some_dir"},
    )
    assert response.status_code == 500
    assert "CODEAI_ANALYSIS_ROOT is not configured" in response.json()["detail"]
