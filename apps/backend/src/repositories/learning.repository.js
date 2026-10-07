import { db } from "../config/db.js";

/**
 * Learning rows persist generated MCQ quizzes and user attempts:
 * LearningSet -> LearningQuestion[] -> LearningAttempt[].
 * Ownership is enforced in the service layer by resolving the
 * parent repository (user-scoped) first.
 */
export const learningRepository = {
  // --- Sets ---
  async findSetById(setId) {
    return db.orm.public.LearningSet.where({ id: setId }).first();
  },

  async findSetsByRepo(userId, repositoryId) {
    return db.orm.public.LearningSet.where({ userId, repositoryId })
      .orderBy((s) => s.createdAt.desc())
      .all();
  },

  async findSetByRepoTopicSha(userId, repositoryId, commitSha, topic, difficulty) {
    return db.orm.public.LearningSet.where({
      userId,
      repositoryId,
      commitSha,
      topic,
      difficulty,
    }).first();
  },

  async createSet(data) {
    return db.orm.public.LearningSet.create({
      userId: data.userId,
      repositoryId: data.repositoryId,
      commitSha: data.commitSha,
      topic: data.topic,
      difficulty: data.difficulty ?? "beginner",
      questionCount: data.questionCount ?? 0,
    });
  },

  async updateSetCount(setId, questionCount) {
    return db.orm.public.LearningSet.where({ id: setId }).update({ questionCount });
  },

  // --- Questions ---
  async findQuestionsBySetId(setId) {
    return db.orm.public.LearningQuestion.where({ setId }).all();
  },

  async findQuestionById(questionId) {
    return db.orm.public.LearningQuestion.where({ id: questionId }).first();
  },

  async createQuestion(data) {
    return db.orm.public.LearningQuestion.create({
      setId: data.setId,
      prompt: data.prompt,
      optionsJson:
        typeof data.optionsJson === "string"
          ? data.optionsJson
          : JSON.stringify(data.optionsJson ?? []),
      answerIndex: data.answerIndex ?? 0,
      explanation: data.explanation ?? null,
      citationPath: data.citationPath ?? null,
      citationStart: data.citationStart ?? null,
      citationEnd: data.citationEnd ?? null,
    });
  },

  // --- Attempts ---
  async createAttempt(data) {
    return db.orm.public.LearningAttempt.create({
      questionId: data.questionId,
      userId: data.userId,
      pickedIndex: data.pickedIndex,
      correct: data.correct ? 1 : 0,
    });
  },

  async findAttemptsByUser(userId, questionIds) {
    if (!questionIds.length) return [];
    const attempts = [];
    for (const questionId of questionIds) {
      const rows = await db.orm.public.LearningAttempt.where({ userId, questionId }).all();
      attempts.push(...rows);
    }
    return attempts;
  },

  async countAttemptsByUserForSets(userId, setIds) {
    const counts = {};
    for (const setId of setIds) {
      const questions = await this.findQuestionsBySetId(setId);
      let correct = 0;
      let answered = 0;
      for (const q of questions) {
        const rows = await db.orm.public.LearningAttempt.where({ userId, questionId: q.id }).all();
        if (rows.length) {
          answered += 1;
          if (rows.some((r) => r.correct === 1)) correct += 1;
        }
      }
      counts[setId] = { answered, correct, total: questions.length };
    }
    return counts;
  },
};

export default learningRepository;
