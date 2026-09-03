import { db } from "../config/db.js";

/**
 * Project repository for Prisma 8 contract access on public.project.
 * Enforces strict user scoping on all database queries.
 */
export const projectRepository = {
  /**
   * Find all projects belonging to a user, ordered newest first
   * @param {string} userId - Internal user UUID
   */
  async findManyByUserId(userId) {
    return db.orm.public.Project
      .where({ userId })
      .orderBy((p) => p.createdAt.desc())
      .all();
  },

  /**
   * Find a specific project by id, scoped strictly to the owning user
   * @param {string} id - Project UUID
   * @param {string} userId - Internal user UUID
   */
  async findByIdAndUserId(id, userId) {
    return db.orm.public.Project.where({ id, userId }).first();
  },

  /**
   * Create a new project for a user
   * @param {object} data - { name, description?, userId }
   */
  async create(data) {
    return db.orm.public.Project.create({
      name: data.name,
      description: data.description ?? null,
      userId: data.userId,
    });
  },

  /**
   * Update a project, scoped strictly to the owning user
   * @param {string} id - Project UUID
   * @param {string} userId - Internal user UUID
   * @param {object} data - Update data fields
   */
  async update(id, userId, data) {
    const updatePayload = {};

    if (data.name !== undefined) {
      updatePayload.name = data.name;
    }
    if (data.description !== undefined) {
      updatePayload.description = data.description;
    }

    return db.orm.public.Project.where({ id, userId }).update(updatePayload);
  },

  /**
   * Delete a project, scoped strictly to the owning user
   * @param {string} id - Project UUID
   * @param {string} userId - Internal user UUID
   */
  async delete(id, userId) {
    return db.orm.public.Project.where({ id, userId }).delete();
  },
};

export default projectRepository;
