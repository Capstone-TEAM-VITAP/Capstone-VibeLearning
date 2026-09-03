import { projectService } from "../services/project.service.js";
import { successResponse, listResponse } from "../utils/response.js";

/**
 * Thin controller for Project endpoints
 */
export const projectController = {
  /**
   * GET /api/v1/projects
   */
  async getProjects(req, res, next) {
    try {
      const result = await projectService.listProjects(req.userId);
      return listResponse(res, result.projects, { total: result.total }, 200);
    } catch (error) {
      next(error);
    }
  },

  /**
   * GET /api/v1/projects/:id
   */
  async getProjectById(req, res, next) {
    try {
      const project = await projectService.getProjectById(req.userId, req.params.id);
      return successResponse(res, project, 200);
    } catch (error) {
      next(error);
    }
  },

  /**
   * POST /api/v1/projects
   */
  async createProject(req, res, next) {
    try {
      const project = await projectService.createProject(req.userId, req.body);
      return successResponse(res, project, 201);
    } catch (error) {
      next(error);
    }
  },

  /**
   * PATCH /api/v1/projects/:id
   */
  async updateProject(req, res, next) {
    try {
      const project = await projectService.updateProject(req.userId, req.params.id, req.body);
      return successResponse(res, project, 200);
    } catch (error) {
      next(error);
    }
  },

  /**
   * DELETE /api/v1/projects/:id
   */
  async deleteProject(req, res, next) {
    try {
      await projectService.deleteProject(req.userId, req.params.id);
      return res.status(204).send();
    } catch (error) {
      next(error);
    }
  },
};

export default projectController;
