# Jarvis - Personal AI System

A self-hosted, sovereign personal AI assistant running on local hardware, accessible via Telegram.

**Status:** 🚧 Under Active Development

**Version:** 0.1.0 (MVP in Progress)

---

## Overview

Jarvis is a "Second Brain" that helps you:

- **Retrieve personal memories** from a local filesystem you control
- **Generate grounded answers** with real-time web data and academic citations
- **Process documents** (PDF, DOCX, text, code) as conversation context
- **Create research reports** (8-15 pages) with deep academic sources

**Key Features:**

- Three conversation modes: Fast (quick answers), Thinking (deep reasoning), Deep Research (academic reports)
- All responses include source citations using academic footnote conventions
- Memories stored as plain Markdown files (portable, queryable, sovereign)
- Secure: 4-layer defense with Cloudflare Tunnel, no open ports
- Local-first with automated cloud backup (Google Drive API)
- Comprehensive observability (logs, metrics, health checks)

---

## Quick Start

### Prerequisites

- macOS (Mac Mini M4/M2 recommended)
- Python 3.12+
- PDM (Python package manager)
- Docker (optional, for containerized deployment)
- Telegram account
- Google Cloud account (for Gemini API)

### Installation

```bash
# Clone repository
git clone https://github.com/yourusername/jarvis.git
cd jarvis

# Install dependencies
pdm install

# Create environment file
cp .env.example .env

# Edit .env with your credentials
nano .env  # Fill in TELEGRAM_BOT_TOKEN, GEMINI_API_KEY, etc.

# Set permissions on .env
chmod 600 .env

# Run application
pdm run uvicorn src.jarvis.main:app --host 0.0.0.0 --port 8000
```

### Docker Deployment

```bash
# Build and run with Docker Compose
docker-compose up -d

# Check health
curl http://localhost:8000/health
```

---

## Documentation

- **[PRDv2.md](docs/PRDv2.md)** - Complete Product Requirements Document (v2.1)
- **[tech-context.md](docs/tech-context.md)** - Architecture and technical design
- **[AGENTS.md](AGENTS.md)** - Development guidelines and coding standards
- **[.env.example](.env.example)** - Environment variables template

---

## Project Structure

```
jarvis/
├── .env.example              # Environment variables template
├── .gitignore               # Git ignore rules
├── pyproject.toml           # PDM configuration and dependencies
├── README.md                # This file
│
├── src/jarvis/             # Application source code
│   ├── main.py             # FastAPI entry point
│   ├── config.py           # Pydantic Settings
│   ├── agents/             # PydanticAI agents
│   ├── tools/              # Agent tools (memory, web, files)
│   ├── citation/           # Citation management
│   ├── reports/            # Report generation
│   ├── context/            # Session management
│   ├── security/           # Security middleware
│   └── telegram/           # Telegram integration
│
├── memories/               # Personal knowledge (Markdown)
│   ├── conversations/      # Conversation histories
│   ├── facts/             # Personal facts and preferences
│   └── entities/          # People, projects, locations
│
├── reports/                # Generated research reports (PDF)
├── tests/                  # Test suites
├── docs/                   # Documentation
│   ├── tech-context.md     # Architecture (source of truth)
│   ├── issues/            # Issue tracking
│   └── PRDv2.md          # Product requirements
│
└── AGENTS.md               # Development guidelines
```

---

## Development

### Setup Development Environment

```bash
# Install PDM (if not already installed)
pip install pdm

# Install project dependencies
pdm install

# Install dev dependencies
pdm install -d
```

### Running Tests

```bash
# Run all tests
pdm run pytest

# Run with coverage
pdm run pytest --cov=src

# Run specific test file
pdm run pytest tests/unit/test_memory.py
```

### Linting and Formatting

```bash
# Check code style
pdm run ruff check

# Format code automatically
pdm run ruff format
```

### Type Checking (Optional)

```bash
pdm run mypy src/
```

---

## Deployment

### Production Checklist

Before deploying to production, ensure:

- [ ] All security items in PRDv2.md Section 9 are completed
- [ ] FileVault enabled on Mac Mini
- [ ] macOS Firewall enabled (stealth mode)
- [ ] `.env` has `chmod 600` permissions
- [ ] Cloudflare Tunnel configured with WAF rules
- [ ] Google Drive API backup configured and tested
- [ ] All tests pass: `pdm run pytest`
- [ ] Linting passes: `pdm run ruff check`
- [ ] Health check endpoint returns healthy status

### Cloudflare Tunnel Setup

```bash
# Install cloudflared
brew install cloudflared

# Create named tunnel
cloudflared tunnel create jarvis

# Configure tunnel (edit config file)
nano ~/.cloudflared/config.yml

# Run tunnel
cloudflared tunnel run jarvis
```

For detailed setup, see PRDv2.md Section 9.

---

## Monitoring

### Health Check

```bash
curl http://localhost:8000/health
```

Expected response:
```json
{
  "status": "healthy",
  "timestamp": "2026-01-18T10:30:00Z",
  "version": "0.1.0",
  "dependencies": {
    "gemini_api": "healthy",
    "arxiv_api": "healthy",
    "database": "healthy"
  }
}
```

### Metrics

```bash
# View Prometheus metrics
curl http://localhost:8000/metrics

# View cost tracking
curl http://localhost:8000/metrics/cost
```

### Logs

```bash
# Tail logs in real-time
tail -f jarvis.log

# Filter by error level
grep -i "ERROR" jarvis.log
```

---

## Troubleshooting

### Common Issues

**Issue: Telegram webhook not receiving messages**
- Check Cloudflare Tunnel status: `cloudflared tunnel info`
- Verify WAF rules allow Telegram IPs
- Check webhook secret in `.env`

**Issue: API quota exceeded**
- Check Gemini API usage in Google Cloud Console
- Wait for quota reset or upgrade plan
- Monitor costs: `curl http://localhost:8000/metrics/cost`

**Issue: Jobs stuck in `in_progress` status**
- Restart service to reset jobs
- Check logs for errors: `grep "ERROR" jarvis.log`
- Manual retry via API: `POST /jobs/<id>/retry`

For full troubleshooting guide, see PRDv2.md Section 18 (Operational Runbook).

---

## Roadmap

### MVP (Current)

- [x] PRD and architecture design
- [x] Environment setup
- [ ] FastAPI skeleton and webhook
- [ ] Router agent and mode selection
- [ ] Chat Fast and Chat Thinking agents
- [ ] Memory system with extraction
- [ ] Deep research pipeline
- [ ] Testing and polish
- [ ] Docker and CI/CD

### Post-MVP

- [ ] Voice input (Whisper/Gemini audio)
- [ ] Anna's Archive integration
- [ ] Feedback system (thumbs up/down)
- [ ] Multi-user support (optional)
- [ ] Advanced citation export (BibTeX)
- [ ] Memory visualization (graphs)
- [ ] Calendar integration

---

## Contributing

This is a personal project, but contributions are welcome!

### Development Workflow

1. Create feature branch: `git checkout -b feature/your-feature`
2. Make changes and commit: `git commit -m "feat: add your feature"`
3. Push and create PR: `git push origin feature/your-feature`
4. CI/CD will run tests and linting automatically

### Coding Standards

Follow guidelines in [AGENTS.md](AGENTS.md):
- PEP 8 style
- Type hints where possible
- Async/await for I/O operations
- Result objects for expected failures
- Never log secrets

---

## License

MIT License - See LICENSE file for details

---

## Acknowledgments

Inspired by:
- [agentfs](https://github.com/tursodatabase/agentfs) - Filesystem as agent context
- [gpt-researcher](https://github.com/assafelovic/gpt-researcher) - Open source research agent
- [Elicit Reports](https://elicit.com/blog/introducing-elicit-reports) - Gold standard for deep research

---

## Support

For issues, questions, or feature requests:
- Create an issue in [docs/issues/](docs/issues/) (local issue tracking)
- Check [PRDv2.md](docs/PRDv2.md) for requirements
- Check [tech-context.md](docs/tech-context.md) for architecture

---

**Built with ❤️ for personal sovereignty and AI transparency**
