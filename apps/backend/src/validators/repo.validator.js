import { z } from "zod";

const shaSchema = z
  .string()
  .regex(/^[0-9a-f]{40}$/i, { message: "Must be a full 40-character commit SHA" });

const repoUrlSchema = z
  .string({ required_error: "repoUrl is required" })
  .trim()
  .min(1, { message: "repoUrl must not be empty" })
  .max(500, { message: "repoUrl must not exceed 500 characters" })
  .refine((v) => /^(https?:\/\/github\.com\/|git@github\.com:)/i.test(v), {
    message: "repoUrl must be a GitHub repository URL (https or ssh)",
  });

export const repoIdParamSchema = z.object({
  id: z.string().uuid({ message: "Invalid repository ID format. Must be a valid UUID." }),
});

export const snapshotParamSchema = z.object({
  id: z.string().uuid({ message: "Invalid repository ID format. Must be a valid UUID." }),
  sha: shaSchema,
});

export const connectRepoSchema = z.object({
  repoUrl: repoUrlSchema,
  projectId: z.string().uuid({ message: "Invalid project ID format. Must be a valid UUID." }).optional(),
  defaultBranch: z
    .string()
    .trim()
    .min(1)
    .max(255)
    .optional(),
  accessToken: z.string().trim().min(1).max(1000).optional(),
});

export const syncRepoSchema = z.object({
  ref: z.string().trim().min(1).max(255).optional(),
  baseSha: shaSchema.optional().nullable(),
  accessToken: z.string().trim().min(1).max(1000).optional(),
});

export const diffQuerySchema = z.object({
  base: shaSchema.optional(),
  path: z.string().trim().min(1).max(500).optional(),
});

export const intelligenceSummarySchema = z.object({
  commitSha: shaSchema,
  refresh: z.boolean().optional(),
});
