import { z } from "zod";

export const learningSetIdParamSchema = z.object({
  id: z.string().uuid({ message: "Invalid repository ID format. Must be a valid UUID." }),
  setId: z.string().uuid({ message: "Invalid learning set ID format. Must be a valid UUID." }),
});

export const generateLearningSchema = z.object({
  topic: z
    .string()
    .trim()
    .min(1, "Topic must not be empty")
    .max(200, "Topic must be 200 characters or fewer"),
  difficulty: z.enum(["beginner", "intermediate", "advanced"]).optional().default("beginner"),
  count: z.number().int().min(1).max(10).optional().default(5),
});

export const submitLearningSchema = z.object({
  answers: z
    .array(
      z.object({
        questionId: z.string().uuid({ message: "Invalid question ID format. Must be a valid UUID." }),
        pickedIndex: z.number().int().min(0).max(3),
      }),
    )
    .min(1, "At least one answer is required")
    .max(10, "At most 10 answers per submission"),
});

export default {
  learningSetIdParamSchema,
  generateLearningSchema,
  submitLearningSchema,
};
