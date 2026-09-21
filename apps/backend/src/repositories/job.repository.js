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

  /**
   * Atomically transition a job from "pending" to "running".
   * Returns true if this request acquired the job, false if already acquired/running/done.
   * Single atomic conditional UPDATE: WHERE id = $id AND status = 'pending'.
   * Uses updateAndCount() to execute a single atomic UPDATE statement with no preceding SELECT.
   */
  async tryAcquireRunning(id, attempts = 1) {
    const res = await db.orm.public.AnalysisJob.where({ id, status: "pending" }).updateAndCount({
      status: "running",
      attempts,
    });
    // In @prisma/orm-postgres, updateAndCount returns affectedRows (number) directly
    if (typeof res === "number") return res === 1;
    if (res && typeof res.affectedRows === "number") return res.affectedRows === 1;
    return false;
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
