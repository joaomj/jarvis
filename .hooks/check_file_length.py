#!/usr/bin/env python3
"""Check Python files do not exceed 300 lines."""

from __future__ import annotations

import sys
from pathlib import Path

MAX_LINES = 300


def main() -> int:
    """Validate line-count limits for Python files passed as arguments."""
    violations: list[tuple[str, int]] = []

    for filepath in sys.argv[1:]:
        if not filepath.endswith(".py"):
            continue

        path = Path(filepath)
        try:
            with path.open(encoding="utf-8") as file_handle:
                line_count = sum(1 for _ in file_handle)
            if line_count > MAX_LINES:
                violations.append((filepath, line_count))
        except OSError as error:
            print(f"Error reading {filepath}: {error}")
            return 1

    if violations:
        print("Files exceeding 300 lines:")
        for filepath, count in violations:
            print(f"  {filepath}: {count} lines")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
