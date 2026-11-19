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
        discover_routes,
        DiscoveredRoute,
        RouteMapResult,
    )
except ImportError:
    from src.repository import (
        RepositoryAnalysisError,
        analyze_repository,
        discover_routes,
        DiscoveredRoute,
        RouteMapResult,
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

    # Cache routes analysis if present
    if result.routes:
        routes_resp = _route_map_to_response(result.repository_name, result.routes)
        _routes_by_path[str(resolved_path)] = routes_resp
        global _latest_routes
        _latest_routes = routes_resp

    return AnalyzeResponse(
        repository_name=result.repository_name,
        ir=result.ir,
    )


# ---------------------------------------------------------------------------
# API & Route Map Models and Endpoints (Section 6)
# ---------------------------------------------------------------------------

class MiddlewareResponse(BaseModel):
    name: str
    source_file: str | None = None
    line: int | None = None
    column: int | None = None
    is_inline: bool = False
    status: str = "resolved"


class ControllerResponse(BaseModel):
    name: str
    function_name: str
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    start_column: int | None = None
    parameters: list[str] = Field(default_factory=list)
    called_functions: list[str] = Field(default_factory=list)
    status: str = "resolved"


class ServiceDependencyResponse(BaseModel):
    service_name: str
    method_name: str | None = None
    file_path: str | None = None
    start_line: int | None = None
    end_line: int | None = None
    status: str = "confirmed"


class ModelDependencyResponse(BaseModel):
    model_name: str
    operation: str | None = None
    file_path: str | None = None
    status: str = "confirmed"


class FlowStepResponse(BaseModel):
    step_type: str
    label: str
    file_path: str | None = None
    line: int | None = None
    description: str | None = None


class RouteResponse(BaseModel):
    id: str
    http_method: str
    route_path: str
    http_endpoint: str
    source_file: str
    start_line: int
    end_line: int
    start_column: int
    router_base_path: str
    controller: ControllerResponse
    middleware: list[MiddlewareResponse] = Field(default_factory=list)
    service_dependencies: list[ServiceDependencyResponse] = Field(default_factory=list)
    model_dependencies: list[ModelDependencyResponse] = Field(default_factory=list)
    execution_flow: list[FlowStepResponse] = Field(default_factory=list)
    status: str = "resolved"


class RouteSummaryResponse(BaseModel):
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


class RouteAnalysisResponse(BaseModel):
    repository_name: str
    summary: RouteSummaryResponse
    routes: list[RouteResponse]


_routes_by_path: dict[str, RouteAnalysisResponse] = {}
_latest_routes: RouteAnalysisResponse | None = None


def _route_to_response(r: DiscoveredRoute) -> RouteResponse:
    return RouteResponse(
        id=r.id,
        http_method=r.http_method,
        route_path=r.route_path,
        http_endpoint=r.http_endpoint,
        source_file=r.source_file,
        start_line=r.start_line,
        end_line=r.end_line,
        start_column=r.start_column,
        router_base_path=r.router_base_path,
        controller=ControllerResponse(
            name=r.controller.name,
            function_name=r.controller.function_name,
            file_path=r.controller.file_path,
            start_line=r.controller.start_line,
            end_line=r.controller.end_line,
            start_column=r.controller.start_column,
            parameters=list(r.controller.parameters),
            called_functions=list(r.controller.called_functions),
            status=r.controller.status,
        ),
        middleware=[
            MiddlewareResponse(
                name=m.name,
                source_file=m.source_file,
                line=m.line,
                column=m.column,
                is_inline=m.is_inline,
                status=m.status,
            )
            for m in r.middleware
        ],
        service_dependencies=[
            ServiceDependencyResponse(
                service_name=s.service_name,
                method_name=s.method_name,
                file_path=s.file_path,
                start_line=s.start_line,
                end_line=s.end_line,
                status=s.status,
            )
            for s in r.service_dependencies
        ],
        model_dependencies=[
            ModelDependencyResponse(
                model_name=m.model_name,
                operation=m.operation,
                file_path=m.file_path,
                status=m.status,
            )
            for m in r.model_dependencies
        ],
        execution_flow=[
            FlowStepResponse(
                step_type=f.step_type,
                label=f.label,
                file_path=f.file_path,
                line=f.line,
                description=f.description,
            )
            for f in r.execution_flow
        ],
        status=r.status,
    )


def _route_map_to_response(repo_name: str, result: RouteMapResult) -> RouteAnalysisResponse:
    summary_resp = RouteSummaryResponse(
        total_endpoints=result.summary.total_endpoints,
        get_count=result.summary.get_count,
        post_count=result.summary.post_count,
        put_patch_count=result.summary.put_patch_count,
        delete_count=result.summary.delete_count,
        other_count=result.summary.other_count,
        unresolved_count=result.summary.unresolved_count,
        controllers_count=result.summary.controllers_count,
        services_count=result.summary.services_count,
        models_count=result.summary.models_count,
    )
    return RouteAnalysisResponse(
        repository_name=repo_name,
        summary=summary_resp,
        routes=[_route_to_response(r) for r in result.routes],
    )


def _get_target_routes(repository_path: str | None = None) -> RouteAnalysisResponse:
    global _latest_routes
    if repository_path:
        trusted_root = get_analysis_root()
        raw_path = Path(repository_path.strip())
        resolved_path = (trusted_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()
        p_key = str(resolved_path)
        if p_key in _routes_by_path:
            return _routes_by_path[p_key]
        if resolved_path.exists() and resolved_path.is_dir():
            res = analyze_repository(resolved_path)
            if res.routes:
                resp = _route_map_to_response(res.repository_name, res.routes)
                _routes_by_path[p_key] = resp
                _latest_routes = resp
                return resp

    if _latest_routes is not None:
        return _latest_routes
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="No route analysis available. Run POST /api/routes/analyze first.",
    )


@app.post(
    "/api/routes/analyze",
    response_model=RouteAnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze repository routes, controllers, middleware, and dependency flow",
)
@app.post(
    "/routes/analyze",
    response_model=RouteAnalysisResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def analyze_routes(request: AnalyzeRequest) -> RouteAnalysisResponse:
    """Analyze and return complete API route map with controller & dependency tracing."""
    repo_path_str = request.repository_path.strip() if request.repository_path else ""
    if not repo_path_str:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="repository_path is required",
        )

    trusted_root = get_analysis_root()
    raw_path = Path(repo_path_str)
    resolved_path = (trusted_root / raw_path).resolve() if not raw_path.is_absolute() else raw_path.resolve()

    if not is_contained_in_root(resolved_path, trusted_root):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Repository path is outside the trusted analysis root",
        )
    if not resolved_path.exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Repository path does not exist")
    if not resolved_path.is_dir():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Repository path is not a directory")

    try:
        result = analyze_repository(repository_path=resolved_path, repo_name=request.repo_name)
    except RepositoryAnalysisError as err:
        logger.warning("Repository analysis error: %s", err)
        clean_detail = sanitize_error_detail(str(err))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=clean_detail) from err
    except Exception as err:
        logger.error("Unexpected error during route analysis: %s", err, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Route analysis failed due to an unexpected internal error",
        ) from err

    if result.routes:
        resp = _route_map_to_response(result.repository_name, result.routes)
    else:
        # Fallback to direct discovery
        discovered = discover_routes(
            result.files,
            result.symbols,
            result.relationships,
            result.resolved_relationships,
            result.architecture,
            repo_path=resolved_path,
        )
        resp = _route_map_to_response(result.repository_name, discovered)

    _routes_by_path[str(resolved_path)] = resp
    global _latest_routes
    _latest_routes = resp
    return resp


@app.get(
    "/api/routes/summary",
    response_model=RouteSummaryResponse,
    status_code=status.HTTP_200_OK,
    summary="Get summary metrics of discovered routes",
)
@app.get(
    "/routes/summary",
    response_model=RouteSummaryResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_routes_summary(repository_path: str | None = None) -> RouteSummaryResponse:
    analysis = _get_target_routes(repository_path)
    return analysis.summary


@app.get(
    "/api/routes",
    response_model=list[RouteResponse],
    status_code=status.HTTP_200_OK,
    summary="List all discovered API endpoints",
)
@app.get(
    "/routes",
    response_model=list[RouteResponse],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def list_routes(
    repository_path: str | None = None,
    method: str | None = None,
    status_filter: str | None = None,
) -> list[RouteResponse]:
    analysis = _get_target_routes(repository_path)
    routes = analysis.routes
    if method:
        routes = [r for r in routes if r.http_method.upper() == method.upper()]
    if status_filter:
        routes = [r for r in routes if r.status.lower() == status_filter.lower()]
    return routes


@app.get(
    "/api/routes/{route_id:path}",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    summary="Get details for a specific route by ID",
)
@app.get(
    "/routes/{route_id:path}",
    response_model=RouteResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_route_by_id(route_id: str, repository_path: str | None = None) -> RouteResponse:
    analysis = _get_target_routes(repository_path)
    clean_id = route_id.strip()
    for r in analysis.routes:
        if r.id == clean_id or r.http_endpoint == clean_id or r.id.endswith(clean_id):
            return r
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Route '{route_id}' not found")



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


if __name__ == "__main__":
    import uvicorn
    host = os.environ.get("AI_HOST", "127.0.0.1")
    port = int(os.environ.get("AI_PORT", "8000"))
    uvicorn.run("src.main:app", host=host, port=port, log_level="info")

