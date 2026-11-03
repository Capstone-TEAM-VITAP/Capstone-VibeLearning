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
