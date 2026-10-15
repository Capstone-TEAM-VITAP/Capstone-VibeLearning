from app.retrieval.semantic_search import search_code
from app.graph.code_graph import build_code_graph
from app.repository_utils import resolve_repository_path

def hybrid_search(query: str, repository_id: str = "demo", limit: int = 5, branch: str | None = None):
    candidates = search_code(query, limit=max(limit * 4, 20), repository_id=repository_id, branch=branch)
    try:
        graph = build_code_graph(resolve_repository_path(repository_id))
    except (ValueError, OSError):
        graph = {"nodes": [], "relationships": []}

    related_symbols = set()
    symbol_by_id = {node["id"]: node for node in graph["nodes"]}
    candidate_symbols = {item["symbol"] for item in candidates[:3] if item.get("symbol")}
    for edge in graph["relationships"]:
        source = symbol_by_id.get(edge["source"], {})
        target = symbol_by_id.get(edge["target"], {})
        if source.get("symbol") in candidate_symbols:
            related_symbols.add(target.get("symbol"))
        if target.get("symbol") in candidate_symbols:
            related_symbols.add(source.get("symbol"))

    for item in candidates:
        bonus = 0.12 if item.get("symbol") in related_symbols else 0.0
        item["graph_bonus"] = bonus
        item["hybrid_score"] = item.get("semantic_score", 0.0) + bonus

    candidates.sort(key=lambda item: item["hybrid_score"], reverse=True)
    return candidates[:limit]
