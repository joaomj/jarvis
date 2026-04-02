# Multi-stage build for minimal, secure image
# Stage 1: Build dependencies
FROM python:3.12-alpine AS builder

WORKDIR /build

# hadolint ignore=DL3018
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy dependency files first for caching (include README.md for pyproject.toml)
COPY pyproject.toml pdm.lock README.md ./

# Copy source code (baked in for GHCR standalone image)
COPY src/ ./src/

# Install PDM and dependencies (install package + prod deps)
RUN pip install --no-cache-dir pdm && \
    pdm install --prod --no-editable

# Stage 2: Runtime image
FROM python:3.12-alpine AS runtime

RUN addgroup -S -g 1000 jarvis && \
    adduser -S -u 1000 -G jarvis jarvis

WORKDIR /app/project

# Copy virtualenv with installed package from builder
COPY --from=builder /build/.venv /app/.venv

# Copy source (used when running standalone GHCR image without bind mount)
COPY --chown=jarvis:jarvis src/ ./src/

# Set environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/project/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_ENV=production \
    LOG_LEVEL=INFO

# Switch to non-root user
USER jarvis

# Health check: uses OPENCODE_URL (overridden by compose to Docker DNS)
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD python -c "import os, httpx; r = httpx.get(os.getenv('OPENCODE_URL', 'http://localhost:4096') + '/global/health', timeout=5); exit(0 if r.status_code == 200 and r.json().get('healthy') else 1)" || exit 1

# Run the bot
CMD ["python", "-m", "jarvis"]
