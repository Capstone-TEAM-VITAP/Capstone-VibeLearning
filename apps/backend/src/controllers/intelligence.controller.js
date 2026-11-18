import intelligenceService from "../services/intelligence.service.js";
import { successResponse } from "../utils/response.js";

export const intelligenceController = {
  async summary(req, res, next) {
    try {
      const { id } = req.params;
      const { commitSha, refresh } = req.body;
      const data = await intelligenceService.getSummary(req.userId, id, commitSha, { refresh: Boolean(refresh) });
      return successResponse(res, data, 200);
    } catch (err) {
      return next(err);
    }
  },
};

export default intelligenceController;
