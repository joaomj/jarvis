# Deployment Guide

Instructions for running Jarvis in production and development environments.

## Production Deployment

### Environment

- **Host**: Mac Mini M4 (16GB RAM) or similar
- **Container Runtime**: Docker or Orbstack
- **Network**: Polling only (no public ports)
- **Storage**: Local SQLite database in `vault/index/` directory

### Quick Deploy

```bash
# Clone repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Configure environment
cp .env.example .env
# Edit .env with your tokens

# Start container
docker compose up -d

# View logs
docker compose logs -f
```

### Monitoring

- **Health Check**: Container health status
- **Logs**: Structured JSON logs with correlation IDs
- **Metrics**: Sync status, query performance, error rates

### Backups

- **Database**: Backup `vault/index/jarvis.db` regularly
- **Config**: Backup `.env` file (contains secrets)
- **Models**: Backup `vault/index/favorite_models.json`

## Development Setup

### Install Dependencies

```bash
pdm install
```

### Run Locally

```bash
# Terminal A: Start OpenCode server
./scripts/start-opencode.sh

# Terminal B: Start Jarvis
pdm run python -m jarvis
```

Or use Docker for Jarvis:

```bash
docker compose up -d jarvis
```

### Run Tests

```bash
# All tests
pdm run pytest

# Specific test file
pdm run pytest tests/test_bookmark_client_sync.py -v

# With coverage
pdm run pytest --cov=src/jarvis --cov-report=term-missing

# PR gate tiers
pdm run pytest -m "fast or integration"

# Real OpenCode smoke tests
JARVIS_ENABLE_E2E_OPENCODE=1 \
JARVIS_E2E_OPENCODE_URL=http://localhost:4096 \
JARVIS_E2E_OPENCODE_PASSWORD=your_password \
pdm run pytest -m e2e_opencode
```

### Lint

```bash
# Check code
pdm run ruff check .

# Format code
pdm run ruff format .
```

## Local Run (OpenCode local + Jarvis Docker)

This is the recommended setup:

```bash
# 1) Start OpenCode server on host
./scripts/start-opencode.sh

# 2) Start Jarvis in Docker
docker compose up -d jarvis

# 3) Follow Jarvis logs
docker logs -f jarvis
```

To stop:

```bash
docker compose stop jarvis
```
