import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { jobRepository } from "../repositories/job.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { NotFoundError, BadRequestError } from "../utils/errors.js";
import gitService from "./git.service.js";
import { getSearchIndex, rankFilesHybrid } from "./retrieval.service.js";
import { aiService } from "./ai.service.js";

const TOKEN_PATTERN = /[A-Za-z0-9_]+/g;

function tokenize(text) {
  if (!text) return new Set();
  const matches = String(text).toLowerCase().match(TOKEN_PATTERN);
  return new Set(matches || []);
}

/**
 * Safely read a file or line range from a directory.
 */
function readCodeExcerpt(filePath, startLine = 1, endLine = 150) {
  try {
    if (!fs.existsSync(filePath)) return null;
    const content = fs.readFileSync(filePath, "utf-8");
    const lines = content.split(/\r?\n/);
    const start = Math.max(1, startLine);
    const end = Math.min(lines.length, endLine || lines.length);
    const slice = lines.slice(start - 1, end);
    return {
      content: slice.join("\n"),
      startLine: start,
      endLine: end,
      totalLines: lines.length,
    };
  } catch {
    return null;
  }
}

/**
 * Read excerpts (and matching citations) for the chosen files. When a matched
 * symbol lives in a file, the excerpt is a window around that symbol.
 */
function buildExcerpts(sortedFiles, matchedSymbols, snapshotDir) {
  const excerpts = [];
  const citations = [];
  for (const relPath of sortedFiles) {
    if (!snapshotDir) break;
    const fullPath = path.join(snapshotDir, relPath);
    const symInFile = matchedSymbols.find((s) => s.metadata?.path === relPath);
    let startLine = 1;
    let endLine = 180;
    if (symInFile && symInFile.metadata?.start_line) {
      startLine = Math.max(1, Number(symInFile.metadata.start_line) - 5);
      endLine = Math.min(startLine + 120, Number(symInFile.metadata.end_line || startLine) + 40);
    }
    const excerpt = readCodeExcerpt(fullPath, startLine, endLine);
    if (excerpt) {
      excerpts.push({ path: relPath, startLine: excerpt.startLine, endLine: excerpt.endLine, content: excerpt.content });
      citations.push({ path: relPath, startLine: excerpt.startLine, endLine: excerpt.endLine });
    }
  }
  return { excerpts, citations };
}

/**
 * Legacy name/path heuristic (v1). Kept so the research benchmark can compare
 * the earlier behaviour with the content-aware retriever.
 */
export function findRelevantContextLegacy(graphIr, query, snapshotDir) {
  const queryTokens = tokenize(query);
  const lowerQuery = query.toLowerCase();

  const nodes = Array.isArray(graphIr?.nodes) ? graphIr.nodes : [];
  const fileNodes = nodes.filter((n) => n.type === "file");
  const symbolNodes = nodes.filter((n) => n.type !== "file" && n.type !== "repository");

  const matchedSymbols = [];

  // Check for architecture intent
  const isArchitectureQuery =
    lowerQuery.includes("architecture") ||
    lowerQuery.includes("overview") ||
    lowerQuery.includes("structure") ||
    lowerQuery.includes("components");

  // Whole-word match: the substring "ai" also occurs in "main", "again", "obtain".
  const isAiQuery = /\b(ai|gpt|llm|openai)\b/.test(lowerQuery);

  const isApiQuery =
    lowerQuery.includes("route") ||
    lowerQuery.includes("api") ||
    lowerQuery.includes("endpoint") ||
    lowerQuery.includes("controller");

  const isAuthQuery =
    lowerQuery.includes("auth") ||
    lowerQuery.includes("login") ||
    lowerQuery.includes("token") ||
    lowerQuery.includes("user");

  const isDbQuery =
    lowerQuery.includes("model") ||
    lowerQuery.includes("database") ||
    lowerQuery.includes("db") ||
    lowerQuery.includes("schema") ||
    lowerQuery.includes("prisma");

  // 1. Exact & partial symbol matching
  for (const s of symbolNodes) {
    const symName = (s.label || s.metadata?.name || "").toLowerCase();
    const symPath = (s.metadata?.path || "").toLowerCase();

    let score = 0;
    if (symName && lowerQuery.includes(symName)) score += 10;
    for (const t of queryTokens) {
      if (t.length > 2) {
        if (symName.includes(t) || (t.length >= 4 && t.includes(symName))) score += 5;
        if (symPath.includes(t)) score += 3;
      }
    }

    if (isAuthQuery && (symName.includes("auth") || symPath.includes("auth"))) {
      score += 6;
    }
    if (isApiQuery && (symName.includes("route") || symPath.includes("route") || symPath.includes("controller"))) {
      score += 4;
    }
    if (isDbQuery && (symPath.includes("prisma") || symPath.includes("repository") || symPath.includes("model"))) {
      score += 4;
    }

    if (score > 0) {
      matchedSymbols.push({ ...s, score });
    }
  }

  // Sort matched symbols by score descending
  matchedSymbols.sort((a, b) => b.score - a.score);

  // 2. Intent-based scored file selection
  const fileScores = new Map();
  function scoreFile(filePath, points) {
    if (!filePath) return;
    fileScores.set(filePath, (fileScores.get(filePath) || 0) + points);
  }

  // Boost files containing matched symbols
  for (const s of matchedSymbols) {
    if (s.metadata?.path) {
      scoreFile(s.metadata.path, (s.score || 5) * 2);
    }
  }

  for (const f of fileNodes) {
    const rawPath = f.metadata?.path || f.label || "";
    const p = rawPath.toLowerCase();
    const role = (f.architecture_role || f.metadata?.role || "").toUpperCase();

    // Specific intent scoring
    if (isAiQuery && (p.includes("ai")|| p.includes("gpt") || p.includes("llm") || p.includes("openai"))) {
      scoreFile(rawPath, 15);
    }
    if (isApiQuery && (role === "ROUTE" || role === "CONTROLLER" || p.includes("route") || p.includes("controller"))) {
      scoreFile(rawPath, 8);
    }
    if (isAuthQuery && (p.includes("auth") || p.includes("user") || p.includes("clerk"))) {
      scoreFile(rawPath, 10);
    }
    if (isDbQuery && (role === "MODEL" || role === "REPOSITORY" || p.includes("prisma") || p.includes("model") || p.includes("schema") || p.includes("db"))) {
      scoreFile(rawPath, 10);
    }
    if (isArchitectureQuery && (p.includes("app.js") || p.includes("main.jsx") || p.includes("main.js") || p.includes("server.js") || p.includes("package.json"))) {
      scoreFile(rawPath, 8);
    }

    // General token matching on file paths
    for (const t of queryTokens) {
      if (t.length > 2 && p.includes(t)) {
        scoreFile(rawPath, 4);
      }
    }
  }

  // Fallback: if no files matched, include top-level entrypoints
  if (fileScores.size === 0 && fileNodes.length > 0) {
    fileNodes.slice(0, 6).forEach((f) => scoreFile(f.metadata?.path || f.label, 1));
  }

  // Sort files by score descending and take top 7
  const sortedFiles = Array.from(fileScores.entries())
    .sort((a, b) => b[1] - a[1])
    .map((entry) => entry[0])
    .slice(0, 7);

  // 3. Read actual excerpts from snapshot directory
  const { excerpts, citations } = buildExcerpts(sortedFiles, matchedSymbols, snapshotDir);

  // Also build architectural role summary
  const rolesSummary = {};
  for (const n of nodes) {
    const role = n.architecture_role || n.metadata?.role;
    if (role) {
      const upper = role.toUpperCase();
      if (!rolesSummary[upper]) rolesSummary[upper] = [];
      const p = n.metadata?.path || n.label;
      if (p && !rolesSummary[upper].includes(p)) {
        rolesSummary[upper].push(p);
      }
    }
  }

  return {
    matchedSymbols: matchedSymbols.slice(0, 10),
    excerpts,
    citations,
    rolesSummary,
  };
}

const TOP_FILES = 7;
const ARCHITECTURE_QUERY = /\b(architecture|overview|structure|components)\b/;

/**
 * Select the files and excerpts that ground an answer.
 *
 * Files are ranked by `rankFilesHybrid` (`retrieval.service.js`): importer
 * questions use the dependency graph, every other question fuses the text
 * ranking (BM25 plus a symbol bonus), the graph ranking and, when supplied,
 * a neural embedding ranking (`options.denseRanking`, from the AI service).
 * Without a snapshot directory there is no text to search, so this falls back
 * to the legacy name/path heuristic. Architecture questions keep the legacy
 * entrypoint-oriented selection because they ask about overall structure.
 */
export function findRelevantContext(graphIr, query, snapshotDir, { denseRanking = null } = {}) {
  const lowerQuery = String(query || "").toLowerCase();
  if (!snapshotDir || ARCHITECTURE_QUERY.test(lowerQuery)) {
    return findRelevantContextLegacy(graphIr, query, snapshotDir);
  }

  const index = getSearchIndex(graphIr, snapshotDir);
  const ranked = rankFilesHybrid(index, query, { denseRanking }).paths.slice(0, TOP_FILES);
  if (ranked.length === 0) return findRelevantContextLegacy(graphIr, query, snapshotDir);

  const symbols = findRelevantContextLegacy(graphIr, query, null);
  const { excerpts, citations } = buildExcerpts(ranked, symbols.matchedSymbols, snapshotDir);
  return {
    matchedSymbols: symbols.matchedSymbols,
    excerpts,
    citations,
    rolesSummary: symbols.rolesSummary,
  };
}

/**
 * `findRelevantContext` plus the AI service's neural ranking when it is available. Neural ranking is
 * best effort: if it is not installed, not ready or slow, the context is the same as without it.
 */
export async function findRelevantContextWithDense(graphIr, query, snapshotDir, { denseRank = aiService.denseRank.bind(aiService) } = {}) {
  let denseRanking = null;
  if (snapshotDir && graphIr && !ARCHITECTURE_QUERY.test(String(query || "").toLowerCase())) {
    const paths = (Array.isArray(graphIr.nodes) ? graphIr.nodes : [])
      .filter((n) => n.type === "file")
      .map((n) => n.metadata?.path || n.label)
      .filter(Boolean);
    denseRanking = await denseRank(snapshotDir, query, paths);
  }
  return findRelevantContext(graphIr, query, snapshotDir, { denseRanking });
}

/**
 * Format system prompt with repository context for the LLM.
 */
export function buildSystemPrompt({ repo, snapshot, context }) {
  const repoName = `${repo.owner}/${repo.name}`;
  const commit = snapshot.commitSha ? snapshot.commitSha.slice(0, 7) : "HEAD";

  let prompt = `You are the expert Senior AI Software Architect for the GitHub repository "${repoName}" (commit ${commit}, branch ${repo.defaultBranch || "main"}).
Your job is to answer the user's questions about this repository accurately, contextually, and clearly.

GUIDELINES:
1. Ground your answers strictly in the repository's architecture and source code provided below.
2. When mentioning files, always use markdown backticks with full relative paths (e.g. \`src/routes/auth.routes.js\`) and include line numbers if available.
3. CODE COMPLETENESS: When showing code, provide full, runnable, and syntactically complete code blocks. Never truncate functions, schemas, or exports mid-way. Always properly close all parentheses, brackets, and code block fences (\`\`\`).
4. If a feature or file is not present in the repository, honestly state that it was not found rather than inventing it.
5. Offer practical tips or examples if the user asks how to modify, extend, or add features to the codebase.
6. COMPLETENESS & CLARITY: Ensure every step, file example, and explanation is 100% finished and complete. Do not leave any step or code block cut off or hanging. Keep explanations focused and clean.

=== REPOSITORY ARCHITECTURAL ROLES ===
`;

  const roles = Object.entries(context.rolesSummary || {});
  if (roles.length > 0) {
    for (const [role, files] of roles) {
      prompt += `- ${role}: ${files.slice(0, 6).join(", ")}${files.length > 6 ? ` (+${files.length - 6} more)` : ""}\n`;
    }
  } else {
    prompt += `No specific architecture roles pre-classified.\n`;
  }

  if (context.excerpts && context.excerpts.length > 0) {
    prompt += `\n=== RELEVANT CODE EXCERPTS FROM REPOSITORY SNAPSHOT ===\n`;
    for (const ex of context.excerpts) {
      prompt += `\n--- File: ${ex.path} (lines ${ex.startLine}-${ex.endLine}) ---\n\`\`\`\n${ex.content}\n\`\`\`\n`;
    }
  }

  return prompt;
}

/**
 * Offline structural intelligence synthesizer when no external LLM key is configured.
 */
function synthesizeOfflineAnswer({ repo, query, context }) {
  const repoName = `${repo.owner}/${repo.name}`;
  const lowerQuery = query.toLowerCase();

  let answer = `### Repository Intelligence: \`${repoName}\`\n\n`;

  if (context.matchedSymbols && context.matchedSymbols.length > 0) {
    const top = context.matchedSymbols[0];
    const path = top.metadata?.path || "Unknown";
    const start = top.metadata?.start_line || 1;
    const end = top.metadata?.end_line || start;
    const kind = top.metadata?.kind || top.type || "symbol";

    answer += `The ${kind} **\`${top.label}\`** is defined in [\`${path}\`](file:///${path}#L${start}-L${end}) at lines **${start}–${end}**.\n\n`;
  }

  if (context.excerpts && context.excerpts.length > 0) {
    answer += `#### Relevant Code Snippet:\n`;
    const ex = context.excerpts[0];
    const snippetLines = ex.content.split(/\r?\n/).slice(0, 25).join("\n");
    answer += `\`\`\`javascript\n// ${ex.path} (lines ${ex.startLine}-${ex.endLine})\n${snippetLines}\n\`\`\`\n\n`;
  }

  // Architecture summary
  const roles = Object.entries(context.rolesSummary || {});
  if (roles.length > 0) {
    answer += `#### Detected Architecture in this Repository:\n`;
    for (const [role, files] of roles.slice(0, 5)) {
      answer += `- **${role}**: ${files.slice(0, 4).map((f) => `\`${f}\``).join(", ")}\n`;
    }
    answer += "\n";
  }

  answer += `\n> 💡 **Tip:** To enable full conversational code generation with Groq, add \`GROQ_API_KEY=gsk_...\` in \`apps/backend/.env\`.`;

  return answer;
}

/**
 * Call an OpenAI-compatible API (Grok, OpenAI, Ollama, LM Studio).
 */
async function callOpenAiCompatible({ baseUrl, apiKey, model, systemPrompt, history = [], message, max_tokens = 2500, extraHeaders = {}, extraBody = {} }) {
  // Keep last 4 history messages to prevent token blowup in multi-turn chats
  const safeHistory = (history || []).slice(-4);
  const messages = [
    { role: "system", content: systemPrompt },
    ...safeHistory.map((h) => ({ role: h.role, content: h.content })),
    { role: "user", content: message },
  ];

  const headers = {
    "Content-Type": "application/json",
    ...extraHeaders,
  };
  if (apiKey) {
    headers["Authorization"] = `Bearer ${apiKey}`;
  }

  const endpoint = `${baseUrl.replace(/\/+$/, "")}/chat/completions`;
  const res = await fetch(endpoint, {
    method: "POST",
    headers,
    body: JSON.stringify({
      model,
      messages,
      temperature: 0.2,
      max_tokens,
      ...extraBody,
    }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`LLM provider error (${res.status}): ${errText.slice(0, 300)}`);
  }

  const json = await res.json();
  const choice = json?.choices?.[0];
  let text = choice?.message?.content;
  if (!text) {
    throw new Error("No response returned from LLM provider");
  }

  // If the model reached max_tokens before completing (finish_reason === "length"), automatically fetch the remainder so code is never cut off
  if (choice.finish_reason === "length") {
    try {
      const contRes = await fetch(endpoint, {
        method: "POST",
        headers,
        body: JSON.stringify({
          model,
          messages: [
            ...messages,
            { role: "assistant", content: text },
            { role: "user", content: "Continue generating the rest of the code and explanation from where you stopped. Do not repeat previous text." },
          ],
          temperature: 0.2,
          max_tokens: Math.min(max_tokens, 1500),
          ...extraBody,
        }),
      });
      if (contRes.ok) {
        const contJson = await contRes.json();
        const contText = contJson?.choices?.[0]?.message?.content;
        if (contText) {
          text = text + contText;
        }
      }
    } catch (contErr) {
      console.warn("Auto-continuation call failed:", contErr.message);
    }
  }

  return text;
}

/**
 * Call Google Gemini REST API.
 */
async function callGemini({ apiKey, model, systemPrompt, history, message }) {
  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${apiKey}`;

  const contents = [];
  if (systemPrompt) {
    contents.push({
      role: "user",
      parts: [{ text: systemPrompt }],
    });
    contents.push({
      role: "model",
      parts: [{ text: "Understood. I will act as the Senior Software Architect for this repository." }],
    });
  }

  for (const h of history) {
    contents.push({
      role: h.role === "assistant" ? "model" : "user",
      parts: [{ text: h.content }],
    });
  }

  contents.push({
    role: "user",
    parts: [{ text: message }],
  });

  const res = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ contents }),
  });

  if (!res.ok) {
    const errText = await res.text().catch(() => "");
    throw new Error(`Gemini API error (${res.status}): ${errText.slice(0, 300)}`);
  }

  const json = await res.json();
  const text = json?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (!text) throw new Error("Empty response from Gemini API");
  return text;
}

export const chatService = {
  findRelevantContext,
  buildSystemPrompt,

  /**
   * Main entry point to ask a question about a repository.
   */
  async askQuestion(clerkUserId, repositoryId, message, history = []) {
    if (!message || typeof message !== "string" || !message.trim()) {
      throw new BadRequestError("Message is required");
    }

    const user = await userRepository.findOrCreateByClerkId(clerkUserId);
    const repo = await repositoryRepository.findByIdAndUserId(repositoryId, user.id);
    if (!repo) {
      throw new NotFoundError("Repository not found");
    }

    // Retrieve latest snapshot
    const snapshots = typeof snapshotRepository.findManyByRepositoryId === "function"
      ? await snapshotRepository.findManyByRepositoryId(repo.id)
      : (typeof snapshotRepository.listByRepo === "function" ? await snapshotRepository.listByRepo(repo.id) : []);
    const latestSnapshot = snapshots[0] || {
      id: "none",
      commitSha: repo.lastSyncSha || "HEAD",
    };

    // Retrieve Graph IR if snapshot has completed AnalysisJob
    let graphIr = null;
    if (latestSnapshot.id !== "none") {
      const job = await jobRepository.findBySnapshotId(latestSnapshot.id);
      if (job?.resultJson) {
        try {
          const parsed = JSON.parse(job.resultJson);
          graphIr = parsed.graph || parsed;
        } catch {
          graphIr = null;
        }
      }
    }

    // Try to ensure local snapshot files exist on disk
    let snapshotDir = null;
    if (latestSnapshot.commitSha && latestSnapshot.commitSha !== "HEAD") {
      try {
        snapshotDir = await gitService.ensureSnapshotTree(repo.id, latestSnapshot.commitSha);
      } catch {
        snapshotDir = null;
      }
    }

    // Search and extract grounded context
    const context = await findRelevantContextWithDense(graphIr, message, snapshotDir);
    const systemPrompt = buildSystemPrompt({ repo, snapshot: latestSnapshot, context });

    let answer = "";
    let activeModel = "offline-structural-intelligence";

    const opencodeKey = process.env.OPENCODE_API_KEY;
    const groqKey = process.env.GROQ_API_KEY;
    const grokKey = process.env.GROK_API_KEY || process.env.XAI_API_KEY;
    const openAiKey = process.env.OPENAI_API_KEY;
    const geminiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
    const customBaseUrl = process.env.AI_BASE_URL || process.env.LOCAL_LLM_URL;

    try {
      if (opencodeKey) {
        // OpenCode Go: OpenAI-compatible. It asks clients to identify themselves
        // and send a stable session id per conversation (routing + prompt caching).
        activeModel = process.env.OPENCODE_MODEL || "deepseek-v4.1-flash";
        const reasoningEffort = process.env.OPENCODE_REASONING_EFFORT || "medium";
        const sessionId = crypto
          .createHash("sha256")
          .update(`${user.id}:${repo.id}`)
          .digest("hex")
          .slice(0, 32);
        answer = await callOpenAiCompatible({
          baseUrl: process.env.OPENCODE_BASE_URL || "https://opencode.ai/zen/go/v1",
          apiKey: opencodeKey,
          model: activeModel,
          systemPrompt,
          history,
          message,
          extraHeaders: {
            "User-Agent": "CodeAI-Assistant/1.0",
            "x-opencode-session": `codeai-${sessionId}`,
          },
          // Thinking tokens count against max_tokens, so leave room for both
          max_tokens: 6000,
          extraBody: reasoningEffort === "none" ? {} : { reasoning_effort: reasoningEffort },
        });
      } else if (groqKey) {
        const preferredModel = process.env.GROQ_MODEL || "openai/gpt-oss-120b";
        const candidateModels = [
          preferredModel,
          "openai/gpt-oss-120b",
          "openai/gpt-oss-20b",
          "qwen/qwen3.8-27b",
        ].filter((m, idx, arr) => arr.indexOf(m) === idx);

        let lastErr = null;
        for (const candidate of candidateModels) {
          try {
            activeModel = candidate;
            const maxTokensForModel = candidate.includes("qwen") ? 900 : 2500;
            answer = await callOpenAiCompatible({
              baseUrl: process.env.GROQ_BASE_URL || "https://api.groq.com/openai/v1",
              apiKey: groqKey,
              model: candidate,
              systemPrompt,
              history,
              message,
              max_tokens: maxTokensForModel,
            });
            lastErr = null;
            break;
          } catch (candErr) {
            lastErr = candErr;
            console.warn(`Groq model candidate ${candidate} failed (${candErr.message}), trying next candidate...`);
          }
        }
        if (lastErr && !answer) {
          throw lastErr;
        }
      } else if (grokKey) {
        activeModel = process.env.GROK_MODEL || "grok-2-latest";
        answer = await callOpenAiCompatible({
          baseUrl: process.env.GROK_BASE_URL || "https://api.x.ai/v1",
          apiKey: grokKey,
          model: activeModel,
          systemPrompt,
          history,
          message,
        });
      } else if (customBaseUrl) {
        activeModel = process.env.AI_MODEL || "qwen2.5-coder";
        answer = await callOpenAiCompatible({
          baseUrl: customBaseUrl,
          apiKey: openAiKey || "dummy",
          model: activeModel,
          systemPrompt,
          history,
          message,
        });
      } else if (openAiKey) {
        activeModel = process.env.OPENAI_MODEL || "gpt-4o-mini";
        answer = await callOpenAiCompatible({
          baseUrl: "https://api.openai.com/v1",
          apiKey: openAiKey,
          model: activeModel,
          systemPrompt,
          history,
          message,
        });
      } else if (geminiKey) {
        activeModel = process.env.GEMINI_MODEL || "gemini-2.0-flash";
        answer = await callGemini({
          apiKey: geminiKey,
          model: activeModel,
          systemPrompt,
          history,
          message,
        });
      } else {
        // Deterministic offline fallback
        answer = synthesizeOfflineAnswer({ repo, query: message, context });
      }
    } catch (err) {
      console.warn("External LLM provider call failed, falling back to structural answer:", err.message);
      answer = synthesizeOfflineAnswer({ repo, query: message, context }) +
        `\n\n*(Notice: LLM call encountered: ${err.message})*`;
    }

    // Default follow-up prompt suggestions
    const suggestedQuestions = [
      "Explain the architectural layers of this codebase",
      "Where are the API routes and controllers located?",
      "How is authentication handled in this project?",
      "What database models exist?",
    ];

    return {
      message: answer,
      citations: context.citations,
      suggestedQuestions,
      model: activeModel,
      snapshotSha: latestSnapshot.commitSha,
    };
  },
};

export default chatService;
