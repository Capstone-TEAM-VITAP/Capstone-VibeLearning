/*
 * Why this test file exists:
 * - utils/diff.js is the Changed Files/Lines contract that every later pipeline
 *   stage (AST, semantic search, impact ranking, LLM explanation) will consume,
 *   so a silent break here would corrupt all downstream results.
 * - These are pure functions (no DB, no git, no network), so the tests run in
 *   milliseconds and can never be flaky.
 * - Hunk line numbers must be exact: an off-by-one would point the AI stages
 *   at the wrong lines of code.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  mergeChangedFiles,
  parseNameStatus,
  parseUnifiedDiff,
  toChangedLineRanges,
} from "../src/utils/diff.js";

const SAMPLE_DIFF = [
  "diff --git a/src/app.js b/src/app.js",
  "--- a/src/app.js",
  "+++ b/src/app.js",
  "@@ -1,3 +1,4 @@",
  " ctx",
  "-old",
  "+new1",
  "+new2",
  " ctx2",
  "",
].join("\n");

describe("parseNameStatus", () => {
  it("parses modified and added files", () => {
    assert.deepEqual(parseNameStatus("M\tsrc/app.js\nA\tnew.txt\n"), [
      { path: "src/app.js", status: "M" },
      { path: "new.txt", status: "A" },
    ]);
  });

  it("parses renames into path + oldPath", () => {
    assert.deepEqual(parseNameStatus("R100\told.txt\tnew.txt\n"), [
      { path: "new.txt", status: "R", oldPath: "old.txt" },
    ]);
  });

  it("returns [] for empty output", () => {
    assert.deepEqual(parseNameStatus(""), []);
    assert.deepEqual(parseNameStatus("   \n"), []);
  });
});

describe("parseUnifiedDiff", () => {
  it("parses hunks with correct line numbers and totals", () => {
    const files = parseUnifiedDiff(SAMPLE_DIFF);
    assert.equal(files.length, 1);
    const [file] = files;
    assert.equal(file.path, "src/app.js");
    assert.equal(file.additions, 2);
    assert.equal(file.deletions, 1);
    assert.equal(file.hunks.length, 1);
    const types = file.hunks[0].lines.map((l) => `${l.type}:${l.newLine ?? l.oldLine}`);
    assert.deepEqual(types, ["context:1", "del:2", "add:2", "add:3", "context:4"]);
  });

  it("returns [] for empty diff", () => {
    assert.deepEqual(parseUnifiedDiff(""), []);
  });
});

describe("mergeChangedFiles + toChangedLineRanges", () => {
  it("merges status with hunks and derives line ranges", () => {
    const merged = mergeChangedFiles([{ path: "src/app.js", status: "M" }], parseUnifiedDiff(SAMPLE_DIFF));
    assert.equal(merged[0].additions, 2);
    assert.equal(merged[0].deletions, 1);
    assert.deepEqual(toChangedLineRanges(merged), [
      {
        path: "src/app.js",
        status: "M",
        addedRanges: [{ start: 2, end: 3 }],
        deletedRanges: [{ start: 2, end: 2 }],
      },
    ]);
  });

  it("defaults to zero counts when a file has no hunks", () => {
    const merged = mergeChangedFiles([{ path: "empty.txt", status: "A" }], []);
    assert.deepEqual(merged, [{ path: "empty.txt", status: "A", additions: 0, deletions: 0, hunks: [] }]);
  });
});
