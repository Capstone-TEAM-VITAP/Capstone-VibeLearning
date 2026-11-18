import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  findRelevantContext,
  buildSystemPrompt,
  chatService,
} from "../src/services/chat.service.js";
import { chatController } from "../src/controllers/chat.controller.js";
import { repositoryRepository } from "../src/repositories/repository.repository.js";
import { snapshotRepository } from "../src/repositories/snapshot.repository.js";
import { jobRepository } from "../src/repositories/job.repository.js";
import { userRepository } from "../src/repositories/user.repository.js";
import { BadRequestError, NotFoundError } from "../src/utils/errors.js";

const SAMPLE_GRAPH_IR = {
  schema_version: "1.0",
  repository: { id: "repo:codeai", name: "codeai" },
  nodes: [
    {
      id: "file:src/routes/auth.routes.js",
      type: "file",
      label: "auth.routes.js",
      architecture_role: "ROUTE",
      metadata: { path: "src/routes/auth.routes.js" },
    },
    {
      id: "file:src/middleware/auth.middleware.js",
      type: "file",
      label: "auth.middleware.js",
      architecture_role: "MIDDLEWARE",
      metadata: { path: "src/middleware/auth.middleware.js" },
    },
    {
      id: "symbol:src/middleware/auth.middleware.js:requireAuth:10:0",
      type: "function",
      label: "requireAuth",
      metadata: {
        name: "requireAuth",
        path: "src/middleware/auth.middleware.js",
        start_line: 10,
        end_line: 25,
      },
    },
    {
      id: "file:src/services/git.service.js",
      type: "file",
      label: "git.service.js",
      architecture_role: "SERVICE",
      metadata: { path: "src/services/git.service.js" },
    },
    {
      id: "symbol:src/services/git.service.js:ensureSnapshotTree:229:0",
      type: "function",
      label: "ensureSnapshotTree",
      metadata: {
        name: "ensureSnapshotTree",
        path: "src/services/git.service.js",
        start_line: 229,
        end_line: 270,
      },
    },
  ],
  edges: [],
};

describe("Repository AI Chat Service", () => {
  it("findRelevantContext matches specific symbol by name", () => {
    const ctx = findRelevantContext(SAMPLE_GRAPH_IR, "Where is ensureSnapshotTree defined?");
    assert.ok(ctx.matchedSymbols.length > 0);
    assert.equal(ctx.matchedSymbols[0].label, "ensureSnapshotTree");
    assert.equal(ctx.matchedSymbols[0].metadata.path, "src/services/git.service.js");
    assert.equal(ctx.matchedSymbols[0].metadata.start_line, 229);
  });

  it("findRelevantContext identifies architectural roles for auth query", () => {
    const ctx = findRelevantContext(SAMPLE_GRAPH_IR, "How does authentication work?");
    assert.ok(ctx.rolesSummary.ROUTE || ctx.rolesSummary.MIDDLEWARE);
    assert.ok(ctx.matchedSymbols.some((s) => s.label === "requireAuth"));
  });

  it("buildSystemPrompt includes repository metadata and roles", () => {
    const repo = { owner: "test-owner", name: "test-repo", defaultBranch: "main" };
    const snapshot = { commitSha: "abc1234567890" };
    const context = {
      rolesSummary: {
        ROUTE: ["src/routes/auth.routes.js"],
        SERVICE: ["src/services/git.service.js"],
      },
      excerpts: [],
    };

    const prompt = buildSystemPrompt({ repo, snapshot, context });
    assert.match(prompt, /test-owner\/test-repo/);
    assert.match(prompt, /abc1234/);
    assert.match(prompt, /ROUTE: src\/routes\/auth\.routes\.js/);
  });

  it("askQuestion validates non-empty message", async () => {
    await assert.rejects(
      () => chatService.askQuestion("user_123", "repo_abc", "   "),
      (err) => {
        assert.ok(err instanceof BadRequestError);
        assert.match(err.message, /Message is required/);
        return true;
      }
    );
  });

  it("askQuestion enforces repository ownership check", async () => {
    const origFindUser = userRepository.findOrCreateByClerkId;
    const origFindRepo = repositoryRepository.findByIdAndUserId;

    userRepository.findOrCreateByClerkId = async () => ({ id: "u1" });
    repositoryRepository.findByIdAndUserId = async () => null;

    try {
      await assert.rejects(
        () => chatService.askQuestion("user_123", "unknown_repo", "Where is the code?"),
        (err) => {
          assert.ok(err instanceof NotFoundError);
          assert.match(err.message, /Repository not found/);
          return true;
        }
      );
    } finally {
      userRepository.findOrCreateByClerkId = origFindUser;
      repositoryRepository.findByIdAndUserId = origFindRepo;
    }
  });

  it("askQuestion synthesizes offline structural intelligence when no API key is set", async () => {
    const origFindUser = userRepository.findOrCreateByClerkId;
    const origFindRepo = repositoryRepository.findByIdAndUserId;
    const origListSnapshots = snapshotRepository.listByRepo;
    const origFindMany = snapshotRepository.findManyByRepositoryId;
    const origFindJob = jobRepository.findBySnapshotId;

    const prevGroqKey = process.env.GROQ_API_KEY;
    const prevGrokKey = process.env.GROK_API_KEY;
    const prevOpenAiKey = process.env.OPENAI_API_KEY;
    const prevGeminiKey = process.env.GEMINI_API_KEY;
    delete process.env.GROQ_API_KEY;
    delete process.env.GROK_API_KEY;
    delete process.env.OPENAI_API_KEY;
    delete process.env.GEMINI_API_KEY;

    userRepository.findOrCreateByClerkId = async () => ({ id: "u1" });
    repositoryRepository.findByIdAndUserId = async () => ({
      id: "repo_1",
      owner: "acme",
      name: "super-app",
      defaultBranch: "main",
      lastSyncSha: "sha123",
    });
    snapshotRepository.listByRepo = async () => [{ id: "snap_1", commitSha: "sha123" }];
    snapshotRepository.findManyByRepositoryId = async () => [{ id: "snap_1", commitSha: "sha123" }];
    jobRepository.findBySnapshotId = async () => ({
      status: "done",
      resultJson: JSON.stringify({ graph: SAMPLE_GRAPH_IR }),
    });

    try {
      const res = await chatService.askQuestion(
        "user_123",
        "repo_1",
        "Where is ensureSnapshotTree defined?"
      );

      assert.equal(res.model, "offline-structural-intelligence");
      assert.match(res.message, /ensureSnapshotTree/);
      assert.match(res.message, /src\/services\/git\.service\.js/);
      assert.ok(Array.isArray(res.suggestedQuestions));
      assert.ok(res.suggestedQuestions.length > 0);
    } finally {
      userRepository.findOrCreateByClerkId = origFindUser;
      repositoryRepository.findByIdAndUserId = origFindRepo;
      snapshotRepository.listByRepo = origListSnapshots;
      snapshotRepository.findManyByRepositoryId = origFindMany;
      jobRepository.findBySnapshotId = origFindJob;
      if (prevGroqKey) process.env.GROQ_API_KEY = prevGroqKey;
      if (prevGrokKey) process.env.GROK_API_KEY = prevGrokKey;
      if (prevOpenAiKey) process.env.OPENAI_API_KEY = prevOpenAiKey;
      if (prevGeminiKey) process.env.GEMINI_API_KEY = prevGeminiKey;
    }
  });

  it("askQuestion calls Groq API when GROQ_API_KEY is configured", async () => {
    const origFindUser = userRepository.findOrCreateByClerkId;
    const origFindRepo = repositoryRepository.findByIdAndUserId;
    const origListSnapshots = snapshotRepository.listByRepo;
    const origFindMany = snapshotRepository.findManyByRepositoryId;
    const origFindJob = jobRepository.findBySnapshotId;
    const origFetch = globalThis.fetch;

    process.env.GROQ_API_KEY = "gsk_test_123";
    process.env.GROQ_MODEL = "llama-3.3-70b-versatile";

    userRepository.findOrCreateByClerkId = async () => ({ id: "u1" });
    repositoryRepository.findByIdAndUserId = async () => ({
      id: "repo_1",
      owner: "acme",
      name: "super-app",
      defaultBranch: "main",
    });
    snapshotRepository.listByRepo = async () => [{ id: "snap_1", commitSha: "sha123" }];
    snapshotRepository.findManyByRepositoryId = async () => [{ id: "snap_1", commitSha: "sha123" }];
    jobRepository.findBySnapshotId = async () => ({
      status: "done",
      resultJson: JSON.stringify({ graph: SAMPLE_GRAPH_IR }),
    });

    let calledUrl = null;
    let authHeader = null;
    let requestBody = null;
    globalThis.fetch = async (url, opts) => {
      calledUrl = String(url);
      authHeader = opts.headers?.["Authorization"];
      requestBody = JSON.parse(opts.body);
      return {
        ok: true,
        json: async () => ({
          choices: [
            {
              message: {
                content: "Groq response: ensureSnapshotTree is in git.service.js.",
              },
            },
          ],
        }),
      };
    };

    try {
      const res = await chatService.askQuestion(
        "user_123",
        "repo_1",
        "Where is ensureSnapshotTree defined?"
      );

      assert.match(calledUrl, /api\.groq\.com\/openai\/v1\/chat\/completions/);
      assert.equal(authHeader, "Bearer gsk_test_123");
      assert.equal(requestBody.model, "llama-3.3-70b-versatile");
      assert.match(res.message, /Groq response:/);
      assert.equal(res.model, "llama-3.3-70b-versatile");
    } finally {
      delete process.env.GROQ_API_KEY;
      delete process.env.GROQ_MODEL;
      globalThis.fetch = origFetch;
      userRepository.findOrCreateByClerkId = origFindUser;
      repositoryRepository.findByIdAndUserId = origFindRepo;
      snapshotRepository.listByRepo = origListSnapshots;
      snapshotRepository.findManyByRepositoryId = origFindMany;
      jobRepository.findBySnapshotId = origFindJob;
    }
  });

  it("askQuestion calls Grok / OpenAI API when key is configured", async () => {
    const origFindUser = userRepository.findOrCreateByClerkId;
    const origFindRepo = repositoryRepository.findByIdAndUserId;
    const origListSnapshots = snapshotRepository.listByRepo;
    const origFindMany = snapshotRepository.findManyByRepositoryId;
    const origFindJob = jobRepository.findBySnapshotId;
    const origFetch = globalThis.fetch;

    process.env.GROK_API_KEY = "xai-test-key";

    userRepository.findOrCreateByClerkId = async () => ({ id: "u1" });
    repositoryRepository.findByIdAndUserId = async () => ({
      id: "repo_1",
      owner: "acme",
      name: "super-app",
      defaultBranch: "main",
    });
    snapshotRepository.listByRepo = async () => [{ id: "snap_1", commitSha: "sha123" }];
    snapshotRepository.findManyByRepositoryId = async () => [{ id: "snap_1", commitSha: "sha123" }];
    jobRepository.findBySnapshotId = async () => ({
      status: "done",
      resultJson: JSON.stringify({ graph: SAMPLE_GRAPH_IR }),
    });

    let calledUrl = null;
    let authHeader = null;
    globalThis.fetch = async (url, opts) => {
      calledUrl = String(url);
      authHeader = opts.headers?.["Authorization"];
      return {
        ok: true,
        json: async () => ({
          choices: [
            {
              message: {
                content: "ensureSnapshotTree is defined in src/services/git.service.js at line 229.",
              },
            },
          ],
        }),
      };
    };

    try {
      const res = await chatService.askQuestion(
        "user_123",
        "repo_1",
        "Where is ensureSnapshotTree defined?"
      );

      assert.match(calledUrl, /api\.x\.ai\/v1\/chat\/completions/);
      assert.equal(authHeader, "Bearer xai-test-key");
      assert.match(res.message, /ensureSnapshotTree is defined in src\/services\/git\.service\.js/);
      assert.equal(res.model, "grok-2-latest");
    } finally {
      delete process.env.GROK_API_KEY;
      globalThis.fetch = origFetch;
      userRepository.findOrCreateByClerkId = origFindUser;
      repositoryRepository.findByIdAndUserId = origFindRepo;
      snapshotRepository.listByRepo = origListSnapshots;
      snapshotRepository.findManyByRepositoryId = origFindMany;
      jobRepository.findBySnapshotId = origFindJob;
    }
  });

  it("chatController dispatches correctly to chatService and returns 200", async () => {
    const origAsk = chatService.askQuestion;
    chatService.askQuestion = async (userId, repoId, message) => ({
      message: `Answer to ${message}`,
      citations: [],
      suggestedQuestions: [],
      model: "mock-model",
    });

    const req = {
      userId: "user_test",
      params: { id: "repo_1" },
      body: { message: "Hello AI", history: [] },
    };

    let statusCode = null;
    let jsonBody = null;
    const res = {
      status(code) {
        statusCode = code;
        return this;
      },
      json(body) {
        jsonBody = body;
        return this;
      },
    };

    try {
      await chatController.chat(req, res, () => {});
      assert.equal(statusCode, 200);
      assert.equal(jsonBody.success, true);
      assert.equal(jsonBody.data.message, "Answer to Hello AI");
      assert.equal(jsonBody.data.model, "mock-model");
    } finally {
      chatService.askQuestion = origAsk;
    }
  });
});

describe("chat grounding prompt", () => {
  it("lists the repository's real files and carries no example file paths", () => {
    const prompt = buildSystemPrompt({
      repo: { owner: "o", name: "stopspoti" },
      snapshot: { commitSha: "b907e8edc4d191f87d27fc1e3a7ee9e7909981d5" },
      context: { rolesSummary: {}, excerpts: [] },
      repoFiles: ["stopspoti/main.py", "stopspoti/audio.py"],
    });
    assert.match(prompt, /ALL FILES IN THIS REPOSITORY \(2\)/);
    assert.match(prompt, /stopspoti\/main\.py/);
    assert.match(prompt, /stopspoti has no authentication/);
    assert.doesNotMatch(prompt, /auth\.routes/);
  });
});
