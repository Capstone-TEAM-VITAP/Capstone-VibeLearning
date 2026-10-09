import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  parseCommitList,
  planHistoryBackfill,
} from "../src/services/git.service.js";

const LOG_OUTPUT = [
  "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa\x00bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\x00Fix login\x00Ada\x002026-01-05T10:00:00+00:00",
  "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb\x00cccccccccccccccccccccccccccccccccccccccc\x00Add tests\x00Grace\x002026-01-04T10:00:00+00:00",
  "cccccccccccccccccccccccccccccccccccccccc\x00\x00Initial commit\x00Linus\x002026-01-01T10:00:00+00:00",
  "not-a-sha-line",
  "",
].join("\n");

describe("Commit list parser", () => {
  it("parses rows with first-parent links", () => {
    const rows = parseCommitList(LOG_OUTPUT);
    assert.equal(rows.length, 3);
    assert.equal(rows[0].commitSha, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa");
    assert.equal(rows[0].parentSha, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
    assert.equal(rows[0].message, "Fix login");
    assert.equal(rows[0].authorName, "Ada");
    assert.equal(rows[2].parentSha, null);
  });

  it("drops malformed lines", () => {
    assert.deepEqual(parseCommitList("garbage\n\n"), []);
    assert.deepEqual(parseCommitList(""), []);
  });
});

describe("History backfill planner", () => {
  const commits = parseCommitList(LOG_OUTPUT);

  it("skips the head and already-recorded shas", () => {
    const rows = planHistoryBackfill(
      commits,
      new Set(["bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"]),
      "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    );
    assert.equal(rows.length, 1);
    assert.equal(rows[0].commitSha, "cccccccccccccccccccccccccccccccccccccccc");
    assert.equal(rows[0].baseSha, null);
  });

  it("links rows to their first parent", () => {
    const rows = planHistoryBackfill(commits, new Set(), "zzzz");
    assert.equal(rows.length, 3);
    assert.equal(rows[0].baseSha, "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb");
    assert.equal(rows[1].baseSha, "cccccccccccccccccccccccccccccccccccccccc");
  });

  it("dedupes repeated shas", () => {
    const rows = planHistoryBackfill([...commits, commits[0]], new Set(), null);
    assert.equal(rows.length, 3);
  });
});
