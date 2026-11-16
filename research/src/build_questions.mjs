// Builds the benchmark. Gold labels come from regex scans of the raw source
// (not from the Tree-sitter graph), so the system under test cannot grade itself.
import fs from "node:fs";
import path from "node:path";
import { ROOT, REPOS, loadGraph, filePathsOf, readText, sha1Int, stripComments } from "./util.mjs";

const JS_EXT = /\.(jsx?|mjs|cjs)$/;
const TESTY = /(^|\/)(__tests__|tests?|spec|specs|examples?|benchmarks?|fixtures?)(\/|$)|\.(test|spec)\./;
const SKIP = /(^|\/)(node_modules|dist|build|vendor|coverage|\.git)(\/|$)|\.min\./;
const MAX_LOCATE = 30;
const MAX_DEPEND = 15;

const DECL = String.raw`(?:export\s+)?(?:default\s+)?(?:async\s+)?(?:function\*?\s+([A-Za-z_$][\w$]*)|class\s+([A-Za-z_$][\w$]*)|(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=|((?:[A-Za-z_$][\w$]*\.)+[A-Za-z_$][\w$]*)\s*=\s*function|([A-Za-z_$][\w$]*)\s*\()`;
const JSDOC = new RegExp(String.raw`/\*\*([\s\S]*?)\*/\s*\n\s*` + DECL, "g");

function describe(raw) {
  const lines = raw.split("\n").map((l) => l.replace(/^\s*\*\s?/, "").trim());
  const text = [];
  for (const l of lines) {
    if (l.startsWith("@")) break;
    text.push(l);
  }
  let d = text.join(" ").replace(/`/g, "").replace(/\s+/g, " ").trim();
  const m = d.match(/^(.+?[.!?])(\s|$)/);
  if (m) d = m[1];
  return d.slice(0, 220);
}

function locateQuestions(repo, files) {
  const found = [];
  for (const rel of files) {
    if (!JS_EXT.test(rel) || SKIP.test(rel) || TESTY.test(rel)) continue;
    const src = readText(repo, rel);
    JSDOC.lastIndex = 0;
    let m;
    while ((m = JSDOC.exec(src))) {
      const ident = m[2] || m[3] || m[4] || m[5] || m[6] || m[7];
      if (!ident) continue;
      const desc = describe(m[1]);
      const words = desc.split(" ").filter(Boolean);
      if (words.length < 6) continue;
      const short = ident.split(".").pop().toLowerCase();
      if (desc.toLowerCase().includes(short)) continue; // no identifier leakage
      found.push({ rel, ident, desc });
    }
  }
  // drop descriptions that occur more than once (ambiguous gold)
  const count = new Map();
  for (const f of found) count.set(f.desc, (count.get(f.desc) || 0) + 1);
  const uniq = found.filter((f) => count.get(f.desc) === 1);
  uniq.sort((a, b) => sha1Int(repo + a.rel + a.ident) - sha1Int(repo + b.rel + b.ident));
  return uniq.slice(0, MAX_LOCATE).map((f, i) => ({
    id: `${repo}:loc:${i}`,
    repo,
    type: "locate",
    query: f.desc,
    gold: [f.rel],
    exclude: [],
    meta: { identifier: f.ident },
  }));
}

const IMPORT_RE = [
  /require\(\s*['"](\.{1,2}\/[^'"]*)['"]\s*\)/g,
  /\bfrom\s+['"](\.{1,2}\/[^'"]*)['"]/g,
  /\bimport\(\s*['"](\.{1,2}\/[^'"]*)['"]\s*\)/g,
];

function resolveRel(fromRel, spec, fileSet) {
  const base = path.posix.normalize(path.posix.join(path.posix.dirname(fromRel), spec));
  const tries = [base, `${base}.js`, `${base}.jsx`, `${base}.mjs`, `${base}.cjs`, `${base}.json`, `${base}/index.js`, `${base}/index.jsx`];
  return tries.find((t) => fileSet.has(t)) || null;
}

function dependencyQuestions(repo, files) {
  const fileSet = new Set(files);
  const importers = new Map();
  for (const rel of files) {
    if (!JS_EXT.test(rel) || SKIP.test(rel)) continue;
    const src = stripComments(readText(repo, rel));
    for (const re of IMPORT_RE) {
      re.lastIndex = 0;
      let m;
      while ((m = re.exec(src))) {
        const target = resolveRel(rel, m[1], fileSet);
        if (!target || target === rel) continue;
        if (!importers.has(target)) importers.set(target, new Set());
        importers.get(target).add(rel);
      }
    }
  }
  const cands = [...importers.entries()].filter(([t, s]) => s.size >= 2 && s.size <= 15 && JS_EXT.test(t) && !SKIP.test(t));
  cands.sort((a, b) => sha1Int(repo + a[0]) - sha1Int(repo + b[0]));
  return cands.slice(0, MAX_DEPEND).map(([target, set], i) => ({
    id: `${repo}:dep:${i}`,
    repo,
    type: "dependency",
    query: `Which files import ${target}?`,
    gold: [...set].sort(),
    exclude: [target],
    meta: { target },
  }));
}

const out = [];
for (const [split, names] of [["dev", REPOS.dev], ["test", REPOS.test], ["test2", REPOS.test2]]) {
  for (const repo of names) {
    const files = filePathsOf(loadGraph(repo));
    for (const q of [...locateQuestions(repo, files), ...dependencyQuestions(repo, files)]) {
      out.push({ ...q, split });
    }
  }
}
fs.writeFileSync(path.join(ROOT, "data", "questions.json"), JSON.stringify(out, null, 1));
const summary = {};
for (const q of out) {
  const k = `${q.split}/${q.repo}/${q.type}`;
  summary[k] = (summary[k] || 0) + 1;
}
console.log(summary);
console.log("total", out.length);
