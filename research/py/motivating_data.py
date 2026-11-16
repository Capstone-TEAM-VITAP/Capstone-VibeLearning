"""Dump the real edges for one flow question (unpruned traversal vs pruner vs gold) for the paper's motivating figure."""

import json

from common import RESEARCH, load_ir, read_text
from src.retrieval.filegraph import build_file_graph
from src.retrieval.hybrid import RepoRetriever, relevance_from_ranking
from src.retrieval.pruner import bfs_edges, prune

QID = "self:B1"
spec = {q["id"]: q for q in json.loads((RESEARCH / "data" / "flows.json").read_text())["questions"]}[QID]
ir = load_ir(spec["repo"])
paths = [n["metadata"]["path"] for n in ir["nodes"] if n["type"] == "file"]
fg = build_file_graph(ir)
retr = RepoRetriever(ir, {p: read_text(spec["repo"], p) for p in paths})
rel = relevance_from_ranking(retr.rankings(spec["query"])["hybrid+bm25"])
out = {
    "id": QID,
    "query": spec["query"],
    "gold": spec["gold"],
    "bfs": sorted(bfs_edges(fg, spec["query"], hops=2)),
    "pruned_hybrid": sorted(e.pair for e in prune(fg, spec["query"], 3, relevance=rel)),
    "roles": {p: sorted(r) for p, r in fg.roles.items()},
}
(RESEARCH / "out" / "motivating.json").write_text(json.dumps(out, indent=1))
print(QID, spec["query"])
print("bfs edges:", len(out["bfs"]), "pruned:", out["pruned_hybrid"])
