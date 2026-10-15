from app.embeddings.embedder import generate_embedding
from app.qdrant_client import client, COLLECTION_NAME

def search_code(query: str, limit: int = 5, repository_id: str | None = None, branch: str | None = None):
    vector = generate_embedding(query)
    query_filter = None
    must = []
    if repository_id:
        from qdrant_client.models import FieldCondition, MatchValue
        must.append(FieldCondition(key="repository_id", match=MatchValue(value=repository_id)))
    if branch:
        from qdrant_client.models import FieldCondition, MatchValue
        must.append(FieldCondition(key="branch", match=MatchValue(value=branch)))
    if must:
        from qdrant_client.models import Filter
        query_filter = Filter(must=must)

    response = client.query_points(
        collection_name=COLLECTION_NAME,
        query=vector,
        query_filter=query_filter,
        limit=limit,
        with_payload=True,
    )
    results = []
    for point in response.points:
        payload = point.payload or {}
        results.append({
            "file": payload.get("file", ""),
            "symbol": payload.get("symbol", ""),
            "type": payload.get("type", ""),
            "language": payload.get("language", "unknown"),
            "code": payload.get("code", ""),
            "repository_id": payload.get("repository_id", ""),
            "branch": payload.get("branch"),
            "start_line": payload.get("start_line"),
            "end_line": payload.get("end_line"),
            "semantic_score": float(point.score or 0.0),
        })
    return results
