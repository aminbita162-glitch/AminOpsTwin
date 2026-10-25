"""P22 directive consistency test (G22.1).

Verifies that directive.txt has no internal contradictions:
  - Single active phase sequence (P21–P24)
  - Single status vocabulary (COMPLETE (CANDIDATE), EXECUTION CANDIDATE)
  - No outdated phase references (Stage 1/2/3 active, P1–P10 active, etc.)
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DIRECTIVE = REPO_ROOT / "directive.txt"


class TestDirectiveConsistency:
    """G22.1: directive.txt has no internal contradictions."""

    def test_directive_exists(self) -> None:
        assert DIRECTIVE.exists(), "directive.txt must exist"

    def test_single_active_phase_sequence(self) -> None:
        """directive.txt declares exactly one active phase sequence."""
        content = DIRECTIVE.read_text()
        assert "P21 THROUGH P24" in content, (
            "Active phase sequence must be P21 THROUGH P24"
        )
        # Count SOLE ACTIVE PHASE SEQUENCE declarations
        matches = re.findall(
            r"SOLE ACTIVE PHASE SEQUENCE", content, re.IGNORECASE
        )
        assert len(matches) == 1, (
            f"Expected exactly 1 'SOLE ACTIVE PHASE SEQUENCE' declaration, "
            f"found {len(matches)}"
        )

    def test_p1_through_p20_complete(self) -> None:
        """directive.txt states P1 through P20 are COMPLETE (CANDIDATE)."""
        content = DIRECTIVE.read_text()
        assert "P1 through P20 are COMPLETE (CANDIDATE)" in content, (
            "P1 through P20 must be marked COMPLETE (CANDIDATE)"
        )

    def test_status_vocabulary(self) -> None:
        """directive.txt uses a single consistent status vocabulary."""
        content = DIRECTIVE.read_text()
        status_match = re.search(r"^STATUS:\s*(.+)$", content, re.MULTILINE)
        assert status_match is not None, "STATUS: line must exist"
        status_val = status_match.group(1).strip()
        assert status_val in ("EXECUTION CANDIDATE", "COMPLETE (CANDIDATE)"), (
            f"Status '{status_val}' must be in valid vocabulary"
        )

    def test_no_outdated_stage_references(self) -> None:
        """directive.txt has no outdated Stage 1/2/3 active references."""
        content = DIRECTIVE.read_text()
        outdated = [
            "Stage 1 active",
            "Stage 2 active",
            "Stage 3 active",
            "stage 1 active",
            "stage 2 active",
            "stage 3 active",
        ]
        for ref in outdated:
            assert ref not in content, (
                f"Outdated reference '{ref}' must not appear in directive.txt"
            )

    def test_no_outdated_phase_active_refs(self) -> None:
        """directive.txt has no outdated P1-P10/P11-P14/P15-P20 active refs."""
        content = DIRECTIVE.read_text()
        outdated = [
            "P1–P10 active",
            "P1-P10 active",
            "P11–P14 active",
            "P11-P14 active",
            "P15–P20 active",
            "P15-P20 active",
        ]
        for ref in outdated:
            assert ref not in content, (
                f"Outdated reference '{ref}' must not appear in directive.txt"
            )

    def test_consistency_script_passes(self) -> None:
        """The consistency check script passes."""
        import subprocess
        import sys

        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "scripts" / "check_directive_consistency.py"),
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0, (
            f"Consistency check failed:\n{result.stdout}\n{result.stderr}"
        )
