import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from qdrant_client.models import PointStruct, Filter, FieldCondition, MatchValue
from app.chunking.code_chunker import chunk_file, EXTENSION_TO_LANGUAGE
from app.embeddings.embedder import generate_embedding
from app.qdrant_client import client, COLLECTION_NAME, create_collection

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build", "qdrant_data"}

def index_repository(repository_path, repository_id=None):
    root = Path(repository_path).resolve()
    if not root.is_dir():
        raise FileNotFoundError(f"Repository directory not found: {root}")
    repository_id = repository_id or root.name
    create_collection()
    points, failures, scanned = [], [], 0

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSION_TO_LANGUAGE:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        try:
            code = path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_file(path, code)
            scanned += 1
            for chunk in chunks:
                key = f"{repository_id}:{relative}:{chunk['symbol']}:{chunk['start_line']}:{chunk['code']}"
                points.append(PointStruct(
                    id=str(uuid.uuid5(uuid.NAMESPACE_URL, key)),
                    vector=generate_embedding(chunk["code"]),
                    payload={
                        "repository_id": repository_id,
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
            failures.append({"file": relative, "error": str(exc)})
            print(f"Skipped {relative}: {exc}")

    if not points:
        print("No chunks extracted; existing Qdrant entries were left unchanged.")
        return {"files_scanned": scanned, "chunks_indexed": 0, "failures": failures}

    client.delete(
        collection_name=COLLECTION_NAME,
        points_selector=Filter(must=[FieldCondition(key="repository_id", match=MatchValue(value=repository_id))]),
        wait=True,
    )
    for start in range(0, len(points), 64):
        client.upsert(collection_name=COLLECTION_NAME, points=points[start:start+64], wait=True)

    languages = sorted({p.payload["language"] for p in points})
    print(f"Repository ID: {repository_id}")
    print(f"Files scanned: {scanned}")
    print(f"Chunks indexed: {len(points)}")
    print(f"Languages: {', '.join(languages)}")
    print(f"Files skipped: {len(failures)}")
    return {"files_scanned": scanned, "chunks_indexed": len(points), "languages": languages, "failures": failures}

if __name__ == "__main__":
    repo_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "data" / "repositories" / "demo"
    repo_id = sys.argv[2] if len(sys.argv) > 2 else repo_path.name
    try:
        index_repository(repo_path, repo_id)
    finally:
        client.close()
