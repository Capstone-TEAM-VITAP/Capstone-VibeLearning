from pathlib import Path
import re

PROJECT_ROOT = Path(__file__).resolve().parent.parent
REPOSITORIES_DIR = PROJECT_ROOT / "data" / "repositories"

def resolve_repository_path(repository_id: str) -> Path:
    if repository_id == "demo":
        return (REPOSITORIES_DIR / "demo").resolve()

    if not isinstance(repository_id, str) or not repository_id.startswith("github:"):
        raise ValueError("Unsupported repository_id. Use 'demo' or 'github:owner/repo'.")

    parts = repository_id[len("github:"):].split("/")
    if len(parts) != 2:
        raise ValueError("GitHub repository ID must look like github:owner/repo.")

    owner, repo = parts
    for item in (owner, repo):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+", item) or item in {".", ".."}:
            raise ValueError("Invalid GitHub owner or repository name.")

    path = (REPOSITORIES_DIR / "github" / owner / repo).resolve()
    if not path.is_relative_to(REPOSITORIES_DIR.resolve()):
        raise ValueError("Invalid repository path.")
    return path
