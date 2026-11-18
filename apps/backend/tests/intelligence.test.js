import { test } from "node:test";
import assert from "node:assert/strict";
import { buildGraphDigest } from "../src/services/intelligence.service.js";
import { completeText } from "../src/services/llm.service.js";

const graph = {
  schema_version: "1.0",
  repository: { name: "demo" },
  nodes: [
    { id: "file:src/a.js", type: "file", label: "a.js", metadata: { path: "src/a.js", language: "javascript" } },
    { id: "file:src/b.js", type: "file", label: "b.js", metadata: { path: "src/b.js", language: "javascript" } },
    { id: "file:README.md", type: "file", label: "README.md", metadata: { path: "README.md", language: "markdown" } },
    { id: "architecture:src/a.js:SERVICE", type: "service", metadata: { path: "src/a.js", role: "service" } },
    { id: "architecture:src/b.js:ENTRYPOINT", type: "entrypoint", metadata: { path: "src/b.js", role: "entrypoint" } },
    { id: "symbol:src/a.js:f", type: "function", label: "f", metadata: { path: "src/a.js" } },
    { id: "external:express", type: "external", label: "express", metadata: { module_path: "express" } },
  ],
  edges: [
    { id: "e1", type: "imports", source: "file:src/b.js", target: "file:src/a.js" },
    { id: "e2", type: "imports", source: "file:src/b.js", target: "external:express" },
    { id: "e3", type: "contains", source: "file:src/a.js", target: "symbol:src/a.js:f" },
  ],
};

test("buildGraphDigest counts files, roles, imports and packages from the graph", () => {
  const d = buildGraphDigest(graph);
  assert.equal(d.totals.files, 3);
  assert.equal(d.totals.symbols, 1);
  assert.deepEqual(d.languages[0], ["javascript", 2]);
  assert.deepEqual(d.mostImportedFiles, [["src/a.js", 1]]);
  assert.deepEqual(d.mostUsedPackages, [["express", 1]]);
  assert.deepEqual(d.entrypoints, ["src/b.js"]);
  assert.ok(d.architectureRoles.some(([r]) => r === "service"));
  assert.deepEqual(d.filesWithMostSymbols, [["src/a.js", 1]]);
});

test("completeText sends OpenCode Go headers, model and reasoning effort", async () => {
  const saved = { ...process.env };
  process.env.OPENCODE_API_KEY = "test-key";
  delete process.env.OPENCODE_MODEL;
  delete process.env.OPENCODE_REASONING_EFFORT;
  let seen;
  const fetchImpl = async (url, opts) => {
    seen = { url, opts, body: JSON.parse(opts.body) };
    return { ok: true, json: async () => ({ choices: [{ message: { content: "{\"ok\":true}" } }] }) };
  };
  try {
    const out = await completeText({ system: "s", user: "u", sessionKey: "k", json: true, fetchImpl });
    assert.equal(out.model, "deepseek-v4.1-flash");
    assert.match(seen.url, /opencode\.ai\/zen\/go\/v1\/chat\/completions$/);
    assert.equal(seen.body.reasoning_effort, "medium");
    assert.deepEqual(seen.body.response_format, { type: "json_object" });
    assert.match(seen.opts.headers["x-opencode-session"], /^codeai-[0-9a-f]{32}$/);
    assert.equal(seen.opts.headers["User-Agent"], "CodeAI-Assistant/1.0");
  } finally {
    process.env = saved;
  }
});

test("completeText reports when no provider is configured", async () => {
  const saved = { ...process.env };
  delete process.env.OPENCODE_API_KEY;
  delete process.env.GROQ_API_KEY;
  try {
    await assert.rejects(completeText({ system: "s", user: "u" }), (err) => err.code === "LLM_NOT_CONFIGURED");
  } finally {
    process.env = saved;
  }
});
