# syntax=docker/dockerfile:1
FROM python:3.11-slim AS base

# Security: Run as non-root
RUN groupadd -r jarvis && useradd -r -g jarvis -u 1000 jarvis

WORKDIR /app

# Install system dependencies (ffmpeg for future voice support)
# hadolint ignore=DL3008
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends \
        curl=7.* \
        ffmpeg=7:* \
    ; \
    rm -rf /var/lib/apt/lists/*

# Install PDM (version pinned)
# hadolint ignore=DL3013
RUN pip install --no-cache-dir pdm==2.22.3

# Copy dependency files
COPY pyproject.toml pdm.lock* ./

# Install dependencies (production only)
RUN pdm install --prod --no-editable

# Copy application code
COPY src/ ./src/

# Set proper permissions
RUN chown -R jarvis:jarvis /app

# Switch to non-root user
USER jarvis

# Webhook port exposure
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run application
CMD ["pdm", "run", "python", "-m", "jarvis"]
