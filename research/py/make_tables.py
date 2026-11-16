"""
Write research/paper/tables.typ: every result table of the paper, generated from the raw result files
in research/out so each number is reproducible. The best value in each column is shaded and bold.
Also writes research/out/significance.md (all paired tests with Holm-adjusted p-values).
"""

from __future__ import annotations

import json
import random
from pathlib import Path

from common import fmt_p, holm, paired_diff_ci, paired_permutation_p

RESEARCH = Path(__file__).resolve().parents[1]
OUT = RESEARCH / "paper" / "tables.typ"
GOOD = 'rgb("#dff0e3")'

SYSTEMS = [
    ("random", "Random ranking (floor)"),
    ("bm25", "BM25 (lexical)"),
    ("product", "CodeAI v1 (before this study)"),
    ("product-v2-dense", "CodeAI v2 (deployed)"),
    ("lsa", "LSA vectors"),
    ("dense", "Neural dense (bge-small)"),
    ("graph", "Graph"),
    ("hybrid-lsa", "RRF: LSA + graph"),
    ("hybrid-dense", "RRF: dense + graph"),
    ("bm25+dense+graph", "RRF: BM25 + dense + graph"),
]
NAMES = {"locate": "Locate", "dependency": "Direct importers", "impact": "Change impact"}


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


def f2(x: float) -> str:
    return f"{x:.2f}"


SPEC = [
    ("locate", ("hit@1", pct, "Hit\\@1"), ("mrr", f2, "MRR")),
    ("dependency", ("hit@1", pct, "Hit\\@1"), ("mrr", f2, "MRR")),
    ("impact", ("capped_recall@10", pct, "Recall\\@10#super[c]"), ("ndcg@10", f2, "nDCG\\@10")),
]
HEAD = ["table(", "  columns: (2fr, 0.8fr, 0.7fr, 0.8fr, 0.7fr, 0.9fr, 0.8fr),",
        "  align: (left, center, center, center, center, center, center),",
        "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),"]


def block(rows, pred, title=None):
    lines = []
    if title:
        cnt = ", ".join(f"{len([r for r in rows if pred(r) and r['type'] == t])} {t}" for t, _, _ in SPEC)
        lines.append(f"  table.cell(colspan: 7, fill: luma(235))[*{title}* #h(6pt) #text(size: 7.5pt)[({cnt} questions)]],")
    data = {}
    for typ, a, b in SPEC:
        sub = [r for r in rows if pred(r) and r["type"] == typ]
        for s, _ in SYSTEMS:
            for key in (a[0], b[0]):
                data[(typ, s, key)] = mean([r["scores"][s][key] for r in sub])
    best = {(typ, k): max(data[(typ, s, k)] for s, _ in SYSTEMS) for typ, a, b in SPEC for k in (a[0], b[0])}
    for s, label in SYSTEMS:
        row = [f"[{label}]"]
        for typ, a, b in SPEC:
            for key, fmt, _ in (a, b):
                v = data[(typ, s, key)]
                row.append(cell(fmt(v), abs(v - best[(typ, key)]) < 1e-12))
        lines.append("  " + ", ".join(row) + ",")
    return lines


def retrieval_table(rows, groups, counts_in_header=None) -> str:
    lines = list(HEAD) + ["  table.header(", "    table.cell(rowspan: 2)[*Ranker*],"]
    for typ, _, _ in SPEC:
        extra = f" #linebreak() #text(size: 7.5pt)[{counts_in_header[typ]} questions]" if counts_in_header else ""
        lines.append(f"    table.cell(colspan: 2)[*{NAMES[typ]}*{extra}],")
    for _, a, b in SPEC:
        lines.append(f"    [{a[2]}], [{b[2]}],")
    lines.append("  ),")
    for title, pred in groups:
        lines += block(rows, pred, title)
    lines.append(")")
    return "\n".join(lines)


def leak_table(rows) -> str:
    groups = [("Held-out JS", "test2"), ("Post-hoc JS", ("dev", "test")), ("Python", "python")]
    sysl = [("bm25", "BM25"), ("product", "CodeAI v1"), ("lsa", "LSA"), ("dense", "Dense"), ("graph", "Graph"), ("hybrid-lsa", "RRF LSA+graph"), ("bm25+dense+graph", "RRF all three")]
    lines = ["table(", f"  columns: (2.3fr, {', '.join(['1fr'] * len(sysl))}),", "  align: (left, " + ", ".join(["center"] * len(sysl)) + "),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header([*Locate MRR*], " + ", ".join(f"[*{l}*]" for _, l in sysl) + "),"]
    for gname, sp in groups:
        inset = (lambda r, sp=sp: r["split"] in sp) if isinstance(sp, tuple) else (lambda r, sp=sp: r["split"] == sp)
        for cond, cl in (("raw", "comments indexed"), ("code", "comments removed")):
            sub = [r for r in rows if r["cond"] == cond and r["type"] == "locate" and inset(r)]
            vals = [mean([r["scores"][s]["mrr"] for r in sub]) for s, _ in sysl]
            b = max(vals)
            lines.append(f"  [{gname}, {cl} (n={len(sub)})], " + ", ".join(cell(f2(v), abs(v - b) < 1e-12) for v in vals) + ",")
    lines.append(")")
    return "\n".join(lines)


def overlap_table(rows) -> str:
    loc = [r for r in rows if r["cond"] == "code" and r["type"] == "locate"]
    xs = sorted(r["overlap"] for r in loc)
    t1, t2 = xs[len(xs) // 3], xs[2 * len(xs) // 3]
    bins = [("Low", lambda o: o < t1), ("Middle", lambda o: t1 <= o < t2), ("High", lambda o: o >= t2)]
    sysl = [("bm25", "BM25"), ("product", "CodeAI v1"), ("lsa", "LSA"), ("dense", "Dense"), ("graph", "Graph"), ("bm25+dense+graph", "RRF all three")]
    lines = ["table(", f"  columns: (2.2fr, {', '.join(['1fr'] * len(sysl))}),", "  align: (left, " + ", ".join(["center"] * len(sysl)) + "),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header([*Word overlap between question and answer file*], " + ", ".join(f"[*{l}*]" for _, l in sysl) + "),"]
    for name, fn in bins:
        sub = [r for r in loc if fn(r["overlap"])]
        lo = min(r["overlap"] for r in sub)
        hi = max(r["overlap"] for r in sub)
        vals = [mean([r["scores"][s]["mrr"] for r in sub]) for s, _ in sysl]
        b = max(vals)
        lines.append(f"  [{name} ({lo:.2f} to {hi:.2f}, n={len(sub)})], " + ", ".join(cell(f2(v), abs(v - b) < 1e-12) for v in vals) + ",")
    lines.append(")")
    return "\n".join(lines)


FLOW_LABELS = [
    ("Baselines without pruning", [
        ("random3", "Random 3 edges", "Three random non-test edges (floor)"),
        ("bfs2", "2-hop traversal, path seeds", "All edges within 2 hops of the 3 best path matches"),
        ("bfs2-bm25", "2-hop traversal, BM25 seeds", "The same traversal from the top 3 BM25 files"),
        ("candidates-bm25", "Pruner's candidate pool", "Every edge touching a BM25 top-10 file (what the pruner scores)"),
    ]),
    ("Simple top-3 baselines", [
        ("overlap-top3", "Top 3 by path words", "3 edges whose file names share most words with the question"),
        ("relevance-top3", "Top 3 by BM25", "3 edges between the files BM25 ranks highest"),
    ]),
    ("Graph Path Pruning", [
        ("pruner-path", "Pruner, path relevance", "Declared before the held-out run"),
        ("pruner-bm25", "Pruner, BM25 relevance (primary)", "Declared before the held-out run"),
        ("pruner-bm25-thr0", "Primary, threshold 0 (post hoc)", "Fix for empty output, chosen after the run"),
        ("pruner-hybrid", "Pruner, fused relevance (post hoc)", "Chosen after the run"),
    ]),
    ("Ablations of the primary pruner", [
        ("pruner-bm25-noroles", "No layer rules", "Ignore route, controller, service layers"),
        ("pruner-bm25-nocont", "No continuity bonus", "Do not prefer connected edges"),
    ]),
]


def flows_table(held, compact: bool = False) -> str:
    """Held-out flow table; *compact* drops the "What it does" column (used by the condensed paper)."""
    stats = {}
    for _, items in FLOW_LABELS:
        for key, _, _ in items:
            f1 = [r["scores"][key]["f1"] for r in held]
            lo, hi = ci(f1)
            stats[key] = {"p": mean([r["scores"][key]["precision"] for r in held]),
                          "r": mean([r["scores"][key]["recall"] for r in held]), "f": mean(f1), "lo": lo, "hi": hi,
                          "n": mean([r["scores"][key]["n_pred"] for r in held]),
                          "e": sum(1 for r in held if r["scores"][key]["n_pred"] == 0)}
    best_f = max(v["f"] for v in stats.values())
    if compact:
        lines = ["table(", "  columns: (2.6fr, 0.8fr, 0.7fr, 0.8fr, 0.8fr, 1.7fr),",
                 "  align: (left, center, center, center, center, center),",
                 "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3pt),",
                 "  table.header[*Method*][*Edges per question*][*Empty outputs*][*Precision*][*Recall*][*F1 (95% interval)*],"]
        for group, items in FLOW_LABELS:
            lines.append(f"  table.cell(colspan: 6, fill: luma(235))[*{group}*],")
            for key, label, _ in items:
                v = stats[key]
                f = f"{v['f']:.3f} \\[{v['lo']:.3f}, {v['hi']:.3f}\\]"
                lines.append(f"  [{label}], [{v['n']:.1f}], [{v['e']}], [{v['p']:.3f}], [{v['r']:.3f}], {cell(f, abs(v['f'] - best_f) < 1e-12)},")
        lines.append(")")
        return "\n".join(lines)
    lines = ["table(", "  columns: (2.1fr, 2.6fr, 0.8fr, 0.7fr, 0.8fr, 0.8fr, 1.7fr),",
             "  align: (left, left, center, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header[*Method*][*What it does*][*Edges per question*][*Empty outputs*][*Precision*][*Recall*][*F1 (95% interval)*],"]
    for group, items in FLOW_LABELS:
        lines.append(f"  table.cell(colspan: 7, fill: luma(235))[*{group}*],")
        for key, label, what in items:
            v = stats[key]
            f = f"{v['f']:.3f} \\[{v['lo']:.3f}, {v['hi']:.3f}\\]"
            lines.append(f"  [{label}], [{what}], [{v['n']:.1f}], [{v['e']}], [{v['p']:.3f}], [{v['r']:.3f}], {cell(f, abs(v['f'] - best_f) < 1e-12)},")
    lines.append(")")
    return "\n".join(lines)


def sensitivity_table(flows) -> str:
    names = {"OVERLAP_WEIGHT": "Relevance weight (1.5)", "KIND_BONUS": "Edge-kind bonuses (2.0/1.5/0.5)",
             "HIERARCHY_BONUS": "Layer bonus (3.0)", "BOTH_ENDS_BONUS": "Route-controller bonus (5.0)",
             "PRIMARY_BONUS": "Primary controller bonus (4.5)", "SECONDARY_BONUS": "Secondary controller bonus (2.5)",
             "CONTINUITY_BONUS": "Continuity bonus (2.0)", "SCORE_THRESHOLD": "Score threshold (2.0)"}
    dev, held = flows["dev"], flows["heldout"]
    base_d = mean([r["scores"]["pruner-bm25"]["f1"] for r in dev])
    base_h = mean([r["scores"]["pruner-bm25"]["f1"] for r in held])
    lines = ["table(", "  columns: (2.6fr, 1fr, 1fr, 1fr, 1fr),", "  align: (left, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header(table.cell(rowspan: 2)[*Constant (declared value)*], table.cell(colspan: 2)[*Dev F1*], table.cell(colspan: 2)[*Held-out F1*], [×0.5], [×2], [×0.5], [×2]),",
             f"  table.cell(colspan: 5, fill: luma(235))[*As declared: dev {base_d:.3f}, held-out {base_h:.3f}*],"]
    for k, label in names.items():
        vals = [mean([r["sensitivity"][f"{k}x{fac}"] for r in s]) for s in (dev, held) for fac in (0.5, 2.0)]
        lines.append(f"  [{label}], " + ", ".join(f"[{v:.3f}]" for v in vals) + ",")
    lines.append(")")
    return "\n".join(lines)


def fusion_sweep_table(sweep) -> str:
    metric = {"locate": "mrr", "dependency": "mrr", "impact": "ndcg@10"}
    k0s = (10, 60, 200)
    wvs = sorted({s["w_vec"] for s in sweep})
    lines = ["table(", f"  columns: (1.6fr, {', '.join(['1fr'] * len(wvs))}),", "  align: (left, " + ", ".join(["center"] * len(wvs)) + "),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header([*Question, $k_0$*], " + ", ".join(f"[$w_\"LSA\" = {w}$]" for w in wvs) + "),"]
    for typ in ("locate", "dependency", "impact"):
        for k0 in k0s:
            vals = []
            for w in wvs:
                xs = [s["scores"][metric[typ]] for s in sweep if s["type"] == typ and s["k0"] == k0 and s["w_vec"] == w]
                vals.append(mean(xs))
            lines.append(f"  [{NAMES[typ]}, {k0}], " + ", ".join(f"[{v:.3f}]" for v in vals) + ",")
    lines.append(")")
    return "\n".join(lines)


def k_table(rows) -> str:
    lines = ["table(", "  columns: (2.2fr, 1fr, 1fr, 1fr, 1fr),", "  align: (left, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header([*Held-out JS, comments removed*], [*MRR\\@7*], [*MRR\\@10*], [*Hit\\@5*], [*Hit\\@10*]),"]
    for typ in ("locate", "dependency"):
        sub = [r for r in rows if r["cond"] == "code" and r["split"] == "test2" and r["type"] == typ]
        lines.append(f"  table.cell(colspan: 5, fill: luma(235))[*{NAMES[typ]} (n={len(sub)})*],")
        for s, label in SYSTEMS[1:]:
            vals = [mean([r["scores"][s][m] for r in sub]) for m in ("mrr", "mrr@10", "hit@5", "hit@10")]
            lines.append(f"  [{label}], " + ", ".join(f"[{v:.3f}]" for v in vals) + ",")
    lines.append(")")
    return "\n".join(lines)


def significance(rows, flows):
    """The pre-declared family of paired tests; Holm correction over the whole family."""
    def ret(split, typ, metric, a, b, label):
        sub = [r for r in rows if r["cond"] == "code" and r["type"] == typ and (r["split"] in split)]
        xa = [r["scores"][a][metric] for r in sub]
        xb = [r["scores"][b][metric] for r in sub]
        return label, len(sub), metric, xa, xb

    held, py = ("test2",), ("python",)
    M = {"mrr": "MRR", "ndcg@10": "nDCG\\@10", "f1": "F1"}
    tests = [
        ret(held, "locate", "mrr", "dense", "bm25", "Locate: dense − BM25 (held-out JS)"),
        ret(held, "locate", "mrr", "dense", "lsa", "Locate: dense − LSA (held-out JS)"),
        ret(held, "locate", "mrr", "bm25+dense+graph", "bm25", "Locate: RRF all three − BM25 (held-out JS)"),
        ret(held, "locate", "mrr", "hybrid-lsa", "bm25", "Locate: RRF LSA+graph − BM25 (held-out JS)"),
        ret(py, "locate", "mrr", "dense", "bm25", "Locate: dense − BM25 (Python)"),
        ret(held, "dependency", "mrr", "graph", "bm25", "Importers: graph − BM25 (held-out JS)"),
        ret(held, "dependency", "mrr", "hybrid-lsa", "graph", "Importers: RRF LSA+graph − graph (held-out JS)"),
        ret(held, "impact", "ndcg@10", "graph", "bm25", "Impact: graph − BM25 (held-out JS)"),
        ret(held, "impact", "ndcg@10", "hybrid-lsa", "graph", "Impact: RRF LSA+graph − graph (held-out JS)"),
        ret(held, "impact", "ndcg@10", "hybrid-dense", "graph", "Impact: RRF dense+graph − graph (held-out JS)"),
        ret(py, "impact", "ndcg@10", "hybrid-lsa", "graph", "Impact: RRF LSA+graph − graph (Python)"),
    ]
    h = flows["heldout"]
    for a, b, label in [
        ("pruner-bm25", "candidates-bm25", "Flows: primary pruner − its candidate pool"),
        ("pruner-bm25", "bfs2-bm25", "Flows: primary pruner − 2-hop traversal (BM25 seeds)"),
        ("pruner-bm25", "random3", "Flows: primary pruner − random 3 edges"),
        ("pruner-bm25", "relevance-top3", "Flows: primary pruner − top 3 by BM25"),
        ("pruner-bm25", "overlap-top3", "Flows: primary pruner − top 3 by path words"),
        ("pruner-bm25-thr0", "relevance-top3", "Flows: threshold-0 pruner − top 3 by BM25 (post hoc)"),
        ("pruner-hybrid", "relevance-top3", "Flows: fused-relevance pruner − top 3 by BM25 (post hoc)"),
    ]:
        tests.append((label, len(h), "f1", [r["scores"][a]["f1"] for r in h], [r["scores"][b]["f1"] for r in h]))

    res = []
    for label, n, metric, xa, xb in tests:
        d, lo, hi = paired_diff_ci(xa, xb, 5000)
        res.append({"label": label, "n": n, "metric": M[metric], "d": d, "lo": lo, "hi": hi,
                    "p": paired_permutation_p(xa, xb, draws=20000)})
    for r, a in zip(res, holm([r["p"] for r in res])):
        r["p_holm"] = a

    md = ["# Paired tests (Holm-adjusted over the whole family)\n", "| Comparison | n | metric | diff | 95% CI | p | p (Holm) |", "|---|---|---|---|---|---|---|"]
    for r in res:
        md.append(f"| {r['label']} | {r['n']} | {r['metric']} | {r['d']:+.3f} | [{r['lo']:+.3f}, {r['hi']:+.3f}] | {fmt_p(r['p'])} | {fmt_p(r['p_holm'])} |")
    (RESEARCH / "out" / "significance.md").write_text("\n".join(md), encoding="utf-8")

    def pp(p):
        return "< 0.0001" if p < 0.0001 else f"{p:.4f}"

    lines = ["table(", "  columns: (3.4fr, 0.5fr, 0.8fr, 1.9fr, 0.9fr, 0.9fr),", "  align: (left, center, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header[*Comparison (A − B)*][*n*][*Score*][*Difference \\[95% interval\\]*][*p*][*p (Holm)*],"]
    for r in res:
        sig = r["p_holm"] < 0.05
        diff = f"{r['d']:+.3f} \\[{r['lo']:+.3f}, {r['hi']:+.3f}\\]".replace("-", "−")
        lines.append(f"  [{r['label']}], [{r['n']}], [{r['metric']}], [{diff}], [{pp(r['p'])}], {cell(pp(r['p_holm']), sig)},")
    lines.append(")")
    return "\n".join(lines), res


def product_before_after(rows) -> str:
    """CodeAI's retriever before (v1) and after (v2) this study, next to the best research ranker."""
    metric = {"locate": "mrr", "dependency": "mrr", "impact": "ndcg@10"}
    best = {"locate": "bm25+dense+graph", "dependency": "graph", "impact": "bm25+dense+graph"}
    groups = [("Held-out JS", lambda r: r["split"] == "test2"), ("Post-hoc JS", lambda r: r["split"] in ("dev", "test")),
              ("Python", lambda r: r["split"] == "python")]
    lines = ["table(", "  columns: (2.3fr, 1fr, 1fr, 1fr, 1fr),", "  align: (left, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header([*Group, question type (score)*], [*v1: before*], [*v2, no embeddings*], [*v2: deployed*], [*Best research ranker*]),"]
    for gname, pred in groups:
        lines.append(f"  table.cell(colspan: 5, fill: luma(235))[*{gname}*],")
        for typ in ("locate", "dependency", "impact"):
            sub = [r for r in rows if r["cond"] == "code" and pred(r) and r["type"] == typ]
            m = metric[typ]
            vals = [mean([r["scores"][s][m] for r in sub]) for s in ("product", "product-v2", "product-v2-dense", best[typ])]
            top = max(vals[:3])
            score_name = "MRR" if m == "mrr" else "nDCG\\@10"
            label = f"{NAMES[typ]} ({score_name}, n={len(sub)})"
            cells = [cell(f"{v:.2f}", abs(v - top) < 1e-12) for v in vals[:3]] + [f"[{vals[3]:.2f}]"]
            lines.append(f"  [{label}], " + ", ".join(cells) + ",")
    lines.append(")")
    return "\n".join(lines)


def product_tests(rows) -> str:
    """CodeAI's retriever after this study (v2, deployed) against before (v1), held-out JS, comments removed.
    v2's design was chosen after seeing these results, so this is a confirmation of the chosen design, not an
    unbiased test; it is its own Holm family of three."""
    spec = [("locate", "mrr", "Locate: CodeAI v2 − v1"),
            ("dependency", "mrr", "Importers: CodeAI v2 − v1"),
            ("impact", "ndcg@10", "Impact: CodeAI v2 − v1")]
    res = []
    for typ, metric, label in spec:
        sub = [r for r in rows if r["cond"] == "code" and r["split"] == "test2" and r["type"] == typ]
        xa = [r["scores"]["product-v2-dense"][metric] for r in sub]
        xb = [r["scores"]["product"][metric] for r in sub]
        d, lo, hi = paired_diff_ci(xa, xb, 5000)
        res.append({"label": label, "n": len(sub), "metric": "MRR" if metric == "mrr" else "nDCG\\@10", "d": d, "lo": lo, "hi": hi,
                    "p": paired_permutation_p(xa, xb, draws=20000)})
    for r, a in zip(res, holm([r["p"] for r in res])):
        r["p_holm"] = a
    with open(RESEARCH / "out" / "significance.md", "a", encoding="utf-8") as fh:
        fh.write("\n\n# CodeAI v2 (deployed) vs v1 (held-out JS; confirmation of the chosen design; separate Holm family of 3)\n\n"
                 "| Comparison | n | diff | 95% CI | p | p (Holm) |\n|---|---|---|---|---|---|\n")
        for r in res:
            fh.write(f"| {r['label']} | {r['n']} | {r['d']:+.3f} | [{r['lo']:+.3f}, {r['hi']:+.3f}] | {fmt_p(r['p'])} | {fmt_p(r['p_holm'])} |\n")

    def pp(p):
        return "< 0.0001" if p < 0.0001 else f"{p:.4f}"

    lines = ["table(", "  columns: (3.4fr, 0.5fr, 0.8fr, 1.9fr, 0.9fr, 0.9fr),", "  align: (left, center, center, center, center, center),",
             "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
             "  table.header[*Comparison (A − B)*][*n*][*Score*][*Difference \\[95% interval\\]*][*p*][*p (Holm)*],"]
    for r in res:
        diff = f"{r['d']:+.3f} \\[{r['lo']:+.3f}, {r['hi']:+.3f}\\]".replace("-", "−")
        lines.append(f"  [{r['label']}], [{r['n']}], [{r['metric']}], [{diff}], [{pp(r['p'])}], {cell(pp(r['p_holm']), r['p_holm'] < 0.05)},")
    lines.append(")")
    return "\n".join(lines)


def accuracy_table(acc) -> str:
    def pooled(sel):
        o = sum(r["oracle"] for r in sel)
        g = sum(r["graph"] for r in sel)
        return o, sum((r["recall"] or 0) * r["oracle"] for r in sel) / o, sum((r["precision"] or 0) * r["graph"] for r in sel) / g

    py = [r for r in acc if r["lang"] == "python"]
    js = [r for r in acc if r["lang"] == "js"]
    sym_o = sum(r["symbols"]["oracle"] for r in py)
    sym_f = sum(r["symbols"]["found"] for r in py)
    sym_rec = sum(r["symbols"]["recall"] * r["symbols"]["oracle"] for r in py) / sym_o
    sym_prec = sum(r["symbols"]["precision"] * r["symbols"]["found"] for r in py) / sym_f
    co = sum(r["calls"]["oracle"] for r in py)
    c_rec = sum((r["calls"]["recall"] or 0) * r["calls"]["oracle"] for r in py) / co
    cs = sum(r["calls"]["graph_in_scope"] for r in py)
    c_prec = sum((r["calls"]["precision_in_scope"] or 0) * r["calls"]["graph_in_scope"] for r in py) / cs
    po, prec_r, prec_p = pooled(py)
    jo, jrec_r, jrec_p = pooled(js)
    return "\n".join([
        "table(", "  columns: (2fr, 2.6fr, 1fr, 1.1fr, 1.1fr),", "  align: (left, left, center, center, center),",
        "  stroke: 0.4pt + luma(170), inset: (x: 4pt, y: 3.5pt),",
        "  table.header[*What was checked*][*Compared against*][*Items in the reference*][*Found (recall)*][*Correct when reported (precision)*],",
        f"  [Python functions, methods and classes (4 repos)], [Python's own `ast` parser], [{sym_o:,}], [{pct(sym_rec)}], [{pct(sym_prec)}],",
        f"  [Python import links between files (4 repos)], [`ast` plus matching module names to files], [{po:,}], [{pct(prec_r)}], [{pct(prec_p)}],",
        f"  [Python cross-file calls (4 repos)], [`ast`: calls of names brought in by `from m import name`], [{co:,}], [{pct(c_rec)}], [{pct(c_prec)}#super[s]],",
        f"  [JavaScript import links between files (15 repos)], [Pattern matching over source text], [{jo:,}], [{pct(jrec_r)}], [{pct(jrec_p)}],",
        ")"])


def main() -> None:
    raw = json.loads((RESEARCH / "out" / "hybrid_raw.json").read_text())
    rows = raw["rows"]
    flows = json.loads((RESEARCH / "out" / "flows_raw.json").read_text())
    acc = json.loads((RESEARCH / "out" / "accuracy_raw.json").read_text())
    code = [r for r in rows if r["cond"] == "code"]
    held_counts = {t: len([r for r in code if r["split"] == "test2" and r["type"] == t]) for t, _, _ in SPEC}
    sig_table, _ = significance(rows, flows)
    parts = [
        "// Generated by research/py/make_tables.py. Do not edit by hand.",
        "#let retrieval-heldout = " + retrieval_table(code, [(None, lambda r: r["split"] == "test2")], held_counts),
        "#let retrieval-other = " + retrieval_table(code, [
            ("JavaScript, 10 development and post-hoc repositories", lambda r: r["split"] in ("dev", "test")),
            ("Python, 4 repositories", lambda r: r["split"] == "python")]),
        "#let leak-table = " + leak_table(rows),
        "#let overlap-table = " + overlap_table(rows),
        "#let flows-held-out = " + flows_table(flows["heldout"]),
        "#let flows-held-out-compact = " + flows_table(flows["heldout"], compact=True),
        "#let pruner-sensitivity = " + sensitivity_table(flows),
        "#let fusion-sweep = " + fusion_sweep_table(raw["sweep"]),
        "#let k-table = " + k_table(rows),
        "#let significance-table = " + sig_table,
        "#let product-tests = " + product_tests(rows),
        "#let product-before-after = " + product_before_after(rows),
        "#let accuracy = " + accuracy_table(acc),
        f"#let n-dropped = {len(raw['dropped_leaky_locate'])}",
    ]
    OUT.write_text("\n\n".join(parts) + "\n", encoding="utf-8")
    print("wrote", OUT)


if __name__ == "__main__":
    main()
