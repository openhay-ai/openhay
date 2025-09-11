# Minimal Dockerfile for FastAPI on Railway (SSE-friendly)
# Uses Python 3.13 slim and uv for fast, reproducible installs

FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PATH="/root/.local/bin:${PATH}" \
    PYTHONPATH=/app \
    DEBIAN_FRONTEND=noninteractive

WORKDIR /app

# Install essential system dependencies first
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    ca-certificates \
  && rm -rf /var/lib/apt/lists/*

# Install Chromium/Playwright runtime dependencies in a separate step for better error handling
RUN apt-get update && apt-get install -y --no-install-recommends \
    libglib2.0-0 \
    libnss3 \
    libnspr4 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxrandr2 \
    libasound2 \
    libpangocairo-1.0-0 \
    libpango-1.0-0 \
    libcairo2 \
    libgdk-pixbuf-2.0-0 \
    libgtk-3-0 \
    libx11-6 \
    libxext6 \
    libxcb1 \
    libxrender1 \
    libgbm1 \
    libxshmfence1 \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*

# Install fonts separately (these are often optional and can fail)
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-liberation \
    fonts-dejavu-core \
  && apt-get clean \
  && rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/* || true

# Install uv package manager
RUN pip install --no-cache-dir uv

# Copy dependency manifests first for better layer caching
COPY pyproject.toml uv.lock ./

# Install project dependencies into a local virtualenv at /app/.venv
RUN uv sync --locked --no-dev

# Ensure browsers are available for Crawl4AI (avoid Ubuntu-only --with-deps on Debian)
RUN /app/.venv/bin/crawl4ai-setup || true
RUN /app/.venv/bin/python -m playwright install chromium || true

# Copy backend source under a top-level package path so imports like `backend.*` work
COPY . /app/backend

# Place executables in the environment at the front of the path
ENV PATH="/app/.venv/bin:$PATH"

# Railway provides $PORT. Expose for local clarity.
ARG PORT=8080
ENV PORT=${PORT}
EXPOSE ${PORT}

# Start FastAPI with Uvicorn; bind to 0.0.0.0 and $PORT
CMD ["sh", "-c", "uvicorn backend.api.main:app --host 0.0.0.0 --port ${PORT}"]
