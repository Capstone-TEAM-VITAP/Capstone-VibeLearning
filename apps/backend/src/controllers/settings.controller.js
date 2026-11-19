import { settingsService } from "../services/settings.service.js";
import { successResponse } from "../utils/response.js";

/**
 * Controller for Settings & Workspace configuration endpoints.
 */
export const settingsController = {
  async getSettings(req, res, next) {
    try {
      const result = await settingsService.getSettings(req.userId);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  async updateSettings(req, res, next) {
    try {
      const result = await settingsService.updateSettings(req.userId, req.body);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },
};

export default settingsController;
