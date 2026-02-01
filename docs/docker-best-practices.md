# Docker Best Practices Applied

## Dockerfile (`Dockerfile`)

### ✅ Security
- **Non-root user**: Runs as `jarvis` user (UID 1000), not root
- **Minimal attack surface**: Uses `python:3.11-slim` base image
- **No secrets in layers**: Only copies `pyproject.toml` and `pdm.lock`, no `.env`
- **Health check**: Includes HTTP health endpoint check

### ✅ Build Optimization
- **Layer caching**: Dependencies installed before copying source code
- **Clean apt cache**: `rm -rf /var/lib/apt/lists/*` after install
- **No cache dir**: `pip install --no-cache-dir` and `pdm install` without cache
- **Single RUN**: Combined apt-get commands to reduce layers

### ✅ Maintenance
- **Version pinning**: 
  - System packages: `curl=7.*`, `ffmpeg=7:*`
  - PDM: `pdm==2.22.3`
- **Explicit syntax**: Uses `# syntax=docker/dockerfile:1`
- **Set options**: Uses `set -eux` for fail-fast and verbosity

### ✅ Runtime
- **JSON CMD**: Uses `["pdm", "run", "python", "-m", "jarvis"]` format
- **Proper signals**: JSON format allows proper signal handling
- **Port exposure**: Only exposes necessary port (8080)

## Docker Compose (`docker-compose.yml`)

### ✅ Reliability
- **Restart policy**: `unless-stopped` for automatic recovery
- **Health checks**: Both services have health checks
- **Dependency ordering**: `depends_on` with `condition: service_healthy`
- **Version pinning**: Uses `opencode:1.0.0` not `latest`

### ✅ Networking
- **Custom network**: `jarvis-network` for service isolation
- **No host networking**: All communication through Docker network
- **Named volumes**: Persistent data in named volumes

### ✅ Secrets Management
- **Environment variables**: All secrets from `.env` file
- **No hardcoded values**: No passwords/tokens in compose file
- **Default values**: Sensible defaults for non-sensitive vars

## Hadolint Compliance

The Dockerfile passes hadolint checks with ignores for:
- `DL3008`: apt-get version pinning (we use wildcards for flexibility)
- `DL3013`: pip version pinning (we pin PDM specifically)

These are acceptable because:
1. System packages use wildcard pinning (`7.*`)
2. PDM is explicitly pinned
3. Python dependencies are locked via `pdm.lock`

## Security Hardening

| Control | Status | Notes |
|---------|--------|-------|
| Non-root user | ✅ | `USER jarvis` in Dockerfile |
| No new privileges | ✅ | Default Docker security |
| Read-only root | ❌ Not implemented | Would need tmpfs for /tmp |
| Resource limits | ❌ Not implemented | Can add deploy.limits if needed |
| Capability drop | ❌ Not implemented | Not required for this use case |
| Seccomp | ❌ Not implemented | Default profile sufficient |

## Recommendations for Production

1. **Enable Docker Content Trust**: `export DOCKER_CONTENT_TRUST=1`
2. **Scan images**: Use `docker scan` or Trivy for vulnerability scanning
3. **Resource limits**: Add memory/CPU limits for resource constraints
4. **Log rotation**: Configure Docker log driver with rotation
5. **Read-only root**: Consider adding `read_only: true` with tmpfs mounts
