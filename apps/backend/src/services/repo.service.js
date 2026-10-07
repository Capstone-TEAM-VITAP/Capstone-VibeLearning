import fs from "node:fs";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { projectRepository } from "../repositories/project.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { ConflictError, GatewayTimeoutError, NotFoundError, ServiceUnavailableError } from "../utils/errors.js";
import { analysisService } from "./analysis.service.js";
import { jobRepository } from "../repositories/job.repository.js";
import { aiService, validateGraphIr } from "./ai.service.js";
import { db } from "../config/db.js";
import gitService, {
  ensureMirror,
  ensureSnapshotTree,
  getChangedFiles,
  getCommitMeta,
  getMirrorDir,
  getSnapshotDiff,
  parseRepoUrl,
  resolveSha,
} from "./git.service.js";


/**
 * Backend slice of the pipeline:
 * GitHub Repo -> Snapshot -> Changed Files/Lines.
 * Heavy analysis (AST, semantic search, ranking, LLM) consumes the
 * snapshot + diff contract produced here.
 */
export const repoService = {
  async _resolveUser(clerkUserId) {
    return userRepository.findOrCreateByClerkId(clerkUserId);
  },

  async _requireRepo(clerkUserId, repositoryId) {
    const user = await this._resolveUser(clerkUserId);
    const repo = await repositoryRepository.findByIdAndUserId(repositoryId, user.id);
    if (!repo) throw new NotFoundError("Repository not found");
    return { user, repo };
  },

  async listRepos(clerkUserId, projectId) {
    const user = await this._resolveUser(clerkUserId);
    if (projectId) {
      const project = await projectRepository.findByIdAndUserId(projectId, user.id);
      if (!project) throw new NotFoundError("Project not found");
    }
    const repos = await repositoryRepository.findManyByUserId(user.id, projectId);
    return { repos, total: repos.length };
  },

  async getRepoById(clerkUserId, repositoryId) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    return repo;
  },

  /**
   * Connect a GitHub repo: validate URL, mirror it, record HEAD snapshot.
   * Atomic — a failed clone leaves no orphan row.
   */
  async connectRepo(clerkUserId, data) {
    const user = await this._resolveUser(clerkUserId);
    const { owner, name, normalizedUrl } = parseRepoUrl(data.repoUrl);

    let projectId = null;
    if (data.projectId) {
      const project = await projectRepository.findByIdAndUserId(data.projectId, user.id);
      if (!project) throw new NotFoundError("Project not found");
      projectId = project.id;
    }

    const existing = await repositoryRepository.findByUserAndUrl(user.id, normalizedUrl);
    if (existing) throw new ConflictError("Repository is already connected");

    const repo = await repositoryRepository.create({
      userId: user.id,
      projectId,
      repoUrl: normalizedUrl,
      owner,
      name,
      defaultBranch: data.defaultBranch || "main",
    });

    try {
      await ensureMirror({
        repositoryId: repo.id,
        repoUrl: normalizedUrl,
        accessToken: data.accessToken,
        defaultBranch: repo.defaultBranch,
      });
      const headSha = await resolveSha(repo.id, `origin/${repo.defaultBranch}`).catch(() => resolveSha(repo.id, null));
      const meta = await getCommitMeta(repo.id, headSha);
      const snapshot = await snapshotRepository.create({
        repositoryId: repo.id,
        commitSha: meta.commitSha,
        baseSha: null,
        message: meta.message,
        authorName: meta.authorName,
        committedAt: meta.committedAt,
      });
      analysisService.enqueueAndDispatch(repo, snapshot);
      return repositoryRepository.update(repo.id, user.id, { lastSyncSha: meta.commitSha });
    } catch (err) {
      await repositoryRepository.delete(repo.id, user.id).catch(() => null);
      try {
        fs.rmSync(getMirrorDir(repo.id), { recursive: true, force: true });
      } catch {
        // ignore mirror cleanup errors
      }
      throw err;
    }
  },

  async deleteRepo(clerkUserId, repositoryId) {
    const { user } = await this._requireRepo(clerkUserId, repositoryId);
    await repositoryRepository.delete(repositoryId, user.id);
    try {
      fs.rmSync(getMirrorDir(repositoryId), { recursive: true, force: true });
    } catch {
      // mirror cache is best-effort
    }
    return true;
  },

  /**
   * Fetch latest refs and record a new snapshot at the resolved HEAD.
   */
  async syncRepo(clerkUserId, repositoryId, data = {}) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    return this.syncConnectedRepo(repo, data);
  },

  /**
   * Sync core keyed by repo row (no Clerk identity needed), shared by the
   * manual sync endpoint and GitHub push deliveries.
   */
  async syncConnectedRepo(repo, data = {}) {
    await ensureMirror({
      repositoryId: repo.id,
      repoUrl: repo.repoUrl,
      accessToken: data.accessToken,
      defaultBranch: repo.defaultBranch,
    });

    const headSha = data.ref
      ? await resolveSha(repo.id, data.ref)
      : await resolveSha(repo.id, `origin/${repo.defaultBranch}`).catch(() => resolveSha(repo.id, null));

    const already = await snapshotRepository.findByRepoAndSha(repo.id, headSha);
    if (already) {
      await repositoryRepository.update(repo.id, repo.userId, { lastSyncSha: headSha });
      const files = await getChangedFiles(repo.id, already.baseSha, headSha);
      return { snapshot: already, files, cached: true };
    }

    const baseSha = data.baseSha || repo.lastSyncSha || null;
    const meta = await getCommitMeta(repo.id, headSha);
    const diff = await getSnapshotDiff(repo.id, baseSha && baseSha !== headSha ? baseSha : null, headSha);

    const snapshot = await snapshotRepository.create({
      repositoryId: repo.id,
      commitSha: meta.commitSha,
      baseSha: baseSha && baseSha !== headSha ? baseSha : null,
      message: meta.message,
      authorName: meta.authorName,
      committedAt: meta.committedAt,
      fileCount: diff.fileCount,
      additions: diff.additions,
      deletions: diff.deletions,
    });
    await repositoryRepository.update(repo.id, repo.userId, { lastSyncSha: headSha });
    analysisService.enqueueAndDispatch(repo, snapshot);

    return {
      snapshot,
      files: diff.files.map(({ path, status, additions, deletions }) => ({ path, status, additions, deletions })),
      cached: false,
    };
  },

  /**
   * Handle a verified GitHub push: snapshot the pushed ref on every
   * connected row matching owner/name. Unknown repos are ignored (not an
   * error) so GitHub stops retrying the delivery.
   */
  async handlePushEvent({ owner, name, ref }) {
    const repos = await repositoryRepository.findManyByOwnerAndName(owner, name);
    const results = [];
    for (const repo of repos) {
      results.push(await this.syncConnectedRepo(repo, { ref }));
    }
    return { matched: repos.length, results };
  },

  async listSnapshots(clerkUserId, repositoryId) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    const snapshots = await snapshotRepository.findManyByRepositoryId(repo.id);
    return { snapshots, total: snapshots.length };
  },

  /** Lightweight changed-file list (no hunks) for the Changed Files step. */
  async getChangedFiles(clerkUserId, repositoryId, headSha, baseSha) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    const snapshot = await snapshotRepository.findByRepoAndSha(repo.id, headSha);
    if (!snapshot) throw new NotFoundError("Snapshot not found");
    const base = baseSha || snapshot.baseSha || null;
    await ensureMirror({ repositoryId: repo.id, repoUrl: repo.repoUrl, defaultBranch: repo.defaultBranch });
    const files = await getChangedFiles(repo.id, base && base !== headSha ? base : null, headSha);
    return { baseSha: base, headSha, fileCount: files.length, files };
  },

  /** Full unified diff with hunks + line numbers for AST/impact stages. */
  async getDiff(clerkUserId, repositoryId, headSha, baseSha, filePath) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    const snapshot = await snapshotRepository.findByRepoAndSha(repo.id, headSha);
    if (!snapshot) throw new NotFoundError("Snapshot not found");
    const base = baseSha || snapshot.baseSha || null;
    await ensureMirror({ repositoryId: repo.id, repoUrl: repo.repoUrl, defaultBranch: repo.defaultBranch });
    const paths = filePath ? [filePath] : [];
    return getSnapshotDiff(repo.id, base && base !== headSha ? base : null, headSha, paths);
  },

  /**
   * Return the canonical Graph IR for a specific repository snapshot.
   * Ensures the snapshot files are extracted on disk, runs analysis via AI service,
   * and caches the result in AnalysisJob.
   */
  async getSnapshotGraph(clerkUserId, repositoryId, commitSha) {
    const { repo } = await this._requireRepo(clerkUserId, repositoryId);
    const snapshot = await snapshotRepository.findByRepoAndSha(repo.id, commitSha);
    if (!snapshot) throw new NotFoundError("Snapshot not found");

    // 1. Return from cache if already computed
    let job = await jobRepository.findBySnapshotId(snapshot.id);
    if (job && job.resultJson) {
      try {
        const parsed = JSON.parse(job.resultJson);
        if (parsed.graph && parsed.graph.schema_version === "1.0") {
          return parsed.graph;
        }
        if (parsed.schema_version === "1.0") {
          return parsed;
        }
      } catch {
        // invalid cached JSON, recompute
      }
    }

    // Helper: poll boundedly for job completion
    const pollForRunningJob = async () => {
      const startTime = Date.now();
      const timeoutMs = Number(process.env.GRAPH_POLL_TIMEOUT_MS) || (process.env.NODE_ENV === "test" ? 400 : 15000);
      const intervalMs = Number(process.env.GRAPH_POLL_INTERVAL_MS) || (process.env.NODE_ENV === "test" ? 30 : 250);

      while (Date.now() - startTime < timeoutMs) {
        await new Promise((resolve) => setTimeout(resolve, intervalMs));
        const currentJob = await jobRepository.findBySnapshotId(snapshot.id);
        if (!currentJob) break;

        if (currentJob.resultJson) {
          try {
            const parsed = JSON.parse(currentJob.resultJson);
            if (parsed.graph && parsed.graph.schema_version === "1.0") {
              return parsed.graph;
            }
            if (parsed.schema_version === "1.0") {
              return parsed;
            }
          } catch {
            // invalid JSON, wait or proceed
          }
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
      if (latestJob && latestJob.resultJson) {
        try {
          const parsed = JSON.parse(latestJob.resultJson);
          if (parsed.graph && parsed.graph.schema_version === "1.0") return parsed.graph;
          if (parsed.schema_version === "1.0") return parsed;
        } catch {
          // ignore
        }
      }
      throw new ServiceUnavailableError("Analysis completed without producing a valid graph");
    };

    // 2. If an existing job is already "running", poll for completion as currently implemented
    if (job && job.status === "running") {
      return pollForRunningJob();
    }

    // 3. Handle no-job case safely: findOrCreateBySnapshotId ensures concurrent callers share/get the same row
    if (!job) {
      job = await jobRepository.findOrCreateBySnapshotId(snapshot.id);
      if (job && job.resultJson) {
        try {
          const parsed = JSON.parse(job.resultJson);
          if (parsed.graph && parsed.graph.schema_version === "1.0") return parsed.graph;
          if (parsed.schema_version === "1.0") return parsed;
        } catch {
          // ignore
        }
      }
      if (job && job.status === "running") {
        return pollForRunningJob();
      }
    }

    // 3b. Stale "done" (missing Graph IR, e.g. legacy stub) or "failed"
    // must be reset to "pending" so it can be atomically re-acquired.
    // Without this, tryAcquireRunning (WHERE status='pending') returns false
    // and the poll path throws "Analysis completed without producing a valid
    // graph" forever without ever calling the AI service.
    if (job && (job.status === "done" || job.status === "failed")) {
      await db.orm.public.AnalysisJob.where({ id: job.id, status: job.status }).update({ status: "pending" });
      job = await jobRepository.findBySnapshotId(snapshot.id);
    }

    // 4. Atomically try to acquire running status (conditional UPDATE: status='pending' -> status='running')
    const attempts = (job.attempts || 0) + 1;
    const acquired = typeof jobRepository.tryAcquireRunning === "function"
      ? await jobRepository.tryAcquireRunning(job.id, attempts)
      : true;

    if (!acquired) {
      // Another request acquired the job.
      // DO NOT call aiService.analyzeRepository(). Enter the bounded polling path instead.
      return pollForRunningJob();
    }

    // 5. This request is the analysis owner!
    // Perform: ensureSnapshotTree(), aiService.analyzeRepository(), markDone()
    const snapshotDir = await gitService.ensureSnapshotTree(repo.id, snapshot.commitSha);

    let graphIr;
    try {
      graphIr = await aiService.analyzeRepository(snapshotDir, repo.name);
      // Strictly validate Graph IR schema version 1.0 contract (mirrors analysis.service.dispatch)
      validateGraphIr(graphIr);
    } catch (err) {
      if (typeof jobRepository.markFailed === "function") {
        try {
          await jobRepository.markFailed(job.id, err.message?.slice(0, 500) || "Analysis failed");
        } catch {
          // ignore cleanup errors
        }
      }
      throw err;
    }

    // 6. Cache in AnalysisJob and mark done
    try {
      let existingResult = {};
      try {
        existingResult = job.resultJson ? JSON.parse(job.resultJson) : {};
      } catch {
        existingResult = {};
      }
      const updatedResult = { ...existingResult, graph: graphIr };
      await jobRepository.markDone(job.id, JSON.stringify(updatedResult));
    } catch (err) {
      console.error("[Graph Cache Warning]", err.message);
    }

    return graphIr;
  },
};

export default repoService;
