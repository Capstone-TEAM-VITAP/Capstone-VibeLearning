import { repoService } from "../services/repo.service.js";
import { parsePushPayload, verifySignature } from "../utils/github.js";
import { successResponse } from "../utils/response.js";

/**
 * Public GitHub webhook receiver (called by GitHub, not by users —
 * no Clerk auth; the HMAC signature is the authentication).
 */
export const webhookController = {
  async handleGithub(req, res, next) {
    try {
      const secret = process.env.GITHUB_WEBHOOK_SECRET;
      if (!secret) {
        console.error("[Webhook] GITHUB_WEBHOOK_SECRET is not configured");
        return res.status(500).json({ success: false, message: "Webhook not configured" });
      }

      const signature = req.get("X-Hub-Signature-256");
      if (!verifySignature(secret, req.rawBody, signature)) {
        return res.status(401).json({ success: false, message: "Invalid signature" });
      }

      const event = req.get("X-GitHub-Event");
      if (event === "ping") {
        return successResponse(res, { ignored: true, reason: "ping" }, 200);
      }

      const push = parsePushPayload(event, req.body);
      if (!push) {
        return successResponse(res, { ignored: true }, 200);
      }

      const result = await repoService.handlePushEvent(push);
      if (result.matched === 0) {
        return successResponse(res, { ignored: true, reason: "unknown repository" }, 200);
      }
      return successResponse(res, { matched: result.matched }, 200);
    } catch (error) {
      next(error);
    }
  },
};

export default webhookController;
