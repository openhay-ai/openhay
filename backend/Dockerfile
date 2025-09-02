# Minimal Dockerfile for FastAPI on Railway (SSE-friendly)
# Uses Python 3.12 slim and uv for fast, reproducible installs

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_SYSTEM_PYTHON=1 \
    PATH="/root/.local/bin:${PATH}"

WORKDIR /app

# Install system deps needed by psycopg (binary) and build tools minimally
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
  && rm -rf /var/lib/apt/lists/*

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies (no dev) into system site-packages
RUN uv sync --locked --no-install-project --no-dev

# Ensure ASGI server is available (use uvicorn by default)
RUN pip install --no-cache-dir "uvicorn[standard]>=0.30"

# Copy backend source under a top-level package path so imports like `backend.*` work
COPY . /app/backend

# Railway provides $PORT. Expose for local clarity.
ARG PORT=8000
ENV PORT=${PORT}
EXPOSE ${PORT}

# Start FastAPI with Uvicorn; bind to 0.0.0.0 and $PORT
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}"]
