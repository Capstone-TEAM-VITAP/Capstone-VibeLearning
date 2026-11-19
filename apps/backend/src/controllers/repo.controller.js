import { repoService } from "../services/repo.service.js";
import { listResponse, successResponse } from "../utils/response.js";

/**
 * Thin controller for Repository / Snapshot / Diff endpoints.
 */
export const repoController = {
  async listRepos(req, res, next) {
    try {
      const result = await repoService.listRepos(req.userId, req.query.projectId);
      return listResponse(res, result.repos, { total: result.total }, 200);
    } catch (error) {
      next(error);
    }
  },

  async getRepoById(req, res, next) {
    try {
      const repo = await repoService.getRepoById(req.userId, req.params.id);
      return successResponse(res, repo, 200);
    } catch (error) {
      next(error);
    }
  },

  async connectRepo(req, res, next) {
    try {
      const repo = await repoService.connectRepo(req.userId, req.body);
      return successResponse(res, repo, 201);
    } catch (error) {
      next(error);
    }
  },

  async deleteRepo(req, res, next) {
    try {
      await repoService.deleteRepo(req.userId, req.params.id);
      return res.status(204).send();
    } catch (error) {
      next(error);
    }
  },

  async updateRepo(req, res, next) {
    try {
      const repo = await repoService.updateRepo(req.userId, req.params.id, req.body);
      return successResponse(res, repo, 200);
    } catch (error) {
      next(error);
    }
  },

  async syncRepo(req, res, next) {
    try {
      const result = await repoService.syncRepo(req.userId, req.params.id, req.body);
      return successResponse(res, result, 201);
    } catch (error) {
      next(error);
    }
  },

  async listSnapshots(req, res, next) {
    try {
      const result = await repoService.listSnapshots(req.userId, req.params.id);
      return listResponse(res, result.snapshots, { total: result.total }, 200);
    } catch (error) {
      next(error);
    }
  },

  async getChangedFiles(req, res, next) {
    try {
      const result = await repoService.getChangedFiles(
        req.userId,
        req.params.id,
        req.params.sha,
        req.query.base
      );
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  async getDiff(req, res, next) {
    try {
      const result = await repoService.getDiff(
        req.userId,
        req.params.id,
        req.params.sha,
        req.query.base,
        req.query.path
      );
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  async getSnapshotGraph(req, res, next) {
    try {
      const graph = await repoService.getSnapshotGraph(
        req.userId,
        req.params.id,
        req.params.sha
      );
      if (req.query?.envelope === "true") {
        return successResponse(res, graph, 200);
      }
      return res.status(200).json(graph);
    } catch (error) {
      next(error);
    }
  },
};

export default repoController;

