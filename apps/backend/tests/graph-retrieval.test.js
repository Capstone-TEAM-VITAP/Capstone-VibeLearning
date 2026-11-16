import { describe, it, before, after } from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import {
  buildFileGraph,
  findNamedFile,
  graphRank,
  questionKind,
  rrf,
  stem,
} from "../src/services/graph-retrieval.service.js";
import { buildSearchIndex, rankFilesHybrid } from "../src/services/retrieval.service.js";
import { findRelevantContextWithDense } from "../src/services/chat.service.js";

const file = (p) => ({ id: `file:${p}`, type: "file", label: p.split("/").pop(), metadata: { path: p } });
const sym = (p, name) => ({ id: `symbol:${p}:${name}:1:0`, type: "function", label: name, metadata: { path: p, name } });
const imp = (a, b) => ({ id: `${a}->${b}`, type: "imports", source: `file:${a}`, target: `file:${b}`, metadata: {} });

const FILES = ["lib/utils.js", "lib/request.js", "lib/client.js", "index.js", "lib/cookies.js", "test/utils.test.js"];
const IR = {
  schema_version: "1.0",
  repository: { name: "demo" },
  nodes: [...FILES.map(file), sym("lib/cookies.js", "parseCookieHeader"), sym("lib/utils.js", "formatDate")],
  edges: [imp("lib/request.js", "lib/utils.js"), imp("lib/client.js", "lib/request.js"), imp("index.js", "lib/client.js"), imp("lib/cookies.js", "lib/utils.js")],
};

describe("graph retrieval (port of the research graph ranker)", () => {
  it("stems like the Python implementation", () => {
    assert.equal(stem("routes"), stem("routing"));
    assert.equal(stem("dependencies"), "dependency");
  });

  it("lifts import edges to a file graph", () => {
    const fg = buildFileGraph(IR);
    assert.deepEqual(fg.inc.get("lib/utils.js").sort(), ["lib/cookies.js", "lib/request.js"]);
    assert.deepEqual(fg.out.get("index.js"), ["lib/client.js"]);
  });

  it("finds a file named in the question by path or unique basename", () => {
    const fg = buildFileGraph(IR);
    assert.equal(findNamedFile(fg, "Which files import lib/utils.js?"), "lib/utils.js");
    assert.equal(findNamedFile(fg, "who uses cookies.js"), "lib/cookies.js");
    assert.equal(findNamedFile(fg, "where is the date formatted"), null);
  });

  it("routes importer, impact and general questions", () => {
    const fg = buildFileGraph(IR);
    assert.equal(questionKind(fg, "Which files import lib/utils.js?").kind, "importers");
    assert.equal(questionKind(fg, "Which files are affected if lib/utils.js changes?").kind, "impact");
    assert.equal(questionKind(fg, "Where are cookie headers parsed?").kind, "general");
  });

  it("ranks importers by reverse-import distance", () => {
    const fg = buildFileGraph(IR);
    assert.deepEqual(graphRank(fg, "Which files are affected if lib/utils.js changes?"), [
      "lib/cookies.js",
      "lib/request.js",
      "lib/client.js",
      "index.js",
    ]);
  });

  it("matches question words against paths and symbol names", () => {
    const fg = buildFileGraph(IR);
    assert.equal(graphRank(fg, "where is the cookie header parsed")[0], "lib/cookies.js");
  });

  it("fuses rankings with RRF and breaks ties by path", () => {
    assert.deepEqual(rrf([["a", "b"], ["b", "a"]]), ["a", "b"]);
    assert.deepEqual(rrf([["a", "b"], ["b", "c"]]), ["b", "a", "c"]);
  });
});

describe("rankFilesHybrid (the product retriever)", () => {
  let dir;
  before(() => {
    dir = fs.mkdtempSync(path.join(os.tmpdir(), "codeai-hybrid-"));
    const write = (p, text) => {
      fs.mkdirSync(path.dirname(path.join(dir, p)), { recursive: true });
      fs.writeFileSync(path.join(dir, p), text);
    };
    write("lib/utils.js", "export function formatDate(d) { return d.toISOString(); }");
    write("lib/request.js", "import { formatDate } from './utils.js'; export function send() {}");
    write("lib/client.js", "import { send } from './request.js';");
    write("index.js", "import './lib/client.js';");
    write("lib/cookies.js", "import { formatDate } from './utils.js'; export function parseCookieHeader(h) { return h.split(';'); }");
    write("test/utils.test.js", "");
  });
  after(() => fs.rmSync(dir, { recursive: true, force: true }));

  it("answers importer questions from the graph", () => {
    const index = buildSearchIndex(IR, dir);
    const { kind, paths } = rankFilesHybrid(index, "Which files import lib/utils.js?");
    assert.equal(kind, "importers");
    assert.deepEqual(paths.slice(0, 2).sort(), ["lib/cookies.js", "lib/request.js"]);
  });

  it("fuses text and graph for other questions and uses a neural ranking when given", () => {
    const index = buildSearchIndex(IR, dir);
    const plain = rankFilesHybrid(index, "where is the cookie header parsed");
    assert.equal(plain.kind, "general");
    assert.equal(plain.paths[0], "lib/cookies.js");
    const withDense = rankFilesHybrid(index, "where is the cookie header parsed", { denseRanking: ["lib/cookies.js", "index.js"] });
    assert.ok(withDense.paths.includes("index.js"));
  });

  it("works without a neural ranking when the AI service has none", async () => {
    let called = 0;
    const ctx = await findRelevantContextWithDense(IR, "where is the cookie header parsed", dir, {
      denseRank: async () => {
        called++;
        return null;
      },
    });
    assert.equal(called, 1);
    assert.equal(ctx.citations[0].path, "lib/cookies.js");
  });
});
