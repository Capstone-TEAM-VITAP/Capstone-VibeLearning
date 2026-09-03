import { db } from "../config/db.js";

/**
 * Analysis job rows track async analysis per snapshot:
 * pending -> running -> done | failed.
 */
export const jobRepository = {
  async findBySnapshotId(snapshotId) {
    return db.orm.public.AnalysisJob.where({ snapshotId }).first();
  },

  async create(snapshotId) {
    return db.orm.public.AnalysisJob.create({
      snapshotId,
      status: "pending",
      attempts: 0,
    });
  },

  async findOrCreateBySnapshotId(snapshotId) {
    const existing = await this.findBySnapshotId(snapshotId);
    if (existing) return existing;
    try {
      return await this.create(snapshotId);
    } catch {
      // Lost a race with a concurrent enqueue — return the winner.
      return this.findBySnapshotId(snapshotId);
    }
  },

  async markRunning(id, attempts) {
    return db.orm.public.AnalysisJob.where({ id }).update({ status: "running", attempts });
  },

  async markDone(id, resultJson) {
    return db.orm.public.AnalysisJob.where({ id }).update({ status: "done", resultJson, error: null });
  },

  async markFailed(id, error) {
    return db.orm.public.AnalysisJob.where({ id }).update({ status: "failed", error });
  },
};

export default jobRepository;
