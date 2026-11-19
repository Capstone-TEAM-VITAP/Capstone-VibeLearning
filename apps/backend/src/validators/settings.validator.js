import { z } from "zod";

export const updateSettingsSchema = z.object({
  workspaceName: z.string().trim().min(1, "Workspace name cannot be empty").max(255).optional(),
  workspaceDescription: z.string().trim().max(1000).optional().nullable(),
  selectedRepositoryId: z.string().uuid("Invalid repository UUID format").optional().nullable(),
  defaultBranch: z.string().trim().min(1, "Default branch cannot be empty").max(255).optional(),
  preferences: z
    .object({
      theme: z.enum(["dark", "light", "system"]).optional(),
      autoSync: z.boolean().optional(),
      defaultView: z.string().trim().min(1).max(50).optional(),
      diffViewMode: z.enum(["split", "unified"]).optional(),
      codeIntelligence: z.enum(["standard", "deep", "fast"]).optional(),
      aiTips: z.boolean().optional(),
      telemetry: z.boolean().optional(),
    })
    .optional(),
});
