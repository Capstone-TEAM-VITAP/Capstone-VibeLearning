/**
 * Folder/file metrics for the Files > Structure view, from a Graph IR 1.0 graph.
 *
 * - role: from `architecture:<path>:<ROLE>` nodes (files are classified_as them)
 * - symbols: symbol nodes whose metadata.path is the file
 * - importers / dependencies: `imports` edges from a file to another file or to a
 *   symbol inside another file, plus imports of external packages
 */

const SYMBOL_TYPES = new Set(["function", "class", "method", "constant", "variable"]);

export function normalizePath(p) {
  return String(p || "").replace(/\\/g, "/").replace(/^\/+/, "");
}

function emptyDir(name, path) {
  return { name, path, isDir: true, children: new Map(), files: 0, symbols: 0, importers: 0, deps: 0, bytes: 0, roles: new Map() };
}

export function buildStructure(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const roleByPath = new Map();
  for (const n of nodes) {
    if (!n.id?.startsWith("architecture:")) continue;
    const role = String(n.metadata?.role || n.id.split(":").pop() || "").toLowerCase();
    const path = normalizePath(n.metadata?.path || n.id.split(":").slice(1, -1).join(":"));
    if (path && role) roleByPath.set(path, role);
  }

  const files = new Map(); // path -> file record
  for (const n of nodes) {
    if (n.type !== "file") continue;
    const path = normalizePath(n.metadata?.path || n.id.replace(/^file:/, ""));
    const role = roleByPath.get(path) || n.architecture_role?.toLowerCase() || null;
    files.set(path, {
      name: path.split("/").pop(),
      path,
      isDir: false,
      nodeId: n.id,
      role: role && role !== "unknown" ? role : null,
      language: n.metadata?.language || null,
      bytes: Number(n.metadata?.size) || 0,
      symbols: [],
      importers: new Set(),
      fileDeps: new Set(),
      packages: new Set(),
    });
  }

  for (const n of nodes) {
    if (!SYMBOL_TYPES.has(n.type)) continue;
    const f = files.get(normalizePath(n.metadata?.path));
    if (f) {
      f.symbols.push({
        name: n.label || n.metadata?.name,
        kind: n.type,
        line: Number(n.metadata?.start_line) || null,
      });
    }
  }

  for (const e of edges) {
    if (String(e.type).toLowerCase() !== "imports") continue;
    const src = byId.get(e.source);
    const tgt = byId.get(e.target);
    if (!src || !tgt || src.type !== "file") continue;
    const from = files.get(normalizePath(src.metadata?.path || src.id.replace(/^file:/, "")));
    if (!from) continue;
    if (tgt.type === "external") {
      from.packages.add(tgt.metadata?.module_path || tgt.label);
      continue;
    }
    const to = files.get(normalizePath(tgt.metadata?.path || tgt.id.replace(/^file:/, "")));
    if (to && to !== from) {
      to.importers.add(from.path);
      from.fileDeps.add(to.path);
    }
  }

  // Assemble the folder tree with rolled-up totals
  const root = emptyDir("", "");
  for (const f of files.values()) {
    const parts = f.path.split("/");
    let dir = root;
    const chain = [root];
    for (let i = 0; i < parts.length - 1; i++) {
      const p = parts.slice(0, i + 1).join("/");
      if (!dir.children.has(parts[i])) dir.children.set(parts[i], emptyDir(parts[i], p));
      dir = dir.children.get(parts[i]);
      chain.push(dir);
    }
    dir.children.set(f.name, f);
    for (const d of chain) {
      d.files += 1;
      d.symbols += f.symbols.length;
      d.bytes += f.bytes;
      if (f.role) d.roles.set(f.role, (d.roles.get(f.role) || 0) + 1);
    }
  }

  // Folder importers / deps = links that cross the folder boundary
  const fileList = [...files.values()];
  const inside = (path, dirPath) => dirPath === "" || path === dirPath || path.startsWith(`${dirPath}/`);
  const walk = (dir) => {
    for (const child of dir.children.values()) if (child.isDir) walk(child);
    if (dir === root) return;
    const importers = new Set();
    const deps = new Set();
    for (const f of fileList) {
      if (!inside(f.path, dir.path)) continue;
      for (const s of f.importers) if (!inside(s, dir.path)) importers.add(s);
      for (const t of f.fileDeps) if (!inside(t, dir.path)) deps.add(t);
    }
    dir.importers = importers.size;
    dir.deps = deps.size;
  };
  walk(root);

  // Headline insights
  // Step into wrapper folders (e.g. `apps/` holding 95% of files) so the
  // "biggest area" names a real area instead of the monorepo root
  let level = root;
  for (;;) {
    const dirs = [...level.children.values()].filter((c) => c.isDir).sort((a, b) => b.files - a.files);
    const top = dirs[0];
    const hasSubdirs = top && [...top.children.values()].some((c) => c.isDir);
    if (top && hasSubdirs && top.files >= level.files * 0.8 && level.files > 0) level = top;
    else break;
  }
  const topDirs = [...level.children.values()].filter((c) => c.isDir).sort((a, b) => b.files - a.files);
  const hubs = fileList.filter((f) => f.importers.size > 0).sort((a, b) => b.importers.size - a.importers.size);
  const hubThreshold = Math.max(3, hubs[Math.floor(hubs.length * 0.1)]?.importers.size || 3);
  const code = fileList.filter((f) => f.symbols.length > 0 || f.fileDeps.size > 0 || f.packages.size > 0);
  const notImported = code.filter((f) => f.importers.size === 0 && !["entrypoint", "test", "config"].includes(f.role));
  const unclassified = fileList.filter((f) => !f.role).length;

  return {
    root,
    files,
    hubThreshold,
    insights: {
      biggestArea: topDirs[0] ? { path: topDirs[0].path, files: topDirs[0].files, share: topDirs[0].files / Math.max(fileList.length, 1) } : null,
      topHub: hubs[0] ? { path: hubs[0].path, importers: hubs[0].importers.size } : null,
      notImported: notImported.length,
      unclassified,
      totalFiles: fileList.length,
    },
  };
}

export function mainRole(dir) {
  let best = null;
  for (const [role, count] of dir.roles) if (!best || count > best.count) best = { role, count };
  return best ? { ...best, share: best.count / Math.max(dir.files, 1) } : null;
}

export function formatBytes(n) {
  if (!n) return "—";
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(n < 10240 ? 1 : 0)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}
