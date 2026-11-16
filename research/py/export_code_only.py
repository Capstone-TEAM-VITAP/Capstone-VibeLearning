"""
Write comment-free copies of every indexed file to research/out/code_only/<repo>/<path> (git-ignored),
so the product's JavaScript retriever (apps/backend/src/services/retrieval.service.js) can be run on
exactly the text the Python rankers see in the main condition. Used by research/src/run_product.mjs.
"""

from __future__ import annotations

from common import ALL_REPOS, RESEARCH, code_only_text, file_paths, load_ir

OUT = RESEARCH / "out" / "code_only"


def main() -> None:
    n = 0
    for repo in ALL_REPOS:
        for rel in file_paths(load_ir(repo)):
            dest = OUT / repo / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(code_only_text(repo, rel), encoding="utf-8")
            n += 1
    print(f"wrote {n} comment-free files to {OUT}")


if __name__ == "__main__":
    main()
