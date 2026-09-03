import { z } from "zod";

export const projectIdParamSchema = z.object({
  id: z.string().uuid({ message: "Invalid project ID format. Must be a valid UUID." }),
});

export const createProjectSchema = z.object({
  name: z
    .string({ required_error: "Project name is required" })
    .trim()
    .min(1, { message: "Project name must not be empty" })
    .max(255, { message: "Project name must not exceed 255 characters" }),
  description: z
    .string()
    .trim()
    .max(1000, { message: "Description must not exceed 1000 characters" })
    .optional()
    .nullable(),
});

export const updateProjectSchema = z
  .object({
    name: z
      .string()
      .trim()
      .min(1, { message: "Project name must not be empty" })
      .max(255, { message: "Project name must not exceed 255 characters" })
      .optional(),
    description: z
      .string()
      .trim()
      .max(1000, { message: "Description must not exceed 1000 characters" })
      .optional()
      .nullable(),
  })
  .refine(
    (data) => data.name !== undefined || data.description !== undefined,
    { message: "At least one field (name or description) must be provided for update" }
  );
