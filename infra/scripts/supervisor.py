#!/usr/bin/env python3
"""
CodeAI Unified Process Supervisor.

Runs both:
- Python FastAPI AI Service (127.0.0.1:8000)
- Node.js Express Backend (0.0.0.0:PORT)

Features:
- Handles SIGTERM and SIGINT gracefully, forwarding to both child processes.
- Monolithic failover: If either process exits unexpectedly, terminates the other and exits.
- Prepares /tmp/codeai-repos (or OS temp dir).
"""

import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

# Paths
ROOT_DIR = Path(__file__).resolve().parent.parent.parent
BACKEND_DIR = ROOT_DIR / "apps" / "backend"
AI_DIR = ROOT_DIR / "apps" / "ai-service"

# Processes
proc_ai = None
proc_backend = None
shutting_down = False


def sig_handler(signum, frame):
    global shutting_down
    if shutting_down:
        return
    shutting_down = True
    sig_name = "SIGTERM" if signum == signal.SIGTERM else "SIGINT"
    print(f"\n[Supervisor] Received {sig_name}. Forwarding shutdown to child processes...", flush=True)

    for name, p in [("backend", proc_backend), ("ai-service", proc_ai)]:
        if p and p.poll() is None:
            try:
                p.send_signal(signal.SIGTERM if os.name != "nt" else signal.SIGINT)
            except OSError:
                pass

    # Wait up to 10 seconds for graceful termination
    start = time.time()
    while time.time() - start < 10:
        if (not proc_backend or proc_backend.poll() is not None) and (not proc_ai or proc_ai.poll() is not None):
            break
        time.sleep(0.2)

    # Force kill if still running
    for name, p in [("backend", proc_backend), ("ai-service", proc_ai)]:
        if p and p.poll() is None:
            try:
                p.kill()
            except OSError:
                pass

    print("[Supervisor] All services stopped. Exiting.", flush=True)
    sys.exit(0)


def main():
    global proc_ai, proc_backend

    # Register signals
    signal.signal(signal.SIGTERM, sig_handler)
    signal.signal(signal.SIGINT, sig_handler)

    port = os.environ.get("PORT", "8080")
    host = os.environ.get("HOST", "0.0.0.0")
    ai_port = os.environ.get("AI_PORT", "8000")
    default_cache = "/tmp/codeai-repos" if os.name != "nt" else str(Path(tempfile.gettempdir()) / "codeai-repos")
    cache_dir = os.environ.get("GIT_CACHE_DIR", default_cache)

    os.environ["PORT"] = port
    os.environ["HOST"] = host
    os.environ["AI_SERVICE_URL"] = f"http://127.0.0.1:{ai_port}"
    os.environ["GIT_CACHE_DIR"] = cache_dir
    os.environ["CODEAI_ANALYSIS_ROOT"] = cache_dir
    os.environ["PYTHONUNBUFFERED"] = "1"

    os.makedirs(cache_dir, exist_ok=True)

    print(f"[Supervisor] Initializing CodeAI Unified Services...", flush=True)
    print(f"[Supervisor] Cache / Analysis Root: {cache_dir}", flush=True)
    print(f"[Supervisor] AI Service URL: http://127.0.0.1:{ai_port}", flush=True)
    print(f"[Supervisor] Express Port: {port} (Host: {host})", flush=True)

    # 1. Start Python FastAPI AI Service
    ai_cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "src.main:app",
        "--app-dir",
        str(AI_DIR),
        "--host",
        "127.0.0.1",
        "--port",
        str(ai_port),
    ]
    print(f"[Supervisor] Starting AI service on 127.0.0.1:{ai_port}...", flush=True)
    proc_ai = subprocess.Popen(ai_cmd, cwd=str(AI_DIR))

    # 2. Start Node.js Express Backend
    backend_script = str(BACKEND_DIR / "index.js")
    backend_cmd = ["node", backend_script]
    print(f"[Supervisor] Starting Backend on {host}:{port}...", flush=True)
    proc_backend = subprocess.Popen(backend_cmd, cwd=str(BACKEND_DIR))

    print("[Supervisor] Both processes launched. Monitoring health...", flush=True)

    # Monitor loop: if either process exits unexpectedly, terminate the other and exit
    while not shutting_down:
        ai_code = proc_ai.poll()
        backend_code = proc_backend.poll()

        if ai_code is not None:
            print(f"[Supervisor] AI Service exited unexpectedly with code {ai_code}! Terminating container...", flush=True)
            if proc_backend.poll() is None:
                proc_backend.terminate()
            sys.exit(ai_code if ai_code != 0 else 1)

        if backend_code is not None:
            print(f"[Supervisor] Backend exited unexpectedly with code {backend_code}! Terminating container...", flush=True)
            if proc_ai.poll() is None:
                proc_ai.terminate()
            sys.exit(backend_code if backend_code != 0 else 1)

        time.sleep(0.5)


if __name__ == "__main__":
    main()
