"""
main.py — AI Service entry point.

Exposes the Repository Intelligence static analysis pipeline via FastAPI.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
import re
from typing import Any

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

import sys

src_dir = Path(__file__).resolve().parent
if str(src_dir) not in sys.path:
    sys.path.insert(0, str(src_dir))

try:
    from repository import (
        RepositoryAnalysisError,
        analyze_repository,
    )
except ImportError:
    from src.repository import (
        RepositoryAnalysisError,
        analyze_repository,
    )

logger = logging.getLogger(__name__)

app = FastAPI(title="AI Service", version="0.1.0")


def get_analysis_root() -> Path:
    """
    Retrieve and validate the configured trusted analysis root directory.

    Controlled via the CODEAI_ANALYSIS_ROOT environment variable.
    """
    root_str = os.environ.get("CODEAI_ANALYSIS_ROOT", "").strip()
    if not root_str and not os.environ.get("PYTEST_CURRENT_TEST"):
        import tempfile
        default_root = Path(tempfile.gettempdir()) / "codeai-repos"
        if default_root.exists():
            return default_root.resolve()
    if not root_str:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CODEAI_ANALYSIS_ROOT is not configured",
        )
    root_path = Path(root_str).resolve()
    if not root_path.exists():
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Configured CODEAI_ANALYSIS_ROOT does not exist",
        )
    return root_path


def is_contained_in_root(candidate: Path, root: Path) -> bool:
    """
    Robust containment check for filesystem paths on both Windows and POSIX.

    Returns True if candidate is equal to root or a descendant of root.
    """
    try:
        return candidate.is_relative_to(root)
    except (ValueError, AttributeError):
        try:
            cand_str = str(candidate).lower()
            root_str = str(root).lower()
            return os.path.commonpath([cand_str, root_str]) == root_str
        except (ValueError, OSError):
            return False


def sanitize_error_detail(msg: str) -> str:
    """
    Redact internal filesystem paths from error messages.
    """
    # Replace Windows drive paths: e.g. D:\path\to\repo or C:\Users\...
    sanitized = re.sub(r"[a-zA-Z]:\\[^\s\"'<>]+", "<path>", msg)
    # Replace Unix-style absolute paths: e.g. /path/to/repo
    sanitized = re.sub(r"/(?:[^\s\"'<>]+/)+[^\s\"'<>]*", "<path>", sanitized)
    return sanitized


class AnalyzeRequest(BaseModel):
    repository_path: str = Field(..., description="Path to local repository directory")
    repo_name: str | None = Field(default=None, description="Optional explicit repository name")


class AnalyzeResponse(BaseModel):
    repository_name: str
    ir: dict[str, Any]


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.post(
    "/analyze",
    response_model=AnalyzeResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a local repository and return Graph IR",
)
def analyze(request: AnalyzeRequest) -> AnalyzeResponse:
    """
    Run full static analysis on the supplied local repository path.

    Returns the canonical CodeGraph IR conforming to schema version 1.0.
    """
    repo_path_str = request.repository_path.strip() if request.repository_path else ""
    if not repo_path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_path is required",
        )

    trusted_root = get_analysis_root()

    raw_path = Path(repo_path_str)
    # Resolve relative paths against the trusted root
    if not raw_path.is_absolute():
        resolved_path = (trusted_root / raw_path).resolve()
    else:
        resolved_path = raw_path.resolve()

    # Enforce boundary containment: reject traversal, outside paths, different drives, symlink escapes
    if not is_contained_in_root(resolved_path, trusted_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path is outside the trusted analysis root",
        )

    if not resolved_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Repository path does not exist",
        )

    if not resolved_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path is not a directory",
        )

    try:
        result = analyze_repository(
            repository_path=resolved_path,
            repo_name=request.repo_name,
        )
    except RepositoryAnalysisError as err:
        logger.warning("Repository analysis error: %s", err)
        clean_detail = sanitize_error_detail(str(err))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=clean_detail,
        ) from err
    except Exception as err:
        logger.error("Unexpected error during repository analysis: %s", err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Repository analysis failed due to an unexpected internal error",
        ) from err

    return AnalyzeResponse(
        repository_name=result.repository_name,
        ir=result.ir,
    )


# ---------------------------------------------------------------------------
# Optional neural dense ranking (used by the backend's chat and quiz retriever)
# ---------------------------------------------------------------------------

try:
    from retrieval import dense as dense_retrieval
except ImportError:
    from src.retrieval import dense as dense_retrieval

import threading
from collections import OrderedDict

DENSE_MAX_FILE_BYTES = 500_000
DENSE_MAX_REPOS = 4
_dense_lock = threading.Lock()
_dense_indexes: "OrderedDict[str, Any]" = OrderedDict()  # resolved path -> DenseIndex
_dense_building: set[str] = set()


class DenseIndexRequest(BaseModel):
    repository_path: str = Field(..., description="Path to a local repository snapshot")
    paths: list[str] = Field(..., description="Repository-relative file paths to embed")


class DenseRankRequest(BaseModel):
    repository_path: str
    query: str
    top_k: int = Field(default=20, ge=1, le=200)


def _resolve_repository(repo_path_str: str) -> Path:
    if not repo_path_str or not repo_path_str.strip():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="repository_path is required")
    root = get_analysis_root()
    raw = Path(repo_path_str.strip())
    resolved = (root / raw).resolve() if not raw.is_absolute() else raw.resolve()
    if not is_contained_in_root(resolved, root):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository path is outside the trusted analysis root")
    if not resolved.is_dir():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository path does not exist")
    return resolved


def _read_docs(root: Path, paths: list[str]) -> dict[str, str]:
    docs: dict[str, str] = {}
    for rel in paths:
        full = (root / rel).resolve()
        if not is_contained_in_root(full, root):
            continue
        try:
            docs[rel] = full.read_text(encoding="utf-8", errors="ignore") if full.is_file() and full.stat().st_size <= DENSE_MAX_FILE_BYTES else ""
        except OSError:
            docs[rel] = ""
    return docs


def _build_dense_index(key: str, root: Path, paths: list[str]) -> None:
    try:
        index = dense_retrieval.DenseIndex(_read_docs(root, paths))
        with _dense_lock:
            _dense_indexes[key] = index
            _dense_indexes.move_to_end(key)
            while len(_dense_indexes) > DENSE_MAX_REPOS:
                _dense_indexes.popitem(last=False)
    except Exception as err:  # never crash the service over an optional feature
        logger.warning("Dense index build failed: %s", sanitize_error_detail(str(err)))
    finally:
        with _dense_lock:
            _dense_building.discard(key)


@app.get("/dense/status")
def dense_status() -> dict[str, Any]:
    """Whether neural ranking is installed in this deployment."""
    return {"available": dense_retrieval.available(), "model": dense_retrieval.MODEL_NAME}


@app.post("/dense/index", status_code=status.HTTP_202_ACCEPTED)
def dense_index(request: DenseIndexRequest) -> dict[str, str]:
    """Start embedding a repository snapshot in the background (idempotent)."""
    if not dense_retrieval.available():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Neural ranking is not installed")
    root = _resolve_repository(request.repository_path)
    key = str(root)
    with _dense_lock:
        if key in _dense_indexes:
            return {"status": "ready"}
        if key in _dense_building:
            return {"status": "building"}
        _dense_building.add(key)
    threading.Thread(target=_build_dense_index, args=(key, root, list(request.paths)), daemon=True).start()
    return {"status": "building"}


@app.post("/dense/rank")
def dense_rank(request: DenseRankRequest) -> dict[str, Any]:
    """Rank the files of an indexed snapshot for a question; 409 if the snapshot is not indexed yet."""
    if not dense_retrieval.available():
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Neural ranking is not installed")
    key = str(_resolve_repository(request.repository_path))
    with _dense_lock:
        index = _dense_indexes.get(key)
        building = key in _dense_building
    if index is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="building" if building else "not_indexed")
    return {"paths": index.rank(request.query)[: request.top_k]}
