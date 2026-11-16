"""Graph Path Pruning, file graph view, LSA, BM25 and RRF."""

from src.retrieval.filegraph import build_file_graph, keywords, stem
from src.retrieval.hybrid import Bm25Index, RepoRetriever, graph_rank, rrf
from src.retrieval.lsa import LsaIndex
from src.retrieval.pruner import bfs_edges, prune, score_edges


def _file(p):
    return {"id": f"file:{p}", "type": "file", "label": p.split("/")[-1], "metadata": {"path": p}}


def _arch(p, role):
    return {"id": f"architecture:{p}:{role.upper()}", "type": role, "label": p, "metadata": {"path": p, "role": role}}


def _edge(t, s, d, **meta):
    return {"id": f"{s}->{t}->{d}", "type": t, "source": s, "target": d, "metadata": meta}


PATHS = [
    "src/routes/repo.routes.js",
    "src/controllers/repo.controller.js",
    "src/services/repo.service.js",
    "src/services/git.service.js",
    "src/utils/logger.js",
    "src/routes/user.routes.js",
    "src/controllers/user.controller.js",
    "src/middleware/auth.js",
]


def _f(i):
    return "file:" + PATHS[i]


IR = {
    "nodes": [_file(p) for p in PATHS]
    + [
        _arch(PATHS[0], "route"),
        _arch(PATHS[1], "controller"),
        _arch(PATHS[2], "service"),
        _arch(PATHS[5], "route"),
        _arch(PATHS[6], "controller"),
    ],
    "edges": [
        _edge("imports", _f(0), _f(1)),
        _edge("imports", _f(1), _f(2)),
        _edge("imports", _f(2), _f(3)),
        _edge("imports", _f(2), _f(4)),
        _edge("imports", _f(0), _f(7)),
        _edge("imports", _f(5), _f(6)),
        _edge("imports", _f(5), _f(7)),
        _edge("imports", _f(6), _f(4)),
        _edge(
            "depends_on",
            "architecture:" + PATHS[0] + ":ROUTE",
            "architecture:" + PATHS[1] + ":CONTROLLER",
            source_role="route",
            target_role="controller",
        ),
        _edge(
            "depends_on",
            "architecture:" + PATHS[1] + ":CONTROLLER",
            "architecture:" + PATHS[2] + ":SERVICE",
            source_role="controller",
            target_role="service",
        ),
    ],
}


def test_keywords_stem_and_drop_stopwords():
    assert stem("routes") == stem("route") == stem("routing")
    assert "repo" in keywords("Trace the repo creation from the URL")
    assert "the" not in keywords("the repo")


def test_file_graph_lifts_edges_and_roles():
    fg = build_file_graph(IR)
    assert fg.has_role(PATHS[0], "route")
    kinds = {(e.source, e.target): e.kinds for e in fg.edges}
    assert "depends_on" in kinds[(PATHS[0], PATHS[1])]
    assert "imports" in kinds[(PATHS[0], PATHS[1])]


def test_pruner_returns_the_matching_chain_not_neighbours():
    fg = build_file_graph(IR)
    pairs = [e.pair for e in prune(fg, "trace the repo request flow", k_max=3)]
    assert (PATHS[0], PATHS[1]) in pairs
    assert (PATHS[1], PATHS[2]) in pairs
    assert all("user" not in a and "user" not in b for a, b in pairs)
    assert len(pairs) <= 3


def test_pruner_is_bounded_and_smaller_than_bfs():
    fg = build_file_graph(IR)
    assert len(bfs_edges(fg, "repo", hops=2)) > len(prune(fg, "repo", k_max=2))
    assert len(prune(fg, "repo", k_max=1)) == 1


def test_pruner_empty_for_unrelated_query():
    fg = build_file_graph(IR)
    assert prune(fg, "zzz qqq") == []
    assert prune(fg, "") == []


def test_pruner_ignores_tests():
    ir = {
        "nodes": IR["nodes"] + [_file("tests/repo.test.js")],
        "edges": IR["edges"] + [_edge("imports", "file:tests/repo.test.js", _f(2))],
    }
    fg = build_file_graph(ir)
    assert all("test" not in e.source for e in score_edges(fg, "repo service"))


def test_roles_can_be_disabled_for_ablation():
    fg = build_file_graph(IR)
    with_roles = {e.pair: e.score for e in score_edges(fg, "repo", use_roles=True)}
    without = {e.pair: e.score for e in score_edges(fg, "repo", use_roles=False)}
    assert with_roles[(PATHS[0], PATHS[1])] > without[(PATHS[0], PATHS[1])]


def test_reverse_intent_ranks_importers_by_distance():
    fg = build_file_graph(IR)
    ranked = graph_rank(fg, "Which files import src/services/git.service.js?")
    assert ranked[0] == PATHS[2]
    assert ranked[1] == PATHS[1]


def test_rrf_prefers_items_ranked_well_by_both_lists():
    fused = rrf({"a": ["x", "y", "z"], "b": ["y", "x", "w"]})
    assert set(fused[:2]) == {"x", "y"}
    assert set(fused) == {"x", "y", "z", "w"}


def test_bm25_and_lsa_rank_relevant_file_first():
    docs = {
        "a.py": "parse the cookie header into values",
        "b.py": "open a database connection",
        "c.py": "render html template",
    }
    assert Bm25Index(docs).rank("cookie header")[0] == "a.py"
    assert LsaIndex(docs, dim=2).rank("cookie header")[0] == "a.py"


def test_retriever_builds_all_rankings():
    r = RepoRetriever(IR, {p: p for p in PATHS}, lsa_dim=4)
    assert set(r.rankings("repo service git")) == {"bm25", "vector", "graph", "hybrid", "hybrid+bm25"}


def test_threshold_zero_avoids_empty_output_with_rank_relevance():
    fg = build_file_graph(IR)
    rel = {PATHS[3]: 0.2, PATHS[4]: 0.1}  # weak reciprocal-rank relevance, below the default threshold
    assert prune(fg, "x", k_max=3, relevance=rel, use_roles=False) == []
    out = prune(fg, "x", k_max=3, relevance=rel, use_roles=False, threshold=0.0)
    assert out and all(PATHS[3] in e.pair or PATHS[4] in e.pair for e in out)


def test_bfs_accepts_explicit_seeds_and_candidate_pool():
    from src.retrieval.pruner import candidate_edges

    fg = build_file_graph(IR)
    edges = bfs_edges(fg, "", hops=1, seeds=[PATHS[1]])
    assert edges == [(PATHS[1], PATHS[2])]
    pool = candidate_edges(fg, {PATHS[2]: 1.0})
    assert set(pool) == {(PATHS[1], PATHS[2]), (PATHS[2], PATHS[3]), (PATHS[2], PATHS[4])}
