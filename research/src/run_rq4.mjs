// RQ4: does the analyzer's resolved file-to-file import graph match a regex oracle
// over the raw source? Only relative (intra-repo) specifiers are compared.
import fs from "node:fs";
import path from "node:path";
import { ROOT, REPOS, loadGraph, filePathsOf, readText, stripComments } from "./util.mjs";

const JS_EXT = /\.(jsx?|mjs|cjs)$/;
const STYLES = {
  commonjs: /require\(\s*['"](\.{1,2}\/[^'"]*)['"]\s*\)/g,
  esm: /\bfrom\s+['"](\.{1,2}\/[^'"]*)['"]|\bimport\(\s*['"](\.{1,2}\/[^'"]*)['"]\s*\)|^\s*import\s+['"](\.{1,2}\/[^'"]*)['"]/gm,
};

function resolveRel(fromRel, spec, fileSet) {
  const base = path.posix.normalize(path.posix.join(path.posix.dirname(fromRel), spec));
  return [base, `${base}.js`, `${base}.jsx`, `${base}.mjs`, `${base}.cjs`, `${base}.json`, `${base}/index.js`, `${base}/index.jsx`].find((t) => fileSet.has(t)) || null;
}

const stats = JSON.parse(fs.readFileSync(path.join(ROOT, "out", "analysis_stats.json"), "utf8"));
const rows = [];
for (const repo of [...REPOS.dev, ...REPOS.test, ...REPOS.test2]) {
  const g = loadGraph(repo);
  const files = filePathsOf(g);
  const fileSet = new Set(files);
  const oracle = { commonjs: new Set(), esm: new Set() };
  for (const rel of files) {
    if (!JS_EXT.test(rel)) continue;
    const src = stripComments(readText(repo, rel));
    for (const [style, re] of Object.entries(STYLES)) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(src))) {
        const spec = m[1] || m[2] || m[3];
        const t = resolveRel(rel, spec, fileSet);
        if (t && t !== rel) oracle[style].add(`${rel}->${t}`);
      }
    }
  }
  const graphPairs = new Set();
  for (const e of g.edges) {
    if (e.type !== "imports") continue;
    if (!e.source.startsWith("file:") || !e.target.startsWith("file:")) continue;
    graphPairs.add(`${e.source.slice(5)}->${e.target.slice(5)}`);
  }
  const all = new Set([...oracle.commonjs, ...oracle.esm]);
  const tp = [...graphPairs].filter((p) => all.has(p)).length;
  const tpEsm = [...oracle.esm].filter((p) => graphPairs.has(p)).length;
  const tpCjs = [...oracle.commonjs].filter((p) => graphPairs.has(p)).length;
  rows.push({
    repo,
    seconds: stats[repo].seconds,
    nodes: stats[repo].nodes,
    oracleEsm: oracle.esm.size,
    oracleCjs: oracle.commonjs.size,
    graph: graphPairs.size,
    precision: graphPairs.size ? tp / graphPairs.size : null,
    recallEsm: oracle.esm.size ? tpEsm / oracle.esm.size : null,
    recallCjs: oracle.commonjs.size ? tpCjs / oracle.commonjs.size : null,
    recallAll: all.size ? tp / all.size : null,
  });
}
const f = (x) => (x === null ? "n/a" : x.toFixed(3));
let md = "# RQ4: import-resolution accuracy vs regex oracle\n\n| Repo | analysis s | nodes | oracle ESM pairs | oracle CJS pairs | graph pairs | precision | recall (ESM) | recall (CJS) | recall (all) |\n|---|---|---|---|---|---|---|---|---|---|\n";
for (const r of rows) md += `| ${r.repo} | ${r.seconds} | ${r.nodes} | ${r.oracleEsm} | ${r.oracleCjs} | ${r.graph} | ${f(r.precision)} | ${f(r.recallEsm)} | ${f(r.recallCjs)} | ${f(r.recallAll)} |\n`;
const sum = (k) => rows.reduce((s, r) => s + r[k], 0);
const tpEsmTot = rows.reduce((s, r) => s + (r.recallEsm ?? 0) * r.oracleEsm, 0);
const tpCjsTot = rows.reduce((s, r) => s + (r.recallCjs ?? 0) * r.oracleCjs, 0);
md += `\nPooled: ESM recall ${(tpEsmTot / sum("oracleEsm")).toFixed(3)} over ${sum("oracleEsm")} pairs; CommonJS recall ${(tpCjsTot / sum("oracleCjs")).toFixed(3)} over ${sum("oracleCjs")} pairs. Analysis crashes: ${Object.values(stats).filter((s) => !s.ok).length}/${Object.keys(stats).length}.\n`;
fs.writeFileSync(path.join(ROOT, "out", "rq4_import_accuracy.md"), md);
fs.writeFileSync(path.join(ROOT, "out", "rq4_raw.json"), JSON.stringify(rows, null, 1));
console.log(md);
