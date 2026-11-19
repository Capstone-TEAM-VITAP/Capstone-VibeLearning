import { routeService } from "../services/route.service.js";
import { successResponse } from "../utils/response.js";

/**
 * Controller for API & Route Map endpoints.
 */
export const routeController = {
  async listRoutes(req, res, next) {
    try {
      const { id, sha } = req.params;
      const filters = {
        method: req.query.method,
        status: req.query.status,
        controller: req.query.controller,
        search: req.query.search,
        refresh: req.query.refresh,
      };

      const result = await routeService.getRoutes(req.userId, id, sha, filters);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  async getRouteSummary(req, res, next) {
    try {
      const { id, sha } = req.params;
      const result = await routeService.getRouteSummary(req.userId, id, sha);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },

  async getRouteById(req, res, next) {
    try {
      const { id, sha, routeId } = req.params;
      const result = await routeService.getRouteById(req.userId, id, sha, routeId);
      return successResponse(res, result, 200);
    } catch (error) {
      next(error);
    }
  },
};

export default routeController;
