import { z } from "zod";

export const chatMessageSchema = z.object({
  message: z
    .string()
    .trim()
    .min(1, "Message must not be empty")
    .max(4000, "Message must be 4000 characters or fewer"),
  history: z
    .array(
      z.object({
        role: z.enum(["user", "assistant", "system"]),
        content: z.string().trim().min(1),
      })
    )
    .optional()
    .default([]),
});

export default {
  chatMessageSchema,
};
