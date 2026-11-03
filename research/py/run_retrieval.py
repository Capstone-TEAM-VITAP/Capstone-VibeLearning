"""
Hybrid semantic + structural retrieval benchmark (file level).

Systems
  random        seeded shuffle
  bm25          lexical
  vector        LSA dense vectors (offline, not a pretrained embedding model)
  graph         structural: name/path/symbol match + 1-hop diffusion; reverse-dependency BFS for
                "who imports / is affected by X" queries
  hybrid        RRF(vector 0.55, graph 0.45)               <- the fusion described in the paper
  hybrid+bm25   RRF(bm25, vector, graph), equal weights    <- strongest combination tried

Groups: JS-confirmatory (test2), JS-posthoc (dev+test), Python (4 repositories).
"""

from __future__ import annotations

import json
import time
from collections import defaultdict

from common import (
    ALL_REPOS,
    RESEARCH,
    bootstrap_ci,
    file_paths,
    fmt_p,
    load_ir,
    mean,
    paired_diff_ci,
    paired_permutation_p,
    rank_scores,
    read_text,
    seeded_shuffle,
)
from src.retrieval.hybrid import RepoRetriever

SYSTEMS = ["random", "bm25", "vector", "graph", "hybrid", "hybrid+bm25"]
GROUPS = {
    "JS confirmatory (5 repos)": lambda q: q["split"] == "test2",
    "JS post-hoc (10 repos)": lambda q: q["split"] in ("dev", "test"),
    "Python (4 repos)": lambda q: q["split"] == "python",
}
METRICS = ["hit@1", "hit@5", "mrr", "ndcg"]
IMPACT_METRICS = ["recall@10", "prec@10", "ndcg@10"]


def impact_scores(ranked: list[str], gold: list[str], k: int = 10) -> dict[str, float]:
    import math

    g = set(gold)
    top = ranked[:k]
    hits = sum(1 for p in top if p in g)
    dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(top) if p in g)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(g), k)))
    return {"recall@10": hits / len(g), "prec@10": hits / k, "ndcg@10": dcg / idcg if idcg else 0.0}


def main() -> None:
    questions = json.loads((RESEARCH / "data" / "questions_v3.json").read_text())
    retrievers: dict[str, RepoRetriever] = {}
    all_files: dict[str, list[str]] = {}
    build_secs: dict[str, float] = {}
    for repo in ALL_REPOS:
        ir = load_ir(repo)
        paths = file_paths(ir)
        all_files[repo] = paths
        texts = {p: read_text(repo, p) for p in paths}
        t0 = time.perf_counter()
        retrievers[repo] = RepoRetriever(ir, texts)
        build_secs[repo] = round(time.perf_counter() - t0, 2)

    rows = []
    for q in questions:
        r = retrievers[q["repo"]]
        lists = r.rankings(q["query"])
        lists["random"] = seeded_shuffle(all_files[q["repo"]], q["id"])
        ex = set(q["exclude"])
        scores = {}
        for s in SYSTEMS:
            ranked = [p for p in lists[s] if p not in ex]
            scores[s] = impact_scores(ranked, q["gold"]) if q["type"] == "impact" else rank_scores(ranked[:7], q["gold"])
        rows.append({"id": q["id"], "repo": q["repo"], "type": q["type"], "split": q["split"], "scores": scores})
    (RESEARCH / "out" / "hybrid_raw.json").write_text(json.dumps(rows))

    md = ["# Hybrid semantic + structural retrieval\n", f"Questions: {len(rows)}. Index build seconds per repo: {build_secs}\n"]

    def table(title, subset, metrics):
        md.append(f"\n## {title} (n={len(subset)})\n")
        md.append("| System | " + " | ".join(metrics) + " |\n|---|" + "---|" * len(metrics))
        for s in SYSTEMS:
            cells = []
            for m in metrics:
                xs = [r["scores"][s][m] for r in subset]
                lo, hi = bootstrap_ci(xs, 2000)
                cells.append(f"{mean(xs):.3f} [{lo:.3f}, {hi:.3f}]")
            md.append(f"| {s} | " + " | ".join(cells) + " |")

    for gname, pred in GROUPS.items():
        grp = [r for r in rows if pred(r)]
        for typ, metrics in (("locate", METRICS), ("dependency", METRICS), ("impact", IMPACT_METRICS)):
            sub = [r for r in grp if r["type"] == typ]
            if sub:
                table(f"{gname} - {typ}", sub, metrics)

    md.append("\n## Paired comparisons (A minus B)\n")
    md.append("| Group | Type | A | B | Metric | n | mean diff | 95% CI | p |\n|---|---|---|---|---|---|---|---|---|")
    pairs = [("hybrid", "vector"), ("hybrid", "graph"), ("hybrid", "bm25"), ("hybrid+bm25", "bm25"), ("graph", "bm25")]
    for gname, pred in GROUPS.items():
        grp = [r for r in rows if pred(r)]
        for typ, metrics in (("locate", ["mrr"]), ("dependency", ["mrr"]), ("impact", ["ndcg@10", "recall@10"])):
            sub = [r for r in grp if r["type"] == typ]
            if not sub:
                continue
            for a, b in pairs:
                for m in metrics:
                    xa = [r["scores"][a][m] for r in sub]
                    xb = [r["scores"][b][m] for r in sub]
                    d, lo, hi = paired_diff_ci(xa, xb, 2000)
                    md.append(f"| {gname} | {typ} | {a} | {b} | {m} | {len(sub)} | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {fmt_p(paired_permutation_p(xa, xb, draws=20000))} |")
    text = "\n".join(md)
    (RESEARCH / "out" / "hybrid_tables.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
