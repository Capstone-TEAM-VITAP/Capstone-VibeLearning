import { useState, useMemo, useCallback, useEffect, useRef } from "react";
import {
  ReactFlow,
  ReactFlowProvider,
  Background,
  Controls,
  MiniMap,
  useReactFlow,
  MarkerType,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import CodeGraphNode from "./CodeGraphNode.jsx";
import GraphNodeInspector from "./GraphNodeInspector.jsx";
import "./CodeGraphView.css";

const nodeTypes = {
  codeGraphNode: CodeGraphNode,
};

// Architecture tier priorities for swimlanes layout
const LAYER_ORDER = {
  PRESENTATION: 0,
  APPLICATION: 1,
  DOMAIN: 2,
  DATA: 3,
  INFRASTRUCTURE: 4,
  DEPENDENCIES: 5,
  SYMBOLS: 6,
  OTHER: 7,
};

function mapNodeToLayer(node) {
  const role = (node.architecture_role || node.metadata?.role || "").toUpperCase();
  const type = (node.type || "").toLowerCase();

  if (role === "COMPONENT" || role === "HOOK") return "PRESENTATION";
  if (role === "ROUTE" || role === "CONTROLLER" || role === "SERVICE") return "APPLICATION";
  if (role === "MODEL" || role === "ENTITY") return "DOMAIN";
  if (role === "REPOSITORY_ROLE") return "DATA";
  if (
    role === "MIDDLEWARE" ||
    role === "CONFIG" ||
    role === "UTILITY" ||
    role === "ENTRYPOINT"
  ) {
    return "INFRASTRUCTURE";
  }

  if (type === "external" || type === "unresolved") return "DEPENDENCIES";
  if (["function", "class", "method", "variable", "constant"].includes(type)) {
    return "SYMBOLS";
  }

  return "OTHER";
}

function computeLayout(nodes, edges, mode = "architecture") {
  if (!nodes || nodes.length === 0) return [];

  const positions = {};

  if (mode === "architecture") {
    // Group nodes by architectural layer
    const buckets = {};
    for (const key of Object.keys(LAYER_ORDER)) {
      buckets[key] = [];
    }

    for (const node of nodes) {
      const layer = mapNodeToLayer(node);
      if (!buckets[layer]) buckets[layer] = [];
      buckets[layer].push(node);
    }

    let currentY = 40;
    const MAX_COLS_PER_TIER = 4;
    const X_SPACING = 240;
    const Y_ROW_SPACING = 95;
    const Y_TIER_GAP = 55;

    for (const [, group] of Object.entries(buckets)) {
      if (group.length === 0) continue;

      const numRows = Math.ceil(group.length / MAX_COLS_PER_TIER);

      group.forEach((node, idx) => {
        const row = Math.floor(idx / MAX_COLS_PER_TIER);
        const col = idx % MAX_COLS_PER_TIER;

        const itemsInThisRow =
          row === numRows - 1 && group.length % MAX_COLS_PER_TIER !== 0
            ? group.length % MAX_COLS_PER_TIER
            : MAX_COLS_PER_TIER;

        const rowWidth = (itemsInThisRow - 1) * X_SPACING;
        const startX = Math.max(40, (960 - rowWidth) / 2);

        positions[node.id] = {
          x: Math.round(startX + col * X_SPACING),
          y: Math.round(currentY + row * Y_ROW_SPACING),
        };
      });

      currentY += numRows * Y_ROW_SPACING + Y_TIER_GAP;
    }
  } else if (mode === "modular") {
    // Group nodes by top-level directory (backend, frontend, root, external)
    const dirBuckets = {};

    for (const node of nodes) {
      let bucket = "root";
      const rawPath =
        node.metadata?.path ||
        (node.id.startsWith("file:") ? node.id.replace(/^file:/, "") : "");
      if (rawPath) {
        const topDir = rawPath.replace(/\\/g, "/").split("/")[0];
        bucket = topDir || "root";
      } else if (node.type?.toLowerCase() === "external") {
        bucket = "external";
      } else if (node.type?.toLowerCase() === "unresolved") {
        bucket = "unresolved";
      }

      if (!dirBuckets[bucket]) dirBuckets[bucket] = [];
      dirBuckets[bucket].push(node);
    }

    let colX = 40;
    const COL_WIDTH = 250;
    const ROW_HEIGHT = 100;

    for (const [, group] of Object.entries(dirBuckets)) {
      group.forEach((node, rowIdx) => {
        positions[node.id] = {
          x: colX,
          y: 40 + rowIdx * ROW_HEIGHT,
        };
      });
      colX += COL_WIDTH;
    }
  } else {
    // Hierarchical DAG (approximate topological layer via in-degree)
    const inDegree = {};
    for (const n of nodes) inDegree[n.id] = 0;
    for (const e of edges) {
      if (inDegree[e.target] !== undefined) inDegree[e.target]++;
    }

    const sorted = [...nodes].sort(
      (a, b) => (inDegree[a.id] || 0) - (inDegree[b.id] || 0),
    );

    const COLS = Math.min(4, Math.max(2, Math.ceil(Math.sqrt(nodes.length))));
    const X_GAP = 240;
    const Y_GAP = 105;

    sorted.forEach((node, index) => {
      const col = index % COLS;
      const row = Math.floor(index / COLS);
      positions[node.id] = {
        x: 40 + col * X_GAP + (row % 2 === 1 ? 30 : 0),
        y: 40 + row * Y_GAP,
      };
    });
  }

  return nodes.map((node) => ({
    ...node,
    position: positions[node.id] || { x: 100, y: 100 },
  }));
}

function CodeGraphContent({
  graphData,
  activeRepo,
  activeSnapshot,
  isLoading,
  error,
  onRetry,
  setView,
}) {
  const { fitView, zoomIn, zoomOut, setCenter, setViewport } = useReactFlow();

  const [selectedNodeId, setSelectedNodeId] = useState(null);
  const [isInspectorOpen, setIsInspectorOpen] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const workspaceRef = useRef(null);

  const [scope, setScope] = useState("architecture_files"); // "architecture_files" | "all" | "files_only" | "architecture_only"
  const [roleFilter, setRoleFilter] = useState("ALL");
  const [edgeTypeFilter, setEdgeTypeFilter] = useState("ALL");
  const [layoutMode, setLayoutMode] = useState("architecture");
  const [searchQuery, setSearchQuery] = useState("");
  const [showSearchDropdown, setShowSearchDropdown] = useState(false);
  const searchWrapRef = useRef(null);

  // Close search dropdown on click outside
  useEffect(() => {
    function handleClickOutside(e) {
      if (searchWrapRef.current && !searchWrapRef.current.contains(e.target)) {
        setShowSearchDropdown(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  // Fullscreen toggle
  const toggleFullscreen = useCallback(() => {
    if (!document.fullscreenElement) {
      if (workspaceRef.current?.requestFullscreen) {
        workspaceRef.current.requestFullscreen().catch((err) => {
          console.warn("Fullscreen error:", err);
        });
      }
    } else {
      if (document.exitFullscreen) {
        document.exitFullscreen().catch((err) => {
          console.warn("Fullscreen exit error:", err);
        });
      }
    }
  }, []);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
      requestAnimationFrame(() => {
        fitView({ padding: 0.18, duration: 300 });
      });
    };

    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () => {
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
    };
  }, [fitView]);

  // Raw Graph IR arrays
  const rawNodes = useMemo(
    () => (Array.isArray(graphData?.nodes) ? graphData.nodes : []),
    [graphData],
  );
  const rawEdges = useMemo(
    () => (Array.isArray(graphData?.edges) ? graphData.edges : []),
    [graphData],
  );

  // Collect all unique architecture roles present in real graph data
  const availableRoles = useMemo(() => {
    const set = new Set();
    for (const n of rawNodes) {
      const r = n.architecture_role || n.metadata?.role;
      if (r) set.add(r.toUpperCase());
    }
    return Array.from(set).sort();
  }, [rawNodes]);

  // Collect all unique edge types present in real graph data
  const availableEdgeTypes = useMemo(() => {
    const set = new Set();
    for (const e of rawEdges) {
      if (e.type) set.add(e.type.toUpperCase());
    }
    return Array.from(set).sort();
  }, [rawEdges]);

  // Filter nodes based on Scope and Role
  const filteredNodes = useMemo(() => {
    return rawNodes.filter((node) => {
      const type = (node.type || "").toLowerCase();
      const role = (node.architecture_role || node.metadata?.role || "").toUpperCase();

      // Role filter check
      if (roleFilter !== "ALL" && role !== roleFilter) {
        return false;
      }

      // Scope filtering
      if (scope === "files_only") {
        return type === "file";
      }
      if (scope === "architecture_only") {
        return (
          Boolean(role) ||
          type.startsWith("controller") ||
          type.startsWith("service") ||
          type.startsWith("model") ||
          type.startsWith("route") ||
          type.startsWith("component") ||
          type.startsWith("hook") ||
          type.startsWith("middleware")
        );
      }
      if (scope === "architecture_files") {
        // Exclude deep individual symbols unless selected
        const isSymbol = ["function", "class", "method", "variable", "constant"].includes(type);
        if (isSymbol && node.id !== selectedNodeId) {
          return false;
        }
        return true;
      }

      // "all" scope includes everything
      return true;
    });
  }, [rawNodes, scope, roleFilter, selectedNodeId]);

  // Set of visible node IDs for edge validation
  const visibleNodeIds = useMemo(() => {
    return new Set(filteredNodes.map((n) => n.id));
  }, [filteredNodes]);

  // Filter edges
  const filteredEdges = useMemo(() => {
    return rawEdges.filter((edge) => {
      // Must connect valid visible nodes
      if (!visibleNodeIds.has(edge.source) || !visibleNodeIds.has(edge.target)) {
        return false;
      }

      // Edge type filter check
      if (edgeTypeFilter !== "ALL") {
        if ((edge.type || "").toUpperCase() !== edgeTypeFilter) {
          return false;
        }
      }

      return true;
    });
  }, [rawEdges, visibleNodeIds, edgeTypeFilter]);

  // Search results
  const searchResults = useMemo(() => {
    if (!searchQuery.trim()) return [];
    const q = searchQuery.toLowerCase();

    return rawNodes
      .filter((n) => {
        const label = (n.label || "").toLowerCase();
        const id = (n.id || "").toLowerCase();
        const role = (n.architecture_role || n.metadata?.role || "").toLowerCase();
        const path = (n.metadata?.path || "").toLowerCase();
        return label.includes(q) || id.includes(q) || role.includes(q) || path.includes(q);
      })
      .slice(0, 8);
  }, [rawNodes, searchQuery]);

  // Direct neighbors of selected node (for graph highlighting)
  const directNeighbors = useMemo(() => {
    if (!selectedNodeId) return null;
    const neighbors = new Set();
    neighbors.add(selectedNodeId);

    for (const e of rawEdges) {
      if (e.source === selectedNodeId) neighbors.add(e.target);
      if (e.target === selectedNodeId) neighbors.add(e.source);
    }
    return neighbors;
  }, [selectedNodeId, rawEdges]);

  // Compute layout positions for nodes
  const layoutedNodes = useMemo(() => {
    return computeLayout(filteredNodes, filteredEdges, layoutMode);
  }, [filteredNodes, filteredEdges, layoutMode]);

  // Transform to React Flow Nodes
  const rfNodes = useMemo(() => {
    return layoutedNodes.map((n) => {
      const isSelected = n.id === selectedNodeId;
      const isHighlighted = directNeighbors ? directNeighbors.has(n.id) : false;
      const isDimmed = directNeighbors ? !directNeighbors.has(n.id) : false;

      const path =
        n.metadata?.path?.replace(/\\/g, "/") ||
        (n.id.startsWith("file:") ? n.id.replace(/^file:/, "") : null);

      return {
        id: n.id,
        type: "codeGraphNode",
        position: n.position,
        data: {
          label: n.label || n.id,
          type: n.type,
          role: n.architecture_role || n.metadata?.role || null,
          path,
          isSelected,
          isHighlighted,
          isDimmed,
        },
      };
    });
  }, [layoutedNodes, selectedNodeId, directNeighbors]);

  // Transform to React Flow Edges
  const rfEdges = useMemo(() => {
    return filteredEdges.map((e) => {
      const isConnectedToSelected =
        selectedNodeId &&
        (e.source === selectedNodeId || e.target === selectedNodeId);

      const isDimmed =
        selectedNodeId &&
        e.source !== selectedNodeId &&
        e.target !== selectedNodeId;

      const typeUpper = (e.type || "DEPENDS_ON").toUpperCase();

      let strokeColor = "#64748b";
      let strokeDash = undefined;

      if (typeUpper === "IMPORTS") {
        strokeColor = "#818cf8";
      } else if (typeUpper === "CALLS") {
        strokeColor = "#38bdf8";
        strokeDash = "5,5";
      } else if (typeUpper === "DEPENDS_ON") {
        strokeColor = "#2dd4bf";
        strokeDash = "4,4";
      } else if (typeUpper === "CONTAINS") {
        strokeColor = "#52525b";
        strokeDash = "2,3";
      } else if (typeUpper === "CLASSIFIED_AS") {
        strokeColor = "#c084fc";
      }

      if (isConnectedToSelected) {
        strokeColor = "#38bdf8";
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "default",
        animated: isConnectedToSelected,
        markerEnd: {
          type: MarkerType.ArrowClosed,
          color: strokeColor,
          width: 14,
          height: 14,
        },
        style: {
          stroke: strokeColor,
          strokeWidth: isConnectedToSelected ? 2.5 : 1.3,
          strokeDasharray: strokeDash,
          opacity: isDimmed ? 0.12 : isConnectedToSelected ? 1 : 0.75,
        },
        zIndex: isConnectedToSelected ? 10 : 1,
      };
    });
  }, [filteredEdges, selectedNodeId]);

  // Handle node selection & centering
  const handleSelectNode = useCallback(
    (nodeId) => {
      setSelectedNodeId(nodeId);
      setIsInspectorOpen(true);
      const targetNode = layoutedNodes.find((n) => n.id === nodeId);
      if (targetNode) {
        setCenter(targetNode.position.x + 105, targetNode.position.y + 35, {
          duration: 500,
          zoom: 1.15,
        });
      }
    },
    [layoutedNodes, setCenter],
  );

  const handleNodeClick = useCallback(
    (_, node) => {
      handleSelectNode(node.id);
    },
    [handleSelectNode],
  );

  const handlePaneClick = useCallback(() => {
    setSelectedNodeId(null);
  }, []);

  // Fit view on initial load or layout/scope/inspector changes
  useEffect(() => {
    if (layoutedNodes.length > 0) {
      const timer = setTimeout(() => {
        requestAnimationFrame(() => {
          fitView({
            padding: 0.18,
            duration: 450,
            maxZoom: 1.15,
            minZoom: 0.35,
          });
        });
      }, 70);
      return () => clearTimeout(timer);
    }
  }, [layoutMode, scope, fitView, layoutedNodes.length, isInspectorOpen]);

  // Handle search result click
  function handleSelectSearchResult(item) {
    setSearchQuery("");
    setShowSearchDropdown(false);
    handleSelectNode(item.id);
  }

  // Fallbacks & States
  if (!activeRepo) {
    return (
      <div className="codegraph-state-box">
        <span className="material-symbols-outlined codegraph-state-icon">
          folder_off
        </span>
        <h3 className="codegraph-state-title">No repository selected</h3>
        <p className="codegraph-state-desc">
          Select or connect a GitHub repository to view its structural CodeGraph.
        </p>
        <button
          className="codegraph-primary-btn"
          onClick={() => setView("repos")}
          type="button"
        >
          <span className="material-symbols-outlined">hub</span>
          Open Repositories
        </button>
      </div>
    );
  }

  if (isLoading) {
    return (
      <div className="codegraph-loading-wrap">
        <div className="codegraph-loading-spinner" />
        <div className="codegraph-loading-title font-mono">
          Loading CodeGraph from Graph IR...
        </div>
        <div className="codegraph-loading-sub">
          Generating deterministic structural models and dependency topology
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="codegraph-state-box">
        <span className="material-symbols-outlined codegraph-state-icon codegraph-state-icon--error">
          error_outline
        </span>
        <h3 className="codegraph-state-title">Unable to load CodeGraph</h3>
        <p className="codegraph-state-desc">{error}</p>
        <button
          className="codegraph-primary-btn"
          onClick={onRetry}
          type="button"
        >
          <span className="material-symbols-outlined">refresh</span>
          Retry
        </button>
      </div>
    );
  }

  if (!graphData || graphData.schema_version !== "1.0") {
    return (
      <div className="codegraph-state-box">
        <span className="material-symbols-outlined codegraph-state-icon codegraph-state-icon--warn">
          account_tree
        </span>
        <h3 className="codegraph-state-title">CodeGraph requires repository analysis</h3>
        <p className="codegraph-state-desc">
          Run repository analysis to generate the canonical Graph IR structural model.
        </p>
        <button
          className="codegraph-primary-btn"
          onClick={() => setView("analysis")}
          type="button"
        >
          <span className="material-symbols-outlined">play_arrow</span>
          Analyze Repository
        </button>
      </div>
    );
  }

  return (
    <div
      className={`codegraph-workspace ${isFullscreen ? "codegraph-workspace--fullscreen" : ""}`}
      ref={workspaceRef}
    >
      {/* Workspace Header */}
      <div className="codegraph-header">
        <div className="codegraph-header-left">
          <div className="codegraph-eyebrow">CODE GRAPH</div>
          <h1 className="codegraph-heading">Repository CodeGraph</h1>
          <p className="codegraph-desc">
            Explore the structural relationships that connect your repository.
          </p>

          <div className="codegraph-context-strip">
            <span className="codegraph-context-pill repo-pill">
              <span className="material-symbols-outlined">folder</span>
              {activeRepo.name}
            </span>
            <span className="codegraph-context-pill branch-pill font-mono">
              <span className="material-symbols-outlined">fork_right</span>
              {activeSnapshot?.branch || "main"}
            </span>
            {activeSnapshot?.commit_sha && (
              <span className="codegraph-context-pill sha-pill font-mono">
                <span className="material-symbols-outlined">commit</span>
                {activeSnapshot.commit_sha.slice(0, 7)}
              </span>
            )}
            <span className="codegraph-context-pill status-pill">
              <span className="status-dot-complete" />
              Analysis Complete
            </span>
          </div>
        </div>

        <div className="codegraph-header-actions">
          <button
            className="codegraph-action-btn codegraph-action-btn--secondary"
            onClick={() => setView("analysis")}
            type="button"
          >
            <span className="material-symbols-outlined">smart_toy</span>
            Ask AI
          </button>
          <button
            className="codegraph-action-btn codegraph-action-btn--primary"
            onClick={() => setView("repos")}
            type="button"
          >
            <span className="material-symbols-outlined">difference</span>
            Analyze Changes
          </button>
        </div>
      </div>

      {/* Graph Toolbar */}
      <div className="codegraph-toolbar">
        {/* Left Toolbar Items */}
        <div className="toolbar-group toolbar-group--left">
          {/* Search with autocomplete dropdown */}
          <div className="graph-search-box" ref={searchWrapRef}>
            <span className="material-symbols-outlined graph-search-icon">search</span>
            <input
              type="text"
              className="graph-search-input font-mono"
              placeholder="Search node, symbol, path, or role..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setShowSearchDropdown(true);
              }}
              onFocus={() => setShowSearchDropdown(true)}
            />
            {searchQuery && (
              <button
                className="graph-search-clear"
                onClick={() => setSearchQuery("")}
                type="button"
              >
                <span className="material-symbols-outlined">close</span>
              </button>
            )}

            {showSearchDropdown && searchResults.length > 0 && (
              <div className="graph-search-results">
                {searchResults.map((item) => (
                  <button
                    key={item.id}
                    className="graph-search-result-item"
                    onClick={() => handleSelectSearchResult(item)}
                    type="button"
                  >
                    <span className="material-symbols-outlined result-icon">
                      {item.type === "file" ? "description" : "hub"}
                    </span>
                    <div className="result-text">
                      <div className="result-label font-mono">
                        {item.label || item.id}
                      </div>
                      <div className="result-sub font-mono">
                        {item.metadata?.path || item.type}
                      </div>
                    </div>
                    {item.architecture_role && (
                      <span className="result-role font-mono">
                        {item.architecture_role}
                      </span>
                    )}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Scope Selector */}
          <div className="graph-select-wrap">
            <span className="graph-select-label">Scope:</span>
            <select
              className="graph-select font-mono"
              value={scope}
              onChange={(e) => setScope(e.target.value)}
            >
              <option value="architecture_files">Architecture & Files</option>
              <option value="all">All Nodes (incl. Symbols)</option>
              <option value="files_only">Files Only</option>
              <option value="architecture_only">Architecture Only</option>
            </select>
          </div>

          {/* Role Filter */}
          {availableRoles.length > 0 && (
            <div className="graph-select-wrap">
              <span className="graph-select-label">Role:</span>
              <select
                className="graph-select font-mono"
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <option value="ALL">All Roles ({availableRoles.length})</option>
                {availableRoles.map((r) => (
                  <option key={r} value={r}>
                    {r}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Edge Type Filter */}
          {availableEdgeTypes.length > 0 && (
            <div className="graph-select-wrap">
              <span className="graph-select-label">Edges:</span>
              <select
                className="graph-select font-mono"
                value={edgeTypeFilter}
                onChange={(e) => setEdgeTypeFilter(e.target.value)}
              >
                <option value="ALL">All Relationships ({availableEdgeTypes.length})</option>
                {availableEdgeTypes.map((et) => (
                  <option key={et} value={et}>
                    {et}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>

        {/* Right Toolbar Items */}
        <div className="toolbar-group toolbar-group--right">
          {/* Layout Selector */}
          <div className="graph-select-wrap">
            <span className="graph-select-label">Layout:</span>
            <select
              className="graph-select font-mono"
              value={layoutMode}
              onChange={(e) => setLayoutMode(e.target.value)}
            >
              <option value="architecture">Architecture Swimlanes</option>
              <option value="hierarchy">Hierarchical DAG</option>
              <option value="modular">Directory Columns</option>
            </select>
          </div>

          {/* Viewport & View Mode Buttons */}
          <div className="toolbar-btn-group">
            <button
              className="toolbar-icon-btn"
              onClick={() => fitView({ padding: 0.18, duration: 400 })}
              title="Fit to Viewport"
              type="button"
            >
              <span className="material-symbols-outlined">fit_screen</span>
            </button>
            <button
              className="toolbar-icon-btn"
              onClick={() => zoomIn({ duration: 300 })}
              title="Zoom In"
              type="button"
            >
              <span className="material-symbols-outlined">zoom_in</span>
            </button>
            <button
              className="toolbar-icon-btn"
              onClick={() => zoomOut({ duration: 300 })}
              title="Zoom Out"
              type="button"
            >
              <span className="material-symbols-outlined">zoom_out</span>
            </button>
            <button
              className="toolbar-icon-btn"
              onClick={() => setViewport({ x: 50, y: 50, zoom: 0.9 }, { duration: 400 })}
              title="Reset View"
              type="button"
            >
              <span className="material-symbols-outlined">restart_alt</span>
            </button>
            <button
              className={`toolbar-icon-btn ${isInspectorOpen ? "toolbar-icon-btn--active" : ""}`}
              onClick={() => setIsInspectorOpen((prev) => !prev)}
              title={isInspectorOpen ? "Hide Inspector (Expand Graph)" : "Show Inspector"}
              type="button"
            >
              <span className="material-symbols-outlined">dock_to_right</span>
            </button>
            <button
              className={`toolbar-icon-btn ${isFullscreen ? "toolbar-icon-btn--active" : ""}`}
              onClick={toggleFullscreen}
              title={isFullscreen ? "Exit Fullscreen" : "Open Fullscreen"}
              type="button"
            >
              <span className="material-symbols-outlined">
                {isFullscreen ? "fullscreen_exit" : "fullscreen"}
              </span>
            </button>
          </div>
        </div>
      </div>

      {/* Main Graph Body (Canvas + Inspector) */}
      <div className={`codegraph-body ${!isInspectorOpen ? "codegraph-body--no-inspector" : ""}`}>
        {/* Canvas */}
        <div className="codegraph-canvas">
          <ReactFlow
            nodes={rfNodes}
            edges={rfEdges}
            nodeTypes={nodeTypes}
            onNodeClick={handleNodeClick}
            onPaneClick={handlePaneClick}
            minZoom={0.2}
            maxZoom={2.0}
            defaultViewport={{ x: 50, y: 50, zoom: 0.9 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color="#27272a" gap={24} size={1} />
            <Controls showInteractive={false} className="codegraph-controls" />
            <MiniMap
              className="codegraph-minimap"
              position="bottom-right"
              nodeStrokeColor="#38bdf8"
              nodeColor="#1e293b"
              maskColor="rgba(9, 9, 11, 0.75)"
            />
          </ReactFlow>
        </div>

        {/* Node Inspector */}
        {isInspectorOpen && (
          <GraphNodeInspector
            selectedNodeId={selectedNodeId}
            graphData={graphData}
            onSelectNode={handleSelectNode}
            onClose={() => setIsInspectorOpen(false)}
          />
        )}
      </div>

      {/* Telemetry Strip */}
      <div className="codegraph-telemetry font-mono">
        <div className="telemetry-item">
          <span className="telemetry-label">TOTAL NODES</span>
          <span className="telemetry-val">{rawNodes.length}</span>
        </div>
        <div className="telemetry-divider">│</div>
        <div className="telemetry-item">
          <span className="telemetry-label">TOTAL EDGES</span>
          <span className="telemetry-val">{rawEdges.length}</span>
        </div>
        <div className="telemetry-divider">│</div>
        <div className="telemetry-item">
          <span className="telemetry-label">VISIBLE NODES</span>
          <span className="telemetry-val highlight">{filteredNodes.length}</span>
        </div>
        <div className="telemetry-divider">│</div>
        <div className="telemetry-item">
          <span className="telemetry-label">VISIBLE EDGES</span>
          <span className="telemetry-val highlight">{filteredEdges.length}</span>
        </div>
        {selectedNodeId && (
          <>
            <div className="telemetry-divider">│</div>
            <div className="telemetry-item">
              <span className="telemetry-label">SELECTED</span>
              <span className="telemetry-val selected-tag font-mono">
                {selectedNodeId}
              </span>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default function CodeGraphView(props) {
  return (
    <ReactFlowProvider>
      <CodeGraphContent {...props} />
    </ReactFlowProvider>
  );
}
