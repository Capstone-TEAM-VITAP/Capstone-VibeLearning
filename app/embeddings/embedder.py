from functools import lru_cache
from sentence_transformers import SentenceTransformer

MODEL_NAME = "all-MiniLM-L6-v2"

@lru_cache(maxsize=1)
def get_model():
    return SentenceTransformer(MODEL_NAME)

def generate_embedding(text: str) -> list[float]:
    if not text or not text.strip():
        raise ValueError("Cannot embed empty text.")
    vector = get_model().encode(text, normalize_embeddings=True)
    return vector.tolist()
