// RQ1: which retriever puts the gold file(s) in the top-k? No LLM involved.
//
// Splits
//   dev   - used to choose the symbol weight (0.25) before the final run.
//   test  - 7 repositories that were looked at while v2 was being designed (post-hoc).
//   test2 - 5 repositories cloned after v2 was frozen; never run before this script (confirmatory).
import fs from "node:fs";
import path from "node:path";
import { ROOT, REPOS, loadGraph, repoDir } from "./util.mjs";
import { buildIndex, bm25, grep, random, codeaiV1, codeaiV2 } from "./retrievers.mjs";
import { buildSearchIndex, rankFiles, SYMBOL_WEIGHT } from "../../apps/backend/src/services/retrieval.service.js";
import { scoreQuestion, rankedAfterExclusion, mean, bootstrapCI, pairedPermutation, pairedBootstrapDiffCI } from "./metrics.mjs";

const questions = JSON.parse(fs.readFileSync(path.join(ROOT, "data", "questions.json"), "utf8"));
const SYSTEMS = ["codeai-v1", "codeai-v2", "bm25", "grep", "random"];
const METRICS = ["hit@1", "hit@3", "hit@5", "hit@7", "recall@5", "mrr", "ndcg"];
const SPLITS = ["test2", "test", "dev"];

const repos = [...REPOS.dev, ...REPOS.test, ...REPOS.test2];
const g1 = {}, g2 = {}, idx = {}, searchIdx = {};
for (const r of repos) {
  g1[r] = loadGraph(r, "v1");
  g2[r] = loadGraph(r);
  idx[r] = buildIndex(r, g2[r]);
  searchIdx[r] = buildSearchIndex(g2[r], repoDir(r));
}

// Evidence for the weight choice: dev split only.
const WEIGHTS = [0, 0.1, 0.25, 0.5, 1];
const devQs = questions.filter((q) => q.split === "dev");
const devNdcg = WEIGHTS.map((w) =>
  mean(devQs.map((q) => scoreQuestion(rankedAfterExclusion(rankFiles(searchIdx[q.repo], q.query, { symbolWeight: w }).map((x) => x.path), q.exclude).slice(0, 7), q.gold).ndcg)),
);

const rows = [];
let aiSubstring = 0, aiWord = 0;
for (const q of questions) {
  const lq = q.query.toLowerCase();
  if (lq.includes("ai")) aiSubstring++;
  if (/\b(ai|gpt|llm|openai)\b/.test(lq)) aiWord++;
  const lists = {
    "codeai-v1": codeaiV1(g1[q.repo], q.repo, q.query),
    "codeai-v2": codeaiV2(g2[q.repo], q.repo, q.query),
    bm25: bm25(idx[q.repo], q.query),
    grep: grep(idx[q.repo], q.query),
    random: random(idx[q.repo], q.id),
  };
  const row = { id: q.id, repo: q.repo, type: q.type, split: q.split, scores: {}, top: {} };
  for (const s of SYSTEMS) {
    const ranked = rankedAfterExclusion(lists[s], q.exclude).slice(0, 7);
    row.scores[s] = scoreQuestion(ranked, q.gold);
    row.top[s] = ranked.slice(0, 3);
  }
  rows.push(row);
}
fs.writeFileSync(path.join(ROOT, "out", "rq1_raw.json"), JSON.stringify(rows));

const f3 = (x) => x.toFixed(3);
let md = `# RQ1 results (v1 = before, v2 = after)\n\nQuestions: ${rows.length}. Product symbol weight: ${SYMBOL_WEIGHT}. ` +
  `Dev nDCG by weight: ${WEIGHTS.map((w, i) => `${w}=${f3(devNdcg[i])}`).join(", ")}.\n\n` +
  `Queries containing the substring "ai": ${aiSubstring}; containing it as a word: ${aiWord}.\n`;

function table(title, subset) {
  let t = `\n## ${title} (n=${subset.length})\n\n| System | ${METRICS.join(" | ")} |\n|---|${METRICS.map(() => "---").join("|")}|\n`;
  for (const s of SYSTEMS) {
    const cells = METRICS.map((m) => {
      const xs = subset.map((r) => r.scores[s][m]);
      const [lo, hi] = bootstrapCI(xs);
      return `${f3(mean(xs))} [${f3(lo)}, ${f3(hi)}]`;
    });
    t += `| ${s} | ${cells.join(" | ")} |\n`;
  }
  return t;
}

for (const split of SPLITS) {
  const sub = rows.filter((r) => r.split === split);
  md += table(`${split} - all`, sub);
  for (const type of ["locate", "dependency"]) md += table(`${split} - ${type}`, sub.filter((r) => r.type === type));
}

md += "\n## Paired comparisons (A minus B)\n\n| Split | A | B | Type | Metric | n | mean diff | 95% CI | permutation p |\n|---|---|---|---|---|---|---|---|---|\n";
const pairs = [["codeai-v2", "codeai-v1"], ["codeai-v2", "bm25"], ["codeai-v2", "grep"], ["codeai-v1", "bm25"]];
for (const split of ["test2", "test"]) {
  for (const [A, B] of pairs) {
    for (const type of ["all", "locate", "dependency"]) {
      for (const m of ["hit@5", "mrr", "ndcg"]) {
        const sub = rows.filter((r) => r.split === split && (type === "all" || r.type === type));
        const a = sub.map((r) => r.scores[A][m]);
        const b = sub.map((r) => r.scores[B][m]);
        const [d, lo, hi] = pairedBootstrapDiffCI(a, b);
        const { p } = pairedPermutation(a, b);
        md += `| ${split} | ${A} | ${B} | ${type} | ${m} | ${sub.length} | ${d.toFixed(3)} | [${lo.toFixed(3)}, ${hi.toFixed(3)}] | ${p < 0.0001 ? "<0.0001" : p.toFixed(4)} |\n`;
      }
    }
  }
}

md += "\n## Per-repository hit@5\n\n| Split | Repo | n | " + SYSTEMS.join(" | ") + " |\n|---|---|---|" + SYSTEMS.map(() => "---").join("|") + "|\n";
for (const split of ["test2", "test", "dev"]) {
  for (const repo of REPOS[split]) {
    const sub = rows.filter((r) => r.repo === repo);
    md += `| ${split} | ${repo} | ${sub.length} | ${SYSTEMS.map((s) => f3(mean(sub.map((r) => r.scores[s]["hit@5"])))).join(" | ")} |\n`;
  }
}
fs.writeFileSync(path.join(ROOT, "out", "rq1_tables.md"), md);
console.log(md);
