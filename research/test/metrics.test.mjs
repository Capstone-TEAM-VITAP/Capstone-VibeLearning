import test from "node:test";
import assert from "node:assert/strict";
import { scoreQuestion, pairedPermutation, rankedAfterExclusion, bootstrapCI } from "../src/metrics.mjs";
import { bm25, buildIndex } from "../src/retrievers.mjs";

test("scoreQuestion hit/recall/mrr/ndcg", () => {
  const s = scoreQuestion(["x", "a", "y", "b"], ["a", "b"]);
  assert.equal(s["hit@1"], 0);
  assert.equal(s["hit@3"], 1);
  assert.equal(s["recall@3"], 0.5);
  assert.equal(s["recall@5"], 1);
  assert.equal(s.mrr, 0.5);
  const dcg = 1 / Math.log2(3) + 1 / Math.log2(5);
  const idcg = 1 + 1 / Math.log2(3);
  assert.ok(Math.abs(s.ndcg - dcg / idcg) < 1e-12);
});

test("perfect and empty rankings", () => {
  assert.equal(scoreQuestion(["a"], ["a"]).ndcg, 1);
  assert.equal(scoreQuestion([], ["a"]).mrr, 0);
});

test("exclusion removes the named file", () => {
  assert.deepEqual(rankedAfterExclusion(["t", "a"], ["t"]), ["a"]);
});

test("exact permutation test: all-positive diffs of size 3 -> p = 0.25", () => {
  const r = pairedPermutation([1, 1, 1], [0, 0, 0]);
  assert.equal(r.p, 2 / 8);
});

test("permutation test: no difference -> p = 1", () => {
  assert.equal(pairedPermutation([1, 2], [1, 2]).p, 1);
});

test("bootstrap CI contains the mean of a constant sample", () => {
  const [lo, hi] = bootstrapCI([0.5, 0.5, 0.5], 200);
  assert.equal(lo, 0.5);
  assert.equal(hi, 0.5);
});

test("bm25 ranks the document containing the rare term first", () => {
  const mk = (p, words) => {
    const tf = new Map();
    words.forEach((w) => tf.set(w, (tf.get(w) || 0) + 1));
    return { path: p, tf, len: words.length, text: words.join(" ") };
  };
  const docs = [mk("a.js", ["common", "common"]), mk("b.js", ["common", "rareterm"])];
  const df = new Map([["common", 2], ["rareterm", 1]]);
  const index = { docs, df, avgLen: 2, N: 2 };
  assert.equal(bm25(index, "rareterm common")[0], "b.js");
});
