/**
 * Structural (graph) file ranking and Reciprocal Rank Fusion for the chat and quiz retriever.
 *
 * A JavaScript port of the research rankers in apps/ai-service/src/retrieval (filegraph.py, hybrid.py),
 * chosen because the research benchmark (research/, paper: "CodeAI: When Does Code Structure Help?")
 * found that:
 *   - questions that name a file and ask who imports or depends on it are answered best by walking the
 *     import graph backwards (held-out MRR 0.97 against 0.68 for the text retriever);
 *   - for every other question, fusing the text ranking with the graph ranking (and, when available,
 *     neural embeddings) ranks the right files higher than the text ranking alone.
 * The functions are pure: they take the analyzer's Graph IR and return ranked file paths.
 */

const TOKEN = /[A-Za-z0-9]+/g;
const STOPWORDS = new Set(
  ("a an the of to in on for and or is are be it this that with as by at from which what where how " +
    "does do file files when then after before into via").split(" "),
);
const DEPENDENCY_INTENT =
  /\b(import|imports|imported|depend|depends|dependent|dependency|dependencies|affect|affected|impact|impacted|break|breaks|use|uses|used|require|requires)\b/i;
/** Subset of DEPENDENCY_INTENT that asks for direct importers rather than for the impact of a change. */
const IMPORTER_INTENT =
  /\b(import|imports|imported|depend|depends|dependent|dependency|dependencies|use|uses|used|require|requires)\b/i;
const IMPACT_INTENT = /\b(affect|affected|impact|impacted|break|breaks|change|changes|changed)\b/i;
const MAX_REVERSE_DEPTH = 4;
export const RRF_K0 = 60;

/** Lowercase identifier-aware tokens (camelCase and snake_case split), as in filegraph.py. */
export function graphTokenize(text) {
  const spaced = String(text || "").replace(/([a-z0-9])([A-Z])/g, "$1 $2");
  return (spaced.match(TOKEN) || []).map((t) => t.toLowerCase()).filter((t) => t.length > 1);
}

/** Light suffix stripping so 'routes' / 'routing' / 'routed' meet 'route' (same rule as filegraph.py). */
export function stem(token) {
  let t = token;
  if (t.length > 5 && t.endsWith("ies")) {
    t = t.slice(0, -3) + "y";
  } else {
    for (const suffix of ["ing", "ed", "es", "s"]) {
      if (t.length > suffix.length + 3 && t.endsWith(suffix)) {
        t = t.slice(0, -suffix.length);
        break;
      }
    }
  }
  if (t.length > 4 && t.endsWith("e")) t = t.slice(0, -1);
  return t;
}

export function keywords(query) {
  return new Set(graphTokenize(query).filter((t) => !STOPWORDS.has(t)).map(stem));
}

const pathTokens = (p) => new Set(graphTokenize(p).map(stem));

/**
 * File-level dependency graph lifted from Graph IR: IMPORTS, CALLS and DEPENDS_ON edges between files
 * (self loops dropped), plus the symbol names defined in each file.
 */
export function buildFileGraph(graphIr) {
  const nodes = Array.isArray(graphIr?.nodes) ? graphIr.nodes : [];
  const edges = Array.isArray(graphIr?.edges) ? graphIr.edges : [];
  const byId = new Map(nodes.map((n) => [n.id, n]));
  const files = [...new Set(nodes.filter((n) => n.type === "file").map((n) => n.metadata?.path || n.label).filter(Boolean))].sort();
  const fileSet = new Set(files);
  const symbols = new Map();
  for (const n of nodes) {
    const p = n.metadata?.path;
    if (!p || !fileSet.has(p) || n.type === "file") continue;
    if (String(n.id || "").startsWith("symbol:") && n.metadata?.name) {
      if (!symbols.has(p)) symbols.set(p, []);
      symbols.get(p).push(n.metadata.name);
    }
  }
  const pathOf = (id) => {
    const p = byId.get(id)?.metadata?.path;
    return p && fileSet.has(p) ? p : null;
  };
  const out = new Map();
  const inc = new Map();
  const seen = new Set();
  for (const e of edges) {
    if (!["imports", "calls", "depends_on"].includes(e.type)) continue;
    const u = pathOf(e.source);
    const v = pathOf(e.target);
    if (!u || !v || u === v || seen.has(`${u}\0${v}`)) continue;
    seen.add(`${u}\0${v}`);
    if (!out.has(u)) out.set(u, []);
    if (!inc.has(v)) inc.set(v, []);
    out.get(u).push(v);
    inc.get(v).push(u);
  }
  return { files, symbols, out, inc };
}

/** A file whose full path (preferred) or unique basename appears verbatim in the question. */
export function findNamedFile(fileGraph, query) {
  const q = String(query || "").toLowerCase();
  const hits = fileGraph.files.filter((p) => q.includes(p.toLowerCase()));
  if (hits.length) return hits.reduce((a, b) => (b.length > a.length ? b : a));
  const byBase = new Map();
  for (const p of fileGraph.files) {
    const base = p.split("/").pop().toLowerCase();
    if (!byBase.has(base)) byBase.set(base, []);
    byBase.get(base).push(p);
  }
  const named = [...byBase.entries()].filter(([b, ps]) => ps.length === 1 && b.includes(".") && q.includes(b)).map(([, ps]) => ps[0]);
  return named.length ? named.reduce((a, b) => (b.length > a.length ? b : a)) : null;
}

/**
 * Classify the question for routing:
 *   "importers" - names a file and asks who imports / depends on / uses it (graph ranking only)
 *   "impact"    - names a file and asks what a change to it affects (graph walk fused with text)
 *   "general"   - everything else (text, neural and graph name matching, fused)
 */
export function questionKind(fileGraph, query) {
  const named = findNamedFile(fileGraph, query);
  if (!named) return { kind: "general", named: null };
  if (IMPACT_INTENT.test(query)) return { kind: "impact", named };
  if (IMPORTER_INTENT.test(query)) return { kind: "importers", named };
  return { kind: "general", named };
}

/**
 * Graph ranking (port of hybrid.graph_rank). A dependency question about a named file is answered by
 * reverse-import distance from that file (up to four steps); any other question by how many question
 * keywords appear in each file's path and symbol names, with half credit for direct neighbours.
 */
export function graphRank(fileGraph, query) {
  const named = findNamedFile(fileGraph, query);
  if (named && DEPENDENCY_INTENT.test(query)) {
    const dist = new Map([[named, 0]]);
    const queue = [named];
    while (queue.length) {
      const cur = queue.shift();
      if (dist.get(cur) >= MAX_REVERSE_DEPTH) continue;
      for (const src of [...(fileGraph.inc.get(cur) || [])].sort()) {
        if (!dist.has(src)) {
          dist.set(src, dist.get(cur) + 1);
          queue.push(src);
        }
      }
    }
    return [...dist.keys()].filter((p) => p !== named).sort((a, b) => dist.get(a) - dist.get(b) || a.localeCompare(b));
  }
  const kws = keywords(query);
  if (!kws.size) return [];
  const seed = new Map();
  for (const p of fileGraph.files) {
    const toks = pathTokens(p);
    for (const name of fileGraph.symbols.get(p) || []) for (const t of graphTokenize(name)) toks.add(stem(t));
    let hit = 0;
    for (const k of kws) if (toks.has(k)) hit++;
    if (hit > 0) seed.set(p, hit / kws.size);
  }
  const score = new Map(seed);
  for (const [p, s] of seed) {
    for (const v of fileGraph.out.get(p) || []) score.set(v, Math.max(score.get(v) || 0, 0.5 * s));
    for (const u of fileGraph.inc.get(p) || []) score.set(u, Math.max(score.get(u) || 0, 0.5 * s));
  }
  return [...score.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([p]) => p);
}

/** Weighted Reciprocal Rank Fusion of ranked path lists; ties broken by path. */
export function rrf(lists, weights = [], k0 = RRF_K0) {
  const score = new Map();
  lists.forEach((ranked, i) => {
    const w = weights[i] ?? 1;
    (ranked || []).forEach((p, r) => score.set(p, (score.get(p) || 0) + w / (k0 + r + 1)));
  });
  return [...score.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map(([p]) => p);
}
