"""Shared helpers for the Python side of the research harness."""

from __future__ import annotations

import hashlib
import json
import math
import random
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "research"
sys.path.insert(0, str(ROOT / "apps" / "ai-service"))

REPOS = json.loads((RESEARCH / "repos.json").read_text())
ALL_REPOS = REPOS["dev"] + REPOS["test"] + REPOS["test2"] + REPOS["python"]
SPLIT_OF = {r: s for s in ("dev", "test", "test2", "python") for r in REPOS[s]}
MAX_BYTES = 500_000


def repo_dir(name: str) -> Path:
    return RESEARCH / "data" / "repos" / name


def load_ir(name: str) -> dict:
    return json.loads((RESEARCH / "out" / "graphs" / f"{name}.json").read_text())


def file_paths(ir: dict) -> list[str]:
    return sorted(n["metadata"]["path"] for n in ir["nodes"] if n["type"] == "file")


def read_text(name: str, rel: str) -> str:
    p = repo_dir(name) / rel
    try:
        if not p.is_file() or p.stat().st_size > MAX_BYTES:
            return ""
        return p.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""


def sha1_int(s: str) -> int:
    return int(hashlib.sha1(s.encode()).hexdigest()[:8], 16)


def seeded_shuffle(items: list, key: str) -> list:
    rng = random.Random(sha1_int(key))
    out = list(items)
    rng.shuffle(out)
    return out


def strip_js_comments(src: str) -> str:
    src = re.sub(r"/\*[\s\S]*?\*/", "", src)
    return re.sub(r"(?m)^[ \t]*//.*$", "", src)


# ---------------------------------------------------------------------------
# Leak-free ("code only") text: what the retrievers index in the main condition.
# Locate questions are built from JSDoc comments and Python docstrings, so indexing those
# comments would let a ranker match the answer text verbatim.
# ---------------------------------------------------------------------------

JS_LIKE = re.compile(r"\.(jsx?|mjs|cjs|tsx?)$")


def strip_js_all_comments(src: str) -> str:
    """Remove every // and /* */ comment, respecting string and template literals."""
    out: list[str] = []
    i, n = 0, len(src)
    quote: str | None = None
    while i < n:
        c = src[i]
        if quote:
            out.append(c)
            if c == "\\" and i + 1 < n:
                out.append(src[i + 1])
                i += 2
                continue
            if c == quote:
                quote = None
            i += 1
            continue
        if c in "'\"`":
            quote = c
            out.append(c)
            i += 1
            continue
        if c == "/" and i + 1 < n and src[i + 1] not in "/*":
            k = len(out) - 1
            while k >= 0 and out[k] in " \t\r\n":
                k -= 1
            prev = out[k] if k >= 0 else ""
            if prev == "" or prev in "(,=:[!&|?{};+-*%<>~^":
                # regex literal: copy through the closing unescaped slash (outside a [...] class)
                j, in_cls = i + 1, False
                while j < n and src[j] != "\n":
                    ch = src[j]
                    if ch == "\\":
                        j += 2
                        continue
                    if ch == "[":
                        in_cls = True
                    elif ch == "]":
                        in_cls = False
                    elif ch == "/" and not in_cls:
                        break
                    j += 1
                if j < n and src[j] == "/":
                    out.append(src[i: j + 1])
                    i = j + 1
                    continue
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j < 0 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            seg = src[i: (n if j < 0 else j + 2)]
            out.append("\n" * seg.count("\n"))
            i = n if j < 0 else j + 2
            continue
        out.append(c)
        i += 1
    return "".join(out)


def strip_py_comments_docstrings(src: str) -> str:
    """Remove # comments and docstrings (module, class, function) from Python source."""
    import ast as _ast
    import io
    import tokenize as _tok

    doc_starts: set[tuple[int, int]] = set()
    try:
        tree = _ast.parse(src)
        for node in _ast.walk(tree):
            if isinstance(node, (_ast.Module, _ast.ClassDef, _ast.FunctionDef, _ast.AsyncFunctionDef)) and node.body:
                first = node.body[0]
                if isinstance(first, _ast.Expr) and isinstance(getattr(first, "value", None), _ast.Constant) and isinstance(first.value.value, str):
                    doc_starts.add((first.value.lineno, first.value.col_offset))
    except (SyntaxError, ValueError):
        return re.sub(r"(?m)#.*$", "", src)
    lines = src.splitlines(keepends=True)
    spans: list[tuple[tuple[int, int], tuple[int, int]]] = []
    try:
        for tok in _tok.generate_tokens(io.StringIO(src).readline):
            if tok.type == _tok.COMMENT or (tok.type == _tok.STRING and tok.start in doc_starts):
                spans.append((tok.start, tok.end))
    except (_tok.TokenError, IndentationError, SyntaxError):
        return re.sub(r"(?m)#.*$", "", src)
    for (sl, sc), (el, ec) in reversed(spans):
        if sl == el:
            ln = lines[sl - 1]
            lines[sl - 1] = ln[:sc] + ln[ec:]
        else:
            lines[sl - 1] = lines[sl - 1][:sc] + "\n"
            for k in range(sl, el - 1):
                lines[k] = "\n"
            lines[el - 1] = lines[el - 1][ec:]
    return "".join(lines)


def code_only_text(name: str, rel: str) -> str:
    text = read_text(name, rel)
    if rel.endswith(".py"):
        return strip_py_comments_docstrings(text)
    if JS_LIKE.search(rel):
        return strip_js_all_comments(text)
    return text


def norm_text(s: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", s.lower()).split())


def holm(pvals: list[float]) -> list[float]:
    """Holm-Bonferroni adjusted p-values (same order as the input)."""
    m = len(pvals)
    order = sorted(range(m), key=lambda i: pvals[i])
    adj = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvals[i]))
        adj[i] = running
    return adj


# ---------------------------------------------------------------------------
# Metrics (set / ranking)
# ---------------------------------------------------------------------------

KS = (1, 3, 5, 7)


def rank_scores(ranked: list[str], gold: list[str], max_k: int = 7) -> dict[str, float]:
    g = set(gold)
    top = ranked[:max_k]
    out: dict[str, float] = {}
    for k in KS:
        hits = sum(1 for p in top[:k] if p in g)
        out[f"hit@{k}"] = 1.0 if hits else 0.0
        out[f"recall@{k}"] = hits / len(g)
    first = next((i for i, p in enumerate(top) if p in g), None)
    out["mrr"] = 1.0 / (first + 1) if first is not None else 0.0
    dcg = sum(1.0 / math.log2(i + 2) for i, p in enumerate(top) if p in g)
    idcg = sum(1.0 / math.log2(i + 2) for i in range(min(len(g), max_k)))
    out["ndcg"] = dcg / idcg if idcg else 0.0
    return out


def set_prf(pred: set, gold: set) -> tuple[float, float, float]:
    tp = len(pred & gold)
    p = tp / len(pred) if pred else 0.0
    r = tp / len(gold) if gold else 0.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def mean(xs: list[float]) -> float:
    return sum(xs) / len(xs) if xs else float("nan")


def bootstrap_ci(xs: list[float], b: int = 10000, seed: int = 1) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(xs)
    ms = sorted(sum(xs[rng.randrange(n)] for _ in range(n)) / n for _ in range(b))
    return ms[int(0.025 * b)], ms[int(0.975 * b)]


def paired_permutation_p(a: list[float], b: list[float], seed: int = 7, draws: int = 100000) -> float:
    d = [x - y for x, y in zip(a, b) if x != y]
    n = len(d)
    if n == 0:
        return 1.0
    obs = abs(sum(d))
    if n <= 18:
        total = 2**n
        ge = 0
        for m in range(total):
            s = sum(d[i] if m >> i & 1 else -d[i] for i in range(n))
            if abs(s) >= obs - 1e-12:
                ge += 1
        return ge / total
    rng = random.Random(seed)
    ge = 1
    for _ in range(draws):
        s = sum(x if rng.random() < 0.5 else -x for x in d)
        if abs(s) >= obs - 1e-12:
            ge += 1
    return ge / (draws + 1)


def paired_diff_ci(a: list[float], b: list[float], B: int = 10000, seed: int = 3) -> tuple[float, float, float]:
    d = [x - y for x, y in zip(a, b)]
    lo, hi = bootstrap_ci(d, B, seed)
    return mean(d), lo, hi


def fmt_p(p: float) -> str:
    return "<0.0001" if p < 0.0001 else f"{p:.4f}"
