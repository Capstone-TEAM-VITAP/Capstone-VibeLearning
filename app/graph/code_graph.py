import re
from pathlib import Path
from app.chunking.code_chunker import chunk_file, EXTENSION_TO_LANGUAGE

SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", "dist", "build"}

def build_code_graph(repository_path):
    root = Path(repository_path)
    nodes = []
    by_symbol = {}
    if not root.is_dir():
        return {"nodes": [], "relationships": []}

    for path in root.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in EXTENSION_TO_LANGUAGE:
            continue
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        try:
            source = path.read_text(encoding="utf-8", errors="replace")
            chunks = chunk_file(path, source)
        except Exception:
            continue
        rel = path.relative_to(root).as_posix()
        for chunk in chunks:
            node = {
                "id": f"{rel}:{chunk['symbol']}:{chunk['start_line']}",
                "file": rel,
                "symbol": chunk["symbol"],
                "type": chunk["type"],
                "language": chunk["language"],
                "start_line": chunk["start_line"],
                "code": chunk["code"],
            }
            nodes.append(node)
            by_symbol.setdefault(chunk["symbol"], []).append(node)

    relationships = []
    for node in nodes:
        identifiers = set(re.findall(r"\b[A-Za-z_]\w*\b", node["code"]))
        for symbol, candidates in by_symbol.items():
            if symbol == node["symbol"] or symbol not in identifiers:
                continue
            for target in candidates:
                if target["id"] != node["id"]:
                    relationships.append({
                        "source": node["id"],
                        "target": target["id"],
                        "source_symbol": node["symbol"],
                        "target_symbol": target["symbol"],
                        "type": "references",
                    })
                    break
    return {"nodes": nodes, "relationships": relationships}

def get_graph_relationships(repository_path):
    return build_code_graph(repository_path).get("relationships", [])
