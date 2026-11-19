"""
tests/test_routes.py

Comprehensive test suite for API & Route Map Intelligence:
1. GET route discovery
2. POST route discovery
3. PUT and DELETE route discovery
4. Router mounting and base paths
5. Controller resolution (named imports and object exports)
6. Middleware extraction
7. Service dependency tracing
8. Model dependency tracing
9. Unresolved handlers
10. Duplicate route prevention
11. CodeGraph node & edge integration (API_ENDPOINT, ROUTES_TO, etc.)
12. FastAPI routes endpoints
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
from repository.graph import EdgeType, NodeType, build_code_graph
from repository.pipeline import analyze_repository
from repository.routes import discover_routes, normalize_endpoint_path

client = TestClient(app)


@pytest.fixture(autouse=True)
def configure_analysis_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODEAI_ANALYSIS_ROOT", str(tmp_path))


# ===========================================================================
# 1. Path Normalization Tests
# ===========================================================================


def test_normalize_endpoint_path() -> None:
    assert normalize_endpoint_path("/api/v1/users", "/:id") == "/api/v1/users/:id"
    assert normalize_endpoint_path("/api/v1", "/") == "/api/v1"
    assert normalize_endpoint_path("", "/health") == "/health"
    assert normalize_endpoint_path("", "/") == "/"
    assert normalize_endpoint_path("/api/", "/items/") == "/api/items"
    assert normalize_endpoint_path("users", "list") == "/users/list"


# ===========================================================================
# 2. Route Discovery: GET, POST, PUT, DELETE, Router Mounts, Middleware, Tracing
# ===========================================================================


@pytest.fixture
def express_sample_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "sample_express_repo"
    repo.mkdir()

    # Controllers
    ctrl_dir = repo / "controllers"
    ctrl_dir.mkdir()
    (ctrl_dir / "user.controller.js").write_text(
        """
import { userService } from '../services/user.service.js';

export const userController = {
  async getUsers(req, res, next) {
    const users = await userService.listUsers();
    res.json(users);
  },
  async createUser(req, res, next) {
    const user = await userService.registerUser(req.body);
    res.status(201).json(user);
  },
  async updateUser(req, res, next) {
    const user = await userService.updateUser(req.params.id, req.body);
    res.json(user);
  },
  async deleteUser(req, res, next) {
    await userService.removeUser(req.params.id);
    res.status(204).send();
  }
};
""",
        encoding="utf-8",
    )

    # Services
    svc_dir = repo / "services"
    svc_dir.mkdir()
    (svc_dir / "user.service.js").write_text(
        """
import { UserModel } from '../models/user.model.js';

export const userService = {
  async listUsers() {
    return await UserModel.find();
  },
  async registerUser(data) {
    return await UserModel.create(data);
  },
  async updateUser(id, data) {
    return await UserModel.findByIdAndUpdate(id, data);
  },
  async removeUser(id) {
    return await UserModel.findByIdAndDelete(id);
  }
};
""",
        encoding="utf-8",
    )

    # Models
    model_dir = repo / "models"
    model_dir.mkdir()
    (model_dir / "user.model.js").write_text(
        """
export const UserModel = {
  find() {},
  create() {},
  findByIdAndUpdate() {},
  findByIdAndDelete() {}
};
""",
        encoding="utf-8",
    )

    # Middleware
    mw_dir = repo / "middleware"
    mw_dir.mkdir()
    (mw_dir / "auth.js").write_text(
        """
export function requireAuth(req, res, next) {
  next();
}
export function validate(schema) {
  return (req, res, next) => next();
}
""",
        encoding="utf-8",
    )

    # Routes
    routes_dir = repo / "routes"
    routes_dir.mkdir()
    (routes_dir / "user.routes.js").write_text(
        """
import express from 'express';
import { userController } from '../controllers/user.controller.js';
import { requireAuth, validate } from '../middleware/auth.js';

const router = express.Router();

router.use(requireAuth);

router.get('/', userController.getUsers);
router.post('/', validate('userSchema'), userController.createUser);
router.put('/:id', userController.updateUser);
router.delete('/:id', userController.deleteUser);

// Chained route
router.route('/active').get(userController.getUsers).post(userController.createUser);

// Unresolved handler
router.get('/external', externalHandler);

// Duplicate route to test prevention
router.get('/', userController.getUsers);

export default router;
""",
        encoding="utf-8",
    )

    # App entrypoint
    (repo / "app.js").write_text(
        """
import express from 'express';
import userRoutes from './routes/user.routes.js';

const app = express();

app.get('/health', (req, res) => {
  res.json({ status: 'ok' });
});

app.use('/api/v1/users', userRoutes);

export default app;
""",
        encoding="utf-8",
    )

    return repo


def test_endpoint_discovery_and_methods(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None
    endpoints = {f"{r.http_method} {r.http_endpoint}" for r in res.routes.routes}

    # 1. GET route discovery
    assert "GET /api/v1/users" in endpoints
    assert "GET /health" in endpoints

    # 2. POST route discovery
    assert "POST /api/v1/users" in endpoints

    # 3. PUT and DELETE route discovery
    assert "PUT /api/v1/users/:id" in endpoints
    assert "DELETE /api/v1/users/:id" in endpoints

    # Chained route endpoints
    assert "GET /api/v1/users/active" in endpoints
    assert "POST /api/v1/users/active" in endpoints


def test_router_mounting_and_base_paths(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    user_route = next(r for r in res.routes.routes if r.http_endpoint == "/api/v1/users" and r.http_method == "GET")
    assert user_route.router_base_path == "/api/v1/users"
    assert user_route.route_path == "/"
    assert user_route.http_endpoint == "/api/v1/users"

    health_route = next(r for r in res.routes.routes if r.http_endpoint == "/health")
    assert health_route.router_base_path == ""
    assert health_route.route_path == "/health"
    assert health_route.status == "inline"


def test_controller_resolution(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    user_get = next(r for r in res.routes.routes if r.http_endpoint == "/api/v1/users" and r.http_method == "GET")
    ctrl = user_get.controller
    assert ctrl.status == "resolved"
    assert ctrl.name == "userController.getUsers"
    assert ctrl.function_name == "getUsers"
    assert ctrl.file_path == "controllers/user.controller.js"
    assert ctrl.parameters == ("req", "res", "next")
    assert "userService.listUsers" in ctrl.called_functions


def test_middleware_extraction(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    user_post = next(r for r in res.routes.routes if r.http_endpoint == "/api/v1/users" and r.http_method == "POST")
    mw_names = [m.name for m in user_post.middleware]
    # Router-level middleware requireAuth + route-level validate
    assert "requireAuth" in mw_names
    assert any("validate" in m for m in mw_names)


def test_service_and_model_dependency_tracing(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    user_post = next(r for r in res.routes.routes if r.http_endpoint == "/api/v1/users" and r.http_method == "POST")
    # Service dependency
    assert len(user_post.service_dependencies) > 0
    svc = user_post.service_dependencies[0]
    assert svc.service_name == "userService"
    assert svc.method_name == "registerUser"
    assert svc.status == "confirmed"

    # Model dependency traced through the service
    assert len(user_post.model_dependencies) > 0
    model_names = [m.model_name for m in user_post.model_dependencies]
    assert "UserModel" in model_names

    # Execution flow verification: Route -> Middleware -> Controller -> Service -> Model -> Database
    step_types = [s.step_type for s in user_post.execution_flow]
    assert "route" in step_types
    assert "middleware" in step_types
    assert "controller" in step_types
    assert "service" in step_types
    assert "model" in step_types
    assert "database" in step_types


def test_unresolved_handler(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    unres = next(r for r in res.routes.routes if r.http_endpoint == "/api/v1/users/external")
    assert unres.controller.status == "unresolved"
    assert unres.status == "unresolved"


def test_duplicate_route_prevention(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    assert res.routes is not None

    route_ids = [r.id for r in res.routes.routes]
    assert len(route_ids) == len(set(route_ids)), "Routes must have unique IDs"


def test_codegraph_node_and_edge_extensions(express_sample_repo: Path) -> None:
    res = analyze_repository(express_sample_repo, repo_name="sample")
    graph = res.graph

    # Verify new node types exist in CodeGraph
    node_types = {n.node_type for n in graph.nodes}
    assert NodeType.API_ENDPOINT in node_types or "api_endpoint" in node_types
    assert NodeType.CONTROLLER in node_types or "controller" in node_types
    assert NodeType.SERVICE in node_types or "service" in node_types
    assert NodeType.MIDDLEWARE in node_types or "middleware" in node_types
    assert NodeType.DATABASE_MODEL in node_types or "database_model" in node_types

    # Verify new edge types exist in CodeGraph
    edge_types = {e.edge_type for e in graph.edges}
    assert EdgeType.ROUTES_TO in edge_types or "routes_to" in edge_types
    assert EdgeType.HANDLED_BY in edge_types or "handled_by" in edge_types
    assert EdgeType.USES_MIDDLEWARE in edge_types or "uses_middleware" in edge_types
    assert EdgeType.CALLS_SERVICE in edge_types or "calls_service" in edge_types
    assert EdgeType.ACCESSES_MODEL in edge_types or "accesses_model" in edge_types

    # Verify IR serializes cleanly without schema validation error
    ir = res.ir
    assert ir["schema_version"] == "1.0"
    assert len(ir["nodes"]) > 0
    assert len(ir["edges"]) > 0


# ===========================================================================
# 3. FastAPI Endpoint Tests
# ===========================================================================


def test_fastapi_routes_endpoints(express_sample_repo: Path) -> None:
    # 1. POST /api/routes/analyze
    res = client.post(
        "/api/routes/analyze",
        json={"repository_path": str(express_sample_repo), "repo_name": "sample"},
    )
    assert res.status_code == 200
    data = res.json()
    assert "summary" in data
    assert "routes" in data
    assert data["summary"]["total_endpoints"] >= 6
    assert data["summary"]["get_count"] >= 3
    assert data["summary"]["post_count"] >= 2

    # 2. GET /api/routes/summary
    sum_res = client.get("/api/routes/summary")
    assert sum_res.status_code == 200
    assert sum_res.json()["total_endpoints"] == data["summary"]["total_endpoints"]

    # 3. GET /api/routes
    list_res = client.get("/api/routes")
    assert list_res.status_code == 200
    routes_arr = list_res.json()
    assert len(routes_arr) == len(data["routes"])

    # 4. GET /api/routes?method=POST
    post_res = client.get("/api/routes?method=POST")
    assert post_res.status_code == 200
    for r in post_res.json():
        assert r["http_method"] == "POST"

    # 5. GET /api/routes/{route_id}
    first_route = routes_arr[0]
    detail_res = client.get(f"/api/routes/{first_route['id']}")
    assert detail_res.status_code == 200
    assert detail_res.json()["http_endpoint"] == first_route["http_endpoint"]
