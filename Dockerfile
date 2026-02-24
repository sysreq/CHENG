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

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1-mesa-glx libglib2.0-0 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install uv && uv sync --frozen --no-dev
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./static/
COPY airfoils/ ./airfoils/

RUN mkdir -p /data/designs /data/tmp

ENV PORT=8000 \
    CHENG_DATA_DIR=/data/designs \
    CHENG_LOG_LEVEL=info

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')"

CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
