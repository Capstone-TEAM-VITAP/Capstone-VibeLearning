def build_context(query, results, graph_data=None):
    graph_data = graph_data or {"nodes": [], "relationships": []}
    symbols = {item.get("symbol") for item in results if item.get("symbol")}
    related = []
    for edge in graph_data.get("relationships", []):
        if edge.get("source_symbol") in symbols or edge.get("target_symbol") in symbols:
            related.append(edge)
    evidence = []
    for item in results:
        evidence.append({
            "file": item.get("file"),
            "symbol": item.get("symbol"),
            "language": item.get("language"),
            "score": item.get("hybrid_score", item.get("semantic_score")),
            "code": item.get("code"),
        })
    return {
        "query": query,
        "result_count": len(results),
        "evidence": evidence,
        "related_relationships": related[:30],
    }
