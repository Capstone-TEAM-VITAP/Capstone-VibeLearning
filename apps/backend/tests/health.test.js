import { test } from "node:test";
import assert from "node:assert/strict";
import http from "node:http";
import app from "../src/app.js";

test("Health endpoint returns 200 and verifies both backend and aiService when healthy", async () => {
  // Start ephemeral server
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;

  const originalFetch = globalThis.fetch;
  // Mock AI service answering 200
  globalThis.fetch = async (url) => {
    if (String(url).includes("/health")) {
      return {
        ok: true,
        status: 200,
        json: async () => ({ status: "ok" }),
      };
    }
    return originalFetch(url);
  };

  try {
    const res = await originalFetch(`http://127.0.0.1:${port}/api/v1/health`);
    assert.equal(res.status, 200);
    const body = await res.json();
    assert.equal(body.success, true);
    assert.equal(body.data.status, "healthy");
    assert.equal(body.data.services.backend, "ok");
    assert.equal(body.data.services.aiService, "ok");

    // Also test root /health
    const resRoot = await originalFetch(`http://127.0.0.1:${port}/health`);
    assert.equal(resRoot.status, 200);
    const bodyRoot = await resRoot.json();
    assert.equal(bodyRoot.success, true);
    assert.equal(bodyRoot.data.status, "healthy");
  } finally {
    globalThis.fetch = originalFetch;
    await new Promise((resolve) => server.close(resolve));
  }
});

test("Health endpoint returns 503 and reports degraded status when AI service is down", async () => {
  const server = http.createServer(app);
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  const port = server.address().port;

  const originalFetch = globalThis.fetch;
  // Mock AI service connection failure
  globalThis.fetch = async (url) => {
    if (String(url).includes("/health")) {
      throw new Error("ECONNREFUSED 127.0.0.1:8000");
    }
    return originalFetch(url);
  };

  try {
    const res = await originalFetch(`http://127.0.0.1:${port}/api/v1/health`);
    assert.equal(res.status, 503);
    const body = await res.json();
    assert.equal(body.success, false);
    assert.equal(body.data.status, "degraded");
    assert.equal(body.data.services.backend, "ok");
    assert.equal(body.data.services.aiService, "unavailable");
    assert.ok((body.data.error || "").includes("ECONNREFUSED"));
  } finally {
    globalThis.fetch = originalFetch;
    await new Promise((resolve) => server.close(resolve));
  }
});
