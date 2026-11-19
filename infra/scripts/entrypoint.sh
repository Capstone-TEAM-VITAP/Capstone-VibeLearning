#!/bin/bash
set -e

echo "[CodeAI Cloud Run] Initializing unified container..."

# 1. Create and prepare shared repository directory
mkdir -p /tmp/codeai-repos
chmod 777 /tmp/codeai-repos
echo "[CodeAI Cloud Run] Shared directory /tmp/codeai-repos ready."

# 2. Ensure log and run directories exist
mkdir -p /var/log/supervisor /var/run

# 3. Apply default environment variables if not supplied by Cloud Run
export PORT="${PORT:-8080}"
export HOST="${HOST:-0.0.0.0}"
export AI_SERVICE_URL="${AI_SERVICE_URL:-http://127.0.0.1:8000}"
export GIT_CACHE_DIR="${GIT_CACHE_DIR:-/tmp/codeai-repos}"
export CODEAI_ANALYSIS_ROOT="${CODEAI_ANALYSIS_ROOT:-/tmp/codeai-repos}"

echo "[CodeAI Cloud Run] PORT=${PORT}, HOST=${HOST}, AI_SERVICE_URL=${AI_SERVICE_URL}"
echo "[CodeAI Cloud Run] Starting supervisord..."

# 4. Exec into supervisord as PID 1
exec /usr/bin/supervisord -c /app/infra/docker/supervisord.conf
