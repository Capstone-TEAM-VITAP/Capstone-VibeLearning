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


def box(ax, x, y, w, h, title, sub="", fill=BLUE, fs=9.0):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.12", fc=fill, ec=EDGE, lw=0.9))
    if sub:
        ax.text(x + w / 2, y + h * 0.66, title, ha="center", va="center", fontsize=fs, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.30, sub, ha="center", va="center", fontsize=fs - 2.0, color="#333333")
    else:
        ax.text(x + w / 2, y + h / 2, title, ha="center", va="center", fontsize=fs, fontweight="bold")


def arrow(ax, p, q, style="-|>", ls="-"):
    ax.add_patch(FancyArrowPatch(p, q, arrowstyle=style, mutation_scale=11, lw=1.0, color=EDGE, linestyle=ls,
                                 shrinkA=0, shrinkB=0))


def line(ax, xs, ys):
    ax.plot(xs, ys, color=EDGE, lw=1.0, solid_capstyle="round")


def band(ax, x, y, w, h, label, fill, right=False):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.18", fc=fill, ec="none", alpha=0.45))
    ax.text(x + w - 0.15 if right else x + 0.15, y + h - 0.15, label, ha="right" if right else "left", va="top",
            fontsize=9.6, fontweight="bold", color="#222222")


def architecture() -> None:
    fig, ax = plt.subplots(figsize=(8.4, 10.6))
    ax.set_xlim(0, 10)
    ax.set_ylim(0, 12.6)
    ax.axis("off")
    W, H = 2.2, 1.0
    xs = [0.25, 2.7, 5.15, 7.6]

    # Band 1: static analysis (two rows, snake order)
    band(ax, 0.1, 8.55, 9.8, 3.95, "1. Static analysis service (apps/ai-service: Python, Tree-sitter)", BLUE)
    y1, y2 = 10.75, 8.85
    box(ax, xs[0], y1, W, H, "Repository", "git snapshot of a commit", GREY)
    box(ax, xs[1], y1, W, H, "Scanner", "file list, ignore rules")
    box(ax, xs[2], y1, W, H, "Tree-sitter parser", "JavaScript | Python")
    box(ax, xs[3], y1, W, H, "Symbols, relations", "defs, imports, calls")
    box(ax, xs[3], y2, W, H, "Import resolver", "relative | package | suffix")
    box(ax, xs[2], y2, W, H, "Role classifier", "route, controller, service")
    box(ax, xs[1], y2, W, H, "CodeGraph", "nodes + typed edges")
    box(ax, xs[0], y2, W, H, "Graph IR (JSON)", "schema 1.0")
    for i in range(3):
        arrow(ax, (xs[i] + W, y1 + H / 2), (xs[i + 1], y1 + H / 2))
    arrow(ax, (xs[3] + W / 2, y1), (xs[3] + W / 2, y2 + H))
    for i in (3, 2, 1):
        arrow(ax, (xs[i], y2 + H / 2), (xs[i - 1] + W, y2 + H / 2))

    # Band 2: retrieval
    band(ax, 0.1, 3.05, 9.8, 5.2, "2. Retrieval layer (apps/ai-service/src/retrieval)", GREEN)
    fx, fy, fw = 3.3, 6.65, 3.4
    box(ax, fx, fy, fw, H, "File graph view", "files + import, call, depends-on edges", GREEN)
    gx = xs[0] + W / 2
    line(ax, [gx, gx], [y2, fy + H / 2])
    arrow(ax, (gx, fy + H / 2), (fx, fy + H / 2))
    ry = 4.95
    centers = [x + W / 2 for x in xs]
    bus1 = 6.2
    line(ax, [fx + fw / 2, fx + fw / 2], [fy, bus1])
    line(ax, [centers[0], centers[-1]], [bus1, bus1])
    for c in centers:
        arrow(ax, (c, bus1), (c, ry + H))
    box(ax, xs[0], ry, W, H, "BM25", "keywords over file text", GREEN)
    box(ax, xs[1], ry, W, H, "LSA vectors", "TF-IDF + truncated SVD", GREEN)
    box(ax, xs[2], ry, W, H, "Neural dense", "bge-small, 40-line windows", GREEN)
    box(ax, xs[3], ry, W, H, "Graph ranker", "reverse BFS, name match", GREEN)
    bus2 = 4.55
    for c in centers:
        line(ax, [c, c], [ry, bus2])
    line(ax, [centers[0], centers[-1]], [bus2, bus2])
    rrf_x, rrf_w, py_ = 0.3, 2.9, 3.3
    arrow(ax, (rrf_x + rrf_w / 2, bus2), (rrf_x + rrf_w / 2, py_ + H))
    box(ax, rrf_x, py_, rrf_w, H, "Reciprocal Rank Fusion", "text ranker(s) + graph", GREEN)
    pr_x, pr_w = 4.05, 2.9
    box(ax, pr_x, py_, pr_w, H, "Graph Path Pruner", "keeps at most K = 3 connected edges", GREEN)
    arrow(ax, (rrf_x + rrf_w, py_ + H / 2), (pr_x, py_ + H / 2))
    ax.text((rrf_x + rrf_w + pr_x) / 2, py_ + H / 2 + 0.14, "relevance", fontsize=7.6, color="#333333", ha="center")

    # Band 3: outputs
    band(ax, 0.1, 0.1, 9.8, 2.65, "3. Outputs and consumers", ORANGE, right=True)
    oy = 0.45
    box(ax, rrf_x, oy, rrf_w, H, "Ranked files", "locate | dependency | impact", ORANGE)
    box(ax, pr_x, oy, pr_w, H, "Flow edges", "at most K-max per question", ORANGE)
    box(ax, 7.2, oy, 2.6, H, "Chat and quizzes", "CodeAI v2: graph routing + RRF", ORANGE)
    arrow(ax, (rrf_x + rrf_w / 2, py_), (rrf_x + rrf_w / 2, oy + H))
    arrow(ax, (pr_x + pr_w / 2, py_), (pr_x + pr_w / 2, oy + H))
    ax.text(8.5, 1.95, "JavaScript port of the rankers;\nneural ranking optional", fontsize=7.4, color="#555555", ha="center", va="center")
    fig.savefig(OUT / "architecture.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def pruning_flow() -> None:
    fig, ax = plt.subplots(figsize=(10.3, 3.3))
    ax.set_xlim(0, 10.3)
    ax.set_ylim(0, 3.3)
    ax.axis("off")
    ax.text(0.05, 3.1, "Input: a question and the file graph", fontsize=9.4, fontweight="bold", va="center")
    steps = [
        ("1. Relevance", "each file gets a score\nfrom 0 to 1: path words,\nor 1 / rank in a retrieval\nranking (top 10 only)", GREEN),
        ("2. Score edges", "1.5 x rel(u) + 1.5 x rel(v)\n+ edge type (0.5 to 2.0)\n+ layer bonus (3.0 to 8.0)", GREEN),
        ("3. Filter", "drop test files,\nedges with no relevance,\nand edges scoring < 2.0", GREEN),
        ("4. Greedy chain", "best edge first, then\nedges that connect to it\n(+2.0), at most K = 3", GREEN),
        ("Output", "2 to 3 file-to-file\ndependency edges\nthat explain the flow", ORANGE),
    ]
    w, gap, y, h = 1.76, 0.30, 0.75, 2.0
    for i, (t, sub, col) in enumerate(steps):
        x = 0.05 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.0,rounding_size=0.12", fc=col, ec=EDGE, lw=0.9))
        ax.text(x + w / 2, y + h - 0.35, t, ha="center", va="center", fontsize=9.6, fontweight="bold")
        ax.text(x + w / 2, y + h * 0.40, sub, ha="center", va="center", fontsize=7.0, color="#333333", linespacing=1.35)
        if i < len(steps) - 1:
            arrow(ax, (x + w + 0.04, y + h / 2), (x + w + gap - 0.04, y + h / 2))
    ax.text(5.1, 0.3, "Ablation switches: the layer bonus (route, controller, service, repository) and the continuity bonus can each be turned off.",
            ha="center", fontsize=7.8, color="#444444")
    fig.savefig(OUT / "pruning_flow.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    architecture()
    pruning_flow()
    print(sorted(p.name for p in OUT.iterdir()))
