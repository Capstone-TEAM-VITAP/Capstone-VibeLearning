import express from "express";
import { requireAuth } from "../middleware/auth.middleware.js";
import { validate } from "../middleware/validate.middleware.js";
import { projectController } from "../controllers/project.controller.js";
import {
  createProjectSchema,
  updateProjectSchema,
  projectIdParamSchema,
} from "../validators/project.validator.js";

const router = express.Router();

// Enforce Clerk authentication across all project endpoints
router.use(requireAuth);

// GET /api/v1/projects - List authenticated user's projects
router.get("/", projectController.getProjects);

// POST /api/v1/projects - Create a new project for authenticated user
router.post(
  "/",
  validate({ body: createProjectSchema }),
  projectController.createProject
);

// GET /api/v1/projects/:id - Get a project by ID (scoped to authenticated user)
router.get(
  "/:id",
  validate({ params: projectIdParamSchema }),
  projectController.getProjectById
);

// PATCH /api/v1/projects/:id - Update a project by ID (scoped to authenticated user)
router.patch(
  "/:id",
  validate({ params: projectIdParamSchema, body: updateProjectSchema }),
  projectController.updateProject
);

// DELETE /api/v1/projects/:id - Delete a project by ID (scoped to authenticated user)
router.delete(
  "/:id",
  validate({ params: projectIdParamSchema }),
  projectController.deleteProject
);

export default router;
