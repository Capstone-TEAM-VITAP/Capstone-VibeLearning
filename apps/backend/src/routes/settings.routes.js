import express from "express";
import { requireAuth } from "../middleware/auth.middleware.js";
import { validate } from "../middleware/validate.middleware.js";
import { settingsController } from "../controllers/settings.controller.js";
import { updateSettingsSchema } from "../validators/settings.validator.js";

const router = express.Router();

// Enforce Clerk authentication across all settings endpoints
router.use(requireAuth);

// GET /api/v1/settings - Get settings and preferences for authenticated user
router.get("/", settingsController.getSettings);

// PATCH /api/v1/settings - Update settings and preferences
router.patch("/", validate({ body: updateSettingsSchema }), settingsController.updateSettings);

// PUT /api/v1/settings - Alias for updating settings
router.put("/", validate({ body: updateSettingsSchema }), settingsController.updateSettings);

export default router;
