"""Run the ai-service static analysis on every benchmark repo and record stats (RQ4)."""
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# AI_SERVICE_DIR / OUT_SUBDIR let the same script analyze with an older analyzer (v1) for before/after runs.
sys.path.insert(0, os.environ.get("AI_SERVICE_DIR", str(ROOT / "apps" / "ai-service")))
OUT_SUBDIR = os.environ.get("OUT_SUBDIR", "")

from src.repository.pipeline import analyze_repository  # noqa: E402

REPOS = json.loads((ROOT / "research" / "repos.json").read_text())
names = REPOS["dev"] + REPOS["test"] + REPOS.get("test2", []) + REPOS.get("python", []) + [x for x in REPOS.get("flow", []) if x not in REPOS["dev"] + REPOS["test"] + REPOS["test2"]]
out_dir = ROOT / "research" / "out" / OUT_SUBDIR / "graphs"
out_dir.mkdir(parents=True, exist_ok=True)

stats = {}
for name in names:
    path = ROOT / "research" / "data" / "repos" / name
    t0 = time.perf_counter()
    try:
        result = analyze_repository(path, repo_name=name)
    except Exception as err:  # record crashes instead of hiding them
        stats[name] = {"ok": False, "error": f"{type(err).__name__}: {err}"}
        print(name, "FAILED", err)
        continue
    secs = time.perf_counter() - t0
    ir = result.ir
    (out_dir / f"{name}.json").write_text(json.dumps(ir))
    types = {}
    for n in ir["nodes"]:
        types[n["type"]] = types.get(n["type"], 0) + 1
    etypes = {}
    for e in ir["edges"]:
        etypes[e["type"]] = etypes.get(e["type"], 0) + 1
    stats[name] = {
        "ok": True,
        "seconds": round(secs, 3),
        "nodes": len(ir["nodes"]),
        "edges": len(ir["edges"]),
        "node_types": types,
        "edge_types": etypes,
    }
    print(name, stats[name]["nodes"], stats[name]["edges"], stats[name]["seconds"])

(ROOT / "research" / "out" / OUT_SUBDIR / "analysis_stats.json").write_text(json.dumps(stats, indent=2))
