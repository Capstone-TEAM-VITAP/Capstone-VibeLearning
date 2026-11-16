import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";
import { fileURLToPath } from "node:url";

export const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
export const REPOS = JSON.parse(fs.readFileSync(path.join(ROOT, "repos.json"), "utf8"));
export const repoDir = (name) => path.join(ROOT, "data", "repos", name);
export const graphPath = (name, v = "") => path.join(ROOT, "out", v, "graphs", `${name}.json`);
export const loadGraph = (name, v = "") => JSON.parse(fs.readFileSync(graphPath(name, v), "utf8"));

export function sha1Int(s) {
  return parseInt(crypto.createHash("sha1").update(s).digest("hex").slice(0, 8), 16);
}

// Small seeded PRNG so every number in the paper is reproducible.
export function mulberry32(seed) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

export function filePathsOf(graph) {
  return graph.nodes.filter((n) => n.type === "file").map((n) => n.metadata?.path || n.label);
}

export function readText(repo, rel, maxBytes = 500_000) {
  try {
    const full = path.join(repoDir(repo), rel);
    const st = fs.statSync(full);
    if (!st.isFile() || st.size > maxBytes) return "";
    return fs.readFileSync(full, "utf8");
  } catch {
    return "";
  }
}

// Remove block comments and whole-line // comments so JSDoc such as {import('./x')} is not
// mistaken for a real dependency by the regex oracle. Strings containing "//" are left alone.
export function stripComments(src) {
  return src.replace(/\/\*[\s\S]*?\*\//g, "").replace(/^[ \t]*\/\/.*$/gm, "");
}
