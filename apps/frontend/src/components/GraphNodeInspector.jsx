import { useMemo } from "react";
import "./GraphNodeInspector.css";

export default function GraphNodeInspector({
  selectedNodeId,
  graphData,
  onSelectNode,
  onClose,
}) {
  const nodes = useMemo(
    () => (Array.isArray(graphData?.nodes) ? graphData.nodes : []),
    [graphData],
  );
  const edges = useMemo(
    () => (Array.isArray(graphData?.edges) ? graphData.edges : []),
    [graphData],
  );

  const node = useMemo(() => {
    if (!selectedNodeId) return null;
    return nodes.find((n) => n.id === selectedNodeId) || null;
  }, [selectedNodeId, nodes]);

  // Contained symbols if this is a file node
  const containedSymbols = useMemo(() => {
    if (!node || node.type?.toLowerCase() !== "file") return [];
    const filePath =
      node.metadata?.path?.replace(/\\/g, "/").replace(/^\/+/, "") ||
      node.id.replace(/^file:/, "");

    return nodes
      .filter(
        (n) =>
          ["function", "class", "method", "variable", "constant"].includes(
            n.type?.toLowerCase(),
          ) &&
          n.metadata?.path?.replace(/\\/g, "/").replace(/^\/+/, "") === filePath,
      )
      .map((s) => ({
        id: s.id,
        name: s.label || s.id,
        type: s.type?.toUpperCase(),
        line: s.metadata?.line,
      }));
  }, [node, nodes]);

  // Incoming relationships (who points to this node)
  const incoming = useMemo(() => {
    if (!node) return [];
    const list = [];
    for (const e of edges) {
      if (e.target === node.id && e.source !== node.id) {
        const sourceNode = nodes.find((n) => n.id === e.source);
        list.push({
          edgeId: e.id,
          sourceId: e.source,
          sourceName:
            sourceNode?.label ||
            e.source.replace(/^(file|symbol|architecture|external|unresolved):/, ""),
          sourceType: sourceNode?.type?.toUpperCase() || "UNKNOWN",
          edgeType: e.type?.toUpperCase() || "DEPENDS_ON",
        });
      }
    }
    return list;
  }, [node, edges, nodes]);

  // Outgoing relationships (what this node points to)
  const outgoing = useMemo(() => {
    if (!node) return [];
    const list = [];
    for (const e of edges) {
      if (e.source === node.id && e.target !== node.id) {
        const targetNode = nodes.find((n) => n.id === e.target);
        list.push({
          edgeId: e.id,
          targetId: e.target,
          targetName:
            targetNode?.label ||
            e.target.replace(/^(file|symbol|architecture|external|unresolved):/, ""),
          targetType: targetNode?.type?.toUpperCase() || "UNKNOWN",
          edgeType: e.type?.toUpperCase() || "DEPENDS_ON",
        });
      }
    }
    return list;
  }, [node, edges, nodes]);

  if (!node) {
    return (
      <aside className="graph-inspector graph-inspector--empty" aria-label="Node Inspector">
        <div className="inspector-placeholder-header">
          <span className="inspector-placeholder-tag font-mono">NODE INSPECTOR</span>
          <button
            type="button"
            className="inspector-close-btn"
            onClick={onClose}
            title="Close Inspector"
          >
            <span className="material-symbols-outlined">close</span>
          </button>
        </div>
        <div className="inspector-placeholder">
          <span className="material-symbols-outlined inspector-placeholder-icon">
            touch_app
          </span>
          <div className="inspector-placeholder-title">Select a node to inspect</div>
          <div className="inspector-placeholder-desc">
            Click any node or relationship in the graph canvas to inspect its
            structural details, AST symbols, and dependencies.
          </div>
          <button
            type="button"
            className="inspector-placeholder-close-btn"
            onClick={onClose}
          >
            <span className="material-symbols-outlined">dock_to_right</span>
            Hide Inspector
          </button>
        </div>
      </aside>
    );
  }

  const role = node.architecture_role || node.metadata?.role || null;
  const path =
    node.metadata?.path?.replace(/\\/g, "/") ||
    (node.id.startsWith("file:") ? node.id.replace(/^file:/, "") : null);
  const line = node.metadata?.line ?? null;
  const nodeType = node.type?.toUpperCase() || "NODE";

  function copyPath() {
    if (path) {
      navigator.clipboard.writeText(path);
    }
  }

  function getNodeIcon(type, r) {
    if (r) {
      switch (r.toUpperCase()) {
        case "CONTROLLER":
          return "tune";
        case "SERVICE":
          return "build_circle";
        case "MODEL":
        case "ENTITY":
          return "database";
        case "COMPONENT":
          return "widgets";
        case "HOOK":
          return "anchor";
        case "ROUTE":
          return "alt_route";
        case "MIDDLEWARE":
          return "security";
        case "UTILITY":
          return "construction";
        case "ENTRYPOINT":
          return "play_arrow";
        default:
          break;
      }
    }
    switch (type.toLowerCase()) {
      case "file":
        return "description";
      case "function":
        return "code";
      case "class":
        return "category";
      case "method":
        return "data_object";
      case "variable":
      case "constant":
        return "tag";
      case "external":
        return "output";
      case "unresolved":
        return "warning";
      case "repository":
        return "folder_special";
      default:
        return "hub";
    }
  }

  return (
    <aside className="graph-inspector" aria-label="Node Inspector">
      {/* Header */}
      <div className="inspector-header">
        <div className="inspector-title-group">
          <span className="material-symbols-outlined inspector-node-icon">
            {getNodeIcon(node.type, role)}
          </span>
          <div className="inspector-title-text">
            <span className="inspector-eyebrow font-mono">{nodeType}</span>
            <h3 className="inspector-node-name font-mono" title={node.label || node.id}>
              {node.label || node.id}
            </h3>
          </div>
        </div>
        <button
          className="inspector-close-btn"
          onClick={onClose}
          title="Close Inspector"
          type="button"
        >
          <span className="material-symbols-outlined">close</span>
        </button>
      </div>

      {/* Badges */}
      <div className="inspector-badges">
        <span className={`inspector-badge badge-type-${node.type?.toLowerCase()}`}>
          {nodeType}
        </span>
        {role && (
          <span className="inspector-badge badge-role font-mono">
            {role.toUpperCase()}
          </span>
        )}
      </div>

      {/* Metadata Attributes */}
      <div className="inspector-section">
        <div className="inspector-section-label">IDENTIFIER & LOCATION</div>
        <div className="inspector-meta-list">
          <div className="inspector-meta-item">
            <span className="inspector-meta-key">ID</span>
            <span className="inspector-meta-val font-mono" title={node.id}>
              {node.id}
            </span>
          </div>
          {path && (
            <div className="inspector-meta-item">
              <span className="inspector-meta-key">Path</span>
              <div className="inspector-path-wrap">
                <span className="inspector-meta-val font-mono" title={path}>
                  {path}
                </span>
                <button
                  className="inspector-copy-btn"
                  onClick={copyPath}
                  title="Copy path"
                  type="button"
                >
                  <span className="material-symbols-outlined">content_copy</span>
                </button>
              </div>
            </div>
          )}
          {line !== null && (
            <div className="inspector-meta-item">
              <span className="inspector-meta-key">Line</span>
              <span className="inspector-meta-val font-mono">Line {line}</span>
            </div>
          )}
          {node.metadata?.kind && (
            <div className="inspector-meta-item">
              <span className="inspector-meta-key">Kind</span>
              <span className="inspector-meta-val font-mono">
                {node.metadata.kind}
              </span>
            </div>
          )}
          {node.metadata?.module && (
            <div className="inspector-meta-item">
              <span className="inspector-meta-key">Module</span>
              <span className="inspector-meta-val font-mono">
                {node.metadata.module}
              </span>
            </div>
          )}
        </div>
      </div>

      {/* Contained Symbols (for file nodes) */}
      {containedSymbols.length > 0 && (
        <div className="inspector-section">
          <div className="inspector-section-header">
            <span className="inspector-section-label">
              CONTAINED SYMBOLS ({containedSymbols.length})
            </span>
          </div>
          <div className="inspector-link-list">
            {containedSymbols.map((sym) => (
              <button
                key={sym.id}
                className="inspector-link-row"
                onClick={() => onSelectNode(sym.id)}
                type="button"
              >
                <div className="inspector-link-info">
                  <span className="inspector-link-badge font-mono">
                    {sym.type.slice(0, 3)}
                  </span>
                  <span className="inspector-link-name font-mono">{sym.name}</span>
                </div>
                {sym.line !== undefined && (
                  <span className="inspector-link-extra font-mono">L{sym.line}</span>
                )}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* Incoming Relationships */}
      <div className="inspector-section">
        <div className="inspector-section-header">
          <span className="inspector-section-label">
            INCOMING RELATIONSHIPS ({incoming.length})
          </span>
        </div>
        {incoming.length === 0 ? (
          <div className="inspector-empty font-mono">— None detected —</div>
        ) : (
          <div className="inspector-link-list">
            {incoming.map((rel, idx) => (
              <button
                key={`${rel.edgeId}-${idx}`}
                className="inspector-link-row"
                onClick={() => onSelectNode(rel.sourceId)}
                type="button"
              >
                <div className="inspector-link-info">
                  <span className="inspector-edge-tag font-mono">
                    {rel.edgeType}
                  </span>
                  <span className="inspector-link-name font-mono" title={rel.sourceName}>
                    {rel.sourceName}
                  </span>
                </div>
                <span className="material-symbols-outlined inspector-nav-arrow">
                  chevron_right
                </span>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Outgoing Relationships */}
      <div className="inspector-section">
        <div className="inspector-section-header">
          <span className="inspector-section-label">
            OUTGOING RELATIONSHIPS ({outgoing.length})
          </span>
        </div>
        {outgoing.length === 0 ? (
          <div className="inspector-empty font-mono">— None detected —</div>
        ) : (
          <div className="inspector-link-list">
            {outgoing.map((rel, idx) => (
              <button
                key={`${rel.edgeId}-${idx}`}
                className="inspector-link-row"
                onClick={() => onSelectNode(rel.targetId)}
                type="button"
              >
                <div className="inspector-link-info">
                  <span className="inspector-edge-tag font-mono">
                    {rel.edgeType}
                  </span>
                  <span className="inspector-link-name font-mono" title={rel.targetName}>
                    {rel.targetName}
                  </span>
                </div>
                <span className="material-symbols-outlined inspector-nav-arrow">
                  chevron_right
                </span>
              </button>
            ))}
          </div>
        )}
      </div>
    </aside>
  );
}
