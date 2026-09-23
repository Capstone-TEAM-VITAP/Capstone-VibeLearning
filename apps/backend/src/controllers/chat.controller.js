import chatService from "../services/chat.service.js";
import { successResponse } from "../utils/response.js";

export const chatController = {
  async chat(req, res, next) {
    try {
      const { id: repositoryId } = req.params;
      const { message, history } = req.body;
      const data = await chatService.askQuestion(req.userId, repositoryId, message, history);
      return successResponse(res, data, 200);
    } catch (err) {
      return next(err);
    }
  },
};

export default chatController;
