import { db } from "../config/db.js";
import { toInstant } from "../utils/time.js";

/**
 * Snapshot rows hang off a Repository; ownership is enforced in the
 * service layer by resolving the parent repository first.
 */
export const snapshotRepository = {
  async findManyByRepositoryId(repositoryId) {
    return db.orm.public.RepoSnapshot.where({ repositoryId })
      .orderBy((s) => s.createdAt.desc())
      .all();
  },

  async listByRepo(repositoryId) {
    return this.findManyByRepositoryId(repositoryId);
  },

  async findByRepoAndSha(repositoryId, commitSha) {
    return db.orm.public.RepoSnapshot.where({ repositoryId, commitSha }).first();
  },

  async create(data) {
    return db.orm.public.RepoSnapshot.create({
      repositoryId: data.repositoryId,
      commitSha: data.commitSha,
      baseSha: data.baseSha ?? null,
      message: data.message ?? null,
      authorName: data.authorName ?? null,
      committedAt: toInstant(data.committedAt),
      fileCount: data.fileCount ?? 0,
      additions: data.additions ?? 0,
      deletions: data.deletions ?? 0,
    });
  },

  async updateStats(id, { fileCount, additions, deletions }) {
    return db.orm.public.RepoSnapshot.where({ id }).update({ fileCount, additions, deletions });
  },
};

export default snapshotRepository;
