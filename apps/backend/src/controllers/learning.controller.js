import learningService from "../services/learning.service.js";
import { listResponse, successResponse } from "../utils/response.js";

export const learningController = {
  async generate(req, res, next) {
    try {
      const { id: repositoryId } = req.params;
      const data = await learningService.generate(req.userId, repositoryId, req.body);
      return successResponse(res, data, 201);
    } catch (err) {
      return next(err);
    }
  },

  async generateDiff(req, res, next) {
    try {
      const { id: repositoryId } = req.params;
      const data = await learningService.generateDiff(req.userId, repositoryId, req.body);
      return successResponse(res, data, 201);
    } catch (err) {
      return next(err);
    }
  },

  async listSets(req, res, next) {
    try {
      const { id: repositoryId } = req.params;
      const data = await learningService.listSets(req.userId, repositoryId);
      return listResponse(res, data, { total: data.length });
    } catch (err) {
      return next(err);
    }
  },

  async getSet(req, res, next) {
    try {
      const { id: repositoryId, setId } = req.params;
      const data = await learningService.getSet(req.userId, repositoryId, setId);
      return successResponse(res, data, 200);
    } catch (err) {
      return next(err);
    }
  },

  async submit(req, res, next) {
    try {
      const { id: repositoryId, setId } = req.params;
      const data = await learningService.submit(req.userId, repositoryId, setId, req.body.answers);
      return successResponse(res, data, 200);
    } catch (err) {
      return next(err);
    }
  },

  async progress(req, res, next) {
    try {
      const { id: repositoryId } = req.params;
      const data = await learningService.progress(req.userId, repositoryId);
      return successResponse(res, data, 200);
    } catch (err) {
      return next(err);
    }
  },
};

export default learningController;
