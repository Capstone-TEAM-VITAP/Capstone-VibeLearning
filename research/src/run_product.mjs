// Runs CodeAI's production chat retriever (apps/backend/src/services/retrieval.service.js) on every question of data/questions_v3.json, in both text conditions:
//   code - comment-free copies written by research/py/export_code_only.py (main condition)
//   raw  - files as they are on disk
// Three versions:
//   product          v1, the retriever before this study: rankFiles (BM25 plus a symbol-name bonus)
//   product-v2       v2, rankFilesHybrid without a neural ranking (AI service without the optional model)
//   product-v2-dense v2 with the neural ranking the AI service supplies (out/dense_rankings.json,
//                    written by research/py/export_dense.py with the same code as the AI service)
// Writes out/product_rankings.json: { system: { cond: { questionId: [top 20 paths] } } }. Scoring happens in
// research/py/run_retrieval.py, so the product is scored exactly like every other ranker.
import fs from "node:fs";
import path from "node:path";
import { ROOT, loadGraph, repoDir } from "./util.mjs";
import { buildSearchIndex, rankFiles, rankFilesHybrid } from "../../apps/backend/src/services/retrieval.service.js";

const questions = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "questions_v3.json"), "utf8"));
const codeOnlyDir = (name) => path.join(ROOT, "out", "code_only", name);
if (!fs.existsSync(path.join(ROOT, "out", "code_only"))) {
  console.error("Run research/py/export_code_only.py first.");
  process.exit(1);
}

const dense = JSON.parse(fs.readFileSync(path.join(ROOT, "out", "dense_rankings.json"), "utf8"));
const out = { product: { code: {}, raw: {} }, "product-v2": { code: {}, raw: {} }, "product-v2-dense": { code: {}, raw: {} } };
const repos = [...new Set(questions.map((q) => q.repo))];
for (const repo of repos) {
  const graph = loadGraph(repo);
  const idx = { code: buildSearchIndex(graph, codeOnlyDir(repo)), raw: buildSearchIndex(graph, repoDir(repo)) };
  for (const q of questions.filter((x) => x.repo === repo)) {
    for (const cond of ["code", "raw"]) {
      out.product[cond][q.id] = rankFiles(idx[cond], q.query).slice(0, 20).map((r) => r.path);
      out["product-v2"][cond][q.id] = rankFilesHybrid(idx[cond], q.query).paths.slice(0, 20);
      out["product-v2-dense"][cond][q.id] = rankFilesHybrid(idx[cond], q.query, { denseRanking: dense[cond][q.id] }).paths.slice(0, 20);
    }
  }
  console.log(`${repo}: ${questions.filter((x) => x.repo === repo).length} questions`);
}
fs.writeFileSync(path.join(ROOT, "out", "product_rankings.json"), JSON.stringify(out));
console.log("wrote out/product_rankings.json");
