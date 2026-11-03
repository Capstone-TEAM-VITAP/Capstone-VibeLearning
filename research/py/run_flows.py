"""
Execution-flow reconstruction: which file-to-file edges carry the behaviour a question asks about?

Two question sets:
  dev       data/flows.json          23 flows on this repository and hackathon-starter; used for error
                                     analysis while the relevance-aware pruner was designed
  held-out  data/flows_heldout.json  25 flows on seven other repositories; annotated before any
                                     relevance-aware variant was run on them

Systems (all predict a set of file-to-file edges)
  bfs2             unpruned 2-hop outgoing BFS from the 3 files whose paths best match the query
  overlap-top3     3 edges whose endpoints best match query words in their paths (no structure)
  relevance-top3   3 edges whose endpoints rank best under BM25 (content-aware, no structure)
  pruner-path      Graph Path Pruning, relevance = path-word overlap          (first design)
  pruner-bm25      Graph Path Pruning, relevance = BM25 reciprocal rank       (primary, declared before held-out run)
  pruner-hybrid    Graph Path Pruning, relevance = RRF(BM25, LSA, graph) reciprocal rank
  ablations of pruner-bm25: -noroles, -nocont, -K2, -K5
"""

from __future__ import annotations

import json

from common import RESEARCH, bootstrap_ci, fmt_p, load_ir, mean, paired_diff_ci, paired_permutation_p, read_text, set_prf
from oracle import import_pairs
from src.retrieval.filegraph import build_file_graph
from src.retrieval.hybrid import RepoRetriever, relevance_from_ranking
from src.retrieval.pruner import bfs_edges, prune, top_overlap_edges, top_relevance_edges

SYSTEMS = [
    "bfs2", "overlap-top3", "relevance-top3", "pruner-path", "pruner-bm25", "pruner-hybrid",
    "pruner-bm25-noroles", "pruner-bm25-nocont", "pruner-bm25-K2", "pruner-bm25-K5",
]
PRIMARY = "pruner-bm25"


def predict(fg, retr: RepoRetriever, query: str) -> dict[str, set[tuple[str, str]]]:
    ranks = retr.rankings(query)
    rel_bm = relevance_from_ranking(ranks["bm25"])
    rel_hy = relevance_from_ranking(ranks["hybrid+bm25"])
    pairs = lambda edges: {e.pair for e in edges}  # noqa: E731
    return {
        "bfs2": set(bfs_edges(fg, query, hops=2)),
        "overlap-top3": set(top_overlap_edges(fg, query, 3)),
        "relevance-top3": set(top_relevance_edges(fg, rel_bm, 3)),
        "pruner-path": pairs(prune(fg, query, 3)),
        "pruner-bm25": pairs(prune(fg, query, 3, relevance=rel_bm)),
        "pruner-hybrid": pairs(prune(fg, query, 3, relevance=rel_hy)),
        "pruner-bm25-noroles": pairs(prune(fg, query, 3, use_roles=False, relevance=rel_bm)),
        "pruner-bm25-nocont": pairs(prune(fg, query, 3, use_continuity=False, relevance=rel_bm)),
        "pruner-bm25-K2": pairs(prune(fg, query, 2, relevance=rel_bm)),
        "pruner-bm25-K5": pairs(prune(fg, query, 5, relevance=rel_bm)),
    }


def evaluate(spec: list[dict], cache: dict) -> list[dict]:
    rows = []
    for q in spec:
        repo = q["repo"]
        if repo not in cache:
            ir = load_ir(repo)
            paths = [n["metadata"]["path"] for n in ir["nodes"] if n["type"] == "file"]
            texts = {p: read_text(repo, p) for p in paths}
            cache[repo] = (
                build_file_graph(ir),
                RepoRetriever(ir, texts),
                import_pairs(repo, False) | import_pairs(repo, True),
            )
        fg, retr, truth = cache[repo]
        gold = {tuple(e) for e in q["gold"]}
        missing = sorted(e for e in gold if e not in truth)
        preds = predict(fg, retr, q["query"])
        scores = {}
        for s, pred in preds.items():
            p, r, f = set_prf(pred, gold)
            scores[s] = {"precision": p, "recall": r, "f1": f, "n_pred": len(pred)}
        rows.append({"id": q["id"], "repo": repo, "lang": q["lang"], "n_gold": len(gold), "missing_gold": missing,
                     "scores": scores, "pruner_edges": sorted(preds[PRIMARY])})
    return rows


def main() -> None:
    cache: dict = {}
    dev_spec = json.loads((RESEARCH / "data" / "flows.json").read_text())["questions"]
    held_spec = json.loads((RESEARCH / "data" / "flows_heldout.json").read_text())["questions"]
    sets = {"dev": evaluate(dev_spec, cache), "heldout": evaluate(held_spec, cache)}
    (RESEARCH / "out" / "flows_raw.json").write_text(json.dumps(sets, indent=1))

    md = ["# Execution-flow reconstruction\n"]
    for name, rows in sets.items():
        bad = [(r["id"], r["missing_gold"]) for r in rows if r["missing_gold"]]
        md.append(f"{name}: {len(rows)} questions; gold edges absent from the independent import oracle: {bad or 'none'}\n")

    def table(title, subset):
        md.append(f"\n## {title} (n={len(subset)})\n")
        md.append("| System | precision | recall | F1 (mean [95% CI]) | mean predicted edges |\n|---|---|---|---|---|")
        for s in SYSTEMS:
            f1 = [r["scores"][s]["f1"] for r in subset]
            lo, hi = bootstrap_ci(f1, 5000)
            md.append(f"| {s} | {mean([r['scores'][s]['precision'] for r in subset]):.3f} | "
                      f"{mean([r['scores'][s]['recall'] for r in subset]):.3f} | {mean(f1):.3f} [{lo:.3f}, {hi:.3f}] | "
                      f"{mean([r['scores'][s]['n_pred'] for r in subset]):.1f} |")

    table("Held-out flows, all (CONFIRMATORY)", sets["heldout"])
    table("Held-out, Python repositories", [r for r in sets["heldout"] if r["lang"] == "py"])
    table("Held-out, JavaScript repositories", [r for r in sets["heldout"] if r["lang"] == "js"])
    table("Dev flows, all", sets["dev"])

    md.append("\n## Paired comparisons on F1 (A minus B)\n")
    md.append("| Set | A | B | mean diff | 95% CI | p |\n|---|---|---|---|---|---|")
    pairs = [(PRIMARY, "bfs2"), (PRIMARY, "overlap-top3"), (PRIMARY, "relevance-top3"), (PRIMARY, "pruner-path"),
             (PRIMARY, "pruner-hybrid"), (PRIMARY, "pruner-bm25-noroles"), (PRIMARY, "pruner-bm25-nocont"),
             ("pruner-hybrid", "bfs2"), ("pruner-hybrid", "overlap-top3"), ("pruner-hybrid", "relevance-top3")]  # last three: exploratory
    for name in ("heldout", "dev"):
        rows = sets[name]
        for a, b in pairs:
            xa = [r["scores"][a]["f1"] for r in rows]
            xb = [r["scores"][b]["f1"] for r in rows]
            d, lo, hi = paired_diff_ci(xa, xb, 5000)
            md.append(f"| {name} | {a} | {b} | {d:+.3f} | [{lo:+.3f}, {hi:+.3f}] | {fmt_p(paired_permutation_p(xa, xb))} |")

    md.append("\n## Edge reduction (held-out)\n")
    a = mean([r["scores"]["bfs2"]["n_pred"] for r in sets["heldout"]])
    b = mean([r["scores"][PRIMARY]["n_pred"] for r in sets["heldout"]])
    md.append(f"Mean predicted edges: bfs2 {a:.1f}, {PRIMARY} {b:.1f} ({100 * (1 - b / a):.1f}% fewer).")

    md.append("\n## Per-question results\n\n| set | id | gold | bfs2 F1 | relevance-top3 F1 | primary F1 | primary edges |\n|---|---|---|---|---|---|---|")
    for name, rows in sets.items():
        for r in rows:
            md.append(f"| {name} | {r['id']} | {r['n_gold']} | {r['scores']['bfs2']['f1']:.2f} | {r['scores']['relevance-top3']['f1']:.2f} | "
                      f"{r['scores'][PRIMARY]['f1']:.2f} | {r['scores'][PRIMARY]['n_pred']} |")
    text = "\n".join(md)
    (RESEARCH / "out" / "flows_tables.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
