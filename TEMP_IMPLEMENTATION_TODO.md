# Jarvis Build Plan (Temporary)

## Phase 1 - CI Pipeline (GitHub Actions)
- [ ] Add `.github/workflows/ci.yml` for push/PR checks.
- [ ] Run on Python 3.11 and 3.12.
- [ ] Verify: `pdm install -G dev`, `pdm run ruff check .`, `pdm run ruff format --check .`, `pdm run pytest`.
- [ ] Verify security/lint checks via pre-commit hooks: `gitleaks`, `hadolint`.

Gate 1 (pass/fail)
- Pass when workflow exists, local CI-equivalent commands pass, and commit is created.

## Phase 2 - OpenCode Event Mode Plumbing (Python)
- [ ] Add SSE subscription support to OpenCode client using `/event`.
- [ ] Add async prompt support using `/session/{sessionID}/prompt_async`.
- [ ] Add API wrappers for question reply/reject and permission reply.
- [ ] Add unit tests for SSE parsing and event decoding.

Gate 2 (pass/fail)
- Pass when unit tests for new client/event plumbing pass and commit is created.

## Phase 3 - Event-Driven Response Delivery
- [ ] Add event aggregator to assemble message/tool updates.
- [ ] Switch bot flow to fire-and-forget prompt + event-driven output delivery.
- [ ] Ensure polling loop remains responsive while long tasks run.

Gate 3 (pass/fail)
- Pass when tests pass and manual verification path is in place (no blocked callbacks during long tasks), then commit.

## Phase 4 - UX Enhancements
- [ ] Add interaction guard/state machine for question/permission flows.
- [ ] Add pinned status message (session, model/agent, context, changed files).
- [ ] Update pinned status from event stream with debounced edits.

Gate 4 (pass/fail)
- Pass when tests pass, new UX flows are wired end-to-end, and commit is created.

## Finalization
- [ ] Run `ruff check` + `pytest`.
- [ ] Run `doc-maintenance` skill and apply any doc cleanup needed.
