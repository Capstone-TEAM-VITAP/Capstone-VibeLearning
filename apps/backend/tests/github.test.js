/*
 * Why this test file exists:
 * - The webhook endpoint is public (no Clerk), so the HMAC signature is the
 *   ONLY authentication. A regression here lets anyone forge push events and
 *   trigger clones/snapshots on our infrastructure.
 * - parsePushPayload decides what gets synced: pings, branch deletions and
 *   malformed payloads must be ignored, otherwise we waste git fetches or
 *   crash on missing fields.
 * - Pure functions: no DB, no git, no network, runs in milliseconds.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import crypto from "node:crypto";
import { parsePushPayload, verifySignature } from "../src/utils/github.js";

function sign(secret, rawBody) {
  return "sha256=" + crypto.createHmac("sha256", secret).update(rawBody).digest("hex");
}

const PUSH = {
  ref: "refs/heads/main",
  after: "6a7c89be37dc5d5e45f0d176c379a4080a5a9054",
  repository: { full_name: "octocat/Hello-World" },
};

describe("verifySignature", () => {
  it("accepts a correctly signed body", () => {
    const raw = Buffer.from(JSON.stringify(PUSH));
    assert.equal(verifySignature("s3cret", raw, sign("s3cret", raw)), true);
  });

  it("rejects tampered bodies and wrong secrets", () => {
    const raw = Buffer.from(JSON.stringify(PUSH));
    const sig = sign("s3cret", raw);
    assert.equal(verifySignature("s3cret", Buffer.from("{}"), sig), false);
    assert.equal(verifySignature("other", raw, sig), false);
  });

  it("rejects missing or malformed signatures", () => {
    const raw = Buffer.from("{}");
    assert.equal(verifySignature("s3cret", raw, null), false);
    assert.equal(verifySignature("s3cret", raw, "sha256=xyz"), false);
    assert.equal(verifySignature(null, raw, sign("s", raw)), false);
  });
});

describe("parsePushPayload", () => {
  it("extracts owner, name, ref and head SHA from pushes", () => {
    assert.deepEqual(parsePushPayload("push", PUSH), {
      owner: "octocat",
      name: "Hello-World",
      ref: "refs/heads/main",
      headSha: "6a7c89be37dc5d5e45f0d176c379a4080a5a9054",
    });
  });

  it("ignores pings, deletions and malformed payloads", () => {
    assert.equal(parsePushPayload("ping", {}), null);
    assert.equal(parsePushPayload("push", { ...PUSH, deleted: true }), null);
    assert.equal(parsePushPayload("push", { ...PUSH, after: "short" }), null);
    assert.equal(parsePushPayload("push", { ref: "refs/heads/main" }), null);
    assert.equal(parsePushPayload("push", null), null);
  });
});
