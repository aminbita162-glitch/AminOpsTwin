"""P20 README completion test (G20.5).

Verifies that README.md reflects Stage 3 completion — every phase
P1 through P20 is marked COMPLETE (CANDIDATE) and Stage 3 is noted
as complete (no longer active).
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"


class TestReadmeCompletion:
    """G20.5: README reflects Stage 3 completion."""

    def test_readme_exists(self) -> None:
        assert README.exists(), "README.md must exist"

    def test_all_phases_through_p20(self) -> None:
        """README status table includes every phase P1 through P20."""
        content = README.read_text()
        for phase in range(1, 21):
            assert f"P{phase}" in content, (
                f"README must mention P{phase}"
            )

    def test_no_phase_marked_not_started(self) -> None:
        """No phase row in the status table says NOT STARTED."""
        content = README.read_text()
        assert "NOT STARTED" not in content, (
            "README must not contain 'NOT STARTED' — all phases are complete"
        )

    def test_stage3_complete(self) -> None:
        """README indicates Stage 3 is complete, not active."""
        content = README.read_text()
        # Must mention Stage 3
        assert "Stage 3" in content, (
            "README must mention Stage 3"
        )

    def test_measured_summary_present(self) -> None:
        """README contains a measured summary with a test pass count."""
        content = README.read_text()
        assert re.search(r"\d+\s+test", content, re.IGNORECASE), (
            "README must contain a measured summary with a test pass count"
        )

    def test_no_placeholder_text(self) -> None:
        """README contains no placeholder or TODO text."""
        content = README.read_text().lower()
        forbidden = ["todo", "placeholder", "lorem ipsum", "tbd", "fixme"]
        for word in forbidden:
            assert word not in content, (
                f"README must not contain placeholder text: {word!r}"
            )

    def test_no_conversational_text(self) -> None:
        """README contains no conversational or private-instruction text."""
        content = README.read_text().lower()
        forbidden = ["as discussed", "as you requested", "here is", "i'll"]
        for phrase in forbidden:
            assert phrase not in content, (
                f"README must not contain conversational text: {phrase!r}"
            )

    def test_claim_links_present(self) -> None:
        """README contains at least one claim-id reference."""
        content = README.read_text()
        assert re.search(r"CLAIM-\d+", content), (
            "README must contain claim-id references"
        )

    def test_email_present(self) -> None:
        """README contains the author email."""
        content = README.read_text()
        assert "azimilab2025@gmail.com" in content, (
            "README must contain the author email azimilab2025@gmail.com"
        )

    def test_status_candidate(self) -> None:
        """README contains STATUS: CANDIDATE."""
        content = README.read_text()
        assert "CANDIDATE" in content, (
            "README must contain STATUS: CANDIDATE"
        )
