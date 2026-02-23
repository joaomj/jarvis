# Multi-stage build for minimal, secure image
# Stage 1: Build dependencies
FROM python:3.12-alpine AS builder

WORKDIR /build

# Install build dependencies
# hadolint ignore=DL3018
RUN apk add --no-cache gcc musl-dev libffi-dev

# Copy dependency files first for caching (include README.md for pyproject.toml)
COPY pyproject.toml pdm.lock README.md ./

# Copy source code
COPY src/ ./src/

# Install PDM and dependencies (install package + prod deps)
RUN pip install --no-cache-dir pdm && \
    pdm install --prod --no-editable

# Stage 2: Runtime image
FROM python:3.12-alpine AS runtime

WORKDIR /app

# Create non-root user
RUN addgroup -S -g 1000 jarvis && \
    adduser -S -u 1000 -G jarvis jarvis && \
    mkdir -p /app/.jarvis && \
    chown -R jarvis:jarvis /app

# Copy virtualenv with installed package from builder
COPY --from=builder /build/.venv /app/.venv
COPY --chown=jarvis:jarvis src/ ./src/

# Set environment
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app/src" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    JARVIS_ENV=production \
    LOG_LEVEL=INFO

# Switch to non-root user
USER jarvis

# Expose webhook port
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/health', timeout=5)" || exit 1

# Run the bot
CMD ["python", "-m", "jarvis"]
