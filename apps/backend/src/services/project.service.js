import { projectRepository } from "../repositories/project.repository.js";
import { userRepository } from "../repositories/user.repository.js";
import { NotFoundError } from "../utils/errors.js";

/**
 * Service orchestrating Project business logic and scoping to the authenticated Clerk user.
 */
export const projectService = {
  /**
   * Helper to resolve the internal User UUID from Clerk user ID
   * @param {string} clerkUserId
   */
  async _resolveUser(clerkUserId) {
    return userRepository.findOrCreateByClerkId(clerkUserId);
  },

  /**
   * List all projects belonging to the authenticated user
   * @param {string} clerkUserId
   */
  async listProjects(clerkUserId) {
    const user = await this._resolveUser(clerkUserId);
    const projects = await projectRepository.findManyByUserId(user.id);

    return {
      projects,
      total: projects.length,
    };
  },

  /**
   * Get a single project by ID for the authenticated user
   * @param {string} clerkUserId
   * @param {string} projectId
   */
  async getProjectById(clerkUserId, projectId) {
    const user = await this._resolveUser(clerkUserId);
    const project = await projectRepository.findByIdAndUserId(projectId, user.id);

    if (!project) {
      throw new NotFoundError("Project not found");
    }

    return project;
  },

  /**
   * Create a project for the authenticated user
   * @param {string} clerkUserId
   * @param {object} data - { name, description? }
   */
  async createProject(clerkUserId, data) {
    const user = await this._resolveUser(clerkUserId);

    return projectRepository.create({
      name: data.name,
      description: data.description,
      userId: user.id,
    });
  },

  /**
   * Update an existing project for the authenticated user
   * @param {string} clerkUserId
   * @param {string} projectId
   * @param {object} data - { name?, description? }
   */
  async updateProject(clerkUserId, projectId, data) {
    const user = await this._resolveUser(clerkUserId);

    // Verify ownership before updating
    const existing = await projectRepository.findByIdAndUserId(projectId, user.id);
    if (!existing) {
      throw new NotFoundError("Project not found");
    }

    return projectRepository.update(projectId, user.id, data);
  },

  /**
   * Delete a project for the authenticated user
   * @param {string} clerkUserId
   * @param {string} projectId
   */
  async deleteProject(clerkUserId, projectId) {
    const user = await this._resolveUser(clerkUserId);

    // Verify ownership before deleting
    const existing = await projectRepository.findByIdAndUserId(projectId, user.id);
    if (!existing) {
      throw new NotFoundError("Project not found");
    }

    await projectRepository.delete(projectId, user.id);
    return true;
  },
};

export default projectService;
