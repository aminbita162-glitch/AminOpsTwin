#!/usr/bin/env python3
"""check_skips.py — unapproved skip checker (C6).

Usage:
    python3 scripts/check_skips.py

Checks that no test uses skip or xfail without an owner-approved entry
in docs/test_exceptions.md.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).parent.parent
_EXCEPTIONS_PATH = _REPO_ROOT / "docs" / "test_exceptions.md"

_SKIP_PATTERNS = [
    re.compile(r"@pytest\.mark\.skip"),
    re.compile(r"@pytest\.mark\.xfail"),
    re.compile(r"pytest\.skip\("),
    re.compile(r"pytest\.xfail\("),
]


def _load_exceptions() -> set[str]:
    """Load approved skip/xfail entries from test_exceptions.md."""
    if not _EXCEPTIONS_PATH.exists():
        return set()
    content = _EXCEPTIONS_PATH.read_text()
    # Extract entries from the markdown — look for test IDs in backticks
    return set(re.findall(r"`([^`]+)`", content))


def _scan_test_files() -> list[tuple[str, int, str]]:
    """Scan test files for skip/xfail markers."""
    test_dir = _REPO_ROOT / "tests"
    results: list[tuple[str, int, str]] = []
    for py_file in test_dir.rglob("test_*.py"):
        for i, line in enumerate(py_file.read_text().splitlines(), 1):
            for pattern in _SKIP_PATTERNS:
                if pattern.search(line):
                    rel = str(py_file.relative_to(_REPO_ROOT))
                    results.append((rel, i, line.strip()))
    return results


def main() -> int:
    skips = _scan_test_files()
    if not skips:
        print("C6: PASS (0 unapproved skips)")
        return 0

    exceptions = _load_exceptions()
    unapproved: list[tuple[str, int, str]] = []
    for rel, line_no, line in skips:
        # Check if any exception string matches this file
        approved = any(rel in exc for exc in exceptions)
        if not approved:
            unapproved.append((rel, line_no, line))

    if unapproved:
        print(f"C6: FAIL ({len(unapproved)} unapproved skips)")
        for rel, line_no, line in unapproved:
            print(f"  {rel}:{line_no}: {line}")
        return 1

    print(f"C6: PASS ({len(skips)} skips, all approved)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
