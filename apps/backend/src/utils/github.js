import crypto from "node:crypto";

/**
 * GitHub webhook helpers: HMAC verification and push-payload parsing.
 * Pure functions — no DB, no git, no network.
 */

/**
 * Verify the X-Hub-Signature-256 header against the raw request bytes.
 * @param {string} secret - GITHUB_WEBHOOK_SECRET
 * @param {Buffer} rawBody - exact request bytes (see app.js json verify)
 * @param {string} signatureHeader - e.g. "sha256=abc123..."
 * @returns {boolean}
 */
export function verifySignature(secret, rawBody, signatureHeader) {
  if (!secret || !rawBody || !signatureHeader) return false;
  const match = String(signatureHeader).match(/^sha256=([0-9a-f]{64})$/i);
  if (!match) return false;

  const expected = crypto.createHmac("sha256", secret).update(rawBody).digest();
  const received = Buffer.from(match[1], "hex");
  if (received.length !== expected.length) return false;
  return crypto.timingSafeEqual(received, expected);
}

/**
 * Extract what a push delivery is about. Returns null when the event
 * carries nothing to sync (ping, branch deletion, missing repo info).
 * @param {string} event - X-GitHub-Event header value
 * @param {object} payload - parsed JSON body
 * @returns {{ owner: string, name: string, ref: string, headSha: string } | null}
 */
export function parsePushPayload(event, payload) {
  if (event !== "push" || !payload || typeof payload !== "object") return null;
  if (payload.deleted === true) return null;

  const fullName = payload.repository?.full_name;
  const ref = typeof payload.ref === "string" ? payload.ref : null;
  const headSha = typeof payload.after === "string" ? payload.after : null;
  if (!fullName || !ref || !headSha) return null;
  if (!/^[0-9a-f]{40}$/i.test(headSha)) return null;

  const [owner, name] = fullName.split("/");
  if (!owner || !name) return null;

  return { owner, name, ref, headSha };
}
