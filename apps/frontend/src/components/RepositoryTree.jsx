import { useState, useMemo } from "react";
import "./RepositoryTree.css";

function buildTree(fileList) {
  const root = { name: "root", isDir: true, children: {} };

  for (const item of fileList) {
    const parts = item.path.split("/");
    let curr = root;

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i];
      const isFile = i === parts.length - 1;

      if (isFile) {
        curr.children[part] = {
          name: part,
          path: item.path,
          isDir: false,
          role: item.role,
          nodeId: item.nodeId,
        };
      } else {
        if (!curr.children[part]) {
          curr.children[part] = {
            name: part,
            path: parts.slice(0, i + 1).join("/"),
            isDir: true,
            children: {},
          };
        }
        curr = curr.children[part];
      }
    }
  }

  return root;
}

function TreeNode({
  node,
  level = 0,
  expanded,
  onToggle,
  selectedPath,
  onSelect,
}) {
  if (node.isDir) {
    const isExpanded = !!expanded[node.path];
    const childKeys = Object.keys(node.children).sort((a, b) => {
      const childA = node.children[a];
      const childB = node.children[b];
      if (childA.isDir && !childB.isDir) return -1;
      if (!childA.isDir && childB.isDir) return 1;
      return a.localeCompare(b);
    });

    return (
      <div>
        <div
          className="tree-node-row"
          style={{ paddingLeft: `${level * 12 + 6}px` }}
          onClick={() => onToggle(node.path)}
        >
          <span
            className={`material-symbols-outlined tree-node-chevron ${
              isExpanded ? "expanded" : ""
            }`}
          >
            chevron_right
          </span>
          <span className="material-symbols-outlined tree-node-icon">
            {isExpanded ? "folder_open" : "folder"}
          </span>
          <span className="tree-node-label">{node.name}</span>
        </div>

        {isExpanded && (
          <div>
            {childKeys.map((key) => (
              <TreeNode
                key={key}
                node={node.children[key]}
                level={level + 1}
                expanded={expanded}
                onToggle={onToggle}
                selectedPath={selectedPath}
                onSelect={onSelect}
              />
            ))}
          </div>
        )}
      </div>
    );
  }

  const isSelected = selectedPath === node.path;

  return (
    <div
      className={`tree-node-row ${isSelected ? "selected" : ""}`}
      style={{ paddingLeft: `${level * 12 + 18}px` }}
      onClick={() => onSelect(node.path)}
    >
      <span className="material-symbols-outlined tree-node-icon">
        description
      </span>
      <span className="tree-node-label">{node.name}</span>
      {node.role && <span className="tree-node-badge">{node.role}</span>}
    </div>
  );
}

function RepositoryTree({
  graphData = null,
  selectedPath = null,
  onSelectFile,
}) {
  const [expanded, setExpanded] = useState({
    "": true,
    backend: true,
    frontend: true,
    src: true,
  });
  const [search, setSearch] = useState("");

  // Map file classifications
  const fileRoleMap = useMemo(() => {
    const map = {};
    const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
    for (const node of nodes) {
      if (node.id?.startsWith("architecture:")) {
        const parts = node.id.split(":");
        if (parts.length >= 3) {
          const path = parts[1];
          const role = parts[2];
          map[path] = role;
        }
      }
    }
    return map;
  }, [graphData]);

  // Extract all file nodes
  const filesList = useMemo(() => {
    const list = [];
    const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
    for (const node of nodes) {
      if (node.type?.toLowerCase() === "file") {
        const rawPath =
          node.metadata?.path ||
          node.id.replace(/^file:/, "") ||
          node.label;
        const normalized = rawPath.replace(/\\/g, "/").replace(/^\/+/, "");
        const role =
          node.architecture_role ||
          node.metadata?.role ||
          fileRoleMap[normalized] ||
          null;

        list.push({
          path: normalized,
          nodeId: node.id,
          role,
        });
      }
    }
    return list.sort((a, b) => a.path.localeCompare(b.path));
  }, [graphData, fileRoleMap]);

  // Filter files by search
  const filteredFiles = useMemo(() => {
    if (!search.trim()) return filesList;
    const q = search.toLowerCase();
    return filesList.filter(
      (f) => f.path.toLowerCase().includes(q) || (f.role && f.role.toLowerCase().includes(q)),
    );
  }, [filesList, search]);

  const treeRoot = useMemo(() => buildTree(filteredFiles), [filteredFiles]);

  // Active selected file path (fallback to first file if none selected)
  const activeSelectedPath = selectedPath || filesList[0]?.path || null;

  function toggleFolder(path) {
    setExpanded((prev) => ({
      ...prev,
      [path]: !prev[path],
    }));
  }

  // Selected file intelligence data
  const selectedFileIntel = useMemo(() => {
    if (!activeSelectedPath) return null;

    const nodes = Array.isArray(graphData?.nodes) ? graphData.nodes : [];
    const edges = Array.isArray(graphData?.edges) ? graphData.edges : [];

    const fileNode = nodes.find(
      (n) =>
        n.type?.toLowerCase() === "file" &&
        (n.metadata?.path?.replace(/\\/g, "/").replace(/^\/+/, "") === activeSelectedPath ||
          n.id === `file:${activeSelectedPath}`),
    );

    const role =
      fileNode?.architecture_role ||
      fileNode?.metadata?.role ||
      fileRoleMap[activeSelectedPath] ||
      null;

    // Symbols declared in this file
    const symbols = nodes
      .filter(
        (n) =>
          ["function", "class", "method", "variable", "constant"].includes(
            n.type?.toLowerCase(),
          ) &&
          n.metadata?.path?.replace(/\\/g, "/").replace(/^\/+/, "") === activeSelectedPath,
      )
      .map((s) => ({
        name: s.label,
        kind: s.type?.toUpperCase(),
        line: s.metadata?.line,
      }));

    // Incoming relationships (who depends on / imports this file or its symbols)
    const targetIds = new Set([
      `file:${activeSelectedPath}`,
      ...(fileNode ? [fileNode.id] : []),
    ]);

    const incoming = [];
    for (const e of edges) {
      if (targetIds.has(e.target) && e.source !== e.target) {
        const sourceLabel = e.source.replace(/^(file|symbol|architecture):/, "");
        incoming.push({
          source: sourceLabel,
          type: e.type?.toUpperCase(),
        });
      }
    }

    // Outgoing relationships (what this file imports / calls)
    const outgoing = [];
    for (const e of edges) {
      if (targetIds.has(e.source) && e.source !== e.target) {
        const targetLabel = e.target.replace(/^(file|symbol|architecture|external|unresolved):/, "");
        outgoing.push({
          target: targetLabel,
          type: e.type?.toUpperCase(),
        });
      }
    }

    return {
      name: activeSelectedPath.split("/").pop(),
      path: activeSelectedPath,
      role,
      symbols,
      incoming,
      outgoing,
    };
  }, [activeSelectedPath, graphData, fileRoleMap]);

  return (
    <div className="repo-structure-grid">
      {/* Left: Repository Tree */}
      <div className="repo-tree-card">
        <div className="repo-tree-header">
          <div className="repo-tree-title-row">
            <span className="repo-tree-title">
              <span className="material-symbols-outlined">folder_open</span>
              Repository Files
            </span>
            <span className="repo-tree-count font-mono">
              {filteredFiles.length} files
            </span>
          </div>

          <input
            type="text"
            className="repo-tree-search-input"
            placeholder="Search files by path or role..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>

        <div className="repo-tree-content">
          {Object.keys(treeRoot.children)
            .sort()
            .map((key) => (
              <TreeNode
                key={key}
                node={treeRoot.children[key]}
                level={0}
                expanded={expanded}
                onToggle={toggleFolder}
                selectedPath={activeSelectedPath}
                onSelect={(p) => onSelectFile && onSelectFile(p)}
              />
            ))}
        </div>
      </div>

      {/* Right: File Intelligence Panel */}
      <div className="file-intel-card">
        {!selectedFileIntel ? (
          <div className="file-intel-empty">
            <span className="material-symbols-outlined" style={{ fontSize: 32 }}>
              touch_app
            </span>
            <span>Select a file from the repository tree to inspect its intelligence.</span>
          </div>
        ) : (
          <>
            <div className="file-intel-header">
              <div className="file-intel-name-row">
                <span className="file-intel-name">{selectedFileIntel.name}</span>
                {selectedFileIntel.role && (
                  <span className="role-badge role-badge-component">
                    {selectedFileIntel.role}
                  </span>
                )}
              </div>
              <span className="file-intel-path">{selectedFileIntel.path}</span>
            </div>

            {/* Declared Symbols */}
            <div className="file-intel-section">
              <span className="file-intel-section-title">
                Declared Symbols ({selectedFileIntel.symbols.length})
              </span>
              {selectedFileIntel.symbols.length === 0 ? (
                <span className="text-muted font-mono" style={{ fontSize: 11 }}>
                  — (No top-level AST symbols exported)
                </span>
              ) : (
                <div className="symbol-list-wrap">
                  {selectedFileIntel.symbols.map((sym, idx) => (
                    <div className="symbol-item" key={idx}>
                      <span className="symbol-name">{sym.name}</span>
                      <span className="symbol-kind">
                        {sym.kind} {sym.line ? `· L${sym.line}` : ""}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Incoming Dependencies */}
            <div className="file-intel-section">
              <span className="file-intel-section-title">
                Incoming Dependencies ({selectedFileIntel.incoming.length})
              </span>
              {selectedFileIntel.incoming.length === 0 ? (
                <span className="text-muted font-mono" style={{ fontSize: 11 }}>
                  — (No incoming import edges detected)
                </span>
              ) : (
                <div className="dep-pills-wrap">
                  {selectedFileIntel.incoming.map((item, idx) => (
                    <span className="dep-pill" key={idx}>
                      <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                        arrow_downward
                      </span>
                      <span>{item.source}</span>
                      <span className="text-muted" style={{ fontSize: 9 }}>
                        [{item.type}]
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>

            {/* Outgoing Dependencies */}
            <div className="file-intel-section">
              <span className="file-intel-section-title">
                Outgoing Dependencies ({selectedFileIntel.outgoing.length})
              </span>
              {selectedFileIntel.outgoing.length === 0 ? (
                <span className="text-muted font-mono" style={{ fontSize: 11 }}>
                  — (No external import edges detected)
                </span>
              ) : (
                <div className="dep-pills-wrap">
                  {selectedFileIntel.outgoing.map((item, idx) => (
                    <span className="dep-pill" key={idx}>
                      <span className="material-symbols-outlined" style={{ fontSize: 12 }}>
                        arrow_upward
                      </span>
                      <span>{item.target}</span>
                      <span className="text-muted" style={{ fontSize: 9 }}>
                        [{item.type}]
                      </span>
                    </span>
                  ))}
                </div>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

export default RepositoryTree;
