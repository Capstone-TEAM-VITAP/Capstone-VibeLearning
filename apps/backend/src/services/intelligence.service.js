import fs from "node:fs";
import path from "node:path";
import { repoService } from "./repo.service.js";
import gitService from "./git.service.js";
import { completeText } from "./llm.service.js";
import { BadGatewayError, ServiceUnavailableError } from "../utils/errors.js";

const SYMBOL_TYPES = new Set(["function", "class", "method", "constant", "variable"]);
const summaryCache = new Map(); // `${repoId}:${sha}` -> summary

function topN(map, n) {
  return [...map.entries()].sort((a, b) => b[1] - a[1] || String(a[0]).localeCompare(String(b[0]))).slice(0, n);
}

function bump(map, key, by = 1) {
  map.set(key, (map.get(key) || 0) + by);
}

/**
 * Compact, model-friendly facts about a Graph IR 1.0 graph.
 * Every number here is counted straight from the graph.
 */
export function buildGraphDigest(graph) {
  const nodes = Array.isArray(graph?.nodes) ? graph.nodes : [];
  const edges = Array.isArray(graph?.edges) ? graph.edges : [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const files = nodes.filter((n) => n.type === "file");
  const languages = new Map();
  const topDirs = new Map();
  for (const f of files) {
    bump(languages, f.metadata?.language || "other");
    const p = f.metadata?.path || f.id.replace(/^file:/, "");
    const parts = p.split("/");
    bump(topDirs, parts.length > 1 ? (parts.length > 2 ? `${parts[0]}/${parts[1]}` : parts[0]) : "(root)");
  }

  const roles = new Map();
  const entrypoints = [];
  for (const n of nodes) {
    if (!n.id?.startsWith("architecture:")) continue;
    const role = (n.metadata?.role || n.id.split(":").pop() || "unknown").toLowerCase();
    bump(roles, role);
    if (role === "entrypoint") entrypoints.push(n.metadata?.path);
  }

  const symbols = new Map();
  for (const n of nodes) if (SYMBOL_TYPES.has(n.type)) bump(symbols, n.type);

  const importedBy = new Map();
  const externalUse = new Map();
  const symbolsPerFile = new Map();
  const edgeTypes = new Map();
  for (const e of edges) {
    bump(edgeTypes, e.type);
    const src = byId.get(e.source);
    const tgt = byId.get(e.target);
    if (!src || !tgt) continue;
    if (e.type === "imports" && src.type === "file" && tgt.type === "file") {
      bump(importedBy, tgt.metadata?.path || tgt.label);
    }
    if (e.type === "imports" && tgt.type === "external") {
      bump(externalUse, tgt.metadata?.module_path || tgt.label);
    }
    if (e.type === "contains" && src.type === "file" && SYMBOL_TYPES.has(tgt.type)) {
      bump(symbolsPerFile, src.metadata?.path || src.label);
    }
  }

  return {
    repository: graph?.repository?.name || null,
    totals: {
      files: files.length,
      symbols: [...symbols.values()].reduce((a, b) => a + b, 0),
      externalPackages: nodes.filter((n) => n.type === "external").length,
      relationships: edges.length,
    },
    languages: topN(languages, 8),
    topDirectories: topN(topDirs, 10),
    architectureRoles: topN(roles, 12),
    symbolKinds: topN(symbols, 6),
    entrypoints: entrypoints.filter(Boolean).slice(0, 8),
    mostImportedFiles: topN(importedBy, 10),
    mostUsedPackages: topN(externalUse, 12),
    filesWithMostSymbols: topN(symbolsPerFile, 8),
    relationshipTypes: topN(edgeTypes, 8),
  };
}

const README_NAMES = ["README.md", "README.MD", "Readme.md", "readme.md", "README"];

async function readReadme(repoId, sha, maxChars = 6000) {
  try {
    const dir = await Promise.race([
      gitService.ensureSnapshotTree(repoId, sha),
      new Promise((resolve) => setTimeout(() => resolve(null), 8000)),
    ]);
    if (!dir) return null;
    for (const name of README_NAMES) {
      const p = path.join(dir, name);
      if (fs.existsSync(p)) return fs.readFileSync(p, "utf8").slice(0, maxChars);
    }
  } catch {
    // README is optional context
  }
  return null;
}

const SYSTEM_PROMPT = `You are a senior engineer writing a briefing on an unfamiliar codebase for a developer who is about to work in it.
Use only the facts provided (graph statistics and README). Do not invent files, packages or features. When something is uncertain, say so.
Reply with a single JSON object, no markdown fences, with exactly these keys:
{
  "overview": "one or two plain sentences: what the project is and does",
  "atAGlance": [{"label": "Kind | Stack | Entry point | Status", "value": "a few words"}],
  "architecture": [{"area": "short name", "path": "real directory or file from the facts", "description": "one sentence"}],
  "keyComponents": [{"name": "short name", "path": "real path from the facts", "role": "one sentence"}],
  "startHere": [{"path": "real path from the facts", "why": "one sentence"}],
  "observations": ["concrete observation backed by a number from the facts"],
  "risks": ["concrete risk or gap, e.g. low test share or a heavily imported hub file"]
}
atAGlance: exactly 4 items with the labels Kind, Stack, Entry point, Status (use "Unknown" when the facts do not say). architecture: 3-5 items covering the main areas. keyComponents: 3-6 items. startHere: 2-4 items. observations: 3-5 items. risks: 1-4 items. Keep every sentence short and specific. Write file and directory names plainly, without backticks. Never mention the field names of the statistics (such as mostImportedFiles); describe them in plain words.`;

function parseSummary(text) {
  const cleaned = text.trim().replace(/^```(?:json)?\s*/i, "").replace(/```\s*$/, "");
  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  const obj = JSON.parse(start >= 0 ? cleaned.slice(start, end + 1) : cleaned);
  const arr = (v) => (Array.isArray(v) ? v : []);
  return {
    overview: String(obj.overview || ""),
    atAGlance: arr(obj.atAGlance)
      .filter((f) => f && f.label && f.value)
      .map((f) => ({ label: String(f.label), value: String(f.value) }))
      .slice(0, 4),
    // Older summaries used a paragraph; keep accepting it
    architecture: Array.isArray(obj.architecture)
      ? obj.architecture.filter((a) => a && (a.area || a.path)).slice(0, 5)
      : String(obj.architecture || ""),
    keyComponents: arr(obj.keyComponents).slice(0, 6),
    startHere: arr(obj.startHere).slice(0, 4),
    observations: arr(obj.observations).map(String).slice(0, 5),
    risks: arr(obj.risks).map(String).slice(0, 4),
  };
}

export const intelligenceService = {
  buildGraphDigest,

  async getSummary(clerkUserId, repositoryId, commitSha, { refresh = false } = {}) {
    const { repo } = await repoService._requireRepo(clerkUserId, repositoryId);
    const cacheKey = `${repo.id}:${commitSha}`;
    if (!refresh && summaryCache.has(cacheKey)) {
      return { ...summaryCache.get(cacheKey), cached: true };
    }

    const graph = await repoService.getSnapshotGraph(clerkUserId, repositoryId, commitSha);
    const digest = buildGraphDigest(graph);
    const readme = await readReadme(repo.id, commitSha);

    const userMessage = [
      `Repository: ${repo.owner ? `${repo.owner}/` : ""}${repo.name}`,
      `Commit: ${commitSha.slice(0, 7)}`,
      "",
      "Graph statistics (counted from the code graph; pairs are [name, count]):",
      JSON.stringify(digest),
      "",
      readme ? `README (truncated):\n${readme}` : "README: not available",
    ].join("\n");

    let result;
    try {
      result = await completeText({
        system: SYSTEM_PROMPT,
        user: userMessage,
        maxTokens: 6000,
        sessionKey: `summary:${repo.id}`,
        json: true,
      });
    } catch (err) {
      if (err.code === "LLM_NOT_CONFIGURED") throw new ServiceUnavailableError(err.message);
      throw new BadGatewayError(err.message);
    }

    let summary;
    try {
      summary = parseSummary(result.text);
    } catch {
      throw new BadGatewayError("The AI returned a summary that could not be read. Try again.");
    }

    const payload = {
      ...summary,
      model: result.model,
      provider: result.provider,
      commitSha,
      generatedAt: new Date().toISOString(),
      usedReadme: Boolean(readme),
    };
    summaryCache.set(cacheKey, payload);
    return { ...payload, cached: false };
  },
};

export default intelligenceService;
