import { mulberry32 } from "./util.mjs";

export const KS = [1, 3, 5, 7];

export function rankedAfterExclusion(ranked, exclude) {
  const ex = new Set(exclude);
  return ranked.filter((p) => !ex.has(p));
}

export function scoreQuestion(ranked, gold, maxK = 7) {
  const g = new Set(gold);
  const top = ranked.slice(0, maxK);
  const out = {};
  for (const k of KS) {
    const hits = top.slice(0, k).filter((p) => g.has(p)).length;
    out[`hit@${k}`] = hits > 0 ? 1 : 0;
    out[`recall@${k}`] = hits / g.size;
  }
  const first = top.findIndex((p) => g.has(p));
  out.mrr = first >= 0 ? 1 / (first + 1) : 0;
  let dcg = 0;
  top.forEach((p, i) => { if (g.has(p)) dcg += 1 / Math.log2(i + 2); });
  let idcg = 0;
  for (let i = 0; i < Math.min(g.size, maxK); i++) idcg += 1 / Math.log2(i + 2);
  out.ndcg = idcg ? dcg / idcg : 0;
  return out;
}

export const mean = (xs) => (xs.length ? xs.reduce((a, b) => a + b, 0) / xs.length : NaN);

export function bootstrapCI(xs, B = 10000, seed = 1) {
  const rng = mulberry32(seed);
  const n = xs.length;
  const ms = [];
  for (let b = 0; b < B; b++) {
    let s = 0;
    for (let i = 0; i < n; i++) s += xs[Math.floor(rng() * n)];
    ms.push(s / n);
  }
  ms.sort((a, c) => a - c);
  return [ms[Math.floor(0.025 * B)], ms[Math.floor(0.975 * B)]];
}

// Paired sign-flip permutation test on per-question differences (two-sided).
// Exact when <= 18 non-zero differences, otherwise Monte Carlo with a fixed seed.
export function pairedPermutation(a, b, seed = 7, draws = 200000) {
  const d = a.map((x, i) => x - b[i]).filter((x) => x !== 0);
  const n = d.length;
  if (n === 0) return { p: 1, n };
  const obs = Math.abs(d.reduce((s, x) => s + x, 0));
  let ge = 0;
  let total;
  if (n <= 18) {
    total = 2 ** n;
    for (let m = 0; m < total; m++) {
      let s = 0;
      for (let i = 0; i < n; i++) s += m & (1 << i) ? d[i] : -d[i];
      if (Math.abs(s) >= obs - 1e-12) ge++;
    }
  } else {
    const rng = mulberry32(seed);
    total = draws;
    for (let t = 0; t < draws; t++) {
      let s = 0;
      for (let i = 0; i < n; i++) s += rng() < 0.5 ? d[i] : -d[i];
      if (Math.abs(s) >= obs - 1e-12) ge++;
    }
    ge += 1; total += 1; // add-one so p is never exactly 0
  }
  return { p: ge / total, n };
}

export function pairedBootstrapDiffCI(a, b, B = 10000, seed = 3) {
  const d = a.map((x, i) => x - b[i]);
  return [mean(d), ...bootstrapCI(d, B, seed)];
}
