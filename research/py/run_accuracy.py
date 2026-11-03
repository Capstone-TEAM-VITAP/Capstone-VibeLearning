"""
Static-analysis accuracy against independent oracles.

Imports : file-to-file pairs in the Graph IR vs the oracle (regex for JS, ``ast`` for Python).
Symbols : Python functions/classes/methods found by Tree-sitter vs ``ast`` definitions.
"""

from __future__ import annotations

import ast
import json

from common import ALL_REPOS, REPOS, RESEARCH, file_paths, load_ir, read_text
from oracle import import_pairs


def graph_pairs(ir: dict) -> set[tuple[str, str]]:
    out = set()
    for e in ir["edges"]:
        if e["type"] == "imports" and e["source"].startswith("file:") and e["target"].startswith("file:"):
            out.add((e["source"][5:], e["target"][5:]))
    return out


def py_symbol_counts(repo: str, ir: dict) -> dict:
    oracle: set[tuple[str, str, str]] = set()
    for rel in file_paths(ir):
        if not rel.endswith(".py"):
            continue
        try:
            tree = ast.parse(read_text(repo, rel))
        except (SyntaxError, ValueError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                oracle.add((rel, node.name, "fn"))
            elif isinstance(node, ast.ClassDef):
                oracle.add((rel, node.name, "class"))
    found: set[tuple[str, str, str]] = set()
    for n in ir["nodes"]:
        if n["type"] in ("function", "method", "class") and n["id"].startswith("symbol:"):
            meta = n["metadata"]
            found.add((meta["path"], meta["name"], "class" if n["type"] == "class" else "fn"))
    tp = len(oracle & found)
    return {"oracle": len(oracle), "found": len(found), "recall": tp / len(oracle) if oracle else None,
            "precision": tp / len(found) if found else None}


def main() -> None:
    rows = []
    for repo in ALL_REPOS:
        ir = load_ir(repo)
        python = repo in REPOS["python"]
        oracle = import_pairs(repo, python)
        graph = graph_pairs(ir)
        # restrict graph pairs to the language of the oracle so JS repos with .json imports compare fairly
        ext = (".py",) if python else (".js", ".jsx", ".mjs", ".cjs", ".json")
        graph = {(s, t) for s, t in graph if s.endswith(ext) and t.endswith(ext)}
        oracle = {(s, t) for s, t in oracle if s.endswith(ext) and t.endswith(ext)}
        tp = len(oracle & graph)
        row = {
            "repo": repo,
            "lang": "python" if python else "js",
            "oracle": len(oracle),
            "graph": len(graph),
            "precision": tp / len(graph) if graph else None,
            "recall": tp / len(oracle) if oracle else None,
        }
        if python:
            row["symbols"] = py_symbol_counts(repo, ir)
        rows.append(row)
    (RESEARCH / "out" / "accuracy_raw.json").write_text(json.dumps(rows, indent=1))

    def f(x):
        return "n/a" if x is None else f"{x:.3f}"

    md = ["# Analyzer accuracy vs independent oracles\n", "| Repo | Lang | oracle pairs | graph pairs | precision | recall |", "|---|---|---|---|---|---|"]
    for r in rows:
        md.append(f"| {r['repo']} | {r['lang']} | {r['oracle']} | {r['graph']} | {f(r['precision'])} | {f(r['recall'])} |")
    for lang in ("js", "python"):
        sub = [r for r in rows if r["lang"] == lang]
        o = sum(r["oracle"] for r in sub)
        tp_r = sum((r["recall"] or 0) * r["oracle"] for r in sub)
        g = sum(r["graph"] for r in sub)
        tp_p = sum((r["precision"] or 0) * r["graph"] for r in sub)
        md.append(f"\nPooled {lang}: recall {tp_r / o:.3f} over {o} pairs, precision {tp_p / g:.3f} over {g} pairs.")
    md.append("\n## Python symbols vs ast\n\n| Repo | ast defs | found | recall | precision |\n|---|---|---|---|---|")
    for r in rows:
        if "symbols" in r:
            s = r["symbols"]
            md.append(f"| {r['repo']} | {s['oracle']} | {s['found']} | {f(s['recall'])} | {f(s['precision'])} |")
    text = "\n".join(md)
    (RESEARCH / "out" / "accuracy_tables.md").write_text(text)
    print(text)


if __name__ == "__main__":
    main()
