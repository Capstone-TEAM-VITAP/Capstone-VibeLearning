/*
 * Why this test file exists:
 * - Express 5 exposes req.query as a getter with no setter, so the old
 *   `req.query = parsed` line threw on EVERY query-validated route and the
 *   repo list 500'd while everything else looked fine.
 * - This pins the fix with a mock that reproduces Express 5 exactly
 *   (prototype-level getter, assignment throws), so a future refactor that
 *   reintroduces plain assignment fails here instead of in production.
 * - No server, no DB: middleware + mock req + real Zod schemas.
 */
import { describe, it } from "node:test";
import assert from "node:assert/strict";
import { z } from "zod";
import { validate } from "../src/middleware/validate.middleware.js";

// Mimics Express 5: query lives behind a prototype getter, so direct
// assignment on the instance throws like the real IncomingMessage did.
function express5MockReq(query) {
  const holder = { value: query };
  return Object.create({
    get query() {
      return holder.value;
    },
  });
}

const querySchema = z.object({ projectId: z.string().uuid().optional() });

describe("validate query (Express 5 getter-only)", () => {
  it("replaces the query without throwing", async () => {
    const req = express5MockReq({});
    let nextArg = "unset";
    await validate({ query: querySchema })(req, {}, (err) => {
      nextArg = err;
    });
    assert.equal(nextArg, undefined);
    assert.deepEqual(req.query, {});
  });

  it("forwards Zod errors for invalid query values", async () => {
    const req = express5MockReq({ projectId: "not-a-uuid" });
    let nextArg = "unset";
    await validate({ query: querySchema })(req, {}, (err) => {
      nextArg = err;
    });
    assert.ok(nextArg && nextArg.name === "ZodError");
  });
});
