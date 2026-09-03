import { jobRepository } from "../repositories/job.repository.js";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { NotFoundError } from "../utils/errors.js";
import { getSnapshotDiff } from "./git.service.js";

/**
 * Analysis job orchestration.
 *
 * Contract for apps/ai-service (to be implemented there):
 *   POST {AI_SERVICE_URL}/v1/analyze
 *   { snapshot: { commitSha, baseSha, message }, files: [{ path, status, additions, deletions, hunks }] }
 *   -> 200 { summary: string, files: [{ path, impact, explanation }] }
 *
 * Until ai-service exists, dispatch falls back to the local stub engine
 * below (diff-stat summary). The stub is intentionally obvious so no one
 * mistakes it for real analysis.
 */

const AI_SERVICE_URL = process.env.AI_SERVICE_URL || null;
const AI_SERVICE_TIMEOUT_MS = 60000;

function scoreImpact({ status, additions, deletions }) {
  if (status === "D") return "high";
  const total = additions + deletions;
  if (total >= 100) return "high";
  if (total >= 20) return "medium";
  return "low";
}

async function runStubAnalyzer(repo, snapshot) {
  const diff = await getSnapshotDiff(
    repo.id,
    snapshot.baseSha && snapshot.baseSha !== snapshot.commitSha ? snapshot.baseSha : null,
    snapshot.commitSha
  );
  return {
    engine: "stub",
    summary: `${diff.fileCount} file(s) changed, +${diff.additions} −${diff.deletions}`,
    files: diff.files.map((f) => ({
      path: f.path,
      status: f.status,
      additions: f.additions,
      deletions: f.deletions,
      impact: scoreImpact(f),
      explanation: null,
    })),
    note: "Stub result from diff stats. Set AI_SERVICE_URL for LLM explanations.",
  };
}

async function callAiService(repo, snapshot) {
  const diff = await getSnapshotDiff(
    repo.id,
    snapshot.baseSha && snapshot.baseSha !== snapshot.commitSha ? snapshot.baseSha : null,
    snapshot.commitSha
  );
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), AI_SERVICE_TIMEOUT_MS);
  try {
    const res = await fetch(`${AI_SERVICE_URL}/v1/analyze`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        snapshot: { commitSha: snapshot.commitSha, baseSha: snapshot.baseSha, message: snapshot.message },
        files: diff.files,
      }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`ai-service responded ${res.status}`);
    return { engine: "ai-service", ...(await res.json()) };
  } finally {
    clearTimeout(timer);
  }
}

export const analysisService = {
  async _requireSnapshot(clerkUserId, repositoryId, commitSha) {
    const user = await userRepository.findOrCreateByClerkId(clerkUserId);
    const repo = await repositoryRepository.findByIdAndUserId(repositoryId, user.id);
    if (!repo) throw new NotFoundError("Repository not found");
    const snapshot = await snapshotRepository.findByRepoAndSha(repo.id, commitSha);
    if (!snapshot) throw new NotFoundError("Snapshot not found");
    return { user, repo, snapshot };
  },

  /** Idempotent enqueue: one job per snapshot, concurrent callers share it. */
  async enqueue(repo, snapshot) {
    return jobRepository.findOrCreateBySnapshotId(snapshot.id);
  },

  /** Run a job to completion (stub or ai-service). Throws on failure. */
  async dispatch(job, repo, snapshot) {
    await jobRepository.markRunning(job.id, (job.attempts || 0) + 1);
    try {
      const result = AI_SERVICE_URL ? await callAiService(repo, snapshot) : await runStubAnalyzer(repo, snapshot);
      return jobRepository.markDone(job.id, JSON.stringify(result));
    } catch (err) {
      const message = err?.message || "Analysis failed";
      await jobRepository.markFailed(job.id, message.slice(0, 500));
      throw err;
    }
  },

  /**
   * Enqueue without blocking the caller (used after sync). Dispatch runs
   * in-process; failures land on the job row, never in the sync response.
   */
  enqueueAndDispatch(repo, snapshot) {
    jobRepository
      .findOrCreateBySnapshotId(snapshot.id)
      .then((job) => {
        if (job.status === "done") return job;
        return this.dispatch(job, repo, snapshot).catch(() => null);
      })
      .catch(() => null);
  },

  /** Manual trigger: enqueue then wait for completion (stub is ms-fast). */
  async analyze(clerkUserId, repositoryId, commitSha) {
    const { repo, snapshot } = await this._requireSnapshot(clerkUserId, repositoryId, commitSha);
    const job = await jobRepository.findOrCreateBySnapshotId(snapshot.id);
    if (job.status === "done") return this._present(job);
    const finished = await this.dispatch(job, repo, snapshot);
    return this._present(finished);
  },

  async getAnalysis(clerkUserId, repositoryId, commitSha) {
    const { snapshot } = await this._requireSnapshot(clerkUserId, repositoryId, commitSha);
    const job = await jobRepository.findBySnapshotId(snapshot.id);
    if (!job) throw new NotFoundError("No analysis for this snapshot yet");
    return this._present(job);
  },

  _present(job) {
    let result = null;
    try {
      result = job.resultJson ? JSON.parse(job.resultJson) : null;
    } catch {
      result = null;
    }
    return {
      id: job.id,
      snapshotId: job.snapshotId,
      status: job.status,
      attempts: job.attempts,
      error: job.error,
      result,
      createdAt: job.createdAt,
      updatedAt: job.updatedAt,
    };
  },
};

export default analysisService;
