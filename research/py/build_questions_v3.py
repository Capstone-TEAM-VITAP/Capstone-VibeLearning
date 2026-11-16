"""
Build the full retrieval benchmark.

Categories (gold always comes from an oracle that does not use the Tree-sitter graph):
  locate      - docstring/JSDoc sentence -> defining file
  dependency  - "Which files import X?" -> direct importers
  impact      - "Which files are affected if X changes?" -> transitive importers (depth <= 4)

JavaScript locate/dependency questions are the ones in data/questions.json (regex oracle);
Python locate questions come from ``ast`` docstrings; impact questions are new for both languages.
"""

from __future__ import annotations

import ast
import json
import re

from common import (
    ALL_REPOS,
    REPOS,
    RESEARCH,
    SPLIT_OF,
    file_paths,
    load_ir,
    read_text,
    seeded_shuffle,
)
from oracle import importers, import_pairs, transitive_importers

MAX_LOCATE = 30
MAX_DEP = 15
MAX_IMPACT = 15
TESTY = re.compile(r"(^|/)(tests?|__tests__|spec|specs|examples?|docs?|benchmarks?|fixtures?|scripts?)(/|$)|(^|/)test_[^/]*\.py$|\.(test|spec)\.|conftest\.py$")


def first_sentence(doc: str) -> str:
    doc = " ".join(doc.strip().split())
    m = re.match(r"^(.+?[.!?])(\s|$)", doc)
    return (m.group(1) if m else doc)[:220]


def py_locate(repo: str) -> list[dict]:
    found = []
    for rel in file_paths(load_ir(repo)):
        if not rel.endswith(".py") or TESTY.search(rel):
            continue
        try:
            tree = ast.parse(read_text(repo, rel))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                doc = ast.get_docstring(node)
                if not doc:
                    continue
                desc = first_sentence(doc)
                if len(desc.split()) < 6 or node.name.lower() in desc.lower():
                    continue
                found.append((rel, node.name, desc))
    count: dict[str, int] = {}
    for _, _, d in found:
        count[d] = count.get(d, 0) + 1
    uniq = [f for f in found if count[f[2]] == 1]
    uniq = seeded_shuffle(uniq, f"{repo}:loc")[:MAX_LOCATE]
    return [
        {"id": f"{repo}:loc:{i}", "repo": repo, "type": "locate", "query": d, "gold": [rel], "exclude": [], "meta": {"identifier": name}}
        for i, (rel, name, d) in enumerate(uniq)
    ]


def dependency_and_impact(repo: str, python: bool) -> tuple[list[dict], list[dict]]:
    pairs = import_pairs(repo, python)
    imp = importers(pairs)
    ext = (".py",) if python else (".js", ".jsx", ".mjs", ".cjs")
    targets = [t for t in imp if t.endswith(ext) and not TESTY.search(t)]
    dep, impact = [], []

    cands = [t for t in targets if 2 <= len(imp[t]) <= 15]
    for i, t in enumerate(seeded_shuffle(sorted(cands), f"{repo}:dep")[:MAX_DEP]):
        dep.append({"id": f"{repo}:dep:{i}", "repo": repo, "type": "dependency", "query": f"Which files import {t}?", "gold": sorted(imp[t]), "exclude": [t], "meta": {"target": t}})

    pool = []
    for t in sorted(targets):
        dist = transitive_importers(imp, t, 4)
        files = [f for f in dist if not TESTY.search(f)]
        if 3 <= len(files) <= 30:
            pool.append((t, sorted(files)))
    for i, (t, files) in enumerate(seeded_shuffle(pool, f"{repo}:imp")[:MAX_IMPACT]):
        impact.append({"id": f"{repo}:imp:{i}", "repo": repo, "type": "impact", "query": f"Which files are affected if {t} changes?", "gold": files, "exclude": [t], "meta": {"target": t}})
    return dep, impact


def main() -> None:
    js_old = json.loads((RESEARCH / "data" / "questions.json").read_text())
    out = []
    for q in js_old:
        q = dict(q)
        out.append(q)
    for repo in ALL_REPOS:
        python = repo in REPOS["python"]
        split = SPLIT_OF[repo]
        if python:
            for q in py_locate(repo):
                out.append({**q, "split": split})
        dep, impact = dependency_and_impact(repo, python)
        if python:
            for q in dep:
                out.append({**q, "split": split})
        for q in impact:
            out.append({**q, "split": split})
    (RESEARCH / "data" / "questions_v3.json").write_text(json.dumps(out, indent=1))
    summary: dict[str, int] = {}
    for q in out:
        k = f"{q['split']}/{q['type']}"
        summary[k] = summary.get(k, 0) + 1
    print(json.dumps(summary, indent=1))
    print("total", len(out))
    per_repo = {}
    for q in out:
        per_repo.setdefault(q["repo"], {}).setdefault(q["type"], 0)
        per_repo[q["repo"]][q["type"]] += 1
    for r, v in per_repo.items():
        print(r, v)


if __name__ == "__main__":
    main()
