/*
 * Why this test file exists:
 * - Snapshot rows carry fileCount/additions/deletions that the dashboard's
 *   Recent activity shows directly. Rows used to be saved with zeros, so
 *   every commit read "0 files +0 −0". These tests pin the totals helper.
 * - parseNumstat is pure; getCommitStats runs real git against a tiny
 *   throwaway mirror (no network, no DB) to cover the parent and
 *   root-commit fallbacks.
 */
import { after, before, describe, it } from "node:test";
import assert from "node:assert/strict";
import { execFileSync } from "node:child_process";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { getCommitStats, parseNumstat } from "../src/services/git.service.js";

describe("parseNumstat", () => {
  it("sums lines and counts files, binary files included", () => {
    const out = ["3\t1\tsrc/a.js", "10\t0\tsrc/b.js", "-\t-\tlogo.png", ""].join("\n");
    assert.deepEqual(parseNumstat(out), { fileCount: 3, additions: 13, deletions: 1 });
  });

  it("returns zeros for empty output", () => {
    assert.deepEqual(parseNumstat(""), { fileCount: 0, additions: 0, deletions: 0 });
    assert.deepEqual(parseNumstat(undefined), { fileCount: 0, additions: 0, deletions: 0 });
  });
});

describe("getCommitStats", () => {
  const repoId = "stats-fixture";
  let tmp;
  let prevCache;
  const shas = {};

  before(() => {
    tmp = fs.mkdtempSync(path.join(os.tmpdir(), "codeai-stats-"));
    prevCache = process.env.GIT_CACHE_DIR;
    process.env.GIT_CACHE_DIR = tmp;
    const work = path.join(tmp, "work");
    const git = (...args) =>
      execFileSync("git", ["-C", work, "-c", "user.name=t", "-c", "user.email=t@t", ...args], {
        encoding: "utf8",
      }).trim();
    fs.mkdirSync(work);
    git("init", "-q");
    fs.writeFileSync(path.join(work, "a.txt"), "one\ntwo\n");
    git("add", ".");
    git("commit", "-qm", "root");
    shas.root = git("rev-parse", "HEAD");
    fs.writeFileSync(path.join(work, "a.txt"), "one\nTWO\nthree\n");
    fs.writeFileSync(path.join(work, "b.txt"), "new\n");
    git("add", ".");
    git("commit", "-qm", "second");
    shas.second = git("rev-parse", "HEAD");
    execFileSync("git", ["clone", "-q", "--mirror", work, path.join(tmp, repoId)]);
  });

  after(() => {
    if (prevCache === undefined) delete process.env.GIT_CACHE_DIR;
    else process.env.GIT_CACHE_DIR = prevCache;
    fs.rmSync(tmp, { recursive: true, force: true });
  });

  it("compares against the first parent when no base is recorded", async () => {
    assert.deepEqual(await getCommitStats(repoId, shas.second, null), {
      fileCount: 2,
      additions: 3,
      deletions: 1,
    });
  });

  it("uses the recorded base when given", async () => {
    assert.deepEqual(await getCommitStats(repoId, shas.second, shas.root), {
      fileCount: 2,
      additions: 3,
      deletions: 1,
    });
  });

  it("treats a root commit as adding its whole tree", async () => {
    assert.deepEqual(await getCommitStats(repoId, shas.root, null), {
      fileCount: 1,
      additions: 2,
      deletions: 0,
    });
  });
});
