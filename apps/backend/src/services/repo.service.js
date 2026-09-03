import fs from "node:fs";
import { repositoryRepository } from "../repositories/repository.repository.js";
import { snapshotRepository } from "../repositories/snapshot.repository.js";
import { projectRepository } from "../repositories/project.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { ConflictError, NotFoundError } from "../utils/errors.js";
import { analysisService } from "./analysis.service.js";
import {
  ensureMirror,
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
};

export default repoService;
