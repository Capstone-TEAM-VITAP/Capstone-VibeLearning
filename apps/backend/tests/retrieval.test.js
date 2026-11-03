import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { tokenize, buildSearchIndex, rankFiles } from "../src/services/retrieval.service.js";
import { findRelevantContext, findRelevantContextLegacy } from "../src/services/chat.service.js";

let dir;
const write = (rel, text) => {
  fs.mkdirSync(path.dirname(path.join(dir, rel)), { recursive: true });
  fs.writeFileSync(path.join(dir, rel), text);
};
const fileNode = (p) => ({ id: `file:${p}`, type: "file", label: p, metadata: { path: p } });
const fnNode = (name, p) => ({
  id: `symbol:${p}:${name}:1:0`, type: "function", label: name,
  metadata: { name, path: p, start_line: 1, end_line: 3 },
});

describe("retrieval.service", () => {
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "retrieval-"));
    write("lib/cookies.js", "// Parse the cookie header into an object of values\nfunction parseCookies(h) { return h; }\n");
    write("lib/router.js", "// Dispatch an incoming request to handlers\nfunction route(req) { return req; }\n");
    write("lib/misc.js", "const x = 1;\n");
    write("docs/main.js", "console.log('hello');\n");
  });
  after(() => fs.rmSync(dir, { recursive: true, force: true }));

  const graph = () => ({
    nodes: [
      fileNode("lib/cookies.js"), fileNode("lib/router.js"), fileNode("lib/misc.js"), fileNode("docs/main.js"),
      fnNode("parseCookies", "lib/cookies.js"), fnNode("route", "lib/router.js"),
    ],
    edges: [],
  });

  it("splits camelCase and snake_case identifiers", () => {
    assert.deepEqual(tokenize("parseCookieHeader snake_case"), ["parse", "cookie", "header", "snake", "case"]);
  });

  it("finds a file by what it does, not only by its name", () => {
    const index = buildSearchIndex(graph(), dir);
    const ranked = rankFiles(index, "Which file reads the header and returns an object of values for cookie data");
    assert.equal(ranked[0].path, "lib/cookies.js");
  });

  it("returns nothing when no query word matches", () => {
    const index = buildSearchIndex(graph(), dir);
    assert.deepEqual(rankFiles(index, "zzzqqq"), []);
  });

  it("symbol bonus can promote a file whose symbol names match the query", () => {
    const index = buildSearchIndex(graph(), dir);
    const without = rankFiles(index, "route", { symbolWeight: 0 }).map((r) => r.path);
    const withSym = rankFiles(index, "route", { symbolWeight: 1 });
    assert.equal(withSym[0].path, "lib/router.js");
    assert.ok(without.includes("lib/router.js"));
  });

  it("findRelevantContext returns content-ranked excerpts and citations", () => {
    const ctx = findRelevantContext(graph(), "where are cookie header values parsed", dir);
    assert.equal(ctx.citations[0].path, "lib/cookies.js");
    assert.ok(ctx.excerpts[0].content.includes("parseCookies"));
  });

  it("the 'ai' path rule fires on the word, not on words that merely contain 'ai'", () => {
    const g = graph();
    const quiet = findRelevantContextLegacy(g, "explain the idea again", dir);
    assert.notEqual(quiet.citations[0].path, "docs/main.js");
    const word = findRelevantContextLegacy(g, "how does the ai part work", dir);
    assert.equal(word.citations[0].path, "docs/main.js");
  });

  it("falls back to the legacy heuristic without a snapshot directory", () => {
    const ctx = findRelevantContext(graph(), "parseCookies", null);
    assert.deepEqual(ctx.excerpts, []);
    assert.ok(ctx.matchedSymbols.length > 0);
  });
});
