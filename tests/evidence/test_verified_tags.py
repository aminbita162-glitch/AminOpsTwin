"""Tests for verified tags P11-verified through P14-verified (G14.3).

Verifies that the tags P11-verified, P12-verified, P13-verified,
and P14-verified exist in the repository.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent

REQUIRED_TAGS = [
    "P11-verified",
    "P12-verified",
    "P13-verified",
    "P14-verified",
]


def list_tags() -> list[str]:
    """List all git tags."""
    result = subprocess.run(
        ["git", "tag", "-l"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        check=True,
    )
    return [t.strip() for t in result.stdout.strip().split("\n") if t.strip()]


class TestVerifiedTags:
    """G14.3: tags P11-verified through P14-verified exist."""

    def test_all_verified_tags_exist(self) -> None:
        tags = set(list_tags())
        for tag in REQUIRED_TAGS:
            assert tag in tags, (
                f"required tag '{tag}' not found in git tags"
            )

    def test_p11_verified_exists(self) -> None:
        tags = set(list_tags())
        assert "P11-verified" in tags

    def test_p12_verified_exists(self) -> None:
        tags = set(list_tags())
        assert "P12-verified" in tags

    def test_p13_verified_exists(self) -> None:
        tags = set(list_tags())
        assert "P13-verified" in tags

    def test_p14_verified_exists(self) -> None:
        tags = set(list_tags())
        assert "P14-verified" in tags
