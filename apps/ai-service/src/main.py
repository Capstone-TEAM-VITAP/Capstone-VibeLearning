"""
main.py — AI Service entry point.

Existing FastAPI service preserved.
Repository Intelligence module will be wired in subsequent milestones.
"""

from fastapi import FastAPI

app = FastAPI(title="AI Service", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}
