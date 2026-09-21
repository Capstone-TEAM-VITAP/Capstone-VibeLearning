import { db } from "../config/db.js";
import { jobRepository } from "../repositories/job.repository.js";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import {
  GatewayTimeoutError,
  NotFoundError,
  ServiceUnavailableError,
} from "../utils/errors.js";
import gitService from "./git.service.js";
import { aiService, validateGraphIr } from "./ai.service.js";

/**
 * Analysis job orchestration.
 *
 * Runs full static analysis via the Python AI Service (POST /analyze)
 * and produces canonical CodeGraph IR conforming to schema version 1.0.
 */

function scoreImpact({ status, additions, deletions }) {
  if (status === "D") return "high";
  const total = additions + deletions;
  if (total >= 100) return "high";
  if (total >= 20) return "medium";
  return "low";
}

async function runStubAnalyzer(repo, snapshot) {
  const diff = await gitService.getSnapshotDiff(
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
    note: "Stub result from diff stats.",
  };
}

export function hasValidGraph(job) {
  if (!job || job.status !== "done" || !job.resultJson) return false;
  try {
    const parsed = typeof job.resultJson === "string" ? JSON.parse(job.resultJson) : job.resultJson;
    if (parsed?.graph?.schema_version === "1.0") return true;
    if (parsed?.schema_version === "1.0") return true;
    return false;
  } catch {
    return false;
  }
}

export const analysisService = {
  hasValidGraph,

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

  /** Run a job to completion via ai-service. Throws on failure. */
  async dispatch(job, repo, snapshot) {
    const attempts = (job.attempts || 0) + 1;
    await jobRepository.markRunning(job.id, attempts);
    try {
      const snapshotDir = await gitService.ensureSnapshotTree(repo.id, snapshot.commitSha);
      const graphIr = await aiService.analyzeRepository(snapshotDir, repo.name);

      // Strictly validate Graph IR schema version 1.0 contract
      validateGraphIr(graphIr);

      let diffStats = {};
      try {
        diffStats = await runStubAnalyzer(repo, snapshot);
      } catch {
        diffStats = {
          summary: `Static analysis completed for ${repo.name}`,
          files: [],
        };
      }

      const result = {
        ...diffStats,
        engine: "ai-service",
        graph: graphIr,
      };

      await jobRepository.markDone(job.id, JSON.stringify(result));
      return jobRepository.findBySnapshotId(snapshot.id);
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
        if (hasValidGraph(job)) return job;
        return this.dispatch(job, repo, snapshot).catch(() => null);
      })
      .catch(() => null);
  },

  /** Manual trigger: enqueue then wait for completion. */
  async analyze(clerkUserId, repositoryId, commitSha) {
    const { repo, snapshot } = await this._requireSnapshot(clerkUserId, repositoryId, commitSha);
    let job = await jobRepository.findOrCreateBySnapshotId(snapshot.id);

    // 1. Return from cache if already computed valid canonical Graph IR
    if (hasValidGraph(job)) {
      return this._present(job);
    }

    // Helper: poll boundedly for job completion if another request acquired the job
    const pollForRunningJob = async () => {
      const timeoutMs = Number(process.env.GRAPH_POLL_TIMEOUT_MS) || (process.env.NODE_ENV === "test" ? 400 : 15000);
      const intervalMs = Number(process.env.GRAPH_POLL_INTERVAL_MS) || (process.env.NODE_ENV === "test" ? 30 : 250);
      const startTime = Date.now();

      while (Date.now() - startTime < timeoutMs) {
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
        const currentJob = await jobRepository.findBySnapshotId(snapshot.id);
        if (!currentJob) break;

        if (hasValidGraph(currentJob)) {
          return currentJob;
        }

        if (currentJob.status === "failed") {
          throw new ServiceUnavailableError(currentJob.error || "Analysis job failed");
        }

        if (currentJob.status === "done") {
          break;
        }
      }

      const latestJob = await jobRepository.findBySnapshotId(snapshot.id);
      if (latestJob && latestJob.status === "running") {
        throw new GatewayTimeoutError("Analysis is currently in progress. Timed out waiting for completion");
      }
      if (latestJob && hasValidGraph(latestJob)) {
        return latestJob;
      }
      throw new ServiceUnavailableError("Analysis completed without producing a valid graph");
    };

    // 2. If an existing job is already "running", poll for completion
    if (job.status === "running") {
      const finishedJob = await pollForRunningJob();
      return this._present(finishedJob);
    }

    // 3. If stale "done" (missing Graph IR) or "failed", reset to "pending" so it can be atomically acquired
    if (job.status !== "pending") {
      await db.orm.public.AnalysisJob.where({ id: job.id, status: job.status }).update({ status: "pending" });
      job = await jobRepository.findBySnapshotId(snapshot.id);
    }

    // 4. Atomically try to acquire running status (conditional UPDATE: status='pending' -> status='running')
    const attempts = (job.attempts || 0) + 1;
    const acquired = typeof jobRepository.tryAcquireRunning === "function"
      ? await jobRepository.tryAcquireRunning(job.id, attempts)
      : true;

    if (!acquired) {
      // Lost race to concurrent caller — enter bounded polling path
      const finishedJob = await pollForRunningJob();
      return this._present(finishedJob);
    }

    // 5. This request acquired the lock: dispatch analysis
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
