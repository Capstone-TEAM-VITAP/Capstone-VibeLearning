"""
File-level retrieval benchmark: lexical vs neural vs LSA vs graph rankers and their fusions.

Text conditions
  code   (primary, leak-free) comments and docstrings are removed before indexing. Locate questions are
         built from those comments, so this stops a ranker from matching the answer text verbatim.
         Locate questions whose text still occurs in the comment-free gold file are dropped.
  raw    files indexed as they are on disk (the setting of the earlier report); kept for comparison.

Systems
  random        seeded shuffle
  bm25          lexical
  product       CodeAI's chat retriever before this study (v1) (apps/backend/src/services/retrieval.service.js: BM25 plus a
                symbol-name bonus), run in Node by research/src/run_product.mjs and read from
                out/product_rankings.json
  product-v2    CodeAI's retriever after this study, without the optional neural ranking
  product-v2-dense  CodeAI's retriever after this study, with the neural ranking (the deployed design)
  lsa           TF-IDF + truncated SVD (not a neural model)
  dense         pretrained neural embeddings (bge-small-en-v1.5), max over 40-line windows
  graph         structural ranker (reverse-dependency BFS for import/impact questions)
  hybrid-lsa    RRF(lsa 0.55, graph 0.45)            <- the fusion of the earlier report
  hybrid-dense  RRF(dense 0.55, graph 0.45)
  bm25+graph    RRF(bm25, graph), equal weights   <- control: fusion with a weak-but-real text ranker
  bm25+dense+graph  RRF of the three, equal weights

Groups: JS held-out (test2), JS post-hoc (dev+test), Python (4 repositories).
"""

from __future__ import annotations

import json
import math
import time

from common import (
    ALL_REPOS,
    RESEARCH,
    bootstrap_ci,
    code_only_text,
    file_paths,
    load_ir,
    mean,
    norm_text,
    rank_scores,
    read_text,
    seeded_shuffle,
)
from dense import DenseIndex, embed_queries
from src.retrieval.filegraph import tokenize
from src.retrieval.hybrid import RRF_WEIGHTS, RepoRetriever, _STOP, graph_rank, rrf

SYSTEMS = ["random", "bm25", "product", "product-v2", "product-v2-dense", "lsa", "dense", "graph", "hybrid-lsa", "hybrid-dense", "bm25+graph", "bm25+dense+graph"]
CONDITIONS = ("code", "raw")
GROUPS = {
    "JS held-out (5 repos)": lambda q: q["split"] == "test2",
    "JS post-hoc (10 repos)": lambda q: q["split"] in ("dev", "test"),
    "Python (4 repos)": lambda q: q["split"] == "python",
}
METRICS = ["hit@1", "hit@5", "mrr", "ndcg"]
IMPACT_METRICS = ["recall@10", "capped_recall@10", "prec@10", "ndcg@10"]


def impact_scores(ranked: list[str], gold: list[str], k: int = 10) -> dict[str, float]:
    g = set(gold)
    top = ranked[:k]
    hits = sum(1 for p in top if p in g)
    dcg = sum(1 / math.log2(i + 2) for i, p in enumerate(top) if p in g)
    idcg = sum(1 / math.log2(i + 2) for i in range(min(len(g), k)))
    return {"recall@10": hits / len(g), "capped_recall@10": hits / min(len(g), k), "prec@10": hits / k,
            "ndcg@10": dcg / idcg if idcg else 0.0}


def score(q: dict, ranked: list[str]) -> dict[str, float]:
    ranked = [p for p in ranked if p not in set(q["exclude"])]
    if q["type"] == "impact":
        return impact_scores(ranked, q["gold"])
    s = rank_scores(ranked[:7], q["gold"])
    s10 = rank_scores(ranked[:10], q["gold"], max_k=10)
    s["mrr@10"] = s10["mrr"]
    s["hit@10"] = 1.0 if any(p in set(q["gold"]) for p in ranked[:10]) else 0.0
    return s


def lexical_overlap(q: dict, gold_text: str) -> float:
    qt = {t for t in tokenize(q["query"]) if t not in _STOP}
    ft = set(tokenize(gold_text))
    return len(qt & ft) / len(qt) if qt else 0.0


def main() -> None:
    questions = json.loads((RESEARCH / "data" / "questions_v3.json").read_text())
    product = json.loads((RESEARCH / "out" / "product_rankings.json").read_text())
    t0 = time.perf_counter()
    qvecs = embed_queries([q["query"] for q in questions])
    qvec = {q["id"]: v for q, v in zip(questions, qvecs)}

    rows: list[dict] = []
    sweep: list[dict] = []
    dropped: list[str] = []
    for cond in CONDITIONS:
        for repo in ALL_REPOS:
            ir = load_ir(repo)
            paths = file_paths(ir)
            reader = code_only_text if cond == "code" else read_text
            texts = {p: reader(repo, p) for p in paths}
            retr = RepoRetriever(ir, texts)
            dense = DenseIndex(repo, cond, {p: texts.get(p, "") for p in retr.fg.files})
            print(f"[{cond}] {repo}: indexed {len(paths)} files ({time.perf_counter() - t0:.0f}s)", flush=True)
            for q in (x for x in questions if x["repo"] == repo):
                if cond == "code" and q["type"] == "locate" and norm_text(q["query"]) in norm_text(texts.get(q["gold"][0], "")):
                    dropped.append(q["id"])
                    continue
                base = retr.rankings(q["query"])
                d = dense.rank_vec(qvec[q["id"]])
                lists = {
                    "random": seeded_shuffle(paths, q["id"]),
                    "bm25": base["bm25"],
                    "product": product["product"][cond][q["id"]],
                    "product-v2": product["product-v2"][cond][q["id"]],
                    "product-v2-dense": product["product-v2-dense"][cond][q["id"]],
                    "lsa": base["vector"],
                    "dense": d,
                    "graph": base["graph"],
                    "hybrid-lsa": base["hybrid"],
                    "hybrid-dense": rrf({"vector": d, "graph": base["graph"]}, RRF_WEIGHTS),
                    "bm25+graph": rrf({"bm25": base["bm25"], "graph": base["graph"]}),
                    "bm25+dense+graph": rrf({"bm25": base["bm25"], "dense": d, "graph": base["graph"]}),
                }
                row = {"id": q["id"], "repo": repo, "type": q["type"], "split": q["split"], "cond": cond,
                       "n_gold": len(q["gold"]), "scores": {s: score(q, lists[s]) for s in SYSTEMS}}
                if q["type"] == "locate":
                    row["overlap"] = lexical_overlap(q, texts.get(q["gold"][0], ""))
                rows.append(row)
                # fusion-parameter sensitivity on the held-out set (code condition only)
                if cond == "code" and q["split"] == "test2":
                    for wv in (0.2, 0.35, 0.5, 0.55, 0.65, 0.8):
                        for k0 in (10, 60, 200):
                            fused = rrf({"vector": base["vector"], "graph": base["graph"]}, {"vector": wv, "graph": 1 - wv}, k0)
                            sweep.append({"id": q["id"], "type": q["type"], "w_vec": wv, "k0": k0, "scores": score(q, fused)})

    out = {"rows": rows, "sweep": sweep, "dropped_leaky_locate": dropped,
           "retrieval_seconds": round(time.perf_counter() - t0, 1)}
    (RESEARCH / "out" / "hybrid_raw.json").write_text(json.dumps(out))

    md = ["# Retrieval: lexical, LSA, neural dense, graph and fusions\n",
          f"Rows: {len(rows)}. Leak-free condition dropped {len(dropped)} locate question(s) whose text survives in code: {dropped}\n"]
    for cond in CONDITIONS:
        for gname, pred in GROUPS.items():
            for typ, metrics in (("locate", METRICS), ("dependency", METRICS), ("impact", IMPACT_METRICS)):
                sub = [r for r in rows if r["cond"] == cond and pred(r) and r["type"] == typ]
                if not sub:
                    continue
                md.append(f"\n## [{cond}] {gname} - {typ} (n={len(sub)})\n")
                md.append("| System | " + " | ".join(metrics) + " |\n|---|" + "---|" * len(metrics))
                for s in SYSTEMS:
                    cells = []
                    for m in metrics:
                        xs = [r["scores"][s][m] for r in sub]
                        lo, hi = bootstrap_ci(xs, 2000)
                        cells.append(f"{mean(xs):.3f} [{lo:.3f}, {hi:.3f}]")
                    md.append(f"| {s} | " + " | ".join(cells) + " |")
    text = "\n".join(md)
    (RESEARCH / "out" / "hybrid_tables.md").write_text(text)
    print(text[:4000])


if __name__ == "__main__":
    main()
