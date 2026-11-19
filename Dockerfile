# Unified Multi-Service Container for Google Cloud Run
# Contains: Node.js 24 Express Backend + Python 3.11 FastAPI AI Service + Git & Tar binaries

FROM node:24-bookworm-slim AS runner

# Prevent interactive prompts during apt package installation
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies: Python 3.11, Git CLI, Tar, Supervisor, CA certificates, and curl
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    git \
    tar \
    supervisor \
    ca-certificates \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Set container working directory
WORKDIR /app

# Enable and configure pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Create Python virtual environment for isolated execution
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Install lightweight AI service dependencies (excluding pytest and optional heavy neural packages)
COPY apps/ai-service/requirements.txt /app/apps/ai-service/requirements.txt
RUN pip install --no-cache-dir --upgrade pip && \
    grep -Ev "^(pytest|#|$)" /app/apps/ai-service/requirements.txt > /tmp/prod-requirements.txt && \
    pip install --no-cache-dir -r /tmp/prod-requirements.txt && \
    rm /tmp/prod-requirements.txt

# Copy monorepo workspace configuration and dependency manifests
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml /app/
COPY apps/backend/package.json /app/apps/backend/package.json

# Install backend production dependencies via pnpm
RUN pnpm install --frozen-lockfile --filter backend...

# Copy application source directories
COPY apps/backend /app/apps/backend
COPY apps/ai-service /app/apps/ai-service
COPY infra /app/infra

# Security: Guarantee zero secrets or .env files exist in container image
RUN find /app -name ".env" -type f -delete && \
    find /app -name ".env.*" ! -name ".env.example" -type f -delete

# Create shared repository directory with full permissions for both services
RUN mkdir -p /tmp/codeai-repos && chmod 777 /tmp/codeai-repos

# Ensure supervisor scripts have proper execute permissions
RUN chmod +x /app/infra/scripts/*.sh /app/infra/scripts/*.py 2>/dev/null || true

# Set required Cloud Run runtime environment variables
ENV NODE_ENV=production \
    PORT=8080 \
    HOST=0.0.0.0 \
    AI_SERVICE_URL=http://127.0.0.1:8000 \
    GIT_CACHE_DIR=/tmp/codeai-repos \
    CODEAI_ANALYSIS_ROOT=/tmp/codeai-repos \
    PYTHONUNBUFFERED=1

# Expose default Cloud Run port
EXPOSE 8080

# Production Entrypoint using Supervisord process supervisor
ENTRYPOINT ["/app/infra/scripts/entrypoint.sh"]
