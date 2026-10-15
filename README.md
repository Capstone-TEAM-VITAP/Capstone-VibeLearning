# CodeAI — Semantic Code Search & RAG

FastAPI app for indexing local or public GitHub repositories and searching code semantically.

## Supported languages
Python, Java, JavaScript/JSX, TypeScript/TSX, C, and C++.

## Setup (Windows PowerShell)
```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
Copy-Item .env.example .env
python -m uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000/ and API docs at http://127.0.0.1:8000/docs.

If you use Python 3.13 and a dependency fails to install, use Python 3.11 or 3.12 in a new virtual environment.

## GitHub token
The app can list public repos without a token, but unauthenticated API limits are low. Put `GITHUB_TOKEN=...` in `.env` for authenticated requests. A token is optional for public repositories. Never commit `.env`.

## Index a local repository
```powershell
python scripts/index_repository.py "C:\path\to\repo" my-repo
```
Then search with repository ID `my-repo`.

## API
- `GET /api/health`
- `GET /api/github/repositories?username=octocat`
- `POST /api/github/analyze` with `{"owner":"octocat","repo":"Hello-World","branch":"master"}`
- `POST /search` with `{"repository_id":"github:octocat/Hello-World","query":"find user login","limit":5}`

## Notes
- Qdrant local storage lives in `qdrant_data/`.
- First search/index may download the `all-MiniLM-L6-v2` embedding model.
- Tree-sitter extracts syntax-aware chunks. Graph edges are inferred from symbol references and are best-effort, not a full compiler call graph.
- GitHub archive indexing stores supported source files only; do not analyze repositories you are not authorized to access.
