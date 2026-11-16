// RQ3 (deterministic part): validity of the offline quiz fallback, checked against raw source.
import fs from "node:fs";
import path from "node:path";
import { ROOT, REPOS, loadGraph, readText } from "./util.mjs";
import { buildOfflineQuestions } from "../../apps/backend/src/services/learning.service.js";

const rows = [];
for (const repo of [...REPOS.dev, ...REPOS.test, ...REPOS.test2]) {
  const g = loadGraph(repo);
  const qs = buildOfflineQuestions(g, 10);
  let supported = 0, lineOk = 0, dupPrompt = 0, trivialName = 0;
  const pos = [0, 0, 0, 0];
  const seen = new Set();
  for (const q of qs) {
    const name = q.prompt.match(/"([^"]+)"/)[1];
    const text = readText(repo, q.citationPath);
    const lines = text.split(/\r?\n/);
    const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    if (new RegExp("\\b" + esc + "\\b").test(text)) supported++;
    if (q.citationStart && q.citationEnd && lines.slice(q.citationStart - 1, q.citationEnd).join("\n").includes(name)) lineOk++;
    if (seen.has(q.prompt)) dupPrompt++;
    seen.add(q.prompt);
    pos[q.answerIndex]++;
    if (name.length <= 2) trivialName++;
  }
  rows.push({ repo, generated: qs.length, nameInFile: supported, nameInCitedLines: lineOk, dupPrompt, shortNames: trivialName, answerPositions: pos });
}
let md = "# RQ3 (offline fallback): deterministic validity checks\n\nAsked for 10 questions per repo.\n\n| Repo | generated | name appears in cited file | name appears in cited lines | duplicate prompts | names <= 2 chars | answer positions A/B/C/D |\n|---|---|---|---|---|---|---|\n";
for (const r of rows) md += `| ${r.repo} | ${r.generated} | ${r.nameInFile} | ${r.nameInCitedLines} | ${r.dupPrompt} | ${r.shortNames} | ${r.answerPositions.join("/")} |\n`;
const tot = (k) => rows.reduce((s, r) => s + r[k], 0);
md += `\nTotals: ${tot("generated")} questions, ${tot("nameInFile")} supported by the cited file, ${tot("nameInCitedLines")} supported by the cited lines.\n`;
fs.writeFileSync(path.join(ROOT, "out", "rq3_offline.md"), md);
console.log(md);
