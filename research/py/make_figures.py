"""Figures for the paper, drawn from the raw result files in research/out/. Run with any Python that has matplotlib."""

from __future__ import annotations

import json
import random
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RESEARCH = Path(__file__).resolve().parents[1]
OUT = RESEARCH / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

COLORS = {
    "random": "#D0D0D0",
    "bm25": "#4C72B0",
    "product": "#E39A9C",
    "product-v2-dense": "#C44E52",
    "lsa": "#8C8C8C",
    "dense": "#8172B3",
    "graph": "#DD8452",
    "hybrid-lsa": "#55A868",
    "bm25+dense+graph": "#2E7D5B",
}
LABELS = {"random": "Random", "bm25": "BM25", "product": "CodeAI v1", "product-v2-dense": "CodeAI v2", "lsa": "LSA", "dense": "Dense (bge)", "graph": "Graph",
          "hybrid-lsa": "RRF LSA+graph", "bm25+dense+graph": "RRF all three"}
plt.rcParams.update({"font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 100})


def mean_ci(xs: list[float], b: int = 2000, seed: int = 1) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(xs)
    m = sum(xs) / n
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return m, ms[int(0.025 * b)], ms[int(0.975 * b)]


def retrieval_figure(rows: list[dict], pred, title: str, fname: str) -> None:
    panels = [("locate", "mrr", "Locate (MRR)"), ("dependency", "mrr", "Direct importers (MRR)"), ("impact", "ndcg@10", "Impact (nDCG@10)")]
    systems = ["random", "bm25", "product", "product-v2-dense", "lsa", "dense", "graph", "hybrid-lsa", "bm25+dense+graph"]
    fig, axes = plt.subplots(1, 3, figsize=(7.4, 2.8), sharey=True)
    for ax, (typ, metric, label) in zip(axes, panels):
        sub = [r for r in rows if r["cond"] == "code" and pred(r) and r["type"] == typ]
        for i, s in enumerate(systems):
            m, lo, hi = mean_ci([r["scores"][s][metric] for r in sub])
            ax.bar(i, m, color=COLORS[s], yerr=[[m - lo], [hi - m]], capsize=2, error_kw={"lw": 0.8})
            ax.text(i, hi + 0.015, f"{m:.2f}", ha="center", va="bottom", fontsize=5.8)
        ax.set_xticks(range(len(systems)))
        ax.set_xticklabels([LABELS[s] for s in systems], rotation=40, ha="right", fontsize=7)
        ax.set_title(f"{label}, n={len(sub)}", fontsize=8.5)
        ax.set_ylim(0, 1.15)
        ax.grid(axis="y", lw=0.3, alpha=0.6)
    axes[0].set_ylabel("score (higher is better)")
    fig.suptitle(title, fontsize=9, y=1.02)
    fig.tight_layout()
    fig.savefig(OUT / fname, dpi=220, bbox_inches="tight")
    plt.close(fig)


def flows_figure(held: list[dict]) -> None:
    systems = [
        ("random3", "Random\n3 edges", "#D0D0D0"),
        ("candidates-bm25", "Candidate\npool", "#A0A0A0"),
        ("bfs2-bm25", "2-hop BFS\n(BM25)", "#8C8C8C"),
        ("overlap-top3", "Top-3 by\npath words", "#B8B8B8"),
        ("relevance-top3", "Top-3 by\nBM25", "#9FB6D6"),
        ("pruner-bm25", "Pruner\n(BM25)\nprimary", "#DD8452"),
        ("pruner-bm25-thr0", "Pruner\nthr 0\npost hoc", "#E8B48F"),
        ("pruner-hybrid", "Pruner\n(fused)\npost hoc", "#55A868"),
    ]
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(7.6, 2.9), gridspec_kw={"width_ratios": [1.9, 1]})
    for i, (s, label, color) in enumerate(systems):
        m, lo, hi = mean_ci([r["scores"][s]["f1"] for r in held], 5000)
        a1.bar(i, m, color=color, yerr=[[m - lo], [hi - m]], capsize=2, error_kw={"lw": 0.8},
               hatch="//" if "post" in label else None, edgecolor="white" if "post" in label else None)
        a1.text(i, hi + 0.015, f"{m:.2f}", ha="center", fontsize=7)
    a1.set_xticks(range(len(systems)))
    a1.set_xticklabels([x[1] for x in systems], fontsize=5.6)
    a1.set_ylabel("flow-edge F1")
    a1.set_ylim(0, 0.62)
    a1.set_title("Flow reconstruction F1, held-out (n=25)", fontsize=8.5)
    a1.grid(axis="y", lw=0.3, alpha=0.6)

    edge_systems = [x for x in systems if x[0] in ("candidates-bm25", "bfs2-bm25", "pruner-bm25", "pruner-hybrid")]
    for i, (s, label, color) in enumerate(edge_systems):
        m = sum(r["scores"][s]["n_pred"] for r in held) / len(held)
        a2.bar(i, m, color=color)
        a2.text(i, m + 0.3, f"{m:.1f}", ha="center", fontsize=7)
    a2.set_xticks(range(len(edge_systems)))
    a2.set_xticklabels([x[1] for x in edge_systems], fontsize=6.5)
    a2.set_ylabel("edges returned per question")
    a2.set_title("Output size", fontsize=8.5)
    a2.grid(axis="y", lw=0.3, alpha=0.6)
    fig.tight_layout()
    fig.savefig(OUT / "flows.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def accuracy_figure(acc: list[dict]) -> None:
    rows = [r for r in acc if r["lang"] == "python"] + [r for r in acc if r["lang"] == "js"]
    fig, ax = plt.subplots(figsize=(7.4, 3.0))
    xs = range(len(rows))
    rec = [r["recall"] if r["recall"] is not None else 0 for r in rows]
    colors = ["#55A868" if r["lang"] == "python" else "#4C72B0" for r in rows]
    ax.bar(xs, rec, color=colors)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([r["repo"] for r in rows], rotation=60, ha="right", fontsize=6.5)
    ax.set_ylim(0.85, 1.005)
    ax.set_ylabel("import-edge recall (axis starts at 0.85)", fontsize=7.5)
    ax.set_title("Import resolution against independent oracles (green: Python vs ast, blue: JavaScript vs regex)", fontsize=8)
    ax.grid(axis="y", lw=0.3, alpha=0.6)
    fig.tight_layout()
    fig.savefig(OUT / "accuracy.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    rows = json.loads((RESEARCH / "out" / "hybrid_raw.json").read_text())["rows"]
    retrieval_figure(rows, lambda r: r["split"] == "test2", "Held-out JavaScript repositories (5), comments removed", "retrieval_js.png")
    retrieval_figure(rows, lambda r: r["split"] == "python", "Python repositories (4), comments removed", "retrieval_py.png")
    held = json.loads((RESEARCH / "out" / "flows_raw.json").read_text())["heldout"]
    flows_figure(held)
    accuracy_figure(json.loads((RESEARCH / "out" / "accuracy_raw.json").read_text()))
    print(sorted(p.name for p in OUT.iterdir()))


if __name__ == "__main__":
    main()
