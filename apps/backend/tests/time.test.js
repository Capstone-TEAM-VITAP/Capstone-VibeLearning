/*
 * Why this test file exists:
 * - Prisma 8 encodes DateTime columns only from Temporal.Instant; passing the
 *   ISO string git gives us crashes snapshot creation with
 *   RUNTIME.ENCODE_FAILED, which is exactly the connect-repo failure we hit.
 * - toInstant is the single choke point for that conversion, so pinning its
 *   behavior (string -> Instant, null/empty -> null, passthrough otherwise)
 *   prevents this class of bug from coming back.
 * - Pure function: no DB, no git, runs in milliseconds.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { toInstant } from "../src/utils/time.js";

describe("toInstant", () => {
  it("converts git ISO timestamps to Temporal.Instant", () => {
    const instant = toInstant("2026-09-03T18:24:02+05:30");
    assert.equal(instant.epochMilliseconds, Date.parse("2026-09-03T18:24:02+05:30"));
  });

  it("maps null/undefined/empty to null for the nullable column", () => {
    assert.equal(toInstant(null), null);
    assert.equal(toInstant(undefined), null);
    assert.equal(toInstant("   "), null);
  });

  it("passes non-strings through untouched", () => {
    const already = Temporal.Instant.from("2026-09-03T12:54:02Z");
    assert.equal(toInstant(already), already);
  });
});
