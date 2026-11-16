"""
Write the neural dense ranking (top 50 files) of every benchmark question, in both text conditions, to
research/out/dense_rankings.json, so research/src/run_product.mjs can run CodeAI's retriever with the
same neural ranking the AI service would supply. Uses the embedding cache in research/out/emb_cache.
"""

from __future__ import annotations

import json

from common import ALL_REPOS, RESEARCH, code_only_text, file_paths, load_ir, read_text
from dense import DenseIndex, embed_queries
from src.retrieval.filegraph import build_file_graph


def main() -> None:
    questions = json.loads((RESEARCH / "data" / "questions_v3.json").read_text())
    qvec = dict(zip((q["id"] for q in questions), embed_queries([q["query"] for q in questions])))
    out: dict[str, dict[str, list[str]]] = {"code": {}, "raw": {}}
    for cond, reader in (("code", code_only_text), ("raw", read_text)):
        for repo in ALL_REPOS:
            ir = load_ir(repo)
            files = build_file_graph(ir).files
            index = DenseIndex(repo, cond, {p: reader(repo, p) for p in files})
            for q in (x for x in questions if x["repo"] == repo):
                out[cond][q["id"]] = index.rank_vec(qvec[q["id"]])[:50]
    (RESEARCH / "out" / "dense_rankings.json").write_text(json.dumps(out))
    print("wrote out/dense_rankings.json")


if __name__ == "__main__":
    main()
