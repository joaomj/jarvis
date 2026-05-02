"""Shared fixtures for integration-style tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def tmp_db_path(tmp_path: Path) -> str:
    """Provide a temporary database path."""
    return str(tmp_path / "test.db")


def pytest_collection_modifyitems(items: list[pytest.Item]) -> None:
    """Assign default `fast` marker for tests without explicit speed tier."""
    for item in items:
        has_explicit_tier = any(
            marker in item.keywords for marker in ("fast", "integration")
        )
        if not has_explicit_tier:
            item.add_marker(pytest.mark.fast)
