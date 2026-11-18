/**
 * Concrete counts for the Repository Intelligence charts, computed from a
 * Graph IR 1.0 graph. Roles live on `architecture:<path>:<ROLE>` nodes that
 * files are `classified_as`; symbols hang off files through `contains` edges.
 */

const SYMBOL_TYPES = new Set(["function", "class", "method", "constant", "variable"]);

function bump(map, key, by = 1) {
  map.set(key, (map.get(key) || 0) + by);
}

function ranked(map, limit) {
  return [...map.entries()]
    .sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0])))
    .slice(0, limit)
    .map(([label, value]) => ({ label, value }));
}

function filePath(node) {
  return node?.metadata?.path || node?.id?.replace(/^file:/, "") || node?.label || "";
}

export function roleOfArchitectureNode(node) {
  if (!node?.id?.startsWith("architecture:")) return null;
  return String(node.metadata?.role || node.id.split(":").pop() || "unknown").toLowerCase();
}

export function computeGraphStats(graph, { limit = 8 } = {}) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const files = nodes.filter((n) => n.type === "file");
  const languages = new Map();
  const directories = new Map();
  for (const f of files) {
    bump(languages, f.metadata?.language || "other");
    const parts = filePath(f).split("/");
    const dir = parts.length > 2 ? `${parts[0]}/${parts[1]}` : parts.length === 2 ? parts[0] : "(root)";
    bump(directories, dir);
  }

  const roles = new Map();
  for (const n of nodes) {
    const role = roleOfArchitectureNode(n);
    if (role) bump(roles, role);
  }

  const symbolKinds = new Map();
  for (const n of nodes) if (SYMBOL_TYPES.has(n.type)) bump(symbolKinds, n.type);

  const importedBy = new Map();
  const packages = new Map();
  const symbolsPerFile = new Map();
  const relationshipTypes = new Map();
  for (const e of edges) {
    bump(relationshipTypes, String(e.type || "other").toLowerCase().replace(/_/g, " "));
    const src = byId.get(e.source);
    const tgt = byId.get(e.target);
    if (!src || !tgt) continue;
    const type = String(e.type || "").toLowerCase();
    if (type === "imports" && src.type === "file" && tgt.type === "file") bump(importedBy, filePath(tgt));
    if (type === "imports" && tgt.type === "external") bump(packages, tgt.metadata?.module_path || tgt.label);
    if (type === "contains" && src.type === "file" && SYMBOL_TYPES.has(tgt.type)) bump(symbolsPerFile, filePath(src));
  }

  return {
    totals: {
      files: files.length,
      symbols: [...symbolKinds.values()].reduce((a, b) => a + b, 0),
      packages: nodes.filter((n) => n.type === "external").length,
      relationships: edges.length,
    },
    languages: ranked(languages, limit),
    directories: ranked(directories, limit),
    roles: ranked(roles, 12),
    symbolKinds: ranked(symbolKinds, limit),
    mostImported: ranked(importedBy, limit),
    packages: ranked(packages, limit),
    symbolsPerFile: ranked(symbolsPerFile, limit),
    relationshipTypes: ranked(relationshipTypes, limit),
  };
}
