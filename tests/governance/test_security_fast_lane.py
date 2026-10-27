"""P23 security fast-lane process documentation check (G23.4).

Verifies that a security fast-lane process for patch-level updates
is documented. The documentation lives in
``docs/security_fast_lane.md``.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
FAST_LANE_DOC = REPO_ROOT / "docs" / "security_fast_lane.md"


class TestSecurityFastLane:
    """G23.4: security fast-lane process documented for patch-level updates."""

    def test_fast_lane_doc_exists(self) -> None:
        """``docs/security_fast_lane.md`` exists."""
        assert FAST_LANE_DOC.exists(), (
            "docs/security_fast_lane.md must exist"
        )

    def test_doc_contains_patch_level_process(self) -> None:
        """The fast-lane doc describes a patch-level update process."""
        content = FAST_LANE_DOC.read_text()
        assert "patch" in content.lower(), (
            "Security fast-lane doc must describe patch-level updates"
        )

    def test_doc_contains_steps(self) -> None:
        """The fast-lane doc contains numbered or bulleted steps."""
        content = FAST_LANE_DOC.read_text()
        # Must have at least 3 step-like entries (numbered or bulleted)
        steps = re.findall(r"^\s*(?:\d+\.|-|\*)\s+", content, re.MULTILINE)
        assert len(steps) >= 3, (
            f"Security fast-lane doc must contain at least 3 steps, "
            f"found {len(steps)}"
        )

    def test_doc_references_pip_audit(self) -> None:
        """The fast-lane doc references pip-audit for dependency checks."""
        content = FAST_LANE_DOC.read_text()
        assert "pip-audit" in content, (
            "Security fast-lane doc must reference pip-audit"
        )

    def test_doc_references_uv_lock(self) -> None:
        """The fast-lane doc references uv lock for lockfile updates."""
        content = FAST_LANE_DOC.read_text()
        assert "uv lock" in content, (
            "Security fast-lane doc must reference uv lock for lockfile updates"
        )

    def test_doc_references_gitleaks(self) -> None:
        """The fast-lane doc references gitleaks for secrets scanning."""
        content = FAST_LANE_DOC.read_text()
        assert "gitleaks" in content, (
            "Security fast-lane doc must reference gitleaks"
        )

    def test_doc_has_scope_section(self) -> None:
        """The fast-lane doc has a scope section defining what qualifies."""
        content = FAST_LANE_DOC.read_text()
        assert "scope" in content.lower(), (
            "Security fast-lane doc must define its scope"
        )
