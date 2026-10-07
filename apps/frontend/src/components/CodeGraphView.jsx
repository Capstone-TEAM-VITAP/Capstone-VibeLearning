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
import Blocks from "./Blocks.jsx";
import "./CodeGraphView.css";

const nodeTypes = {
  codeGraphNode: CodeGraphNode,
};

// Architecture tier priorities for swimlanes layout (top-down architectural flow)
const LAYER_ORDER = {
  ENTRYPOINT: 0,
  PRESENTATION: 1,
  ROUTING: 2,
  APPLICATION: 3,
  DOMAIN: 4,
  DATA: 5,
  INFRASTRUCTURE: 6,
  DEPENDENCIES: 7,
  SYMBOLS: 8,
  OTHER: 9,
};

function mapNodeToLayer(node) {
  const role = (node.architecture_role || node.metadata?.role || "").toUpperCase();
  const type = (node.type || "").toLowerCase();

  if (role === "ENTRYPOINT") return "ENTRYPOINT";
  if (role === "COMPONENT" || role === "HOOK") return "PRESENTATION";
  if (role === "ROUTE") return "ROUTING";
  if (role === "CONTROLLER" || role === "SERVICE" || role === "HANDLER") return "APPLICATION";
  if (role === "MODEL" || role === "ENTITY") return "DOMAIN";
  if (role === "REPOSITORY_ROLE") return "DATA";
  if (
    role === "MIDDLEWARE" ||
    role === "CONFIG" ||
    role === "UTILITY"
  ) {
    return "INFRASTRUCTURE";
  }

  if (type === "external" || type === "unresolved") return "DEPENDENCIES";
  if (["function", "class", "method", "variable", "constant"].includes(type)) {
    return "SYMBOLS";
  }

  return "OTHER";
}

// Helper to extract clean domain/module stem for grouping (e.g. auth, user, workout)
function getModuleStem(node) {
  const raw = (node.metadata?.path || (node.id.startsWith("file:") ? node.id.replace(/^file:/, "") : node.id))
    .replace(/\\/g, "/")
    .toLowerCase();
  const filename = raw.split("/").pop() || "";
  const base = filename.replace(/\.[^.]+$/, "");
  return (
    base
      .replace(/(controller|service|routes?|router|handler|model|entity|repo|repository|view|component|hook|test|spec)$/i, "")
      .replace(/[-_.]/g, "") || base
  );
}

// Sub-role priority within layers (e.g. Route -> Controller -> Service)
function getSubRolePriority(role, type) {
  const r = (role || "").toUpperCase();
  const t = (type || "").toLowerCase();
  if (r === "ENTRYPOINT") return 0;
  if (r === "COMPONENT") return 0;
  if (r === "HOOK") return 1;
  if (r === "ROUTE") return 0;
  if (r === "CONTROLLER") return 0;
  if (r === "SERVICE") return 1;
  if (r === "HANDLER") return 2;
  if (r === "MODEL") return 0;
  if (r === "ENTITY") return 1;
  if (r === "REPOSITORY_ROLE") return 0;
  if (r === "MIDDLEWARE") return 0;
  if (r === "CONFIG") return 1;
  if (r === "UTILITY") return 2;
  if (t === "function") return 0;
  if (t === "class") return 1;
  if (t === "method") return 2;
  return 5;
}

function computeLayout(nodes, edges = [], mode = "architecture") {
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

    // Build incoming and outgoing connection maps for barycentric crossing minimization
    const incomingMap = {};
    const outgoingMap = {};
    for (const e of edges) {
      if (!incomingMap[e.target]) incomingMap[e.target] = [];
      incomingMap[e.target].push(e.source);
      if (!outgoingMap[e.source]) outgoingMap[e.source] = [];
      outgoingMap[e.source].push(e.target);
    }

    // Extract unique module stems across nodes to assign consistent horizontal lanes
    const allStems = Array.from(
      new Set(nodes.map((n) => getModuleStem(n)).filter(Boolean)),
    ).sort();
    const stemLaneIndex = {};
    allStems.forEach((stem, idx) => {
      stemLaneIndex[stem] = idx;
    });

    let currentY = 50;
    const MAX_COLS_PER_TIER = Math.max(4, Math.min(6, allStems.length || 4));
    const X_SPACING = 300;
    const Y_ROW_SPACING = 125;
    const Y_TIER_GAP = 95;

    for (const [, group] of Object.entries(buckets)) {
      if (group.length === 0) continue;

      // Sort nodes within tier to minimize edge crossings:
      // Priority 1: Average X of upstream connected nodes (barycentric heuristic)
      // Priority 2: Average X of downstream connected nodes
      // Priority 3: Module stem alignment (e.g. auth, user, workout in matching lane)
      // Priority 4: Sub-role order (e.g. ROUTE before CONTROLLER before SERVICE)
      group.sort((a, b) => {
        const aIncoming = incomingMap[a.id] || [];
        const bIncoming = incomingMap[b.id] || [];

        const getConnectedX = (ids) => {
          let sum = 0, count = 0;
          for (const id of ids) {
            if (positions[id]) {
              sum += positions[id].x;
              count++;
            }
          }
          return count > 0 ? sum / count : null;
        };

        const aInX = getConnectedX(aIncoming);
        const bInX = getConnectedX(bIncoming);

        if (aInX !== null && bInX !== null && Math.abs(aInX - bInX) > 15) {
          return aInX - bInX;
        }
        if (aInX !== null && bInX === null) return -1;
        if (aInX === null && bInX !== null) return 1;

        // Try outgoing targets if neither has incoming placed
        const aOutX = getConnectedX(outgoingMap[a.id] || []);
        const bOutX = getConnectedX(outgoingMap[b.id] || []);
        if (aOutX !== null && bOutX !== null && Math.abs(aOutX - bOutX) > 15) {
          return aOutX - bOutX;
        }
        if (aOutX !== null && bOutX === null) return -1;
        if (aOutX === null && bOutX !== null) return 1;

        // Module stem lane priority
        const aStem = getModuleStem(a);
        const bStem = getModuleStem(b);
        const aLane = stemLaneIndex[aStem] ?? 99;
        const bLane = stemLaneIndex[bStem] ?? 99;
        if (aLane !== bLane) return aLane - bLane;

        // Sub-role priority within layer (e.g. Route -> Controller -> Service)
        const aRole = getSubRolePriority(a.architecture_role || a.metadata?.role, a.type);
        const bRole = getSubRolePriority(b.architecture_role || b.metadata?.role, b.type);
        if (aRole !== bRole) return aRole - bRole;

        return (a.label || a.id).localeCompare(b.label || b.id);
      });

      const numRows = Math.ceil(group.length / MAX_COLS_PER_TIER);

      group.forEach((node, idx) => {
        const row = Math.floor(idx / MAX_COLS_PER_TIER);
        const col = idx % MAX_COLS_PER_TIER;

        const itemsInThisRow =
          row === numRows - 1 && group.length % MAX_COLS_PER_TIER !== 0
            ? group.length % MAX_COLS_PER_TIER
            : Math.min(group.length, MAX_COLS_PER_TIER);

        const rowWidth = (itemsInThisRow - 1) * X_SPACING;
        const startX = Math.max(60, (1150 - rowWidth) / 2);

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

    let colX = 60;
    const COL_WIDTH = 300;
    const ROW_HEIGHT = 125;

    for (const [, group] of Object.entries(dirBuckets)) {
      // Sort nodes in directory column by architectural layer so each directory flows logically
      group.sort((a, b) => {
        const aLayer = LAYER_ORDER[mapNodeToLayer(a)] ?? 99;
        const bLayer = LAYER_ORDER[mapNodeToLayer(b)] ?? 99;
        if (aLayer !== bLayer) return aLayer - bLayer;
        return (a.label || a.id).localeCompare(b.label || b.id);
      });

      group.forEach((node, rowIdx) => {
        positions[node.id] = {
          x: colX,
          y: 60 + rowIdx * ROW_HEIGHT,
        };
      });
      colX += COL_WIDTH;
    }
  } else {
    // Hierarchical DAG: Topological layer grouping via in-degree
    const inDegree = {};
    for (const n of nodes) inDegree[n.id] = 0;
    for (const e of edges) {
      if (inDegree[e.target] !== undefined) inDegree[e.target]++;
    }

    // Assign topological rank (0 = sources/roots, 1, 2...)
    const rankMap = {};
    const queue = [];
    for (const n of nodes) {
      if ((inDegree[n.id] || 0) === 0) {
        rankMap[n.id] = 0;
        queue.push(n.id);
      }
    }

    while (queue.length > 0) {
      const u = queue.shift();
      const currentRank = rankMap[u] || 0;
      for (const e of edges) {
        if (e.source === u) {
          const nextRank = Math.max(rankMap[e.target] || 0, currentRank + 1);
          rankMap[e.target] = nextRank;
        }
      }
    }

    // Group nodes by rank
    const rankBuckets = {};
    for (const n of nodes) {
      const r = rankMap[n.id] || 0;
      if (!rankBuckets[r]) rankBuckets[r] = [];
      rankBuckets[r].push(n);
    }

    const X_GAP = 300;
    const Y_GAP = 130;
    let currentY = 60;

    for (const [, group] of Object.entries(rankBuckets)) {
      group.sort((a, b) => {
        const aStem = getModuleStem(a);
        const bStem = getModuleStem(b);
        if (aStem !== bStem) return aStem.localeCompare(bStem);
        return (a.label || a.id).localeCompare(b.label || b.id);
      });

      const totalWidth = (group.length - 1) * X_GAP;
      const startX = Math.max(60, (1150 - totalWidth) / 2);

      group.forEach((node, colIdx) => {
        positions[node.id] = {
          x: Math.round(startX + colIdx * X_GAP),
          y: currentY,
        };
      });

      currentY += Y_GAP;
    }
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
  const [hoveredNodeId, setHoveredNodeId] = useState(null);
  const [hoveredEdgeId, setHoveredEdgeId] = useState(null);
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

  // Theme listener for graph canvas adaptation
  const [currentTheme, setCurrentTheme] = useState(() => {
    if (typeof document !== "undefined") {
      return document.documentElement.getAttribute("data-theme") || "dark";
    }
    return "dark";
  });

  useEffect(() => {
    const handleTheme = (e) => {
      if (e.detail?.theme) {
        setCurrentTheme(e.detail.theme);
      }
    };
    window.addEventListener("codeai-theme-change", handleTheme);
    return () => window.removeEventListener("codeai-theme-change", handleTheme);
  }, []);

  const isLight = currentTheme === "light";

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

  // Active focus node: hovered node takes precedence for immediate feedback, falling back to selected node
  const activeFocusNodeId = hoveredNodeId || selectedNodeId;

  // Direct neighbors of active focus node or hovered edge
  const activeFocusNeighbors = useMemo(() => {
    if (!activeFocusNodeId && !hoveredEdgeId) return null;
    const neighbors = new Set();
    if (activeFocusNodeId) {
      neighbors.add(activeFocusNodeId);
      for (const e of rawEdges) {
        if (e.source === activeFocusNodeId) neighbors.add(e.target);
        if (e.target === activeFocusNodeId) neighbors.add(e.source);
      }
    }
    if (hoveredEdgeId) {
      const edge = rawEdges.find((e) => e.id === hoveredEdgeId);
      if (edge) {
        neighbors.add(edge.source);
        neighbors.add(edge.target);
      }
    }
    return neighbors;
  }, [activeFocusNodeId, hoveredEdgeId, rawEdges]);

  // Compute layout positions for nodes
  const layoutedNodes = useMemo(() => {
    return computeLayout(filteredNodes, filteredEdges, layoutMode);
  }, [filteredNodes, filteredEdges, layoutMode]);

  // Transform to React Flow Nodes
  const rfNodes = useMemo(() => {
    return layoutedNodes.map((n) => {
      const isSelected = n.id === selectedNodeId;
      const isHovered = n.id === hoveredNodeId;
      const isHighlighted = activeFocusNeighbors ? activeFocusNeighbors.has(n.id) : false;
      const isDimmed = activeFocusNeighbors ? !activeFocusNeighbors.has(n.id) : false;

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
          isHovered,
          isHighlighted,
          isDimmed,
        },
      };
    });
  }, [layoutedNodes, selectedNodeId, hoveredNodeId, activeFocusNeighbors]);

  // Transform to React Flow Edges with Noise-Reduction & Low-Opacity Default
  const rfEdges = useMemo(() => {
    return filteredEdges.map((e) => {
      const isConnectedToFocus =
        activeFocusNodeId &&
        (e.source === activeFocusNodeId || e.target === activeFocusNodeId);
      const isEdgeHovered = hoveredEdgeId === e.id;
      const isHighlighted = isConnectedToFocus || isEdgeHovered;
      const isDimmed = Boolean(activeFocusNodeId || hoveredEdgeId) && !isHighlighted;

      const typeUpper = (e.type || "DEPENDS_ON").toUpperCase();

      // Semantic highlight colors (vibrant and prominent only when focused)
      let highlightColor = isLight ? "#BC6C25" : "#38bdf8";
      let strokeDash = undefined;

      if (typeUpper === "IMPORTS") {
        highlightColor = isLight ? "#BC6C25" : "#818cf8";
      } else if (typeUpper === "CALLS") {
        highlightColor = isLight ? "#386641" : "#38bdf8";
        strokeDash = "5,5";
      } else if (typeUpper === "DEPENDS_ON") {
        highlightColor = isLight ? "#283618" : "#2dd4bf";
        strokeDash = "4,4";
      } else if (typeUpper === "CONTAINS") {
        highlightColor = isLight ? "#7E8B54" : "#94a3b8";
        strokeDash = "2,3";
      } else if (typeUpper === "CLASSIFIED_AS") {
        highlightColor = isLight ? "#9B4811" : "#c084fc";
      }

      // Default neutral low-opacity trace (reduces visual noise)
      const neutralColor = isLight
        ? "rgba(126, 139, 84, 0.28)"
        : "rgba(148, 163, 184, 0.20)";

      let strokeColor = neutralColor;
      let strokeWidth = 1.0;
      let opacity = isLight ? 0.24 : 0.20;
      let zIndex = 2;
      let animated = false;

      // Small subtle arrowhead on default edges to avoid visual clutter
      let markerEnd = {
        type: MarkerType.ArrowClosed,
        color: neutralColor,
        width: 7,
        height: 7,
      };

      if (isHighlighted) {
        strokeColor = highlightColor;
        strokeWidth = 2.4;
        opacity = 1.0;
        zIndex = 30;
        animated = true;
        markerEnd = {
          type: MarkerType.ArrowClosed,
          color: highlightColor,
          width: 14,
          height: 14,
        };
      } else if (isDimmed) {
        strokeColor = isLight
          ? "rgba(212, 163, 115, 0.12)"
          : "rgba(100, 116, 139, 0.08)";
        strokeWidth = 0.75;
        opacity = 0.05;
        zIndex = 1;
        markerEnd = undefined;
      }

      return {
        id: e.id,
        source: e.source,
        target: e.target,
        type: "default",
        animated,
        markerEnd,
        style: {
          stroke: strokeColor,
          strokeWidth,
          strokeDasharray: isHighlighted ? strokeDash : undefined,
          opacity,
          transition: "stroke 0.2s ease, stroke-width 0.2s ease, opacity 0.2s ease",
        },
        zIndex,
      };
    });
  }, [filteredEdges, activeFocusNodeId, hoveredEdgeId, isLight]);

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
    setHoveredNodeId(null);
    setHoveredEdgeId(null);
  }, []);

  const handleNodeMouseEnter = useCallback((_, node) => {
    setHoveredNodeId(node.id);
  }, []);

  const handleNodeMouseLeave = useCallback(() => {
    setHoveredNodeId(null);
  }, []);

  const handleEdgeMouseEnter = useCallback((_, edge) => {
    setHoveredEdgeId(edge.id);
  }, []);

  const handleEdgeMouseLeave = useCallback(() => {
    setHoveredEdgeId(null);
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
        <Blocks size={48} className="codegraph-loading-blocks" />
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
            onNodeMouseEnter={handleNodeMouseEnter}
            onNodeMouseLeave={handleNodeMouseLeave}
            onEdgeMouseEnter={handleEdgeMouseEnter}
            onEdgeMouseLeave={handleEdgeMouseLeave}
            onPaneClick={handlePaneClick}
            minZoom={0.2}
            maxZoom={2.0}
            defaultViewport={{ x: 50, y: 50, zoom: 0.9 }}
            proOptions={{ hideAttribution: true }}
          >
            <Background color={isLight ? "rgba(212, 163, 115, 0.45)" : "#27272a"} gap={24} size={1} />
            <Controls showInteractive={false} className="codegraph-controls" />
            <MiniMap
              className="codegraph-minimap"
              position="bottom-right"
              nodeStrokeColor={isLight ? "#BC6C25" : "#38bdf8"}
              nodeColor={isLight ? "#FAEDCD" : "#1e293b"}
              maskColor={isLight ? "rgba(233, 237, 201, 0.75)" : "rgba(9, 9, 11, 0.75)"}
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
