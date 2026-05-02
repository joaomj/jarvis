FROM python:3.12-slim AS builder

WORKDIR /build

RUN pip install --no-cache-dir uv

COPY pyproject.toml uv.lock README.md ./
COPY src/ ./src/

RUN uv sync --no-dev --no-editable

FROM python:3.12-slim AS runtime

RUN groupadd -r -g 1000 jarvis && \
    useradd -r -g jarvis -u 1000 -d /app jarvis

WORKDIR /app

COPY --from=builder /build/.venv .venv
COPY --chown=jarvis:jarvis src/ ./src/
COPY --chown=jarvis:jarvis skills/ ./skills/

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONPATH="/app" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

USER jarvis

HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD python -c "import sys; sys.exit(0)" || exit 1

CMD ["python", "-m", "src.bot"]
