import { db } from "../config/db.js";

/**
 * Repository rows are owned directly via userId (plus optional project link).
 * All reads/writes stay scoped to the authenticated user's internal UUID.
 */
export const repositoryRepository = {
  async findManyByUserId(userId, projectId) {
    const where = projectId ? { userId, projectId } : { userId };
    return db.orm.public.Repository.where(where)
      .orderBy((r) => r.createdAt.desc())
      .all();
  },

  async findByIdAndUserId(id, userId) {
    return db.orm.public.Repository.where({ id, userId }).first();
  },

  async findByUserAndUrl(userId, repoUrl) {
    return db.orm.public.Repository.where({ userId, repoUrl }).first();
  },

  async create(data) {
    return db.orm.public.Repository.create({
      userId: data.userId,
      projectId: data.projectId ?? null,
      repoUrl: data.repoUrl,
      owner: data.owner,
      name: data.name,
      defaultBranch: data.defaultBranch || "main",
      lastSyncSha: data.lastSyncSha ?? null,
    });
  },

  async update(id, userId, data) {
    const payload = {};
    if (data.defaultBranch !== undefined) payload.defaultBranch = data.defaultBranch;
    if (data.lastSyncSha !== undefined) payload.lastSyncSha = data.lastSyncSha;
    if (data.projectId !== undefined) payload.projectId = data.projectId;
    return db.orm.public.Repository.where({ id, userId }).update(payload);
  },

  async delete(id, userId) {
    return db.orm.public.Repository.where({ id, userId }).delete();
  },
};

export default repositoryRepository;
