"""P23 lockfile CI check (G23.1).

Verifies that a lockfile exists, is committed, and is checked in CI
via ``uv lock --check``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
UV_LOCK = REPO_ROOT / "uv.lock"
CI_YML = REPO_ROOT / ".github" / "workflows" / "ci.yml"


class TestLockfileCI:
    """G23.1: lockfile exists and is checked in CI."""

    def test_lockfile_exists(self) -> None:
        """uv.lock exists in the repository root."""
        assert UV_LOCK.exists(), "uv.lock must exist in the repository root"

    def test_lockfile_nonempty(self) -> None:
        """uv.lock is non-empty."""
        assert UV_LOCK.exists(), "uv.lock must exist"
        assert UV_LOCK.stat().st_size > 0, "uv.lock must not be empty"

    def test_lockfile_not_in_gitignore(self) -> None:
        """uv.lock is NOT in .gitignore (it must be committed)."""
        gitignore = REPO_ROOT / ".gitignore"
        if not gitignore.exists():
            return
        content = gitignore.read_text()
        # Check that uv.lock is not ignored — it must be tracked.
        for line in content.splitlines():
            stripped = line.strip()
            if stripped == "uv.lock" or stripped == "/uv.lock":
                raise AssertionError(
                    f"uv.lock must not be in .gitignore (found: {stripped!r})"
                )

    def test_ci_has_lock_check(self) -> None:
        """CI workflow includes a ``uv lock --check`` step."""
        assert CI_YML.exists(), ".github/workflows/ci.yml must exist"
        content = CI_YML.read_text()
        assert "uv lock" in content, (
            "CI workflow must include a uv lock check step"
        )
        assert "--check" in content, (
            "CI workflow must include 'uv lock --check' to verify lockfile freshness"
        )

    def test_ci_lock_check_is_a_step(self) -> None:
        """The uv lock --check appears as a named step in the CI workflow."""
        assert CI_YML.exists(), "ci.yml must exist"
        content = CI_YML.read_text()
        # The lock check must be inside a job step, not just a comment.
        # We look for a step name containing "lock" and the command.
        lock_check_pattern = re.compile(
            r"uv lock --check", re.MULTILINE
        )
        assert lock_check_pattern.search(content), (
            "CI workflow must contain 'uv lock --check' as a step"
        )
