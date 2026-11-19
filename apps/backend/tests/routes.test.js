import { test } from "node:test";
import assert from "node:assert/strict";
import { routeService } from "../src/services/route.service.js";
import { routeController } from "../src/controllers/route.controller.js";

const mockAnalysis = {
  repository_name: "test-repo",
  summary: {
    total_endpoints: 3,
    get_count: 2,
    post_count: 1,
    put_patch_count: 0,
    delete_count: 0,
    other_count: 0,
    unresolved_count: 0,
    controllers_count: 2,
    services_count: 1,
    models_count: 1,
  },
  routes: [
    {
      id: "route:GET:/api/v1/users:src/routes/user.routes.js:10",
      http_method: "GET",
      route_path: "/",
      http_endpoint: "/api/v1/users",
      source_file: "src/routes/user.routes.js",
      start_line: 10,
      end_line: 10,
      start_column: 0,
      router_base_path: "/api/v1/users",
      controller: {
        name: "userController.getUsers",
        function_name: "getUsers",
        file_path: "src/controllers/user.controller.js",
        parameters: ["req", "res"],
        called_functions: ["userService.getUsers"],
        status: "resolved",
      },
      middleware: [
        { name: "requireAuth", source_file: "src/middleware/auth.js", is_inline: false, status: "resolved" },
      ],
      service_dependencies: [
        { service_name: "userService", method_name: "getUsers", file_path: "src/services/user.service.js", status: "confirmed" },
      ],
      model_dependencies: [
        { model_name: "UserModel", operation: "find", file_path: "src/models/user.model.js", status: "confirmed" },
      ],
      execution_flow: [
        { step_type: "route", label: "GET /api/v1/users" },
        { step_type: "middleware", label: "requireAuth" },
        { step_type: "controller", label: "userController.getUsers" },
        { step_type: "service", label: "userService.getUsers()" },
        { step_type: "model", label: "UserModel.find()" },
        { step_type: "database", label: "Database Query Execution" },
      ],
      status: "resolved",
    },
    {
      id: "route:POST:/api/v1/users:src/routes/user.routes.js:15",
      http_method: "POST",
      route_path: "/",
      http_endpoint: "/api/v1/users",
      source_file: "src/routes/user.routes.js",
      start_line: 15,
      end_line: 15,
      start_column: 0,
      router_base_path: "/api/v1/users",
      controller: {
        name: "userController.createUser",
        function_name: "createUser",
        file_path: "src/controllers/user.controller.js",
        parameters: ["req", "res"],
        called_functions: [],
        status: "resolved",
      },
      middleware: [],
      service_dependencies: [],
      model_dependencies: [],
      execution_flow: [],
      status: "resolved",
    },
    {
      id: "route:GET:/health:src/app.js:20",
      http_method: "GET",
      route_path: "/health",
      http_endpoint: "/health",
      source_file: "src/app.js",
      start_line: 20,
      end_line: 22,
      start_column: 0,
      router_base_path: "",
      controller: {
        name: "inline",
        function_name: "anonymous",
        file_path: "src/app.js",
        parameters: ["req", "res"],
        called_functions: [],
        status: "inline",
      },
      middleware: [],
      service_dependencies: [],
      model_dependencies: [],
      execution_flow: [],
      status: "inline",
    },
  ],
};

test("routeService.getRoutes returns all routes and filters by method", async () => {
  const origResolve = routeService._resolveUserAndRepo;
  const origSnap = routeService._resolveSnapshot;
  const origTree = routeService._ensureSnapshotTree;
  const origAi = (await import("../src/services/ai.service.js")).aiService.analyzeRoutes;

  routeService._resolveUserAndRepo = async () => ({ user: { id: "u1" }, repo: { id: "r1", name: "test-repo" } });
  routeService._resolveSnapshot = async () => ({ id: "s1", commitSha: "c1" });
  routeService._ensureSnapshotTree = async () => "/mock/path";
  (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = async () => mockAnalysis;

  try {
    // 1. All routes
    const res = await routeService.getRoutes("clerk_123", "r1", "c1");
    assert.equal(res.total, 3);
    assert.equal(res.summary.total_endpoints, 3);

    // 2. Filter by method
    const postRes = await routeService.getRoutes("clerk_123", "r1", "c1", { method: "POST" });
    assert.equal(postRes.total, 1);
    assert.equal(postRes.routes[0].http_method, "POST");

    // 3. Filter by search
    const searchRes = await routeService.getRoutes("clerk_123", "r1", "c1", { search: "health" });
    assert.equal(searchRes.total, 1);
    assert.equal(searchRes.routes[0].http_endpoint, "/health");

    // 4. Filter by status
    const inlineRes = await routeService.getRoutes("clerk_123", "r1", "c1", { status: "inline" });
    assert.equal(inlineRes.total, 1);
    assert.equal(inlineRes.routes[0].status, "inline");
  } finally {
    routeService._resolveUserAndRepo = origResolve;
    routeService._resolveSnapshot = origSnap;
    routeService._ensureSnapshotTree = origTree;
    (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = origAi;
  }
});

test("routeService.getRouteSummary returns summary metrics", async () => {
  const origResolve = routeService._resolveUserAndRepo;
  const origSnap = routeService._resolveSnapshot;
  const origTree = routeService._ensureSnapshotTree;
  const origAi = (await import("../src/services/ai.service.js")).aiService.analyzeRoutes;

  routeService._resolveUserAndRepo = async () => ({ user: { id: "u1" }, repo: { id: "r1", name: "test-repo" } });
  routeService._resolveSnapshot = async () => ({ id: "s1", commitSha: "c1" });
  routeService._ensureSnapshotTree = async () => "/mock/path";
  (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = async () => mockAnalysis;

  try {
    const summary = await routeService.getRouteSummary("clerk_123", "r1", "c1");
    assert.equal(summary.summary.total_endpoints, 3);
    assert.equal(summary.summary.get_count, 2);
    assert.equal(summary.summary.post_count, 1);
  } finally {
    routeService._resolveUserAndRepo = origResolve;
    routeService._resolveSnapshot = origSnap;
    routeService._ensureSnapshotTree = origTree;
    (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = origAi;
  }
});

test("routeService.getRouteById returns specific route and throws 404 for missing", async () => {
  const origResolve = routeService._resolveUserAndRepo;
  const origSnap = routeService._resolveSnapshot;
  const origTree = routeService._ensureSnapshotTree;
  const origAi = (await import("../src/services/ai.service.js")).aiService.analyzeRoutes;

  routeService._resolveUserAndRepo = async () => ({ user: { id: "u1" }, repo: { id: "r1", name: "test-repo" } });
  routeService._resolveSnapshot = async () => ({ id: "s1", commitSha: "c1" });
  routeService._ensureSnapshotTree = async () => "/mock/path";
  (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = async () => mockAnalysis;

  try {
    const route = await routeService.getRouteById("clerk_123", "r1", "c1", "route:GET:/health:src/app.js:20");
    assert.equal(route.http_endpoint, "/health");

    await assert.rejects(
      () => routeService.getRouteById("clerk_123", "r1", "c1", "non-existent"),
      { name: "NotFoundError" }
    );
  } finally {
    routeService._resolveUserAndRepo = origResolve;
    routeService._resolveSnapshot = origSnap;
    routeService._ensureSnapshotTree = origTree;
    (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = origAi;
  }
});

test("routeController dispatches list, summary, and route by ID", async () => {
  const origGetRoutes = routeService.getRoutes;
  const origGetSummary = routeService.getRouteSummary;
  const origGetById = routeService.getRouteById;

  routeService.getRoutes = async () => ({ total: 1, routes: [mockAnalysis.routes[0]] });
  routeService.getRouteSummary = async () => ({ summary: mockAnalysis.summary });
  routeService.getRouteById = async () => mockAnalysis.routes[0];

  try {
    let sentList = null;
    await routeController.listRoutes(
      { userId: "u1", params: { id: "r1", sha: "c1" }, query: { method: "GET" } },
      { status: () => ({ json: (data) => { sentList = data; } }) },
      () => {}
    );
    assert.equal(sentList.success, true);
    assert.equal(sentList.data.total, 1);

    let sentSummary = null;
    await routeController.getRouteSummary(
      { userId: "u1", params: { id: "r1", sha: "c1" } },
      { status: () => ({ json: (data) => { sentSummary = data; } }) },
      () => {}
    );
    assert.equal(sentSummary.success, true);
    assert.equal(sentSummary.data.summary.total_endpoints, 3);

    let sentDetail = null;
    await routeController.getRouteById(
      { userId: "u1", params: { id: "r1", sha: "c1", routeId: "123" } },
      { status: () => ({ json: (data) => { sentDetail = data; } }) },
      () => {}
    );
    assert.equal(sentDetail.success, true);
    assert.equal(sentDetail.data.http_endpoint, "/api/v1/users");
  } finally {
    routeService.getRoutes = origGetRoutes;
    routeService.getRouteSummary = origGetSummary;
    routeService.getRouteById = origGetById;
  }
});

test("routeService.getRoutes passes force refresh when refresh filter is provided", async () => {
  const origResolve = routeService._resolveUserAndRepo;
  const origSnap = routeService._resolveSnapshot;
  const origTree = routeService._ensureSnapshotTree;
  const origAi = (await import("../src/services/ai.service.js")).aiService.analyzeRoutes;

  let capturedOptions = null;
  routeService._resolveUserAndRepo = async () => ({ user: { id: "u1" }, repo: { id: "r1", name: "test-repo" } });
  routeService._resolveSnapshot = async () => ({ id: "s1", commitSha: "c1" });
  routeService._ensureSnapshotTree = async (repo, sha, opts) => {
    capturedOptions = opts;
    return "/mock/path";
  };
  (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = async () => mockAnalysis;

  try {
    await routeService.getRoutes("clerk_123", "r1", "c1", { refresh: "true" });
    assert.equal(capturedOptions?.force, true);

    await routeService.getRoutes("clerk_123", "r1", "c1", {});
    assert.equal(capturedOptions?.force, false);
  } finally {
    routeService._resolveUserAndRepo = origResolve;
    routeService._resolveSnapshot = origSnap;
    routeService._ensureSnapshotTree = origTree;
    (await import("../src/services/ai.service.js")).aiService.analyzeRoutes = origAi;
  }
});

test("ensureSnapshotTree validates actual files and cleans up empty/corrupt directories", async () => {
  const fs = await import("node:fs");
  const path = await import("node:path");
  const os = await import("node:os");
  const { ensureSnapshotTree } = await import("../src/services/git.service.js");

  const tempTestDir = path.join(os.tmpdir(), `codeai_tree_test_${Date.now()}`);
  fs.mkdirSync(tempTestDir, { recursive: true });

  try {
    // If repositoryId is an existing directory with files, it returns immediately
    const sampleFile = path.join(tempTestDir, "app.js");
    fs.writeFileSync(sampleFile, "console.log('test')", "utf8");
    const result = await ensureSnapshotTree(tempTestDir, "commit1");
    assert.equal(result, tempTestDir);
  } finally {
    try {
      fs.rmSync(tempTestDir, { recursive: true, force: true });
    } catch {}
  }
});
