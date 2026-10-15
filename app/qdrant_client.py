from pathlib import Path
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams

PROJECT_ROOT = Path(__file__).resolve().parent.parent
QDRANT_PATH = PROJECT_ROOT / "qdrant_data"
COLLECTION_NAME = "code_chunks"
VECTOR_SIZE = 384

client = QdrantClient(path=str(QDRANT_PATH))

def create_collection():
    if not client.collection_exists(COLLECTION_NAME):
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

def close_client():
    client.close()
