import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  buildDiffPack,
  buildLearningPack,
  parseMcqResponse,
  buildOfflineQuestions,
  buildDiffOfflineQuestions,
  gradeAnswers,
} from "../src/services/learning.service.js";

const REPO = { owner: "octo", name: "hello", defaultBranch: "main" };
const SNAPSHOT = { commitSha: "abc1234567890abcdef" };

const GRAPH_IR = {
  schema_version: "1.0",
  repository: { id: "repo:hello", name: "hello" },
  nodes: [
    { id: "file:src/a.js", type: "file", label: "a.js", architecture_role: "ROUTE", metadata: { path: "src/a.js" } },
    { id: "file:src/b.js", type: "file", label: "b.js", metadata: { path: "src/b.js" } },
    { id: "file:src/c.js", type: "file", label: "c.js", metadata: { path: "src/c.js" } },
    { id: "file:src/d.js", type: "file", label: "d.js", metadata: { path: "src/d.js" } },
    {
      id: "symbol:src/a.js:handleAuth:10:0",
      type: "function",
      label: "handleAuth",
      metadata: { name: "handleAuth", path: "src/a.js", start_line: 10, end_line: 25 },
    },
  ],
  edges: [],
};

describe("Learning pack builder", () => {
  it("builds markdown with repo meta, roles, and excerpts", () => {
    const pack = buildLearningPack({
      repo: REPO,
      snapshot: SNAPSHOT,
      rolesSummary: { ROUTE: ["src/a.js"] },
      excerpts: [{ path: "src/a.js", startLine: 1, endLine: 5, content: "const x = 1;" }],
    });
    assert.match(pack, /octo\/hello/);
    assert.match(pack, /abc1234/);
    assert.match(pack, /ROUTE: src\/a\.js/);
    assert.match(pack, /File: src\/a\.js \(lines 1-5\)/);
    assert.match(pack, /const x = 1;/);
  });

  it("handles empty roles and excerpts without crashing", () => {
    const pack = buildLearningPack({ repo: REPO, snapshot: {}, rolesSummary: {}, excerpts: [] });
    assert.match(pack, /HEAD/);
    assert.match(pack, /No code excerpts/);
  });
});

describe("MCQ response parser", () => {
  const valid = JSON.stringify([
    {
      prompt: "Where is handleAuth defined?",
      options: ["src/a.js", "src/b.js", "src/c.js", "src/d.js"],
      answerIndex: 0,
      explanation: "It lives in src/a.js.",
      citation: { path: "src/a.js", startLine: 10, endLine: 25 },
    },
  ]);

  it("accepts valid MCQ JSON", () => {
    const out = parseMcqResponse(valid, ["src/a.js"]);
    assert.equal(out.length, 1);
    assert.equal(out[0].prompt, "Where is handleAuth defined?");
    assert.equal(out[0].answerIndex, 0);
    assert.equal(out[0].citationPath, "src/a.js");
  });

  it("accepts fenced JSON blocks", () => {
    const out = parseMcqResponse(`\`\`\`json\n${valid}\n\`\`\``, ["src/a.js"]);
    assert.equal(out.length, 1);
  });

  it("rejects non-4-option questions", () => {
    const bad = JSON.stringify([{ prompt: "Q?", options: ["a", "b"], answerIndex: 0 }]);
    assert.throws(() => parseMcqResponse(bad, []), /exactly 4/);
  });

  it("rejects out-of-range answerIndex", () => {
    const bad = JSON.stringify([
      { prompt: "Q?", options: ["a", "b", "c", "d"], answerIndex: 7 },
    ]);
    assert.throws(() => parseMcqResponse(bad, []), /answerIndex/);
  });

  it("rejects citations to files outside the pack", () => {
    const bad = JSON.stringify([
      {
        prompt: "Q?",
        options: ["a", "b", "c", "d"],
        answerIndex: 0,
        citation: { path: "src/evil.js", startLine: 1, endLine: 2 },
      },
    ]);
    assert.throws(() => parseMcqResponse(bad, ["src/a.js"]), /unknown file/);
  });

  it("rejects invalid JSON", () => {
    assert.throws(() => parseMcqResponse("not json", []), /invalid JSON/);
  });
});

describe("Offline question fallback", () => {
  it("builds definition questions from graph symbols", () => {
    const out = buildOfflineQuestions(GRAPH_IR, 5);
    assert.equal(out.length, 1);
    assert.match(out[0].prompt, /handleAuth/);
    assert.equal(out[0].options.length, 4);
    assert.equal(out[0].options[out[0].answerIndex], "src/a.js");
  });

  it("returns empty when the graph has no usable symbols", () => {
    assert.deepEqual(buildOfflineQuestions({ nodes: [] }, 5), []);
  });

  it("ignores architecture role nodes like CHANGELOG.md (UNKNOWN)", () => {
    const graph = {
      nodes: [
        { id: "file:CHANGELOG.md", type: "file", label: "CHANGELOG.md", metadata: { path: "CHANGELOG.md" } },
        { id: "file:src/a.js", type: "file", label: "a.js", metadata: { path: "src/a.js" } },
        { id: "file:src/b.js", type: "file", label: "b.js", metadata: { path: "src/b.js" } },
        { id: "file:src/c.js", type: "file", label: "c.js", metadata: { path: "src/c.js" } },
        {
          id: "architecture:CHANGELOG.md:UNKNOWN",
          type: "unknown",
          label: "CHANGELOG.md (UNKNOWN)",
          metadata: { path: "CHANGELOG.md", role: "unknown", layer: "docs" },
        },
        {
          id: "symbol:src/a.js:handleAuth:10:0",
          type: "function",
          label: "handleAuth",
          metadata: { name: "handleAuth", path: "src/a.js", start_line: "10", end_line: "25" },
        },
      ],
      edges: [],
    };
    const out = buildOfflineQuestions(graph, 5);
    assert.equal(out.length, 1);
    assert.match(out[0].prompt, /handleAuth/);
    assert.doesNotMatch(out[0].prompt, /CHANGELOG/);
    // Real IR stringifies metadata — line numbers must be Ints for the DB
    assert.equal(out[0].citationStart, 10);
    assert.equal(out[0].citationEnd, 25);
  });

  it("skips external and unresolved nodes", () => {
    const graph = {
      nodes: [
        { id: "file:src/a.js", type: "file", label: "a.js", metadata: { path: "src/a.js" } },
        { id: "file:src/b.js", type: "file", label: "b.js", metadata: { path: "src/b.js" } },
        { id: "file:src/c.js", type: "file", label: "c.js", metadata: { path: "src/c.js" } },
        { id: "file:src/d.js", type: "file", label: "d.js", metadata: { path: "src/d.js" } },
        { id: "external:react", type: "external", label: "react", metadata: { module_path: "react" } },
      ],
      edges: [],
    };
    assert.deepEqual(buildOfflineQuestions(graph, 5), []);
  });
});

describe("Answer grading", () => {
  const questions = [
    { id: "q1", answerIndex: 2 },
    { id: "q2", answerIndex: 0 },
  ];

  it("scores picks and flags each result", () => {
    const { correct, total, results } = gradeAnswers(questions, [
      { questionId: "q1", pickedIndex: 2 },
      { questionId: "q2", pickedIndex: 1 },
    ]);
    assert.equal(correct, 1);
    assert.equal(total, 2);
    assert.equal(results[0].correct, true);
    assert.equal(results[1].correct, false);
  });

  it("rejects picks for unknown questions", () => {
    assert.throws(
      () => gradeAnswers(questions, [{ questionId: "nope", pickedIndex: 0 }]),
      /Unknown question/,
    );
  });
});

const DIFF_FILES = [
  { path: "src/a.js", status: "M" },
  { path: "src/b.js", status: "A" },
  { path: "src/c.js", status: "D" },
  { path: "src/d.js", status: "M" },
  { path: "src/e.js", status: "R" },
];

const DIFF_HUNKS = [
  {
    path: "src/a.js",
    status: "M",
    additions: 3,
    deletions: 1,
    hunks: [
      { oldStart: 10, oldLines: 3, newStart: 10, newLines: 5, lines: [
        { type: "context", text: "function old() {" },
        { type: "del", text: "  return 1;" },
        { type: "add", text: "  return 2;" },
      ] },
    ],
  },
];

describe("Diff pack builder", () => {
  it("builds markdown with range, file list, and hunks", () => {
    const pack = buildDiffPack({
      repo: REPO,
      baseSha: "aaaaaaa000000000000000000000000000000000",
      headSha: "bbbbbbb111111111111111111111111111111111",
      files: DIFF_FILES,
      diffFiles: DIFF_HUNKS,
    });
    assert.match(pack, /octo\/hello/);
    assert.match(pack, /aaaaaaa\.\.bbbbbbb/);
    assert.match(pack, /5 files changed/);
    assert.match(pack, /- M src\/a\.js/);
    assert.match(pack, /```diff/);
    assert.match(pack, /\+  return 2;/);
    assert.match(pack, /-  return 1;/);
  });

  it("falls back to file-list quizzing when hunks are missing", () => {
    const pack = buildDiffPack({ repo: REPO, baseSha: "a", headSha: "b", files: DIFF_FILES, diffFiles: [] });
    assert.match(pack, /No hunk details available/);
    assert.match(pack, /- A src\/b\.js/);
  });
});

describe("Diff offline fallback", () => {
  it("builds which-file-changed questions with 4 options", () => {
    const out = buildDiffOfflineQuestions({ baseSha: "a", headSha: "b", files: DIFF_FILES }, 5);
    assert.equal(out.length, 5);
    assert.match(out[0].prompt, /Which file was modified/);
    assert.match(out[1].prompt, /Which file was added/);
    for (const q of out) {
      assert.equal(q.options.length, 4);
      assert.equal(new Set(q.options).size, 4);
    }
    assert.equal(out[0].options[out[0].answerIndex], "src/a.js");
    assert.equal(out[1].options[out[1].answerIndex], "src/b.js");
  });

  it("rotates answer positions deterministically", () => {
    const once = buildDiffOfflineQuestions({ baseSha: "a", headSha: "b", files: DIFF_FILES }, 5);
    const twice = buildDiffOfflineQuestions({ baseSha: "a", headSha: "b", files: DIFF_FILES }, 5);
    assert.deepEqual(once.map((q) => q.answerIndex), twice.map((q) => q.answerIndex));
  });

  it("returns empty when fewer than 4 files changed", () => {
    assert.deepEqual(
      buildDiffOfflineQuestions({ baseSha: "a", headSha: "b", files: DIFF_FILES.slice(0, 3) }, 5),
      [],
    );
  });
});
