"""
Write research/paper/tables.typ: the result tables of the paper, generated from the raw result
files so every number is reproducible. The best value in each column is shaded and bold.
"""

from __future__ import annotations

import json
import random
from pathlib import Path

RESEARCH = Path(__file__).resolve().parents[1]
OUT = RESEARCH / "paper" / "tables.typ"
GOOD = 'rgb("#dff0e3")'

SYSTEMS = [
    ("bm25", "BM25 text search"),
    ("vector", "Vector (LSA)"),
    ("graph", "Graph"),
    ("hybrid", "Hybrid (vector + graph)"),
    ("hybrid+bm25", "Hybrid + BM25"),
]


def mean(xs):
    return sum(xs) / len(xs)


def ci(xs, b=5000, seed=1):
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return ms[int(0.025 * b)], ms[int(0.975 * b)]


def cell(text: str, best: bool) -> str:
    return f"table.cell(fill: {GOOD})[*{text}*]" if best else f"[{text}]"


def pct(x: float) -> str:
    return f"{100 * x:.1f}%"


def retrieval_table(rows, pred, title: str | None, n_note: bool = True) -> str:
    """One table with three question types; two numbers each."""
    spec = [
        ("locate", ("hit@1", pct, "Ranked 1st"), ("mrr", lambda v: f"{v:.2f}", "MRR")),
        ("dependency", ("hit@1", pct, "Ranked 1st"), ("mrr", lambda v: f"{v:.2f}", "MRR")),
        ("impact", ("recall@10", pct, "Found in top 10"), ("ndcg@10", lambda v: f"{v:.2f}", "nDCG\\@10")),
    ]
    names = {"locate": "Where is it implemented?", "dependency": "Who imports file X?", "impact": "What is affected if X changes?"}
    data = {}
    counts = {}
    for typ, a, b in spec:
        sub = [r for r in rows if pred(r) and r["type"] == typ]
        counts[typ] = len(sub)
        for s, _ in SYSTEMS:
            data[(typ, s, a[0])] = mean([r["scores"][s][a[0]] for r in sub])
            data[(typ, s, b[0])] = mean([r["scores"][s][b[0]] for r in sub])
    best = {}
    for typ, a, b in spec:
        for key in (a[0], b[0]):
            best[(typ, key)] = max(data[(typ, s, key)] for s, _ in SYSTEMS)

    lines = ["table(", "  columns: (1.7fr, 0.9fr, 0.7fr, 0.9fr, 0.7fr, 1.0fr, 0.8fr),",
             "  align: (left, center, center, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header("]
    lines.append("    table.cell(rowspan: 2)[*Method*],")
    for typ, _, _ in spec:
        lines.append(f"    table.cell(colspan: 2)[*{names[typ]}* #linebreak() #text(size: 7.5pt)[{counts[typ]} questions]],")
    for typ, a, b in spec:
        lines.append(f"    [{a[2]}], [{b[2]}],")
    lines.append("  ),")
    if title:
        lines.append(f"  table.cell(colspan: 7, fill: luma(235))[*{title}*],")
    for s, label in SYSTEMS:
        row = [f"[{label}]"]
        for typ, a, b in spec:
            va, vb = data[(typ, s, a[0])], data[(typ, s, b[0])]
            row.append(cell(a[1](va), abs(va - best[(typ, a[0])]) < 1e-12))
            row.append(cell(b[1](vb), abs(vb - best[(typ, b[0])]) < 1e-12))
        lines.append("  " + ", ".join(row) + ",")
    lines.append(")")
    return "\n".join(lines)


def retrieval_multi(rows) -> str:
    """Post-hoc JavaScript and Python in one table, as two stacked blocks."""
    spec = [
        ("locate", ("hit@1", pct), ("mrr", lambda v: f"{v:.2f}")),
        ("dependency", ("hit@1", pct), ("mrr", lambda v: f"{v:.2f}")),
        ("impact", ("recall@10", pct), ("ndcg@10", lambda v: f"{v:.2f}")),
    ]
    groups = [
        ("JavaScript, ten repositories used earlier in the study (post hoc)", lambda r: r["split"] in ("dev", "test")),
        ("Python, four repositories", lambda r: r["split"] == "python"),
    ]
    names = {"locate": "Where is it implemented?", "dependency": "Who imports file X?", "impact": "What is affected if X changes?"}
    first = groups[0][1]
    counts = {typ: len([r for r in rows if first(r) and r["type"] == typ]) for typ, _, _ in spec}
    counts_py = {typ: len([r for r in rows if groups[1][1](r) and r["type"] == typ]) for typ, _, _ in spec}

    lines = ["table(", "  columns: (1.7fr, 0.9fr, 0.7fr, 0.9fr, 0.7fr, 1.0fr, 0.8fr),",
             "  align: (left, center, center, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),", "  table.header("]
    lines.append("    table.cell(rowspan: 2)[*Method*],")
    for typ, _, _ in spec:
        lines.append(f"    table.cell(colspan: 2)[*{names[typ]}*],")
    heads = {"locate": ("Ranked 1st", "MRR"), "dependency": ("Ranked 1st", "MRR"), "impact": ("Found in top 10", "nDCG\\@10")}
    for typ, _, _ in spec:
        lines.append(f"    [{heads[typ][0]}], [{heads[typ][1]}],")
    lines.append("  ),")
    for (gname, pred), cnt in zip(groups, (counts, counts_py)):
        note = ", ".join(f"{cnt[t]} {t}" for t, _, _ in spec)
        lines.append(f"  table.cell(colspan: 7, fill: luma(235))[*{gname}* #h(6pt) #text(size: 7.5pt)[({note} questions)]],")
        data = {}
        for typ, a, b in spec:
            sub = [r for r in rows if pred(r) and r["type"] == typ]
            for s, _ in SYSTEMS:
                data[(typ, s, a[0])] = mean([r["scores"][s][a[0]] for r in sub])
                data[(typ, s, b[0])] = mean([r["scores"][s][b[0]] for r in sub])
        best = {(typ, k): max(data[(typ, s, k)] for s, _ in SYSTEMS) for typ, a, b in spec for k in (a[0], b[0])}
        for s, label in SYSTEMS:
            row = [f"[{label}]"]
            for typ, a, b in spec:
                for key, fmt in (a, b):
                    v = data[(typ, s, key)]
                    row.append(cell(fmt(v), abs(v - best[(typ, key)]) < 1e-12))
            lines.append("  " + ", ".join(row) + ",")
    lines.append(")")
    return "\n".join(lines)


FLOW_LABELS = [
    ("baseline", "Baselines", [
        ("bfs2", "Unpruned traversal", "Follow every dependency up to 2 hops from the best-matching files"),
        ("overlap-top3", "Top 3 by path words", "The 3 edges whose file names share the most words with the question"),
        ("relevance-top3", "Top 3 by BM25", "The 3 edges between the files BM25 ranks highest"),
    ]),
    ("pruner", "Graph Path Pruning", [
        ("pruner-path", "Pruner, path relevance", "Scores edges by words in file names"),
        ("pruner-bm25", "Pruner, BM25 relevance (primary)", "Scores edges by BM25 file ranking; chosen before the held-out run"),
        ("pruner-hybrid", "Pruner, hybrid relevance (post hoc)", "Scores edges by the fused ranking; chosen after seeing results"),
    ]),
    ("ablation", "Switching parts off (from the primary pruner)", [
        ("pruner-bm25-noroles", "No layer hierarchy", "Ignore route, controller, service layers"),
        ("pruner-bm25-nocont", "No continuity bonus", "Do not prefer edges that connect to chosen ones"),
    ]),
]


def flows_table(held) -> str:
    stats = {}
    for _, _, items in FLOW_LABELS:
        for key, _, _ in items:
            f1 = [r["scores"][key]["f1"] for r in held]
            lo, hi = ci(f1)
            stats[key] = {
                "p": mean([r["scores"][key]["precision"] for r in held]),
                "r": mean([r["scores"][key]["recall"] for r in held]),
                "f": mean(f1), "lo": lo, "hi": hi,
                "n": mean([r["scores"][key]["n_pred"] for r in held]),
            }
    best_f = max(v["f"] for v in stats.values())
    lines = ["table(", "  columns: (2.2fr, 2.8fr, 0.9fr, 0.9fr, 0.8fr, 1.9fr),",
             "  align: (left, left, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header[*Method*][*What it does*][*Edges per question*][*Precision*][*Recall*][*F1 (95% interval)*],"]
    for _, group, items in FLOW_LABELS:
        lines.append(f"  table.cell(colspan: 6, fill: luma(235))[*{group}*],")
        for key, label, what in items:
            v = stats[key]
            f = f"{v['f']:.3f} \\[{v['lo']:.3f}, {v['hi']:.3f}\\]"
            fcell = cell(f, abs(v["f"] - best_f) < 1e-12)
            lines.append(f"  [{label}], [{what}], [{v['n']:.1f}], [{v['p']:.3f}], [{v['r']:.3f}], {fcell},")
    lines.append(")")
    return "\n".join(lines)


def accuracy_table(acc) -> str:
    def pooled(sel):
        o = sum(r["oracle"] for r in sel)
        g = sum(r["graph"] for r in sel)
        rec = sum((r["recall"] or 0) * r["oracle"] for r in sel) / o
        prec = sum((r["precision"] or 0) * r["graph"] for r in sel) / g
        return o, g, rec, prec

    py = [r for r in acc if r["lang"] == "python"]
    js = [r for r in acc if r["lang"] == "js"]
    sym_o = sum(r["symbols"]["oracle"] for r in py)
    sym_f = sum(r["symbols"]["found"] for r in py)
    sym_rec = sum(r["symbols"]["recall"] * r["symbols"]["oracle"] for r in py) / sym_o
    sym_prec = sum(r["symbols"]["precision"] * r["symbols"]["found"] for r in py) / sym_f
    po, pg, prec_r, prec_p = pooled(py)
    jo, jg, jrec_r, jrec_p = pooled(js)
    lines = ["table(", "  columns: (2fr, 2.6fr, 1fr, 1.1fr, 1.1fr),",
             "  align: (left, left, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header[*What was checked*][*Compared against*][*Items in the reference*][*Found (recall)*][*Correct when reported (precision)*],",
             f"  [Python functions, methods and classes (4 repos)], [Python's own `ast` parser], [{sym_o:,}], [{pct(sym_rec)}], [{pct(sym_prec)}],",
             f"  [Python import links between files (4 repos)], [`ast` plus matching module names to files], [{po:,}], [{pct(prec_r)}], [{pct(prec_p)}],",
             f"  [JavaScript import links between files (15 repos)], [Pattern matching over source text], [{jo:,}], [{pct(jrec_r)}], [{pct(jrec_p)}],",
             ")"]
    return "\n".join(lines)


def main() -> None:
    rows = json.loads((RESEARCH / "out" / "hybrid_raw.json").read_text())
    held = json.loads((RESEARCH / "out" / "flows_raw.json").read_text())["heldout"]
    acc = json.loads((RESEARCH / "out" / "accuracy_raw.json").read_text())
    parts = [
        "// Generated by research/py/make_tables.py. Do not edit by hand.",
        "#let retrieval-heldout = " + retrieval_table(rows, lambda r: r["split"] == "test2", None),
        "#let retrieval-other = " + retrieval_multi(rows),
        "#let flows-held-out = " + flows_table(held),
        "#let accuracy = " + accuracy_table(acc),
    ]
    OUT.write_text("\n\n".join(parts) + "\n")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
