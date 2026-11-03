"""Architecture and algorithm diagrams for the paper (matplotlib, no data needed)."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

BLUE, GREEN, ORANGE, GREY = "#DCE8F7", "#DDF0E1", "#FBE5D0", "#EEEEEE"
EDGE = "#4A4A4A"


def box(ax, x, y, w, h, title, sub="", fill=BLUE, fs=7.4):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.012,rounding_size=0.015", fc=fill, ec=EDGE, lw=0.8))
    if sub:
        ax.text(x + w / 2, y + h * 0.64, title, ha="center", va="center", fontsize=fs, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.28, sub, ha="center", va="center", fontsize=fs - 1.2, color="#333333")
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=fs, fontweight="bold")


def arrow(ax, p, q, style="-|>", ls="-", rad=0.0):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=9, lw=0.9, color=EDGE, linestyle=ls,
                                 connectionstyle=f"arc3,rad={rad}"))


def band(ax, x, y, w, h, label, fill):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.02", fc=fill, ec="none", alpha=0.35))
    ax.text(x + 0.008, y + h - 0.012, label, ha="left", va="top", fontsize=7.6, fontweight="bold", color="#222222")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(7.4, 6.6))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    # Band 1: static analysis
    band(ax, 0.01, 0.665, 0.98, 0.32, "1. Static analysis service (apps/ai-service: Python, Tree-sitter)", BLUE)
    w, h = 0.21, 0.105
    xs = [0.03, 0.27, 0.51, 0.75]
    y1, y2 = 0.82, 0.685
    box(ax, xs[0], y1, w, h, "Repository", "git snapshot of a commit", GREY)
    box(ax, xs[1], y1, w, h, "Scanner", "file list, ignore rules", BLUE)
    box(ax, xs[2], y1, w, h, "Tree-sitter parser", "JavaScript | Python", BLUE)
    box(ax, xs[3], y1, w, h, "Symbols, relations", "defs, imports, calls", BLUE)
    box(ax, xs[3], y2, w, h, "Import resolver", "relative | package | suffix", BLUE)
    box(ax, xs[2], y2, w, h, "Role classifier", "route, controller, service", BLUE)
    box(ax, xs[1], y2, w, h, "CodeGraph", "nodes + typed edges", BLUE)
    box(ax, xs[0], y2, w, h, "Graph IR (JSON)", "schema 1.0", BLUE)
    for i in range(3):
        arrow(ax, (xs[i] + w, y1 + h / 2), (xs[i + 1], y1 + h / 2))
    arrow(ax, (xs[3] + w / 2, y1), (xs[3] + w / 2, y2 + h))
    for i in (3, 2, 1):
        arrow(ax, (xs[i], y2 + h / 2), (xs[i - 1] + w, y2 + h / 2))

    # Band 2: retrieval
    band(ax, 0.01, 0.215, 0.98, 0.43, "2. Retrieval layer (apps/ai-service/src/retrieval)", GREEN)
    box(ax, 0.35, 0.505, 0.30, 0.085, "File graph view", "files + import, call, depends-on edges", GREEN)
    arrow(ax, (xs[0] + w / 2, y2), (0.35, 0.55), rad=0.25)
    rw, ry, rh = 0.26, 0.375, 0.085
    rx = [0.05, 0.37, 0.69]
    box(ax, rx[0], ry, rw, rh, "BM25", "keywords over file text", GREEN)
    box(ax, rx[1], ry, rw, rh, "Vector (LSA)", "TF-IDF + truncated SVD", GREEN)
    box(ax, rx[2], ry, rw, rh, "Graph ranker", "reverse BFS, name match", GREEN)
    for x0 in rx:
        arrow(ax, (0.50, 0.505), (x0 + rw / 2, ry + rh))
    box(ax, 0.17, 0.245, 0.32, 0.085, "Reciprocal Rank Fusion", "weights 0.55 vector, 0.45 graph", GREEN)
    for x0 in rx:
        arrow(ax, (x0 + rw / 2, ry), (0.33, 0.33))
    box(ax, 0.60, 0.245, 0.32, 0.085, "Graph Path Pruner", "keep at most K = 3 connected edges", GREEN)
    arrow(ax, (0.49, 0.2875), (0.60, 0.2875))
    ax.text(0.545, 0.305, "relevance", fontsize=6.2, color="#333333", ha="center")

    # Band 3: outputs
    band(ax, 0.01, 0.01, 0.98, 0.18, "3. Outputs and consumers", ORANGE)
    box(ax, 0.03, 0.03, 0.29, 0.085, "Ranked files", "locate | dependency | impact", ORANGE)
    box(ax, 0.355, 0.03, 0.29, 0.085, "Flow edges", "at most K-max per question", ORANGE)
    box(ax, 0.68, 0.03, 0.29, 0.085, "Backend chat and quizzes", "own BM25 + symbol retriever", ORANGE, fs=7.0)
    arrow(ax, (0.33, 0.245), (0.175, 0.115))
    arrow(ax, (0.76, 0.245), (0.50, 0.115))
    ax.text(0.825, 0.135, "separate JavaScript code;\nLLM answers not evaluated", fontsize=5.8, color="#555555", ha="center")
    fig.savefig(OUT / "architecture.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def pruning_flow() -> None:
    fig, ax = plt.subplots(figsize=(7.4, 2.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.text(0.01, 0.93, "Input: a question and the file graph", fontsize=7, fontweight="bold", va="center")
    steps = [
        ("1. Relevance", "each file gets a score\nfrom 0 to 1: path words,\nor 1 / rank in a retrieval\nranking (top 10 only)", GREEN),
        ("2. Score edges", "1.5 x rel(u) + 1.5 x rel(v)\n+ edge type (0.5 to 2.0)\n+ layer bonus (3.0 to 8.0)", GREEN),
        ("3. Filter", "drop test files,\nedges with no relevance,\nand edges scoring < 2.0", GREEN),
        ("4. Greedy chain", "best edge first, then\nedges that connect to it\n(+2.0), at most K = 3", GREEN),
        ("Output", "2 to 3 file-to-file\ndependency edges\nthat explain the flow", ORANGE),
    ]
    n = len(steps)
    w, gap = 0.175, 0.025
    for i, (t, sub, col) in enumerate(steps):
        x = 0.01 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, 0.20), w, 0.58, boxstyle="round,pad=0.012,rounding_size=0.015", fc=col, ec=EDGE, lw=0.8))
        ax.text(x + w / 2, 0.68, t, ha="center", va="center", fontsize=7.4, fontweight="bold")
        ax.text(x + w / 2, 0.40, sub, ha="center", va="center", fontsize=5.9, color="#333333", linespacing=1.3)
        if i < n - 1:
            arrow(ax, (x + w + 0.012, 0.49), (x + w + gap - 0.002, 0.49))
    ax.text(0.5, 0.06, "Ablation switches: the layer bonus (route, controller, service, repository) and the continuity bonus can each be turned off.",
            ha="center", fontsize=6.2, color="#444444")
    fig.savefig(OUT / "pruning_flow.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    pruning_flow()
    print(sorted(p.name for p in OUT.iterdir()))
