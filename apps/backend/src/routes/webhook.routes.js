import express from "express";
import { webhookController } from "../controllers/webhook.controller.js";

const router = express.Router();

// Public: GitHub signs deliveries with GITHUB_WEBHOOK_SECRET instead of Clerk.
// No requireAuth, no Zod body schema — GitHub's payload shape is parsed in code.
router.post("/github", webhookController.handleGithub);

export default router;
