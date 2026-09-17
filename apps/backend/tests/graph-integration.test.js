import { describe, it, mock } from "node:test";
import assert from "node:assert/strict";
import { aiService, validateGraphIr } from "../src/services/ai.service.js";
import { repoService } from "../src/services/repo.service.js";
import { repoController } from "../src/controllers/repo.controller.js";
import { repositoryRepository } from "../src/repositories/repository.repository.js";
import { snapshotRepository } from "../src/repositories/snapshot.repository.js";
import { jobRepository } from "../src/repositories/job.repository.js";
import { userRepository } from "../src/repositories/user.repository.js";
import { db } from "../src/config/db.js";
import { analysisService, hasValidGraph } from "../src/services/analysis.service.js";
import gitService from "../src/services/git.service.js";
import {
  BadGatewayError,
  BadRequestError,
  GatewayTimeoutError,
  NotFoundError,
  ServiceUnavailableError,
} from "../src/utils/errors.js";

const VALID_GRAPH_IR = {
  schema_version: "1.0",
  repository: {
    id: "repo:sample-repo",
    name: "sample-repo",
  },
  nodes: [
    {
      id: "file:src/routes/auth.js",
      type: "file",
      label: "auth.js",
      metadata: {},
    },
    {
      id: "symbol:src/routes/auth.js:setupAuthRoutes:3:0",
      type: "function",
      label: "setupAuthRoutes",
      metadata: {},
    },
  ],
  edges: [
    {
      id: "edge:file:src/routes/auth.js->contains->symbol:src/routes/auth.js:setupAuthRoutes:3:0",
      type: "contains",
      source: "file:src/routes/auth.js",
      target: "symbol:src/routes/auth.js:setupAuthRoutes:3:0",
      metadata: {},
    },
  ],
};

// ===========================================================================
// 1. AI Service Client Tests (Success, Timeout, Unavailable, Validation)
// ===========================================================================

describe("AI Service Client Integration", () => {
  it("1. AI service client success — returns valid Graph IR", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async (url, opts) => {
      assert.match(String(url), /\/analyze$/);
      const body = JSON.parse(opts.body);
      assert.equal(body.repository_path, "/path/to/repo");
      assert.equal(body.repo_name, "my-repo");
      return {
        ok: true,
        status: 200,
        json: async () => ({
          repository_name: "my-repo",
          ir: VALID_GRAPH_IR,
        }),
      };
    };

    try {
      const ir = await aiService.analyzeRepository("/path/to/repo", "my-repo");
      assert.equal(ir.schema_version, "1.0");
      assert.equal(ir.repository.name, "sample-repo");
      assert.equal(ir.nodes.length, 2);
      assert.equal(ir.edges.length, 1);
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("2. AI service timeout — throws GatewayTimeoutError (504)", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => {
      const err = new Error("The operation was aborted");
      err.name = "AbortError";
      throw err;
    };

    try {
      await assert.rejects(
        () => aiService.analyzeRepository("/path/to/repo"),
        (err) => {
          assert.ok(err instanceof GatewayTimeoutError);
          assert.equal(err.statusCode, 504);
          assert.match(err.message, /timed out/i);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("3. AI service unavailable — throws ServiceUnavailableError (503)", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => {
      throw new TypeError("fetch failed: connect ECONNREFUSED 127.0.0.1:8000");
    };

    try {
      await assert.rejects(
        () => aiService.analyzeRepository("/path/to/repo"),
        (err) => {
          assert.ok(err instanceof ServiceUnavailableError);
          assert.equal(err.statusCode, 503);
          assert.match(err.message, /unavailable/i);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("4. Invalid AI response (missing IR or bad schema) — throws BadGatewayError (502)", async () => {
    const originalFetch = globalThis.fetch;

    // Missing IR entirely
    globalThis.fetch = async () => ({
      ok: true,
      status: 200,
      json: async () => ({ repository_name: "test" }),
    });

    try {
      await assert.rejects(
        () => aiService.analyzeRepository("/path/to/repo"),
        (err) => {
          assert.ok(err instanceof BadGatewayError);
          assert.equal(err.statusCode, 502);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });

  it("10. Malformed Graph IR validation", () => {
    // Missing schema_version
    assert.throws(
      () => validateGraphIr({ repository: {}, nodes: [], edges: [] }),
      BadGatewayError
    );

    // Unsupported schema_version
    assert.throws(
      () => validateGraphIr({ schema_version: "2.0", repository: {}, nodes: [], edges: [] }),
      BadGatewayError
    );

    // Missing nodes array
    assert.throws(
      () => validateGraphIr({ schema_version: "1.0", repository: {}, edges: [] }),
      BadGatewayError
    );

    // Missing edges array
    assert.throws(
      () => validateGraphIr({ schema_version: "1.0", repository: {}, nodes: [] }),
      BadGatewayError
    );
  });

  it("12. No leakage of internal filesystem paths in error messages", async () => {
    const originalFetch = globalThis.fetch;
    globalThis.fetch = async () => ({
      ok: false,
      status: 400,
      json: async () => ({
        detail: "Repository path does not exist: D:\\secret\\keys\\private\\repo",
      }),
    });

    try {
      await assert.rejects(
        () => aiService.analyzeRepository("D:\\secret\\keys\\private\\repo"),
        (err) => {
          assert.ok(err instanceof BadRequestError);
          assert.ok(!err.message.includes("D:\\secret\\keys\\private\\repo"));
          assert.match(err.message, /<path>/);
          return true;
        }
      );
    } finally {
      globalThis.fetch = originalFetch;
    }
  });
});

// ===========================================================================
// 2. Repository & Snapshot Integration Tests
// ===========================================================================

describe("Backend Snapshot Graph Service & Controller", () => {
  const mockUser = { id: "user-123", clerkUserId: "clerk-abc" };
  const mockRepo = { id: "repo-456", userId: "user-123", name: "sample-repo", repoUrl: "https://github.com/org/repo" };
  const mockSnapshot = { id: "snap-789", repositoryId: "repo-456", commitSha: "c0ffee1234567890abcdef1234567890abcdef12" };

  it("5 & 6. Repository analysis success & graph endpoint success", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origTryAcquire = jobRepository.tryAcquireRunning;
    const origEnsureTree = gitService.ensureSnapshotTree;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;
    jobRepository.findBySnapshotId = async () => null;
    jobRepository.create = async () => ({ id: "job-new" });
    jobRepository.tryAcquireRunning = async () => true;
    jobRepository.markDone = async () => ({ id: "job-new", status: "done" });
    gitService.ensureSnapshotTree = async () => "/mock/snapshots/repo-456/c0ffee";
    aiService.analyzeRepository = async (path, name) => {
      assert.equal(path, "/mock/snapshots/repo-456/c0ffee");
      assert.equal(name, "sample-repo");
      return VALID_GRAPH_IR;
    };

    try {
      // 5. Service returns valid Graph IR
      const graph = await repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha);
      assert.equal(graph.schema_version, "1.0");
      assert.equal(graph.repository.name, "sample-repo");
      assert.equal(graph.nodes.length, 2);

      // 6. Controller returns 200 with pure Graph IR
      let responseStatus = null;
      let responseJson = null;
      const res = {
        status(code) {
          responseStatus = code;
          return this;
        },
        json(data) {
          responseJson = data;
          return this;
        },
      };

      await repoController.getSnapshotGraph(
        {
          userId: "clerk-abc",
          params: { id: "repo-456", sha: mockSnapshot.commitSha },
          query: {},
        },
        res,
        (err) => {
          if (err) throw err;
        }
      );

      assert.equal(responseStatus, 200);
      assert.deepEqual(responseJson, VALID_GRAPH_IR);
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      jobRepository.tryAcquireRunning = origTryAcquire;
      gitService.ensureSnapshotTree = origEnsureTree;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("7. Repository not found — throws NotFoundError (404)", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => null;

    try {
      await assert.rejects(
        () => repoService.getSnapshotGraph("clerk-abc", "missing-repo", "sha-123"),
        (err) => {
          assert.ok(err instanceof NotFoundError);
          assert.match(err.message, /Repository not found/i);
          return true;
        }
      );
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
    }
  });

  it("8. Snapshot not found — throws NotFoundError (404)", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => null;

    try {
      await assert.rejects(
        () => repoService.getSnapshotGraph("clerk-abc", "repo-456", "non-existent-sha"),
        (err) => {
          assert.ok(err instanceof NotFoundError);
          assert.match(err.message, /Snapshot not found/i);
          return true;
        }
      );
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
    }
  });

  it("9. Correct snapshot SHA handling — analyzes exact requested commit", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origTryAcquire = jobRepository.tryAcquireRunning;
    const origEnsureTree = gitService.ensureSnapshotTree;
    const origAnalyze = aiService.analyzeRepository;

    const requestedSha = "deadbeef1234567890deadbeef1234567890dead";
    const customSnapshot = { id: "snap-custom", repositoryId: "repo-456", commitSha: requestedSha };

    let extractedSha = null;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async (repoId, sha) => {
      assert.equal(sha, requestedSha);
      return customSnapshot;
    };
    jobRepository.findBySnapshotId = async () => null;
    jobRepository.create = async () => ({ id: "job-deadbeef" });
    jobRepository.tryAcquireRunning = async () => true;
    jobRepository.markDone = async () => ({ id: "job-deadbeef" });
    gitService.ensureSnapshotTree = async (repoId, sha) => {
      extractedSha = sha;
      return `/mock/snapshots/${repoId}/${sha}`;
    };
    aiService.analyzeRepository = async (path) => {
      assert.ok(path.includes(requestedSha));
      return VALID_GRAPH_IR;
    };

    try {
      await repoService.getSnapshotGraph("clerk-abc", "repo-456", requestedSha);
      assert.equal(extractedSha, requestedSha);
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      jobRepository.tryAcquireRunning = origTryAcquire;
      gitService.ensureSnapshotTree = origEnsureTree;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("11. Authentication & ownership enforcement — rejects unauthorized users", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;

    userRepository.findOrCreateByClerkId = async (clerkId) => ({ id: `user-${clerkId}`, clerkUserId: clerkId });
    // User A cannot access User B's repository
    repositoryRepository.findByIdAndUserId = async (repoId, userId) => {
      if (userId === "user-attacker") return null;
      return mockRepo;
    };

    try {
      await assert.rejects(
        () => repoService.getSnapshotGraph("attacker", "repo-456", mockSnapshot.commitSha),
        (err) => {
          assert.ok(err instanceof NotFoundError);
          return true;
        }
      );
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
    }
  });

  it("13. running AnalysisJob does not cause a second AI analysis", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;

    let analyzeCallCount = 0;
    aiService.analyzeRepository = async () => {
      analyzeCallCount++;
      return VALID_GRAPH_IR;
    };

    // First call: job is running, second call: job completes with valid graph
    let findCount = 0;
    jobRepository.findBySnapshotId = async () => {
      findCount++;
      if (findCount === 1) {
        return { id: "job-run-1", status: "running", resultJson: null };
      }
      return {
        id: "job-run-1",
        status: "done",
        resultJson: JSON.stringify({ graph: VALID_GRAPH_IR }),
      };
    };

    try {
      const graph = await repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha);
      assert.equal(graph.schema_version, "1.0");
      assert.equal(analyzeCallCount, 0, "AI service must not be called when a job is already running");
      assert.ok(findCount >= 2, "Must poll job until completion");
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("14. completed AnalysisJob returns cached graph", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origEnsureTree = gitService.ensureSnapshotTree;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;

    jobRepository.findBySnapshotId = async () => ({
      id: "job-cached",
      status: "done",
      resultJson: JSON.stringify({ graph: VALID_GRAPH_IR }),
    });

    let treeExtracted = false;
    gitService.ensureSnapshotTree = async () => {
      treeExtracted = true;
      return "/some/dir";
    };

    let analyzeCalled = false;
    aiService.analyzeRepository = async () => {
      analyzeCalled = true;
      return VALID_GRAPH_IR;
    };

    try {
      const graph = await repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha);
      assert.deepEqual(graph, VALID_GRAPH_IR);
      assert.equal(treeExtracted, false, "Git tree extraction must be skipped on cache hit");
      assert.equal(analyzeCalled, false, "AI service call must be skipped on cache hit");
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      gitService.ensureSnapshotTree = origEnsureTree;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("15. failed/stuck job follows bounded timeout behavior", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;

    let analyzeCalled = false;
    aiService.analyzeRepository = async () => {
      analyzeCalled = true;
      return VALID_GRAPH_IR;
    };

    // Case A: Running job fails during polling
    let callCount = 0;
    jobRepository.findBySnapshotId = async () => {
      callCount++;
      if (callCount === 1) {
        return { id: "job-fail", status: "running" };
      }
      return { id: "job-fail", status: "failed", error: "AST parse failed due to syntax error" };
    };

    try {
      await assert.rejects(
        () => repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
        (err) => {
          assert.ok(err instanceof ServiceUnavailableError);
          assert.equal(err.statusCode, 503);
          assert.match(err.message, /AST parse failed/);
          return true;
        }
      );
      assert.equal(analyzeCalled, false, "AI analysis must not be started when job fails");

      // Case B: Stuck job exceeds bounded timeout
      jobRepository.findBySnapshotId = async () => ({
        id: "job-stuck",
        status: "running",
        resultJson: null,
      });

      process.env.GRAPH_POLL_TIMEOUT_MS = "100";
      process.env.GRAPH_POLL_INTERVAL_MS = "20";

      await assert.rejects(
        () => repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
        (err) => {
          assert.ok(err instanceof GatewayTimeoutError);
          assert.equal(err.statusCode, 504);
          assert.match(err.message, /timed out/i);
          return true;
        }
      );
      assert.equal(analyzeCalled, false, "AI analysis must not be started on stuck job timeout");
    } finally {
      delete process.env.GRAPH_POLL_TIMEOUT_MS;
      delete process.env.GRAPH_POLL_INTERVAL_MS;
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("16. concurrent getSnapshotGraph calls for pending snapshot — exactly ONE AI analysis performed", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origFindOrCreate = jobRepository.findOrCreateBySnapshotId;
    const origTryAcquire = jobRepository.tryAcquireRunning;
    const origMarkDone = jobRepository.markDone;
    const origEnsureTree = gitService.ensureSnapshotTree;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;
    gitService.ensureSnapshotTree = async () => "/mock/dir";

    const sharedJob = {
      id: "job-shared-concurrent",
      snapshotId: mockSnapshot.id,
      status: "pending",
      attempts: 0,
      resultJson: null,
    };

    jobRepository.findBySnapshotId = async () => ({ ...sharedJob });
    jobRepository.findOrCreateBySnapshotId = async () => sharedJob;

    // Simulate atomic conditional UPDATE: WHERE id = $id AND status = 'pending'
    jobRepository.tryAcquireRunning = async (id, attempts) => {
      if (sharedJob.status === "pending") {
        sharedJob.status = "running";
        sharedJob.attempts = attempts;
        return true; // Acquired
      }
      return false; // Already running or finished
    };

    jobRepository.markDone = async (id, resultJson) => {
      sharedJob.status = "done";
      sharedJob.resultJson = resultJson;
      return sharedJob;
    };

    let analyzeCallCount = 0;
    aiService.analyzeRepository = async () => {
      analyzeCallCount++;
      // Simulate real async analysis latency
      await new Promise((r) => setTimeout(r, 60));
      return VALID_GRAPH_IR;
    };

    try {
      // Dispatch two concurrent calls simultaneously
      const [res1, res2] = await Promise.all([
        repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
        repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
      ]);

      assert.deepEqual(res1, VALID_GRAPH_IR);
      assert.deepEqual(res2, VALID_GRAPH_IR);
      assert.equal(analyzeCallCount, 1, "Exactly ONE AI analysis must be executed across concurrent requests");
      assert.equal(sharedJob.status, "done");
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      jobRepository.findOrCreateBySnapshotId = origFindOrCreate;
      jobRepository.tryAcquireRunning = origTryAcquire;
      jobRepository.markDone = origMarkDone;
      gitService.ensureSnapshotTree = origEnsureTree;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("17. lock acquisition winner performs analysis while loser polls without calling AI service", async () => {
    const origUserFind = userRepository.findOrCreateByClerkId;
    const origRepoFind = repositoryRepository.findByIdAndUserId;
    const origSnapFind = snapshotRepository.findByRepoAndSha;
    const origJobFind = jobRepository.findBySnapshotId;
    const origTryAcquire = jobRepository.tryAcquireRunning;
    const origMarkDone = jobRepository.markDone;
    const origEnsureTree = gitService.ensureSnapshotTree;
    const origAnalyze = aiService.analyzeRepository;

    userRepository.findOrCreateByClerkId = async () => mockUser;
    repositoryRepository.findByIdAndUserId = async () => mockRepo;
    snapshotRepository.findByRepoAndSha = async () => mockSnapshot;
    gitService.ensureSnapshotTree = async () => "/mock/dir";

    let state = "pending";
    let cachedJson = null;

    jobRepository.findBySnapshotId = async () => ({
      id: "job-lock-test",
      snapshotId: mockSnapshot.id,
      status: state,
      resultJson: cachedJson,
    });

    let acquisitionCalls = 0;
    jobRepository.tryAcquireRunning = async () => {
      acquisitionCalls++;
      if (acquisitionCalls === 1) {
        state = "running";
        return true; // First request is the winner
      }
      return false; // Second request loses acquisition
    };

    jobRepository.markDone = async (id, resultJson) => {
      state = "done";
      cachedJson = resultJson;
    };

    const callers = [];
    aiService.analyzeRepository = async () => {
      callers.push("winner");
      await new Promise((r) => setTimeout(r, 60));
      return VALID_GRAPH_IR;
    };

    try {
      const [winnerResult, loserResult] = await Promise.all([
        repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
        repoService.getSnapshotGraph("clerk-abc", "repo-456", mockSnapshot.commitSha),
      ]);

      assert.deepEqual(winnerResult, VALID_GRAPH_IR);
      assert.deepEqual(loserResult, VALID_GRAPH_IR);
      assert.equal(callers.length, 1, "Only the winner must call aiService.analyzeRepository");
      assert.equal(callers[0], "winner");
    } finally {
      userRepository.findOrCreateByClerkId = origUserFind;
      repositoryRepository.findByIdAndUserId = origRepoFind;
      snapshotRepository.findByRepoAndSha = origSnapFind;
      jobRepository.findBySnapshotId = origJobFind;
      jobRepository.tryAcquireRunning = origTryAcquire;
      jobRepository.markDone = origMarkDone;
      gitService.ensureSnapshotTree = origEnsureTree;
      aiService.analyzeRepository = origAnalyze;
    }
  });

  it("18. tryAcquireRunning succeeds when job is pending (atomic updateAndCount = 1)", async () => {
    const origWhere = db.orm.public.AnalysisJob.where;
    let updateFilter = null;
    let updatePayload = null;

    db.orm.public.AnalysisJob.where = (filter) => {
      updateFilter = filter;
      return {
        updateAndCount: async (payload) => {
          updatePayload = payload;
          return 1; // 1 row atomically transitioned
        },
      };
    };

    try {
      const acquired = await jobRepository.tryAcquireRunning("job-test-123", 2);
      assert.equal(acquired, true);
      assert.deepEqual(updateFilter, { id: "job-test-123", status: "pending" });
      assert.deepEqual(updatePayload, { status: "running", attempts: 2 });
    } finally {
      db.orm.public.AnalysisJob.where = origWhere;
    }
  });

  it("19. tryAcquireRunning fails when job is already running (atomic updateAndCount = 0)", async () => {
    const origWhere = db.orm.public.AnalysisJob.where;
    db.orm.public.AnalysisJob.where = () => ({
      updateAndCount: async () => 0, // 0 rows affected because status != 'pending'
    });

    try {
      const acquired = await jobRepository.tryAcquireRunning("job-test-already-running", 1);
      assert.equal(acquired, false);
    } finally {
      db.orm.public.AnalysisJob.where = origWhere;
    }
  });

  describe("Analysis Service Cache & Recomputation Pipeline", () => {
    it("20. hasValidGraph accurately identifies valid Graph IR and rejects stubs", () => {
      // Valid cases
      assert.equal(hasValidGraph({ status: "done", resultJson: JSON.stringify({ graph: VALID_GRAPH_IR }) }), true);
      assert.equal(hasValidGraph({ status: "done", resultJson: JSON.stringify(VALID_GRAPH_IR) }), true);

      // Stale stub cases
      assert.equal(hasValidGraph({ status: "done", resultJson: JSON.stringify({ engine: "stub", summary: "diff stat" }) }), false);
      assert.equal(hasValidGraph({ status: "done", resultJson: null }), false);
      assert.equal(hasValidGraph({ status: "running", resultJson: JSON.stringify(VALID_GRAPH_IR) }), false);
      assert.equal(hasValidGraph({ status: "pending", resultJson: null }), false);
      assert.equal(hasValidGraph(null), false);
    });

    it("21. analysisService.analyze detects legacy stub as stale, calls aiService, and stores Graph IR", async () => {
      const origRequire = analysisService._requireSnapshot;
      const origFindOrCreate = jobRepository.findOrCreateBySnapshotId;
      const origFindBySnapshotId = jobRepository.findBySnapshotId;
      const origEnsureTree = gitService.ensureSnapshotTree;
      const origAnalyzeRepo = aiService.analyzeRepository;
      const origWhere = db.orm.public.AnalysisJob.where;
      const origMarkRunning = jobRepository.markRunning;
      const origMarkDone = jobRepository.markDone;

      let aiCalled = false;
      let markDonePayload = null;

      const mockRepo = { id: "repo-documind", name: "DocuMind" };
      const mockSnapshot = { id: "snap-421", commitSha: "28e9524d287174127e4c37bcc9509150d2c2b809" };
      let mockJob = {
        id: "job-f1a7",
        snapshotId: "snap-421",
        status: "done",
        attempts: 1,
        resultJson: JSON.stringify({
          engine: "stub",
          summary: "31 file(s) changed",
          note: "Stub result from diff stats.",
        }),
      };

      analysisService._requireSnapshot = async () => ({ user: { id: "u-1" }, repo: mockRepo, snapshot: mockSnapshot });
      jobRepository.findOrCreateBySnapshotId = async () => mockJob;
      jobRepository.findBySnapshotId = async () => mockJob;
      jobRepository.tryAcquireRunning = async () => true;
      jobRepository.markRunning = async (id, attempts) => {
        mockJob.status = "running";
        mockJob.attempts = attempts;
        return mockJob;
      };
      jobRepository.markDone = async (id, resultJson) => {
        markDonePayload = JSON.parse(resultJson);
        mockJob.status = "done";
        mockJob.resultJson = resultJson;
        return mockJob;
      };
      db.orm.public.AnalysisJob.where = () => ({
        update: async (payload) => {
          Object.assign(mockJob, payload);
          return 1;
        },
        updateAndCount: async () => 1,
      });
      gitService.ensureSnapshotTree = async () => "/mock/snapshot/dir";
      aiService.analyzeRepository = async (dir, name) => {
        aiCalled = true;
        assert.equal(dir, "/mock/snapshot/dir");
        assert.equal(name, "DocuMind");
        return VALID_GRAPH_IR;
      };

      try {
        const result = await analysisService.analyze("u-1", "repo-documind", "28e9524d287174127e4c37bcc9509150d2c2b809");
        assert.equal(aiCalled, true, "AI service must be called because stub was stale");
        assert.equal(result.status, "done");
        assert.equal(result.result.engine, "ai-service");
        assert.equal(result.result.graph.schema_version, "1.0");
        assert.equal(markDonePayload.graph.schema_version, "1.0");

        // Subsequent call: returns cached Graph IR immediately without calling aiService again
        aiCalled = false;
        const secondResult = await analysisService.analyze("u-1", "repo-documind", "28e9524d287174127e4c37bcc9509150d2c2b809");
        assert.equal(aiCalled, false, "AI service must NOT be called on second call (cache hit)");
        assert.equal(secondResult.status, "done");
        assert.equal(secondResult.result.graph.schema_version, "1.0");
      } finally {
        analysisService._requireSnapshot = origRequire;
        jobRepository.findOrCreateBySnapshotId = origFindOrCreate;
        jobRepository.findBySnapshotId = origFindBySnapshotId;
        gitService.ensureSnapshotTree = origEnsureTree;
        aiService.analyzeRepository = origAnalyzeRepo;
        db.orm.public.AnalysisJob.where = origWhere;
        jobRepository.markRunning = origMarkRunning;
        jobRepository.markDone = origMarkDone;
      }
    });
  });
});



