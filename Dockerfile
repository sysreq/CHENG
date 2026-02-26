# ── Stage 1: Frontend Build ──────────────────────────────────────────
FROM node:22-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm build

# ── Stage 2: Python Runtime ──────────────────────────────────────────
FROM python:3.11-slim AS runtime

LABEL org.opencontainers.image.title="CHENG" \
      org.opencontainers.image.description="Parametric RC Plane Generator" \
      org.opencontainers.image.version="0.1.0" \
      org.opencontainers.image.source="https://github.com/sysreq/CHENG"

# System libs required by CadQuery/OpenCascade (OCP)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libx11-6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install uv and project dependencies (into .venv)
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Copy application code
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY airfoils/ ./airfoils/

# Create data directories
RUN mkdir -p /data/designs /data/tmp

ENV PORT=8000 \
    CHENG_DATA_DIR=/data/designs \
    CHENG_LOG_LEVEL=info \
    CHENG_MODE=local \
    PATH="/app/.venv/bin:$PATH"

EXPOSE 8000

# Health check uses $PORT so it works in both local (8000) and Cloud Run (8080) modes.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request, os; urllib.request.urlopen('http://localhost:' + os.environ.get('PORT', '8000') + '/health')"

# Shell form with exec so uvicorn becomes PID 1 and receives signals correctly.
# Cloud Run injects PORT (typically 8080); local Docker defaults to 8000.
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}"
