# AGENTS.md: Development Guidelines

## 1) Core Principles

* Consistency over novelty: follow existing patterns; don't add tools or frameworks unless they already exist in the repo or the user approves.
* More code = larger error surface.
* Simplicity first: prefer the fewest moving parts that satisfy requirements.
* No assumptions: verify dependencies, versions, and APIs against the codebase or docs; ask the user if not sure.
* Transparency: explain the rationale behind changes and architectural decisions.
* Security by default: never expose or persist secrets.
* INVESTIGATE and PLAN FIRST, without changing anything. Ask the user for permission BEFORE changing anything.
* Proactive investigation: thoroughly investigate the codebase and web documentation before asking questions.

## 2) Plan-Then-Execute Lifecycle

You must always plan before writing code:

1. **Workspace analysis**: scan docs/tech-context.md, pyproject.toml, repo structure, dependencies, and entry points. If docs feel stale, validate against code.
2. **Questions for the user**: list targeted questions to remove ambiguity. Interview the user in detail about technical implementation, UI & UX, concerns, tradeoffs. Continue until complete, then write the spec to the file.
3. **Action plan**: propose a step-by-step implementation plan with expected file changes and impacts. Be detailed.
4. **Approval gate**: wait for explicit user approval to proceed.
5. **Execute**: only after approval, implement changes incrementally.

Notes:
- Do not write any code before the approval gate
- Justify each file modification BEFORE writing
- Update docs/tech-context.md whenever architecture or design changes

## 3) Operating Constraints

* Python: use PDM for running python scripts and managing pyproject.toml. Commands: pdm add <package>, pdm remove <package>, pdm run <command>, pdm lock.
* Secrets: store in .env with chmod 600. Never commit secrets.
* Destructive commands: use --dry-run first, explain before running.
* Respect user changes: never override without explicit approval.

## 4) Coding Standards

* Language: write code, comments, and docs 100% in English.
* Idiomatic style: conform to local imports, naming, and formatting (PEP 8 for Python: snake_case vars/functions, PascalCase classes, UPPER_SNAKE_CASE constants).
* Readability: prefer clear, maintainable solutions over cleverness.
* Modularity: single-responsibility modules; keep code files under 300 lines.
* Async: use async/await consistently; use asyncio.gather() for concurrent operations.
* Error handling: provide observability; use Result objects for expected failures, exceptions for true exceptions only.
* Logging: never log secrets; use structured logging.
* Comments: explain intent (the "why"), not obvious mechanics.
* Grep: use for finding code words, TODO comments, function definitions.

## 5) Development Workflow

**Feature Development:**
1. Investigate existing codebase
2. Review documentation
3. Ask clarifying questions
4. Create detailed action plan
5. Get user approval
6. Implement incrementally
7. Add/update tests
8. Run lint: pdm run ruff check
9. Run tests: pdm run pytest
10. Update documentation
11. Manual verification

**Bug Fix:**
1. Reproduce the issue
2. Add failing test case
3. Identify root cause
4. Implement fix
5. Verify test passes
6. Check for regressions

**Dependency Management:**
- pdm list: check versions
- pdm add/remove: manage deps
- pdm audit: check vulnerabilities

## 6) Testing Policy

* No mocks: prefer end-to-end tests as close to the final user experience.
* Always run tests: pdm run pytest for all tests; pdm run pytest --cov=src for coverage.
* Test organization: tests/unit/, tests/integration/, tests/e2e/
* Async tests: use @pytest.mark.asyncio decorator.
* Test naming: test_<function>_<expected_behavior>
* Target: 80%+ coverage for critical paths.
* Server code warning: background servers may block execution; use timeouts and cleanup.

## 7) Debugging & Troubleshooting

* Debug logging: export LOG_LEVEL=DEBUG
* Log analysis: grep -i "error\|exception" app.log, tail -f app.log
* Performance: pdm run python -m cProfile -o profile.stats script.py, pdm run python -m memory_profiler script.py
* Common issues: lsof -i :PORT for port conflicts, pdm graph for dependency conflicts.

## 8) Documentation Rules

* Source of truth: docs/tech-context.md for architecture, flows, tooling, and key decisions; validate with code.
* README: external-facing overview and setup.
* CHANGELOG.md: keep up to date with all changes, releases, and features, following Keep a Changelog format.
* Issue tracking: create markdown file per issue in docs/issues/ with sections: description, context, date, impact, investigation, resolution, status.
* Docstrings: Google style, explain args, returns, raises, examples.
* Update docs: after completing tasks, update docs/, tech-context.md, README.md, CHANGELOG.md, and project structure chart.
* Write ASCII charts for state machine diagrams, mapping out all paths and flows.

## 9) Security Best Practices

* Secrets: use pydantic-settings with .env file; sanitize logs; never log secrets.
* Input validation: use Pydantic models with validators.
* Output sanitization: remove sensitive keys from logs.
* Dependency audit: pdm audit for vulnerabilities.
* Security review: no secrets in code/logs, input validation, output sanitization, rate limiting.

## 10) Performance Guidelines

* Async optimization: use asyncio.gather() for concurrent operations over sequential awaits.
* Caching: use @lru_cache for expensive functions.
* Database: use JOINs to avoid N+1 queries; add indexes.
* Memory: use generators for large data; process in chunks.
* Profiling: python -m cProfile for CPU, python -m memory_profiler for memory.

## 11) Git & Version Control

* Branch naming: feature/<name>, bugfix/<name>, hotfix/<name>, docs/<name>, refactor/<name>
* Commit messages: <type>(<scope>): <subject>. Types: feat, fix, docs, style, refactor, test, chore.
* Merge: use --no-ff to preserve history; use --squash for feature branches.
* Code review: check conventions, tests, docs, no secrets, no debug code, lint passes, tests pass.
* Release: update version in pyproject.toml, update CHANGELOG.md, tag vX.Y.Z.
* Common commands: git status, git diff, git add, git commit, git checkout -b, git merge, git push, git pull.
