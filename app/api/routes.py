from fastapi import APIRouter, HTTPException
from app.models import SearchRequest
from app.retrieval.hybrid_search import hybrid_search
from app.graph.code_graph import build_code_graph
from app.context.context_builder import build_context
from app.repository_utils import resolve_repository_path

router = APIRouter(tags=["Search"])

@router.get("/api/health")
def health():
    return {"status": "ok", "service": "CodeAI"}

@router.post("/search")
def search(request: SearchRequest):
    query = request.query.strip()
    if not query:
        raise HTTPException(status_code=400, detail="Query cannot be empty.")
    try:
        repo_path = resolve_repository_path(request.repository_id)
        if not repo_path.is_dir():
            raise HTTPException(status_code=404, detail="Repository is not downloaded/indexed locally.")
        results = hybrid_search(query, request.repository_id, request.limit)
        graph = build_code_graph(repo_path)
        context = build_context(query, results, graph)
        return {
            "repository_id": request.repository_id,
            "query": query,
            "count": len(results),
            "results": results,
            "context": context,
        }
    except HTTPException:
        raise
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Search failed: {exc}") from exc
