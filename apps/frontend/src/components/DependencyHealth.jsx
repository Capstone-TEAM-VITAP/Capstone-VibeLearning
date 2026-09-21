import { useMemo } from "react";
import "./DependencyHealth.css";

function detectCycles(adj) {
  const visited = new Set();
  const recStack = new Set();
  let cycleCount = 0;

  function dfs(node) {
    visited.add(node);
    recStack.add(node);

    const neighbors = adj[node] || [];
    for (const neighbor of neighbors) {
      if (!visited.has(neighbor)) {
        dfs(neighbor);
      } else if (recStack.has(neighbor)) {
        cycleCount++;
      }
    }

    recStack.delete(node);
  }

  for (const node of Object.keys(adj)) {
    if (!visited.has(node)) {
      dfs(node);
    }
  }

  return cycleCount;
}

function DependencyHealth({ graphData = null }) {
  const hasData = graphData !== null && graphData?.schema_version === "1.0";

  const stats = useMemo(() => {
    if (!hasData) return null;

    const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
    const edges = Array.isArray(graphData?.edges) ? graphData.edges : [];

    const externalCount = nodes.filter(
      (n) => n.type?.toLowerCase() === "external" || n.id?.startsWith("external:"),
    ).length;

    const unresolvedCount = nodes.filter(
      (n) => n.type?.toLowerCase() === "unresolved" || n.id?.startsWith("unresolved:"),
    ).length;

    const internalEdges = edges.filter(
      (e) =>
        !e.target?.startsWith("external:") &&
        !e.target?.startsWith("unresolved:") &&
        e.type?.toLowerCase() !== "classified_as",
    );

    // Degree for each file node
    const degreeMap = {};
    const adj = {};

    for (const node of nodes) {
      if (node.type?.toLowerCase() === "file") {
        degreeMap[node.id] = 0;
        adj[node.id] = [];
      }
    }

    for (const edge of edges) {
      if (degreeMap[edge.source] !== undefined) {
        degreeMap[edge.source]++;
      }
      if (degreeMap[edge.target] !== undefined) {
        degreeMap[edge.target]++;
      }
      if (adj[edge.source] && degreeMap[edge.target] !== undefined) {
        adj[edge.source].push(edge.target);
      }
    }

    const isolatedNodesCount = Object.values(degreeMap).filter((d) => d === 0).length;
    const cyclesCount = detectCycles(adj);

    const topConnected = Object.entries(degreeMap)
      .map(([id, deg]) => {
        const fileNode = nodes.find((n) => n.id === id);
        const path =
          fileNode?.metadata?.path ||
          id.replace(/^file:/, "") ||
          fileNode?.label ||
          id;
        return {
          path: path.replace(/\\/g, "/").replace(/^\/+/, ""),
          degree: deg,
        };
      })
      .filter((item) => item.degree > 0)
      .sort((a, b) => b.degree - a.degree)
      .slice(0, 5);

    return {
      externalCount,
      unresolvedCount,
      internalEdgesCount: internalEdges.length,
      isolatedNodesCount,
      cyclesCount,
      topConnected,
    };
  }, [graphData, hasData]);

  if (!hasData) return null;

  return (
    <div className="dep-health-grid">
      {/* Dependency Overview */}
      <div className="dep-health-card">
        <div className="dep-health-header">
          <span className="dep-health-title">
            <span className="material-symbols-outlined">lan</span>
            Dependency Overview
          </span>
          <span className="dep-health-badge font-mono">
            Deterministic Graph IR
          </span>
        </div>

        <div className="health-facts-list">
          <div className="health-fact-item">
            <span className="health-fact-label">Internal dependencies:</span>
            <span className="health-fact-value">
              {stats?.internalEdgesCount ?? "—"}
            </span>
          </div>

          <div className="health-fact-item">
            <span className="health-fact-label">External modules:</span>
            <span className="health-fact-value">
              {stats?.externalCount ?? "—"}
            </span>
          </div>

          <div className="health-fact-item">
            <span className="health-fact-label">Unresolved modules:</span>
            <span
              className={`health-fact-value ${
                stats?.unresolvedCount === 0 ? "clean" : "notice"
              }`}
            >
              {stats?.unresolvedCount ?? "—"}
            </span>
          </div>
        </div>

        {stats?.topConnected && stats.topConnected.length > 0 && (
          <div style={{ marginTop: 6 }}>
            <span
              className="font-mono text-muted"
              style={{ fontSize: 11, display: "block", marginBottom: 6 }}
            >
              Most connected modules (in + out degree):
            </span>
            <div className="connected-modules-list">
              {stats.topConnected.map((mod) => (
                <div className="connected-module-item" key={mod.path}>
                  <span className="connected-module-path">{mod.path}</span>
                  <span className="connected-module-degree">
                    {mod.degree} edges
                  </span>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Structural Health */}
      <div className="dep-health-card">
        <div className="dep-health-header">
          <span className="dep-health-title">
            <span className="material-symbols-outlined">health_and_safety</span>
            Architecture Health Facts
          </span>
          <span className="dep-health-badge font-mono">
            Static AST Facts
          </span>
        </div>

        <div className="health-facts-list">
          <div className="health-fact-item">
            <span className="health-fact-label">Circular dependencies:</span>
            <span
              className={`health-fact-value ${
                stats?.cyclesCount === 0 ? "clean" : "notice"
              }`}
            >
              {stats
                ? stats.cyclesCount === 0
                  ? "None detected (clean)"
                  : `${stats.cyclesCount} cycles detected`
                : "Not available"}
            </span>
          </div>

          <div className="health-fact-item">
            <span className="health-fact-label">Unresolved imports:</span>
            <span
              className={`health-fact-value ${
                stats?.unresolvedCount === 0 ? "clean" : "notice"
              }`}
            >
              {stats
                ? stats.unresolvedCount === 0
                  ? "0 (all resolved)"
                  : stats.unresolvedCount
                : "Not available"}
            </span>
          </div>

          <div className="health-fact-item">
            <span className="health-fact-label">External dependencies:</span>
            <span className="health-fact-value">
              {stats ? `${stats.externalCount} packages` : "Not available"}
            </span>
          </div>

          <div className="health-fact-item">
            <span className="health-fact-label">Isolated files:</span>
            <span
              className={`health-fact-value ${
                stats?.isolatedNodesCount === 0 ? "clean" : ""
              }`}
            >
              {stats ? `${stats.isolatedNodesCount} files` : "Not available"}
            </span>
          </div>
        </div>

        <div style={{ marginTop: 4 }}>
          <p
            className="font-mono text-muted"
            style={{ fontSize: 10, lineHeight: 1.4, margin: 0 }}
          >
            * All structural indicators are calculated deterministically from static analysis AST Graph IR 1.0. No fabricated scores or subjective percentages.
          </p>
        </div>
      </div>
    </div>
  );
}

export default DependencyHealth;
