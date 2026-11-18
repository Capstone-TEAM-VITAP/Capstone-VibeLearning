import { useMemo, useState } from "react";
import { ChevronRight, FileCode2, Folder, FolderOpen, Search } from "lucide-react";
import { buildStructure, formatBytes, mainRole } from "../utils/structureStats.js";
import "./RepositoryTree.css";

const KIND_ORDER = ["class", "function", "method", "constant", "variable"];

function sortChildren(dir, sortBy) {
  return [...dir.children.values()].sort((a, b) => {
    if (a.isDir !== b.isDir) return a.isDir ? -1 : 1;
    if (sortBy === "name") return a.name.localeCompare(b.name);
    const av = a.isDir ? a.files : a.importers.size;
    const bv = b.isDir ? b.files : b.importers.size;
    return bv - av || a.name.localeCompare(b.name);
  });
}

function matches(node, q) {
  if (!q) return true;
  if (!node.isDir) return node.path.toLowerCase().includes(q) || (node.role || "").includes(q);
  for (const c of node.children.values()) if (matches(c, q)) return true;
  return false;
}

function Rows({ dir, depth, ctx }) {
  const { expanded, toggle, sortBy, query, selectedPath, onSelect, hubThreshold, rootFiles } = ctx;
  return sortChildren(dir, sortBy)
    .filter((child) => matches(child, query))
    .map((child) => {
      const pad = { paddingLeft: `${8 + depth * 16}px` };
      if (child.isDir) {
        const open = query ? true : expanded.has(child.path);
        const role = mainRole(child);
        const share = child.files / Math.max(rootFiles, 1);
        return (
          <FragmentRows key={child.path}>
            <tr className="st-row st-row--dir" onClick={() => toggle(child.path)}>
              <td>
                <button
                  type="button"
                  className="st-name"
                  style={pad}
                  aria-expanded={open}
                  onClick={(e) => {
                    e.stopPropagation();
                    toggle(child.path);
                  }}
                >
                  <ChevronRight size={13} className={`st-chev ${open ? "open" : ""}`} />
                  {open ? <FolderOpen size={14} /> : <Folder size={14} />}
                  <span className="st-label">{child.name}</span>
                </button>
              </td>
              <td className="num">
                <span className="st-files">
                  <span className="st-bar" title={`${Math.round(share * 100)}% of all files`}>
                    <i style={{ width: `${Math.max(share * 100, 2)}%` }} />
                  </span>
                  {child.files}
                </span>
              </td>
              <td className="num">{child.symbols || "—"}</td>
              <td className="num">{child.importers || "—"}</td>
              <td className="num">{child.deps || "—"}</td>
              <td className="st-role">
                {role ? (
                  <>
                    {role.role} <span className="st-dim">{Math.round(role.share * 100)}%</span>
                  </>
                ) : (
                  <span className="st-dim">—</span>
                )}
              </td>
            </tr>
            {open && <Rows dir={child} depth={depth + 1} ctx={ctx} />}
          </FragmentRows>
        );
      }

      const isHub = child.importers.size >= hubThreshold;
      const selected = selectedPath === child.path;
      return (
        <tr
          key={child.path}
          className={`st-row st-row--file ${selected ? "selected" : ""}`}
          onClick={() => onSelect(child.path)}
        >
          <td>
            <button type="button" className="st-name" style={pad} onClick={() => onSelect(child.path)}>
              <span className="st-chev-spacer" />
              <FileCode2 size={14} />
              <span className="st-label">{child.name}</span>
              {isHub && <span className="st-hub" title={`Imported by ${child.importers.size} files`}>hub</span>}
            </button>
          </td>
          <td className="num st-dim">{child.language || ""}</td>
          <td className="num">{child.symbols.length || "—"}</td>
          <td className={`num ${isHub ? "st-strong" : ""}`}>{child.importers.size || "—"}</td>
          <td className="num">{child.fileDeps.size + child.packages.size || "—"}</td>
          <td className="st-role">{child.role || <span className="st-dim">unclassified</span>}</td>
        </tr>
      );
    });
}

function FragmentRows({ children }) {
  return <>{children}</>;
}

function RepositoryTree({ graphData = null, selectedPath = null, onSelectFile }) {
  const structure = useMemo(() => buildStructure(graphData), [graphData]);
  const { root, files, insights, hubThreshold } = structure;

  const [expanded, setExpanded] = useState(() => {
    // Open the top two folder levels so the shape is visible right away
    const open = new Set();
    for (const c of root.children.values()) {
      if (!c.isDir) continue;
      open.add(c.path);
      for (const g of c.children.values()) if (g.isDir && c.children.size <= 6) open.add(g.path);
    }
    return open;
  });
  const [sortBy, setSortBy] = useState("size");
  const [search, setSearch] = useState("");

  const fallback = insights.topHub?.path || [...files.keys()][0] || null;
  const activePath = selectedPath && files.has(selectedPath) ? selectedPath : fallback;
  const file = activePath ? files.get(activePath) : null;

  const toggle = (path) =>
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  const onSelect = (p) => onSelectFile && onSelectFile(p);

  const symbolsByKind = useMemo(() => {
    if (!file) return [];
    const groups = new Map();
    for (const s of file.symbols) {
      if (!groups.has(s.kind)) groups.set(s.kind, []);
      groups.get(s.kind).push(s);
    }
    return [...groups.entries()]
      .sort((a, b) => KIND_ORDER.indexOf(a[0]) - KIND_ORDER.indexOf(b[0]))
      .map(([kind, list]) => [kind, list.sort((a, b) => (a.line || 0) - (b.line || 0))]);
  }, [file]);

  const ctx = {
    expanded,
    toggle,
    sortBy,
    query: search.trim().toLowerCase(),
    selectedPath: activePath,
    onSelect,
    hubThreshold,
    rootFiles: insights.totalFiles,
  };

  return (
    <div className="st-wrap">
      {/* Headline insights */}
      <div className="st-insights">
        {insights.biggestArea && (
          <div className="st-insight">
            <span className="st-insight-k">Biggest area</span>
            <span className="st-insight-v">
              <code>{insights.biggestArea.path}</code>
            </span>
            <span className="st-insight-s">
              {insights.biggestArea.files} files · {Math.round(insights.biggestArea.share * 100)}% of the repo
            </span>
          </div>
        )}
        {insights.topHub && (
          <button type="button" className="st-insight st-insight--link" onClick={() => onSelect(insights.topHub.path)}>
            <span className="st-insight-k">Most depended-on file</span>
            <span className="st-insight-v">
              <code>{insights.topHub.path.split("/").pop()}</code>
            </span>
            <span className="st-insight-s">imported by {insights.topHub.importers} files</span>
          </button>
        )}
        <div className="st-insight">
          <span className="st-insight-k">Not imported anywhere</span>
          <span className="st-insight-v st-num">{insights.notImported}</span>
          <span className="st-insight-s">code files, excluding entry points, tests and config</span>
        </div>
        <div className="st-insight">
          <span className="st-insight-k">Unclassified</span>
          <span className="st-insight-v st-num">{insights.unclassified}</span>
          <span className="st-insight-s">of {insights.totalFiles} files have no architecture role</span>
        </div>
      </div>

      <div className="st-grid">
        {/* Structure table */}
        <section className="console-card st-table-card">
          <div className="console-card-head">
            <h2 className="console-card-title">
              Structure <small>{insights.totalFiles} files</small>
            </h2>
            <div className="st-tools">
              <label className="st-search">
                <Search size={13} />
                <input
                  type="search"
                  placeholder="Filter by path or role"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Filter files by path or role"
                />
              </label>
              <div className="st-seg" role="group" aria-label="Sort">
                <button type="button" aria-pressed={sortBy === "size"} onClick={() => setSortBy("size")}>
                  Largest
                </button>
                <button type="button" aria-pressed={sortBy === "name"} onClick={() => setSortBy("name")}>
                  A–Z
                </button>
              </div>
            </div>
          </div>
          <div className="st-scroll">
            <table className="st-table">
              <thead>
                <tr>
                  <th>Name</th>
                  <th className="num" title="Files in the folder, or the file's language">Files</th>
                  <th className="num" title="Functions, classes, constants and variables">Symbols</th>
                  <th className="num" title="Files outside this folder (or other files) that import it">Imported by</th>
                  <th className="num" title="Files outside this folder (or files and packages) it imports">Depends on</th>
                  <th title="Most common architecture role">Main role</th>
                </tr>
              </thead>
              <tbody>
                <Rows dir={root} depth={0} ctx={ctx} />
              </tbody>
            </table>
          </div>
        </section>

        {/* File inspector */}
        <aside className="console-card st-inspector">
          {!file ? (
            <p className="st-empty">Select a file to see what depends on it and what it contains.</p>
          ) : (
            <>
              <div className="st-insp-head">
                <h3>{file.name}</h3>
                <code className="st-insp-path">{file.path}</code>
                <div className="st-chips">
                  <span className="st-chip">{file.role || "unclassified"}</span>
                  {file.language && <span className="st-chip">{file.language}</span>}
                  <span className="st-chip">{formatBytes(file.bytes)}</span>
                </div>
              </div>

              <dl className="st-stats">
                <div>
                  <dt>Imported by</dt>
                  <dd>{file.importers.size}</dd>
                </div>
                <div>
                  <dt>Depends on</dt>
                  <dd>{file.fileDeps.size}</dd>
                </div>
                <div>
                  <dt>Packages</dt>
                  <dd>{file.packages.size}</dd>
                </div>
                <div>
                  <dt>Symbols</dt>
                  <dd>{file.symbols.length}</dd>
                </div>
              </dl>

              <div className="st-insp-section">
                <h4>Imported by</h4>
                {file.importers.size === 0 ? (
                  <p className="st-dim">No other file imports this one.</p>
                ) : (
                  <ul className="st-links">
                    {[...file.importers].sort().map((p) => (
                      <li key={p}>
                        <button type="button" onClick={() => onSelect(p)} title={p}>
                          {p}
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              <div className="st-insp-section">
                <h4>Depends on</h4>
                {file.fileDeps.size === 0 && file.packages.size === 0 ? (
                  <p className="st-dim">Imports nothing.</p>
                ) : (
                  <>
                    {file.fileDeps.size > 0 && (
                      <ul className="st-links">
                        {[...file.fileDeps].sort().map((p) => (
                          <li key={p}>
                            <button type="button" onClick={() => onSelect(p)} title={p}>
                              {p}
                            </button>
                          </li>
                        ))}
                      </ul>
                    )}
                    {file.packages.size > 0 && (
                      <div className="st-pkgs">
                        {[...file.packages].sort().map((p) => (
                          <span key={p} className="st-chip st-chip--pkg">
                            {p}
                          </span>
                        ))}
                      </div>
                    )}
                  </>
                )}
              </div>

              <div className="st-insp-section">
                <h4>Symbols</h4>
                {symbolsByKind.length === 0 ? (
                  <p className="st-dim">No symbols extracted from this file.</p>
                ) : (
                  symbolsByKind.map(([kind, list]) => (
                    <div key={kind} className="st-sym-group">
                      <span className="st-sym-kind">
                        {kind} <span className="st-dim">{list.length}</span>
                      </span>
                      <ul className="st-syms">
                        {list.slice(0, 40).map((s, i) => (
                          <li key={`${s.name}-${i}`}>
                            <code>{s.name}</code>
                            {s.line && <span className="st-dim">L{s.line}</span>}
                          </li>
                        ))}
                        {list.length > 40 && <li className="st-dim">+{list.length - 40} more</li>}
                      </ul>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </aside>
      </div>
    </div>
  );
}

export default RepositoryTree;
