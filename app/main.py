from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import router as search_router
from app.api.github_routes import router as github_router
from app.qdrant_client import create_collection

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(title="CodeAI - Semantic Code Search & RAG", version="1.0.0")

create_collection()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
app.include_router(search_router)
app.include_router(github_router)

@app.get("/", include_in_schema=False)
def home():
    return FileResponse(STATIC_DIR / "index.html")
