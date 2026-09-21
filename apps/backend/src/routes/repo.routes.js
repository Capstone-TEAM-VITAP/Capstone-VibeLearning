import express from "express";
import { z } from "zod";
import { requireAuth } from "../middleware/auth.middleware.js";
import { validate } from "../middleware/validate.middleware.js";
import { analysisController } from "../controllers/analysis.controller.js";
import { repoController } from "../controllers/repo.controller.js";
import {
  connectRepoSchema,
  diffQuerySchema,
  repoIdParamSchema,
  snapshotParamSchema,
  syncRepoSchema,
} from "../validators/repo.validator.js";

const router = express.Router();

// Enforce Clerk authentication across all repository endpoints
router.use(requireAuth);

// GET /api/v1/repos?projectId= — list connected repos (optionally by project)
router.get(
  "/",
  validate({ query: z.object({ projectId: z.string().uuid().optional() }) }),
  repoController.listRepos
);

// POST /api/v1/repos/connect — connect a GitHub repo + record HEAD snapshot
router.post("/connect", validate({ body: connectRepoSchema }), repoController.connectRepo);

// GET /api/v1/repos/:id — single connected repo (scoped to user)
router.get("/:id", validate({ params: repoIdParamSchema }), repoController.getRepoById);

// DELETE /api/v1/repos/:id — disconnect (scoped to user)
router.delete("/:id", validate({ params: repoIdParamSchema }), repoController.deleteRepo);

// POST /api/v1/repos/:id/sync — fetch + record a new snapshot
router.post(
  "/:id/sync",
  validate({ params: repoIdParamSchema, body: syncRepoSchema }),
  repoController.syncRepo
);

// GET /api/v1/repos/:id/snapshots — list snapshots newest first
router.get(
  "/:id/snapshots",
  validate({ params: repoIdParamSchema }),
  repoController.listSnapshots
);

// GET /api/v1/repos/:id/snapshots/:sha/files?base= — changed files (no hunks)
router.get(
  "/:id/snapshots/:sha/files",
  validate({ params: snapshotParamSchema, query: diffQuerySchema }),
  repoController.getChangedFiles
);

// GET /api/v1/repos/:id/snapshots/:sha/diff?base=&path= — full diff with hunks
router.get(
  "/:id/snapshots/:sha/diff",
  validate({ params: snapshotParamSchema, query: diffQuerySchema }),
  repoController.getDiff
);

// POST /api/v1/repos/:id/snapshots/:sha/analyze — run analysis now, wait for it
router.post(
  "/:id/snapshots/:sha/analyze",
  validate({ params: snapshotParamSchema }),
  analysisController.analyze
);

// GET /api/v1/repos/:id/snapshots/:sha/analysis — latest job + result
router.get(
  "/:id/snapshots/:sha/analysis",
  validate({ params: snapshotParamSchema }),
  analysisController.getAnalysis
);

// GET /api/v1/repos/:id/snapshots/:sha/graph — Graph IR for this snapshot
router.get(
  "/:id/snapshots/:sha/graph",
  validate({ params: snapshotParamSchema }),
  repoController.getSnapshotGraph
);

export default router;

