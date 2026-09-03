import { analysisService } from "../services/analysis.service.js";
import { successResponse } from "../utils/response.js";

/**
 * Thin controller for analysis trigger + result endpoints.
 */
export const analysisController = {
  /**
   * POST /api/v1/repos/:id/snapshots/:sha/analyze
   */
  async analyze(req, res, next) {
    try {
      const result = await analysisService.analyze(req.userId, req.params.id, req.params.sha);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  /**
   * GET /api/v1/repos/:id/snapshots/:sha/analysis
   */
  async getAnalysis(req, res, next) {
    try {
      const result = await analysisService.getAnalysis(req.userId, req.params.id, req.params.sha);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },
};

export default analysisController;
