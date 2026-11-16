import { jobRepository } from "../repositories/job.repository.js";
import { learningRepository } from "../repositories/learning.repository.js";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { findRelevantContextWithDense } from "./chat.service.js";
import gitService from "./git.service.js";
import { BadRequestError, NotFoundError } from "../utils/errors.js";

const VALID_DIFFICULTIES = ["beginner", "intermediate", "advanced"];
const DEFAULT_COUNT = 5;
const MAX_COUNT = 10;

/**
 * Learning flow (MCQ v1):
 *
 *   Other services (Graph IR, snapshots, excerpts)
 *     -> buildLearningPack (deterministic markdown)
 *     -> Groq generates MCQs grounded in the pack
 *     -> LearningSet + LearningQuestion rows persist the quiz
 *     -> submit() grades picks and persists LearningAttempt rows
 */

/**
 * Build the deterministic markdown "learning pack" from other services'
 * outputs. Pure function — no I/O, fully testable.
 */
export function buildLearningPack({ repo, snapshot, rolesSummary = {}, excerpts = [] }) {
  const repoName = `${repo.owner}/${repo.name}`;
  const commit = snapshot.commitSha ? snapshot.commitSha.slice(0, 7) : "HEAD";
  const lines = [];
  lines.push(`# Learning Pack: ${repoName}`);
  lines.push(`Commit: ${commit} (branch ${repo.defaultBranch || "main"})`);
  lines.push(``);
  lines.push(`## Architecture Roles`);
  const roles = Object.entries(rolesSummary);
  if (!roles.length) {
    lines.push(`No architecture roles classified for this snapshot.`);
  } else {
    for (const [role, files] of roles) {
      lines.push(`- ${role}: ${(files || []).slice(0, 8).join(", ")}`);
    }
  }
  lines.push(``);
  lines.push(`## Code Excerpts`);
  if (!excerpts.length) {
    lines.push(`No code excerpts available for this snapshot.`);
  } else {
    for (const ex of excerpts) {
      lines.push(`### File: ${ex.path} (lines ${ex.startLine}-${ex.endLine})`);
      lines.push("```");
      lines.push(ex.content);
      lines.push("```");
    }
  }
  return lines.join("\n");
}

/**
 * Parse and validate LLM-generated MCQ JSON. Every question must have
 * exactly 4 options, an answerIndex of 0-3, and (when given) a citation
 * pointing at a file present in the pack. Returns sanitized questions
 * or throws BadRequestError. Pure function.
 */
export function parseMcqResponse(text, knownPaths = []) {
  let parsed;
  try {
    const fenced = String(text).match(/```(?:json)?\s*([\s\S]*?)```/);
    parsed = JSON.parse((fenced ? fenced[1] : text).trim());
  } catch {
    throw new BadRequestError("Question generation returned invalid JSON");
  }
  const list = Array.isArray(parsed) ? parsed : parsed.questions;
  if (!Array.isArray(list) || !list.length) {
    throw new BadRequestError("Question generation returned no questions");
  }
  const known = new Set(knownPaths);
  return list.map((q, i) => {
    if (!q || typeof q.prompt !== "string" || !q.prompt.trim()) {
      throw new BadRequestError(`Question ${i + 1} is missing a prompt`);
    }
    if (!Array.isArray(q.options) || q.options.length !== 4 || q.options.some((o) => typeof o !== "string" || !o.trim())) {
      throw new BadRequestError(`Question ${i + 1} must have exactly 4 text options`);
    }
    if (!Number.isInteger(q.answerIndex) || q.answerIndex < 0 || q.answerIndex > 3) {
      throw new BadRequestError(`Question ${i + 1} has an invalid answerIndex`);
    }
    const citation = q.citation || {};
    if (citation.path && known.size && !known.has(citation.path)) {
      throw new BadRequestError(`Question ${i + 1} cites an unknown file`);
    }
    return {
      prompt: q.prompt.trim(),
      options: q.options.map((o) => o.trim()),
      answerIndex: q.answerIndex,
      explanation: typeof q.explanation === "string" ? q.explanation.trim() : null,
      citationPath: citation.path || null,
      citationStart: Number.isInteger(citation.startLine) ? citation.startLine : null,
      citationEnd: Number.isInteger(citation.endLine) ? citation.endLine : null,
    };
  });
}

/**
 * Real code symbols extracted from AST parsing (M3). Architecture role
 * nodes (route, unknown, config, ...), external imports and unresolved
 * references are NOT symbols and must never become quiz subjects.
 */
const CODE_SYMBOL_TYPES = new Set(["function", "class", "method", "variable", "constant"]);

/** Real Graph IR stringifies all metadata values — coerce line numbers back to Int. */
function toLineNumber(value) {
  const n = Number(value);
  return Number.isInteger(n) && n > 0 ? n : null;
}

/**
 * Deterministic offline fallback: build simple "where is it defined?"
 * MCQs straight from Graph IR code symbols. Pure function.
 */
export function buildOfflineQuestions(graphIr, count = DEFAULT_COUNT) {
  const nodes = Array.isArray(graphIr?.nodes) ? graphIr.nodes : [];
  const symbols = nodes.filter((n) => CODE_SYMBOL_TYPES.has(n.type));
  const fileSet = new Set(
    nodes.filter((n) => n.type === "file").map((n) => n.metadata?.path || n.label).filter(Boolean),
  );
  const files = [...fileSet];
  // A name defined in several files has no single correct answer, so it is never quizzed.
  const definingFiles = new Map();
  for (const sym of symbols) {
    const n = sym.metadata?.name || sym.label;
    if (!n) continue;
    if (!definingFiles.has(n)) definingFiles.set(n, new Set());
    definingFiles.get(n).add(sym.metadata?.path);
  }
  const questions = [];
  const asked = new Set();
  for (const sym of symbols) {
    if (questions.length >= count) break;
    const name = sym.metadata?.name || sym.label;
    if (!name || /[/\\]/.test(name)) continue; // never quiz on path-like labels
    if (name.length < 3 || asked.has(name) || definingFiles.get(name).size > 1) continue;
    const correctPath = sym.metadata?.path;
    if (!correctPath || !fileSet.has(correctPath)) continue;
    // Prefer same-extension distractors so options look plausible
    const ext = correctPath.includes(".") ? correctPath.slice(correctPath.lastIndexOf(".")) : "";
    const sameExt = files.filter((f) => f !== correctPath && ext && f.endsWith(ext));
    const others = files.filter((f) => f !== correctPath && !(ext && f.endsWith(ext)));
    const distractors = [...sameExt, ...others].slice(0, 3);
    if (distractors.length < 3) continue;
    const options = [correctPath, ...distractors];
    // Deterministic rotation by question index so answer positions cycle A, B, C, D
    const rotation = questions.length % 4;
    const rotated = options.map((_, idx) => options[(idx + rotation) % 4]);
    asked.add(name);
    const kind = sym.metadata?.kind || sym.type;
    questions.push({
      prompt: questions.length % 2 === 0
        ? `In which file is "${name}" defined?`
        : `Which file contains the ${kind} "${name}"?`,
      options: rotated,
      answerIndex: rotated.indexOf(correctPath),
      explanation: `"${name}" (${kind}) is defined in ${correctPath}.`,
      citationPath: correctPath,
      citationStart: toLineNumber(sym.metadata?.start_line),
      citationEnd: toLineNumber(sym.metadata?.end_line),
    });
  }
  return questions;
}

/**
 * Grade submitted picks against stored questions. Pure function.
 */
export function gradeAnswers(questions, picks) {
  const byId = new Map(questions.map((q) => [q.id, q]));
  let correct = 0;
  const results = picks.map((p) => {
    const q = byId.get(p.questionId);
    if (!q) throw new BadRequestError(`Unknown question: ${p.questionId}`);
    const isCorrect = p.pickedIndex === q.answerIndex;
    if (isCorrect) correct += 1;
    return { questionId: q.id, pickedIndex: p.pickedIndex, correct: isCorrect, answerIndex: q.answerIndex };
  });
  return { correct, total: picks.length, results };
}

/** Hide answers when serving a quiz for solving. */
function presentQuestion(q) {
  let options = [];
  try {
    options = JSON.parse(q.optionsJson);
  } catch {
    options = [];
  }
  return {
    id: q.id,
    prompt: q.prompt,
    options,
    citationPath: q.citationPath,
    citationStart: q.citationStart,
    citationEnd: q.citationEnd,
  };
}

/** Call the first configured LLM provider (Groq first, same chain as chat). */
async function callLlm(systemPrompt, userMessage, maxTokens = 2000) {
  const groqKey = process.env.GROQ_API_KEY;
  const grokKey = process.env.GROK_API_KEY || process.env.XAI_API_KEY;
  const openAiKey = process.env.OPENAI_API_KEY;
  const geminiKey = process.env.GEMINI_API_KEY || process.env.GOOGLE_API_KEY;
  const customBaseUrl = process.env.AI_BASE_URL || process.env.LOCAL_LLM_URL;

  async function openAiCompatible({ baseUrl, apiKey, model, max_tokens = maxTokens }) {
    const res = await fetch(`${baseUrl.replace(/\/+$/, "")}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(apiKey ? { Authorization: `Bearer ${apiKey}` } : {}),
      },
      body: JSON.stringify({
        model,
        messages: [
          { role: "system", content: systemPrompt },
          { role: "user", content: userMessage },
        ],
        temperature: 0.2,
        max_tokens,
      }),
    });
    if (!res.ok) {
      const errText = await res.text().catch(() => "");
      throw new Error(`LLM provider error (${res.status}): ${errText.slice(0, 300)}`);
    }
    const json = await res.json();
    const text = json?.choices?.[0]?.message?.content;
    if (!text) throw new Error("No response returned from LLM provider");
    return text;
  }

  if (groqKey) {
    return openAiCompatible({
      baseUrl: process.env.GROQ_BASE_URL || "https://api.groq.com/openai/v1",
      apiKey: groqKey,
      model: process.env.GROQ_MODEL || "llama-3.3-70b-versatile",
    });
  }
  if (grokKey) {
    return openAiCompatible({
      baseUrl: process.env.GROK_BASE_URL || "https://api.x.ai/v1",
      apiKey: grokKey,
      model: process.env.GROK_MODEL || "grok-2-latest",
    });
  }
  if (customBaseUrl) {
    return openAiCompatible({
      baseUrl: customBaseUrl,
      apiKey: process.env.AI_API_KEY || "dummy",
      model: process.env.AI_MODEL || "qwen2.5-coder",
    });
  }
  if (openAiKey) {
    return openAiCompatible({
      baseUrl: "https://api.openai.com/v1",
      apiKey: openAiKey,
      model: process.env.OPENAI_MODEL || "gpt-4o-mini",
    });
  }
  if (geminiKey) {
    const model = process.env.GEMINI_MODEL || "gemini-2.0-flash";
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${model}:generateContent?key=${geminiKey}`;
    const res = await fetch(endpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        contents: [
          { role: "user", parts: [{ text: systemPrompt }] },
          { role: "user", parts: [{ text: userMessage }] },
        ],
      }),
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
  return null; // No provider configured — caller uses the offline fallback.
}

function mcqSystemPrompt() {
  return `You generate multiple-choice questions that teach a developer how a real codebase works.
Return ONLY a JSON array. Each item: {"prompt": string, "options": [exactly 4 strings], "answerIndex": 0-3, "explanation": string, "citation": {"path": string, "startLine": number, "endLine": number}}.
Rules: every question must be answerable from the pack below; cite the file + lines that prove the answer; vary the correct option position; keep prompts under 280 characters.`;
}

export const learningService = {
  buildLearningPack,
  parseMcqResponse,
  buildOfflineQuestions,
  gradeAnswers,

  async _resolveRepo(clerkUserId, repositoryId) {
    const user = await userRepository.findOrCreateByClerkId(clerkUserId);
    const repo = await repositoryRepository.findByIdAndUserId(repositoryId, user.id);
    if (!repo) throw new NotFoundError("Repository not found");
    return { user, repo };
  },

  async _loadGraphContext(repo, topic) {
    const snapshots =
      typeof snapshotRepository.findManyByRepositoryId === "function"
        ? await snapshotRepository.findManyByRepositoryId(repo.id)
        : [];
    const latestSnapshot = snapshots[0] || { commitSha: repo.lastSyncSha || "HEAD" };
    let graphIr = null;
    if (latestSnapshot.id) {
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
    let snapshotDir = null;
    if (latestSnapshot.commitSha && latestSnapshot.commitSha !== "HEAD") {
      try {
        snapshotDir = await gitService.ensureSnapshotTree(repo.id, latestSnapshot.commitSha);
      } catch {
        snapshotDir = null;
      }
    }
    const context = await findRelevantContextWithDense(graphIr, topic || "repository overview", snapshotDir);
    return { snapshot: latestSnapshot, graphIr, context };
  },

  /**
   * Generate (or reuse) an MCQ set for a repo + topic + snapshot.
   * Idempotent: same user/repo/sha/topic/difficulty returns the saved set.
   */
  async generate(clerkUserId, repositoryId, { topic, difficulty = "beginner", count = DEFAULT_COUNT } = {}) {
    if (!topic || !topic.trim()) throw new BadRequestError("Topic is required");
    if (!VALID_DIFFICULTIES.includes(difficulty)) throw new BadRequestError("Invalid difficulty");
    const n = Math.min(Math.max(Number(count) || DEFAULT_COUNT, 1), MAX_COUNT);
    const { user, repo } = await this._resolveRepo(clerkUserId, repositoryId);
    const { snapshot, graphIr, context } = await this._loadGraphContext(repo, topic);
    const commitSha = snapshot.commitSha || "HEAD";

    const existing = await learningRepository.findSetByRepoTopicSha(user.id, repo.id, commitSha, topic.trim(), difficulty);
    if (existing) return this.getSet(clerkUserId, repositoryId, existing.id);

    const pack = buildLearningPack({ repo, snapshot, rolesSummary: context.rolesSummary, excerpts: context.excerpts });
    const knownPaths = (context.excerpts || []).map((e) => e.path);
    let questions = [];
    let engine = "offline";
    try {
      const raw = await callLlm(
        mcqSystemPrompt(),
        `LEARNING PACK:\n${pack}\n\nGenerate ${n} ${difficulty}-level multiple-choice questions about: ${topic.trim()}`,
      );
      if (raw) {
        questions = parseMcqResponse(raw, knownPaths).slice(0, n);
        engine = "llm";
      }
    } catch (err) {
      console.warn("Learning LLM generation failed, using offline fallback:", err.message);
    }
    if (!questions.length) {
      questions = buildOfflineQuestions(graphIr, n);
      if (!questions.length) throw new BadRequestError("Not enough repository context to generate questions yet — run analysis first");
    }

    const set = await learningRepository.createSet({
      userId: user.id,
      repositoryId: repo.id,
      commitSha,
      topic: topic.trim(),
      difficulty,
      questionCount: questions.length,
    });
    for (const q of questions) {
      await learningRepository.createQuestion({
        setId: set.id,
        prompt: q.prompt,
        optionsJson: q.options,
        answerIndex: q.answerIndex,
        explanation: q.explanation,
        citationPath: q.citationPath,
        citationStart: q.citationStart,
        citationEnd: q.citationEnd,
      });
    }
    const saved = await this.getSet(clerkUserId, repositoryId, set.id);
    return { ...saved, engine };
  },

  async listSets(clerkUserId, repositoryId) {
    const { user, repo } = await this._resolveRepo(clerkUserId, repositoryId);
    const sets = await learningRepository.findSetsByRepo(user.id, repo.id);
    const counts = await learningRepository.countAttemptsByUserForSets(
      user.id,
      sets.map((s) => s.id),
    );
    return sets.map((s) => ({ ...s, progress: counts[s.id] || { answered: 0, correct: 0, total: s.questionCount } }));
  },

  async getSet(clerkUserId, repositoryId, setId) {
    const { user, repo } = await this._resolveRepo(clerkUserId, repositoryId);
    const set = await learningRepository.findSetById(setId);
    if (!set || set.repositoryId !== repo.id || set.userId !== user.id) {
      throw new NotFoundError("Learning set not found");
    }
    const questions = await learningRepository.findQuestionsBySetId(set.id);
    const attempts = await learningRepository.findAttemptsByUser(
      user.id,
      questions.map((q) => q.id),
    );
    const latestAttempt = {};
    for (const a of attempts) latestAttempt[a.questionId] = a;
    return {
      ...set,
      questions: questions.map((q) => ({ ...presentQuestion(q), attempt: latestAttempt[q.id] || null })),
    };
  },

  /** Grade picks, persist attempts, return score + explanations. */
  async submit(clerkUserId, repositoryId, setId, picks) {
    if (!Array.isArray(picks) || !picks.length) throw new BadRequestError("Answers are required");
    const { user, repo } = await this._resolveRepo(clerkUserId, repositoryId);
    const set = await learningRepository.findSetById(setId);
    if (!set || set.repositoryId !== repo.id || set.userId !== user.id) {
      throw new NotFoundError("Learning set not found");
    }
    const questions = await learningRepository.findQuestionsBySetId(set.id);
    const { correct, total, results } = gradeAnswers(questions, picks);
    for (const r of results) {
      await learningRepository.createAttempt({
        questionId: r.questionId,
        userId: user.id,
        pickedIndex: r.pickedIndex,
        correct: r.correct,
      });
    }
    const byId = new Map(questions.map((q) => [q.id, q]));
    return {
      correct,
      total,
      results: results.map((r) => {
        const q = byId.get(r.questionId);
        let options = [];
        try {
          options = JSON.parse(q.optionsJson);
        } catch {
          options = [];
        }
        return {
          ...r,
          prompt: q.prompt,
          options,
          explanation: q.explanation,
          citationPath: q.citationPath,
          citationStart: q.citationStart,
          citationEnd: q.citationEnd,
        };
      }),
    };
  },

  async progress(clerkUserId, repositoryId) {
    const { user, repo } = await this._resolveRepo(clerkUserId, repositoryId);
    const sets = await learningRepository.findSetsByRepo(user.id, repo.id);
    const counts = await learningRepository.countAttemptsByUserForSets(
      user.id,
      sets.map((s) => s.id),
    );
    let answered = 0;
    let correct = 0;
    let total = 0;
    for (const s of sets) {
      const c = counts[s.id] || { answered: 0, correct: 0, total: 0 };
      answered += c.answered;
      correct += c.correct;
      total += c.total;
    }
    return { sets: sets.length, answered, correct, total };
  },
};

export default learningService;
