/*
 * Why this test file exists:
 * - parseRepoUrl is the front door of the connect flow: bad input must fail
 *   with a 400 before we ever touch git or the database, and only github.com
 *   is supported so self-hosted/typo URLs cannot slip through.
 * - stripSecrets guards the single worst failure of this slice: leaking a
 *   private-repo access token into error logs or API responses. A regression
 *   here is a credential leak, so it gets a dedicated assertion.
 * - buildAuthenticatedUrl must inject the token for private clones while
 *   rejecting malformed tokens that could break the git command line.
 * - All three are pure functions, so these tests need no git binary, no DB,
 *   and no network.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import {
  buildAuthenticatedUrl,
  parseRepoUrl,
  stripSecrets,
} from "../src/services/git.service.js";
import { BadRequestError } from "../src/utils/errors.js";

describe("parseRepoUrl", () => {
  it("accepts https, .git suffix and ssh forms and normalizes them", () => {
    const expected = {
      owner: "octocat",
      name: "Hello-World",
      normalizedUrl: "https://github.com/octocat/Hello-World",
    };
    assert.deepEqual(parseRepoUrl("https://github.com/octocat/Hello-World"), expected);
    assert.deepEqual(parseRepoUrl("https://github.com/octocat/Hello-World.git"), expected);
    assert.deepEqual(parseRepoUrl("git@github.com:octocat/Hello-World.git"), expected);
  });

  it("rejects non-GitHub hosts, garbage and incomplete URLs with 400", () => {
    for (const bad of ["https://gitlab.com/a/b", "not-a-url", "https://github.com/onlyone", ""]) {
      assert.throws(() => parseRepoUrl(bad), (err) => err instanceof BadRequestError && err.statusCode === 400);
    }
  });
});

describe("buildAuthenticatedUrl + stripSecrets", () => {
  it("injects the token for private clones and passes through without one", () => {
    const url = "https://github.com/o/r";
    assert.equal(buildAuthenticatedUrl(url, "tok123"), "https://x-access-token:tok123@github.com/o/r");
    assert.equal(buildAuthenticatedUrl(url), url);
  });

  it("rejects tokens that could break the git command line", () => {
    assert.throws(() => buildAuthenticatedUrl("https://github.com/o/r", "has space"), BadRequestError);
  });

  it("redacts tokens from error text so they never reach logs", () => {
    const dirty = "fatal: https://x-access-token:SUPERSECRET@github.com/o/r not found";
    const clean = stripSecrets(dirty);
    assert.ok(!clean.includes("SUPERSECRET"), "token leaked into error text");
    assert.ok(clean.includes("<redacted>"));
  });
});
