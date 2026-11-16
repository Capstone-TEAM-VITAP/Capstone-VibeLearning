import fs from "node:fs";
import path from "node:path";
import { buildFileGraph, graphRank, questionKind, rrf } from "./graph-retrieval.service.js";

/**
 * Content-aware file retrieval for repository questions.
 *
 * Ranks the files of a snapshot with BM25 over file text and path tokens, then
 * adds a small bonus for files whose analyzer-extracted symbol names overlap the
 * query. The symbol weight was chosen on a development split of the research
 * benchmark (see research/), not on held-out repositories.
 */

export const SYMBOL_WEIGHT = 0.25;
const MAX_FILE_BYTES = 500_000;
const K1 = 1.2;
const B = 0.75;
const CACHE_LIMIT = 8;

const STOP = new Set(
  "a an the of to in on for and or is are be it this that with as by at from which what where how does do file files".split(" "),
);
const SYMBOL_TYPES = new Set(["function", "class", "method", "variable", "constant", "component"]);

/** Lowercased identifier-aware tokens: splits camelCase, snake_case and punctuation. */
export function tokenize(text) {
  const spaced = String(text || "").replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase();
  return (spaced.match(/[a-z0-9]+/g) || []).filter((t) => t.length > 1);
}

const queryTokens = (q) => tokenize(q).filter((t) => !STOP.has(t));

function readFileText(snapshotDir, rel) {
  try {
    const full = path.join(snapshotDir, rel);
    const st = fs.statSync(full);
    if (!st.isFile() || st.size > MAX_FILE_BYTES) return "";
    return fs.readFileSync(full, "utf-8");
  } catch {
    return "";
  }
}

/** Build an in-memory BM25 index plus a per-file symbol-name index. */
export function buildSearchIndex(graphIr, snapshotDir) {
  const nodes = Array.isArray(graphIr?.nodes) ? graphIr.nodes : [];
  const paths = nodes
    .filter((n) => n.type === "file")
    .map((n) => n.metadata?.path || n.label)
    .filter(Boolean);

  const docs = paths.map((p) => {
    const toks = [...tokenize(readFileText(snapshotDir, p)), ...tokenize(p), ...tokenize(p)];
    const tf = new Map();
    for (const t of toks) tf.set(t, (tf.get(t) || 0) + 1);
    return { path: p, tf, len: toks.length };
  });

  const df = new Map();
  for (const d of docs) for (const t of d.tf.keys()) df.set(t, (df.get(t) || 0) + 1);
  const avgLen = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, docs.length);

  const symbols = new Map();
  for (const n of nodes) {
    if (!SYMBOL_TYPES.has(n.type)) continue;
    const p = n.metadata?.path;
    const name = n.metadata?.name || n.label;
    if (!p || !name) continue;
    if (!symbols.has(p)) symbols.set(p, []);
    symbols.get(p).push(new Set(tokenize(name)));
  }
  return { docs, df, avgLen, N: docs.length, symbols, fileGraph: buildFileGraph(graphIr) };
}

/** Ranked list of `{ path, score }`, best first. Files with no signal are omitted. */
export function rankFiles(index, query, { symbolWeight = SYMBOL_WEIGHT } = {}) {
  const q = queryTokens(query);
  const bm = new Map();
  for (const d of index.docs) {
    let s = 0;
    for (const t of q) {
      const f = d.tf.get(t);
      if (!f) continue;
      const n = index.df.get(t);
      const idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
      s += (idf * f * (K1 + 1)) / (f + K1 * (1 - B + (B * d.len) / index.avgLen));
    }
    if (s > 0) bm.set(d.path, s);
  }
  const max = Math.max(1e-9, ...bm.values());
  const score = new Map();
  for (const [p, s] of bm) score.set(p, s / max);

  const longQ = new Set(q.filter((t) => t.length > 2));
  for (const [p, syms] of index.symbols) {
    let best = 0;
    for (const toks of syms) {
      if (!toks.size) continue;
      let hit = 0;
      for (const t of toks) if (longQ.has(t)) hit++;
      best = Math.max(best, hit / toks.size);
    }
    if (best > 0) score.set(p, (score.get(p) || 0) + symbolWeight * best);
  }
  return [...score.entries()]
    .sort((a, c) => c[1] - a[1] || a[0].localeCompare(c[0]))
    .map(([p, s]) => ({ path: p, score: s }));
}

/**
 * The retriever CodeAI's chat and quizzes use (version 2, adopted from the research benchmark).
 *
 * Routing by question type:
 *   - importers ("which files import lib/x.js?"): reverse-import ranking from the dependency graph;
 *   - impact ("what is affected if lib/x.js changes?") and every other question: Reciprocal Rank Fusion
 *     of the text ranking (`rankFiles`), the graph ranking and, when the AI service provides it, a neural
 *     embedding ranking (`denseRanking`, a list of paths best first).
 * Returns paths best first. `kind` reports the route taken.
 */
export function rankFilesHybrid(index, query, { denseRanking = null } = {}) {
  const fg = index.fileGraph || buildFileGraph(null);
  const { kind } = questionKind(fg, query);
  const graph = graphRank(fg, query);
  if (kind === "importers" && graph.length > 0) return { kind, paths: graph };
  const text = rankFiles(index, query).map((r) => r.path);
  const lists = [text, graph];
  if (Array.isArray(denseRanking) && denseRanking.length > 0) lists.push(denseRanking);
  return { kind, paths: rrf(lists) };
}

const cache = new Map();

/** Cached index per snapshot directory; a snapshot is immutable for a given commit. */
export function getSearchIndex(graphIr, snapshotDir) {
  const nodeCount = Array.isArray(graphIr?.nodes) ? graphIr.nodes.length : 0;
  const key = `${snapshotDir}|${nodeCount}`;
  if (cache.has(key)) {
    const hit = cache.get(key);
    cache.delete(key);
    cache.set(key, hit);
    return hit;
  }
  const index = buildSearchIndex(graphIr, snapshotDir);
  cache.set(key, index);
  while (cache.size > CACHE_LIMIT) cache.delete(cache.keys().next().value);
  return index;
}
