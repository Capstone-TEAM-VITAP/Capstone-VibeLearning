import uuid
from fastapi import APIRouter, HTTPException
from app.models import AnalyzeRequest
from app.github_service import list_public_repositories, download_public_repository
from app.chunking.code_chunker import chunk_file, EXTENSION_TO_LANGUAGE
from app.embeddings.embedder import generate_embedding
from app.qdrant_client import client, COLLECTION_NAME, create_collection
from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue

router = APIRouter(prefix="/api/github", tags=["GitHub"])

@router.get("/repositories")
def repositories(username: str):
    try:
        repos = list_public_repositories(username)
        return {"repositories": repos, "count": len(repos)}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

@router.post("/analyze")
def analyze(request: AnalyzeRequest):
    repository_id = f"github:{request.owner}/{request.repo}"
    try:
        create_collection()
        folder, files_extracted = download_public_repository(request.owner, request.repo, request.branch)
        points, failures, files_scanned = [], [], 0

        for path in folder.rglob("*"):
            if not path.is_file() or path.suffix.lower() not in EXTENSION_TO_LANGUAGE:
                continue
            try:
                code = path.read_text(encoding="utf-8", errors="replace")
                relative = path.relative_to(folder).as_posix()
                chunks = chunk_file(path, code)
                files_scanned += 1
                for chunk in chunks:
                    key = f"{repository_id}:{request.branch}:{relative}:{chunk['symbol']}:{chunk['start_line']}:{chunk['code']}"
                    points.append(PointStruct(
                        id=str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
                        vector=generate_embedding(chunk["code"]),
                        payload={
                            "repository_id": repository_id,
                            "branch": request.branch,
                            "file": relative,
                            "symbol": chunk["symbol"],
                            "type": chunk["type"],
                            "language": chunk["language"],
                            "start_line": chunk["start_line"],
                            "end_line": chunk["end_line"],
                            "code": chunk["code"],
                        },
                    ))
            except Exception as exc:
                failures.append({"file": str(path.relative_to(folder)), "error": str(exc)})

        if not points:
            raise HTTPException(status_code=400, detail="No code chunks were extracted from supported source files.")

        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=Filter(must=[
                FieldCondition(key="repository_id", match=MatchValue(value=repository_id)),
                FieldCondition(key="branch", match=MatchValue(value=request.branch)),
            ]),
            wait=True,
        )
        for start in range(0, len(points), 64):
            client.upsert(collection_name=COLLECTION_NAME, points=points[start:start + 64], wait=True)

        return {
            "message": "Repository analyzed successfully",
            "repository_id": repository_id,
            "branch": request.branch,
            "source_files_extracted": files_extracted,
            "files_scanned": files_scanned,
            "chunks_indexed": len(points),
            "languages": sorted({p.payload["language"] for p in points}),
            "failed_files_count": len(failures),
            "failed_files": failures[:20],
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Repository analysis failed: {exc}") from exc
