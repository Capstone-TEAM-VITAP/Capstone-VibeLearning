import { findRelevantContext } from "../../apps/backend/src/services/chat.service.js";
import { findRelevantContext as findRelevantContextV1 } from "../legacy/chat.service.v1.js";
import { filePathsOf, readText, repoDir, mulberry32, sha1Int } from "./util.mjs";

const STOP = new Set(("a an the of to in on for and or is are be it this that with as by at from which what where how does do " +
  "file files").split(" "));

export function tokens(text) {
  return (text.replace(/([a-z0-9])([A-Z])/g, "$1 $2").toLowerCase().match(/[a-z0-9]+/g) || []).filter((t) => t.length > 1);
}
const qTokens = (q) => tokens(q).filter((t) => !STOP.has(t));

// Shared index so every baseline sees the same corpus CodeAI's graph lists.
export function buildIndex(repo, graph) {
  const paths = filePathsOf(graph);
  const docs = paths.map((p) => {
    const toks = [...tokens(readText(repo, p)), ...tokens(p), ...tokens(p)];
    const tf = new Map();
    for (const t of toks) tf.set(t, (tf.get(t) || 0) + 1);
    return { path: p, tf, len: toks.length, text: readText(repo, p).toLowerCase() };
  });
  const df = new Map();
  for (const d of docs) for (const t of d.tf.keys()) df.set(t, (df.get(t) || 0) + 1);
  const avgLen = docs.reduce((s, d) => s + d.len, 0) / Math.max(1, docs.length);
  return { docs, df, avgLen, N: docs.length };
}

export function bm25(index, query, k1 = 1.2, b = 0.75) {
  const q = qTokens(query);
  const scored = index.docs.map((d) => {
    let s = 0;
    for (const t of q) {
      const f = d.tf.get(t);
      if (!f) continue;
      const n = index.df.get(t);
      const idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
      s += (idf * f * (k1 + 1)) / (f + k1 * (1 - b + (b * d.len) / index.avgLen));
    }
    return { path: d.path, s };
  });
  return scored.filter((x) => x.s > 0).sort((a, c) => c.s - a.s || a.path.localeCompare(c.path)).map((x) => x.path);
}

// Literal-match baseline: number of distinct query words found as substrings.
export function grep(index, query) {
  const q = [...new Set(qTokens(query).filter((t) => t.length > 2))];
  return index.docs
    .map((d) => ({ path: d.path, s: q.filter((t) => d.text.includes(t) || d.path.toLowerCase().includes(t)).length }))
    .filter((x) => x.s > 0)
    .sort((a, c) => c.s - a.s || a.path.localeCompare(c.path))
    .map((x) => x.path);
}

export function random(index, qid) {
  const rng = mulberry32(sha1Int(qid));
  return [...index.docs.map((d) => d.path)].sort(() => rng() - 0.5);
}

// v1: the name/path heuristic exactly as committed before this study (legacy/chat.service.v1.js),
// run on the graph produced by the v1 analyzer.
export function codeaiV1(graphV1, repo, query) {
  return findRelevantContextV1(graphV1, query, repoDir(repo)).citations.map((c) => c.path);
}

// v2: the retriever now in the product (content-aware BM25 + symbol bonus), on the v2 graph.
export function codeaiV2(graphV2, repo, query) {
  return findRelevantContext(graphV2, query, repoDir(repo)).citations.map((c) => c.path);
}

// Exploratory: reciprocal-rank fusion of CodeAI and BM25 (k0 = 60).
export function rrf(lists, k0 = 60) {
  const s = new Map();
  for (const l of lists) l.forEach((p, i) => s.set(p, (s.get(p) || 0) + 1 / (k0 + i + 1)));
  return [...s.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0])).map((x) => x[0]);
}

// Proposed variant (research only): BM25 over file content plus a graph signal,
// i.e. how many query words appear in the names of symbols the static analyzer found in the file.
export function bm25Scores(index, query, k1 = 1.2, b = 0.75) {
  const q = qTokens(query);
  const m = new Map();
  for (const d of index.docs) {
    let s = 0;
    for (const t of q) {
      const f = d.tf.get(t);
      if (!f) continue;
      const n = index.df.get(t);
      const idf = Math.log(1 + (index.N - n + 0.5) / (n + 0.5));
      s += (idf * f * (k1 + 1)) / (f + k1 * (1 - b + (b * d.len) / index.avgLen));
    }
    if (s > 0) m.set(d.path, s);
  }
  return m;
}

const SYMBOL_TYPES = new Set(["function", "class", "method", "variable", "constant", "component"]);

export function symbolIndex(graph) {
  const byFile = new Map();
  for (const n of graph.nodes) {
    if (!SYMBOL_TYPES.has(n.type)) continue;
    const p = n.metadata?.path;
    const name = n.metadata?.name || n.label;
    if (!p || !name) continue;
    if (!byFile.has(p)) byFile.set(p, []);
    byFile.get(p).push(new Set(tokens(name)));
  }
  return byFile;
}

export function hybridSymbols(index, symIdx, query, w) {
  const bm = bm25Scores(index, query);
  const max = Math.max(1e-9, ...bm.values());
  const q = new Set(qTokens(query).filter((t) => t.length > 2));
  const score = new Map();
  for (const [p, s] of bm) score.set(p, s / max);
  for (const [p, syms] of symIdx) {
    let best = 0;
    for (const toks of syms) {
      if (!toks.size) continue;
      let hit = 0;
      for (const t of toks) if (q.has(t)) hit++;
      best = Math.max(best, hit / toks.size);
    }
    if (best > 0) score.set(p, (score.get(p) || 0) + w * best);
  }
  return [...score.entries()].sort((a, c) => c[1] - a[1] || a[0].localeCompare(c[0])).map((x) => x[0]);
}
