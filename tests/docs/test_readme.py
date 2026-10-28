"""P15 README professional criteria test (G15.4).

Verifies that README.md contains the required sections:
- Living status table through P14 (COMPLETE CANDIDATE)
- Note that Stage 3 is active
- Updated architecture diagram reflecting current package layout
- Direct links to test_home/P11 through P14 Hard-Stop reports
- Short measured summary (latest full-suite pass count)
- No placeholder or conversational text
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"


class TestReadmeProfessional:
    """G15.4: README meets professional criteria."""

    def test_readme_exists(self) -> None:
        assert README.exists(), "README.md must exist"

    def test_status_candidate(self) -> None:
        content = README.read_text()
        assert "CANDIDATE" in content, "README must contain STATUS: CANDIDATE"

    def test_status_table_through_p14(self) -> None:
        """Status table includes phases P1 through P14."""
        content = README.read_text()
        for phase in range(1, 15):
            assert f"P{phase}" in content, f"README must mention P{phase}"

    def test_stage_3_active_note(self) -> None:
        """README notes that Stage 3 is active."""
        content = README.read_text()
        assert "Stage 3" in content, (
            "README must mention Stage 3 is active"
        )

    def test_architecture_diagram(self) -> None:
        """README contains an architecture diagram or package layout description."""
        content = README.read_text()
        assert "aminopstwin" in content, (
            "README architecture section must reference aminopstwin package"
        )

    def test_hardstop_report_links(self) -> None:
        """README links to test_home/P11 through P14 Hard-Stop reports."""
        content = README.read_text()
        for phase in range(11, 15):
            pattern = rf"P{phase}/HARD_STOP_REPORT|test_home/P{phase}"
            assert re.search(pattern, content), (
                f"README must link to test_home/P{phase} Hard-Stop report"
            )

    def test_measured_summary(self) -> None:
        """README contains a measured summary with a pass count."""
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
