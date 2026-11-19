import { useState, useMemo, useEffect } from "react";
import {
  ReactFlow,
  Background,
  Controls,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  Search,
  Filter,
  ArrowUpDown,
  CheckCircle2,
  AlertCircle,
  Code2,
  Layers,
  Database,
  Server,
  Shield,
  Activity,
  X,
  RefreshCw,
  ExternalLink,
  Webhook,
  FileCode,
  HardDrive,
  Info,
} from "lucide-react";
import { getSnapshotRoutes } from "../services/api.js";
import "./ApiMapView.css";

// Custom node component for the visual execution flow
function FlowStepNode({ data }) {
  const { stepType, label, file, line, desc } = data;

  const icons = {
    route: <Webhook size={14} className="text-sky-400" />,
    middleware: <Shield size={14} className="text-amber-400" />,
    controller: <Code2 size={14} className="text-purple-400" />,
    service: <Server size={14} className="text-emerald-400" />,
    model: <Database size={14} className="text-rose-400" />,
    database: <HardDrive size={14} className="text-zinc-200" />,
  };

  const borderClass = {
    route: "step-route",
    middleware: "step-middleware",
    controller: "step-controller",
    service: "step-service",
    model: "step-model",
    database: "step-database",
  }[stepType] || "step-route";

  return (
    <div
      className={`apimap-step-badge ${borderClass}`}
      style={{
        padding: "10px 14px",
        borderRadius: "8px",
        display: "flex",
        flexDirection: "column",
        gap: "4px",
        minWidth: "160px",
        boxShadow: "0 4px 12px rgba(0,0,0,0.3)",
      }}
    >
      <div style={{ display: "flex", alignItems: "center", gap: "6px", fontSize: "11px", opacity: 0.8 }}>
        {icons[stepType] || <Activity size={12} />}
        <span style={{ textTransform: "uppercase", letterSpacing: "0.05em" }}>{stepType}</span>
      </div>
      <div style={{ fontSize: "12px", fontWeight: 700, color: "var(--text-primary)", wordBreak: "break-all" }}>
        {label}
      </div>
      {desc && <div style={{ fontSize: "10px", color: "var(--text-muted)", fontStyle: "italic" }}>{desc}</div>}
      {file && (
        <div style={{ fontSize: "10px", color: "var(--text-muted)", marginTop: "2px" }}>
          {file.split("/").pop()}{line ? `:${line}` : ""}
        </div>
      )}
    </div>
  );
}

const nodeTypes = {
  flowStep: FlowStepNode,
};

function formatEndpointPath(path) {
  if (!path) return "/";
  const parts = path.split(/(:[a-zA-Z0-9_]+)/g);
  return (
    <span className="endpoint-path">
      {parts.map((p, i) =>
        p.startsWith(":") ? (
          <span key={i} className="endpoint-param">
            {p}
          </span>
        ) : (
          <span key={i}>{p}</span>
        )
      )}
    </span>
  );
}

export default function ApiMapView({
  repository = null,
  snapshot = null,
  graphData = null,
  getToken = null,
}) {
  const [routes, setRoutes] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [refreshKey, setRefreshKey] = useState(0);

  // Filters & Sorting state
  const [search, setSearch] = useState("");
  const [methodFilter, setMethodFilter] = useState("ALL");
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [controllerFilter, setControllerFilter] = useState("ALL");
  const [sortBy, setSortBy] = useState("endpoint-asc");

  // Selected route for detail slide-over
  const [selectedRoute, setSelectedRoute] = useState(null);

  // Fetch routes from Backend API
  useEffect(() => {
    let isCancelled = false;

    async function loadRoutes() {
      const commitSha = snapshot?.commitSha || snapshot?.commit_sha || snapshot?.sha;

      if (!repository?.id || !commitSha || !getToken) {
        // Fallback: extract endpoints directly from graphData if available
        if (graphData?.nodes) {
          const epNodes = graphData.nodes.filter(
            (n) => n.type === "api_endpoint" || n.node_type === "api_endpoint"
          );
          if (epNodes.length > 0) {
            console.log(`[ApiMapView] Loaded ${epNodes.length} endpoints from graphData fallback`);
            const mapped = epNodes.map((n) => {
              const method = n.metadata?.method || "GET";
              const endpoint = n.metadata?.endpoint || n.label.split(" ")[1] || n.label;
              return {
                id: n.id,
                http_method: method,
                http_endpoint: endpoint,
                route_path: n.metadata?.path || endpoint,
                source_file: n.metadata?.source_file || "unknown",
                start_line: Number(n.metadata?.start_line) || 1,
                router_base_path: "",
                controller: {
                  name: "controller",
                  function_name: "handler",
                  file_path: null,
                  parameters: ["req", "res"],
                  status: "resolved",
                },
                middleware: [],
                service_dependencies: [],
                model_dependencies: [],
                execution_flow: [
                  { step_type: "route", label: `${method} ${endpoint}` },
                  { step_type: "controller", label: "handler" },
                ],
                status: n.metadata?.status || "resolved",
              };
            });
            setRoutes(mapped);
            setSummary({
              total_endpoints: mapped.length,
              get_count: mapped.filter((r) => r.http_method === "GET").length,
              post_count: mapped.filter((r) => r.http_method === "POST").length,
              put_patch_count: mapped.filter((r) => ["PUT", "PATCH"].includes(r.http_method)).length,
              delete_count: mapped.filter((r) => r.http_method === "DELETE").length,
              unresolved_count: mapped.filter((r) => r.status === "unresolved").length,
            });
            setLoading(false);
            return;
          }
        }
        setLoading(false);
        return;
      }

      setLoading(true);
      setError(null);

      try {
        console.log(
          `[ApiMapView] Requesting routes for repo ${repository.id} (${repository.name || repository.owner || "repo"}), commit: ${commitSha}, refresh: ${refreshKey > 0}`
        );
        const data = await getSnapshotRoutes(getToken, repository.id, commitSha, {
          refresh: refreshKey > 0,
        });
        if (isCancelled) return;
        console.log(
          `[ApiMapView] Received ${data?.routes?.length || 0} routes, summary:`,
          data?.summary
        );
        setRoutes(data?.routes || []);
        setSummary(data?.summary || null);
      } catch (err) {
        if (isCancelled) return;
        console.warn("[ApiMapView] Could not fetch route analysis:", err);
        setError(err.message || "Failed to load API route map");
      } finally {
        if (!isCancelled) setLoading(false);
      }
    }

    loadRoutes();

    return () => {
      isCancelled = true;
    };
  }, [
    repository?.id,
    snapshot?.commitSha,
    snapshot?.commit_sha,
    snapshot?.sha,
    getToken,
    refreshKey,
    graphData,
  ]);

  // Distinct controller list for filter dropdown
  const controllerOptions = useMemo(() => {
    const set = new Set();
    routes.forEach((r) => {
      if (r.controller?.name && r.controller.name !== "unresolved" && r.controller.name !== "inline") {
        set.add(r.controller.name);
      }
    });
    return Array.from(set).sort();
  }, [routes]);

  // Filtered and sorted route list
  const filteredRoutes = useMemo(() => {
    let result = [...routes];

    if (search.trim()) {
      const q = search.trim().toLowerCase();
      result = result.filter(
        (r) =>
          r.http_endpoint.toLowerCase().includes(q) ||
          r.controller?.name?.toLowerCase().includes(q) ||
          r.source_file?.toLowerCase().includes(q) ||
          r.middleware?.some((m) => m.name.toLowerCase().includes(q))
      );
    }

    if (methodFilter !== "ALL") {
      if (methodFilter === "PUT/PATCH") {
        result = result.filter((r) => r.http_method === "PUT" || r.http_method === "PATCH");
      } else {
        result = result.filter((r) => r.http_method === methodFilter);
      }
    }

    if (statusFilter !== "ALL") {
      result = result.filter((r) => r.status?.toLowerCase() === statusFilter.toLowerCase());
    }

    if (controllerFilter !== "ALL") {
      result = result.filter((r) => r.controller?.name === controllerFilter);
    }

    result.sort((a, b) => {
      if (sortBy === "endpoint-asc") return a.http_endpoint.localeCompare(b.http_endpoint);
      if (sortBy === "endpoint-desc") return b.http_endpoint.localeCompare(a.http_endpoint);
      if (sortBy === "method") return a.http_method.localeCompare(b.http_method);
      if (sortBy === "status") return a.status.localeCompare(b.status);
      if (sortBy === "file") return a.source_file.localeCompare(b.source_file);
      return 0;
    });

    return result;
  }, [routes, search, methodFilter, statusFilter, controllerFilter, sortBy]);

  // Build ReactFlow nodes & edges for the visual execution flow of selected route
  const flowDiagram = useMemo(() => {
    if (!selectedRoute?.execution_flow || selectedRoute.execution_flow.length === 0) {
      return { nodes: [], edges: [] };
    }

    const flowSteps = selectedRoute.execution_flow;
    const spacingX = 220;
    const startY = 80;

    const nodes = flowSteps.map((step, idx) => ({
      id: `step-${idx}`,
      type: "flowStep",
      position: { x: 30 + idx * spacingX, y: startY },
      data: {
        stepType: step.step_type,
        label: step.label,
        file: step.file_path,
        line: step.line,
        desc: step.description,
      },
    }));

    const edges = [];
    for (let i = 0; i < flowSteps.length - 1; i++) {
      edges.push({
        id: `e-${i}-${i + 1}`,
        source: `step-${i}`,
        target: `step-${i + 1}`,
        animated: true,
        style: { stroke: "var(--border-focus, #38bdf8)", strokeWidth: 2 },
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: "var(--border-focus, #38bdf8)",
        },
      });
    }

    return { nodes, edges };
  }, [selectedRoute]);

  return (
    <div className="apimap-container">
      {/* 1. Header with Controls */}
      <div className="apimap-header">
        <div className="apimap-title-group">
          <div className="apimap-title-icon">
            <Webhook size={20} />
          </div>
          <div>
            <h2 className="apimap-title">API & Route Map</h2>
            <div className="apimap-subtitle">
              Automatic HTTP endpoint detection, controller resolution, and execution flow tracing
            </div>
          </div>
        </div>

        <div className="apimap-header-actions">
          <button
            type="button"
            className="apimap-btn-refresh"
            onClick={() => setRefreshKey((k) => k + 1)}
            disabled={loading}
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
            <span>Rescan Routes</span>
          </button>
        </div>
      </div>

      {/* 2. Summary Cards Grid */}
      <div className="apimap-summary-grid">
        <div
          className={`apimap-summary-card ${methodFilter === "ALL" && statusFilter === "ALL" ? "active" : ""}`}
          onClick={() => {
            setMethodFilter("ALL");
            setStatusFilter("ALL");
          }}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">Total Endpoints</span>
            <Webhook size={14} className="text-zinc-400" />
          </div>
          <div className="apimap-card-count">{summary?.total_endpoints ?? routes.length}</div>
          <div className="apimap-card-meta">Discovered across codebase</div>
        </div>

        <div
          className={`apimap-summary-card ${methodFilter === "GET" ? "active" : ""}`}
          onClick={() => setMethodFilter(methodFilter === "GET" ? "ALL" : "GET")}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">GET</span>
            <span className="method-pill method-GET">GET</span>
          </div>
          <div className="apimap-card-count">{summary?.get_count ?? routes.filter((r) => r.http_method === "GET").length}</div>
          <div className="apimap-card-meta">Read operations</div>
        </div>

        <div
          className={`apimap-summary-card ${methodFilter === "POST" ? "active" : ""}`}
          onClick={() => setMethodFilter(methodFilter === "POST" ? "ALL" : "POST")}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">POST</span>
            <span className="method-pill method-POST">POST</span>
          </div>
          <div className="apimap-card-count">{summary?.post_count ?? routes.filter((r) => r.http_method === "POST").length}</div>
          <div className="apimap-card-meta">Create & Mutation</div>
        </div>

        <div
          className={`apimap-summary-card ${methodFilter === "PUT/PATCH" ? "active" : ""}`}
          onClick={() => setMethodFilter(methodFilter === "PUT/PATCH" ? "ALL" : "PUT/PATCH")}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">PUT / PATCH</span>
            <span className="method-pill method-PUT">PUT</span>
          </div>
          <div className="apimap-card-count">
            {summary?.put_patch_count ?? routes.filter((r) => ["PUT", "PATCH"].includes(r.http_method)).length}
          </div>
          <div className="apimap-card-meta">Update operations</div>
        </div>

        <div
          className={`apimap-summary-card ${methodFilter === "DELETE" ? "active" : ""}`}
          onClick={() => setMethodFilter(methodFilter === "DELETE" ? "ALL" : "DELETE")}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">DELETE</span>
            <span className="method-pill method-DELETE">DEL</span>
          </div>
          <div className="apimap-card-count">
            {summary?.delete_count ?? routes.filter((r) => r.http_method === "DELETE").length}
          </div>
          <div className="apimap-card-meta">Removal operations</div>
        </div>

        <div
          className={`apimap-summary-card ${statusFilter === "unresolved" ? "active" : ""}`}
          onClick={() => setStatusFilter(statusFilter === "unresolved" ? "ALL" : "unresolved")}
        >
          <div className="apimap-card-top">
            <span className="apimap-card-label">Unresolved</span>
            <AlertCircle size={14} className="text-rose-400" />
          </div>
          <div className="apimap-card-count" style={{ color: (summary?.unresolved_count || 0) > 0 ? "#fb7185" : "inherit" }}>
            {summary?.unresolved_count ?? routes.filter((r) => r.status === "unresolved").length}
          </div>
          <div className="apimap-card-meta">Missing controller link</div>
        </div>
      </div>

      {/* 3. Filter Toolbar */}
      <div className="apimap-toolbar">
        <div className="apimap-toolbar-left">
          {/* Search box */}
          <div className="apimap-search-box">
            <Search size={14} className="text-zinc-400" />
            <input
              type="text"
              placeholder="Search endpoint, controller, file..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            {search && (
              <button type="button" className="apimap-clear-btn" onClick={() => setSearch("")}>
                <X size={13} />
              </button>
            )}
          </div>

          {/* HTTP Method filter pills */}
          <div className="apimap-method-filters">
            {["ALL", "GET", "POST", "PUT/PATCH", "DELETE"].map((m) => (
              <button
                key={m}
                type="button"
                className={`apimap-filter-pill ${methodFilter === m ? "active" : ""}`}
                onClick={() => setMethodFilter(m)}
              >
                {m}
              </button>
            ))}
          </div>

          {/* Controller select */}
          {controllerOptions.length > 0 && (
            <select
              className="apimap-select-dropdown"
              value={controllerFilter}
              onChange={(e) => setControllerFilter(e.target.value)}
            >
              <option value="ALL">All Controllers ({controllerOptions.length})</option>
              {controllerOptions.map((c) => (
                <option key={c} value={c}>
                  {c}
                </option>
              ))}
            </select>
          )}

          {/* Status filter */}
          <select
            className="apimap-select-dropdown"
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
          >
            <option value="ALL">All Statuses</option>
            <option value="resolved">Resolved</option>
            <option value="inline">Inline Handler</option>
            <option value="unresolved">Unresolved</option>
          </select>
        </div>

        <div className="apimap-toolbar-right">
          <select
            className="apimap-select-dropdown"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value)}
          >
            <option value="endpoint-asc">Endpoint (A-Z)</option>
            <option value="endpoint-desc">Endpoint (Z-A)</option>
            <option value="method">HTTP Method</option>
            <option value="status">Status</option>
            <option value="file">Source File</option>
          </select>

          <span className="apimap-counter-badge">
            {filteredRoutes.length} of {routes.length}
          </span>
        </div>
      </div>

      {/* 4. Table / State Box */}
      {loading ? (
        <div className="apimap-state-box">
          <div className="apimap-spinner" />
          <div className="apimap-state-title">Analyzing Repository Endpoints</div>
          <div className="apimap-state-desc">
            Parsing Tree-sitter syntax trees, resolving router mount hierarchies, and tracing controller chains...
          </div>
        </div>
      ) : error ? (
        <div className="apimap-state-box" style={{ borderColor: "rgba(244, 63, 94, 0.3)" }}>
          <AlertCircle size={28} className="text-rose-400" />
          <div className="apimap-state-title" style={{ color: "#fb7185" }}>
            Failed to Load Routes
          </div>
          <div className="apimap-state-desc">{error}</div>
          <button
            type="button"
            className="apimap-btn-refresh"
            style={{ marginTop: "8px" }}
            onClick={() => setRefreshKey((k) => k + 1)}
          >
            Retry
          </button>
        </div>
      ) : filteredRoutes.length === 0 ? (
        <div className="apimap-state-box">
          <Webhook size={32} className="text-zinc-500" />
          <div className="apimap-state-title">No Endpoints Match Your Filters</div>
          <div className="apimap-state-desc">
            {routes.length === 0
              ? "No Express HTTP endpoints were discovered in this repository snapshot."
              : "Try adjusting your search query, HTTP method filter, or controller selection."}
          </div>
        </div>
      ) : (
        <div className="apimap-table-wrapper">
          <table className="apimap-table">
            <thead>
              <tr>
                <th style={{ width: "90px" }}>Method</th>
                <th>HTTP Endpoint</th>
                <th>Controller</th>
                <th>Middleware</th>
                <th style={{ width: "110px" }}>Status</th>
                <th>Source File</th>
                <th style={{ width: "80px", textAlign: "right" }}>Inspect</th>
              </tr>
            </thead>
            <tbody>
              {filteredRoutes.map((r) => {
                const isSelected = selectedRoute?.id === r.id;
                return (
                  <tr
                    key={r.id}
                    className={`apimap-row ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedRoute(r)}
                  >
                    <td>
                      <span className={`method-pill method-${r.http_method}`}>{r.http_method}</span>
                    </td>
                    <td>{formatEndpointPath(r.http_endpoint)}</td>
                    <td>
                      {r.controller?.name && r.controller.name !== "inline" ? (
                        <span className="controller-tag">
                          <Code2 size={12} />
                          {r.controller.name}
                        </span>
                      ) : (
                        <span className="controller-inline">inline handler</span>
                      )}
                    </td>
                    <td>
                      {r.middleware && r.middleware.length > 0 ? (
                        <div className="middleware-badge-list">
                          {r.middleware.slice(0, 2).map((m, i) => (
                            <span key={i} className="middleware-badge">
                              {m.name}
                            </span>
                          ))}
                          {r.middleware.length > 2 && (
                            <span className="middleware-count-pill">+{r.middleware.length - 2}</span>
                          )}
                        </div>
                      ) : (
                        <span style={{ color: "var(--text-muted)", fontSize: "11px" }}>none</span>
                      )}
                    </td>
                    <td>
                      <span className={`status-pill status-${r.status}`}>
                        <span className="status-dot" />
                        {r.status === "resolved" ? "Resolved" : r.status === "inline" ? "Inline" : "Unresolved"}
                      </span>
                    </td>
                    <td>
                      <span className="source-file-tag">
                        <FileCode size={12} />
                        {r.source_file.split("/").pop()}:{r.start_line}
                      </span>
                    </td>
                    <td style={{ textAlign: "right" }}>
                      <button
                        type="button"
                        className="inspect-btn"
                        onClick={(e) => {
                          e.stopPropagation();
                          setSelectedRoute(r);
                        }}
                      >
                        Inspect
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* 5. Endpoint Detail Slide-Over Drawer */}
      {selectedRoute && (
        <div className="apimap-drawer-overlay" onClick={() => setSelectedRoute(null)}>
          <div className="apimap-drawer" onClick={(e) => e.stopPropagation()}>
            {/* Drawer Header */}
            <div className="apimap-drawer-header">
              <div className="apimap-drawer-header-left">
                <span className={`method-pill method-${selectedRoute.http_method}`}>
                  {selectedRoute.http_method}
                </span>
                <h3 className="apimap-drawer-endpoint">{selectedRoute.http_endpoint}</h3>
              </div>
              <button
                type="button"
                className="apimap-drawer-close"
                onClick={() => setSelectedRoute(null)}
              >
                <X size={18} />
              </button>
            </div>

            {/* Drawer Body */}
            <div className="apimap-drawer-body">
              {/* Route Information Card */}
              <div className="apimap-detail-section">
                <div className="apimap-detail-section-title">
                  <Info size={14} />
                  Route Information
                </div>
                <div className="apimap-meta-card">
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">HTTP Method</span>
                    <span className="apimap-meta-item-value">{selectedRoute.http_method}</span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Full Endpoint</span>
                    <span className="apimap-meta-item-value">{selectedRoute.http_endpoint}</span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Route Path</span>
                    <span className="apimap-meta-item-value">{selectedRoute.route_path}</span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Router Base Path</span>
                    <span className="apimap-meta-item-value">
                      {selectedRoute.router_base_path || "/ (root)"}
                    </span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Source File</span>
                    <span className="apimap-meta-item-value">
                      {selectedRoute.source_file}:{selectedRoute.start_line}
                    </span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Resolution Status</span>
                    <span className={`status-pill status-${selectedRoute.status}`}>
                      <span className="status-dot" />
                      {selectedRoute.status.toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>

              {/* Visual Execution Flow Graph (Interactive ReactFlow) */}
              <div className="apimap-detail-section">
                <div className="apimap-detail-section-title">
                  <Activity size={14} />
                  Visual Execution Flow (Route → Controller → Service → Model)
                </div>
                <div className="apimap-flow-canvas-container">
                  {flowDiagram.nodes.length > 0 ? (
                    <ReactFlow
                      nodes={flowDiagram.nodes}
                      edges={flowDiagram.edges}
                      nodeTypes={nodeTypes}
                      fitView
                      fitViewOptions={{ padding: 0.25 }}
                      proOptions={{ hideAttribution: true }}
                    >
                      <Background color="#27272a" gap={16} size={1} />
                      <Controls showInteractive={false} />
                    </ReactFlow>
                  ) : (
                    <div className="apimap-state-box" style={{ height: "100%", border: "none" }}>
                      <span style={{ color: "var(--text-muted)", fontSize: "12px" }}>
                        No execution steps traced for this endpoint.
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Controller Details */}
              <div className="apimap-detail-section">
                <div className="apimap-detail-section-title">
                  <Code2 size={14} />
                  Controller Handler
                </div>
                <div className="apimap-meta-card">
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Controller Identifier</span>
                    <span className="apimap-meta-item-value">{selectedRoute.controller?.name || "inline"}</span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Function Name</span>
                    <span className="apimap-meta-item-value">{selectedRoute.controller?.function_name || "anonymous"}</span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">File Location</span>
                    <span className="apimap-meta-item-value">
                      {selectedRoute.controller?.file_path || selectedRoute.source_file}
                      {selectedRoute.controller?.start_line ? `:${selectedRoute.controller.start_line}` : ""}
                    </span>
                  </div>
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Parameters</span>
                    <span className="apimap-meta-item-value">
                      {selectedRoute.controller?.parameters?.length > 0
                        ? `(${selectedRoute.controller.parameters.join(", ")})`
                        : "()"}
                    </span>
                  </div>
                  {selectedRoute.controller?.called_functions?.length > 0 && (
                    <div className="apimap-meta-item" style={{ gridColumn: "1 / -1" }}>
                      <span className="apimap-meta-item-label">Called Functions / Invocations</span>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "6px", marginTop: "4px" }}>
                        {selectedRoute.controller.called_functions.map((fn, i) => (
                          <span key={i} className="controller-tag">
                            {fn}
                          </span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Middleware Chain */}
              <div className="apimap-detail-section">
                <div className="apimap-detail-section-title">
                  <Shield size={14} />
                  Middleware Chain ({selectedRoute.middleware?.length || 0})
                </div>
                {selectedRoute.middleware && selectedRoute.middleware.length > 0 ? (
                  <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
                    {selectedRoute.middleware.map((m, i) => (
                      <div
                        key={i}
                        className="apimap-meta-card"
                        style={{ padding: "10px 14px", display: "flex", justifyContent: "space-between", alignItems: "center" }}
                      >
                        <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
                          <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
                            #{i + 1}
                          </span>
                          <span style={{ fontFamily: "var(--font-mono)", fontWeight: 600, color: "var(--text-primary)" }}>
                            {m.name}
                          </span>
                          {m.is_inline && (
                            <span style={{ fontSize: "10px", color: "#60a5fa", fontStyle: "italic" }}>(inline)</span>
                          )}
                        </div>
                        <span style={{ fontFamily: "var(--font-mono)", fontSize: "11px", color: "var(--text-muted)" }}>
                          {m.source_file || "shared"}
                        </span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ fontSize: "12px", color: "var(--text-muted)", fontStyle: "italic" }}>
                    No middleware configured for this endpoint.
                  </div>
                )}
              </div>

              {/* Service & Database Dependencies */}
              <div className="apimap-detail-section">
                <div className="apimap-detail-section-title">
                  <Database size={14} />
                  Downstream Services & Database Models
                </div>
                <div className="apimap-meta-card">
                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Service Dependencies</span>
                    {selectedRoute.service_dependencies?.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "4px" }}>
                        {selectedRoute.service_dependencies.map((s, i) => (
                          <span key={i} className="controller-tag" style={{ color: "#34d399", background: "rgba(52, 211, 153, 0.08)" }}>
                            <Server size={12} />
                            {s.service_name}{s.method_name ? `.${s.method_name}()` : ""}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="apimap-meta-item-value" style={{ color: "var(--text-muted)" }}>None</span>
                    )}
                  </div>

                  <div className="apimap-meta-item">
                    <span className="apimap-meta-item-label">Database Model Access</span>
                    {selectedRoute.model_dependencies?.length > 0 ? (
                      <div style={{ display: "flex", flexDirection: "column", gap: "4px", marginTop: "4px" }}>
                        {selectedRoute.model_dependencies.map((m, i) => (
                          <span key={i} className="controller-tag" style={{ color: "#fb7185", background: "rgba(244, 63, 94, 0.08)" }}>
                            <Database size={12} />
                            {m.model_name}{m.operation ? `.${m.operation}()` : ""}
                          </span>
                        ))}
                      </div>
                    ) : (
                      <span className="apimap-meta-item-value" style={{ color: "var(--text-muted)" }}>None</span>
                    )}
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
