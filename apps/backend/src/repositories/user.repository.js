import { db } from "../config/db.js";

/**
 * User repository for Prisma 8 contract access on public.user
 */
export const userRepository = {
  /**
   * Find a user record by Clerk user ID
   * @param {string} clerkUserId
   */
  async findByClerkId(clerkUserId) {
    return db.orm.public.User.where({ clerkUserId }).first();
  },

  /**
   * Find a user record by internal UUID id
   * @param {string} id
   */
  async findById(id) {
    return db.orm.public.User.where({ id }).first();
  },

  /**
   * Create a new user record
   * @param {object} userData - { clerkUserId, email?, name? }
   */
  async create(userData) {
    return db.orm.public.User.create({
      clerkUserId: userData.clerkUserId,
      email: userData.email || null,
      name: userData.name || null,
    });
  },

  /**
   * Resolve an internal application User record by Clerk ID,
   * creating one just-in-time if it does not yet exist.
   * @param {string} clerkUserId
   * @param {object} profileData - Optional { email, name }
   */
  async findOrCreateByClerkId(clerkUserId, profileData = {}) {
    const existing = await this.findByClerkId(clerkUserId);
    if (existing) {
      return existing;
    }

    return this.create({
      clerkUserId,
      email: profileData.email,
      name: profileData.name,
    });
  },
};

export default userRepository;
