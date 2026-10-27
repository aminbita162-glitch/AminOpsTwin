"""P21 cinematic README rewrite test (G21.2).

Verifies that README.md contains all mandatory sections specified in
the P21 directive (deliverable 2a–2h) with clear visual hierarchy:
  a. Centered header panel (project name, one-sentence mission, stage status)
  b. Living phase status table (Phase | Status | Evidence links)
  c. Non-negotiable invariants table (Principle | Enforcement | Verification)
  d. High-level system flow diagram in clean text blocks
  e. Contaminated Context Control section with deny-path diagram
  f. Maturity ladder (Model → Shadow → Twin) — currently at Model stage
  g. Measured summary with numbers from latest full regression
  h. Safety boundaries paragraph
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"


class TestReadmeCinematic:
    """G21.2: cinematic README rewrite with all mandatory sections."""

    def test_readme_exists(self) -> None:
        assert README.exists(), "README.md must exist"

    # (a) Centered header panel

    def test_header_panel(self) -> None:
        """README has a centered header with project name, mission, status."""
        content = README.read_text()
        assert "AminOpsTwin" in content, (
            "Header must contain project name"
        )
        assert "CANDIDATE" in content, (
            "Header must contain stage status (CANDIDATE)"
        )

    def test_one_sentence_mission(self) -> None:
        """README contains a one-sentence mission statement."""
        content = README.read_text()
        assert "operational" in content.lower(), (
            "Mission must describe the operational nature of the system"
        )
        assert "clinical research" in content.lower(), (
            "Mission must reference clinical research operations"
        )

    # (b) Living phase status table with Evidence links

    def test_status_table_with_evidence_links(self) -> None:
        """Status table has Phase | Level | Evidence columns linking to evidence."""
        content = README.read_text()
        # Table must have Phase | Level | Evidence columns
        assert re.search(r"\|.*Phase.*\|.*Level.*\|.*Evidence.*\|", content), (
            "Status table must have Phase | Level | Evidence columns"
        )
        # Must link to test_home evidence
        assert re.search(r"test_home/P\d+", content), (
            "Status table must link to test_home/P<n> evidence"
        )

    # (c) Non-negotiable invariants table

    def test_invariants_table(self) -> None:
        """README contains a non-negotiable invariants table."""
        content = README.read_text()
        assert re.search(
            r"\|.*Principle.*\|.*Enforcement.*\|.*Verification.*\|",
            content,
        ), (
            "Invariants table must have Principle | Enforcement | Verification columns"
        )

    # (d) High-level system flow diagram

    def test_system_flow_diagram(self) -> None:
        """README contains a system flow diagram in text blocks."""
        content = README.read_text()
        # Must contain an ASCII/text block diagram
        assert "Gateway" in content, (
            "Flow diagram must reference the Gateway"
        )
        assert "Executor" in content, (
            "Flow diagram must reference the Executor"
        )
        # Must contain a code block with diagram-like content
        assert "```" in content, (
            "README must contain at least one code block (diagram)"
        )

    # (e) Contaminated Context Control section

    def test_contaminated_context_control(self) -> None:
        """README has a Contaminated Context Control section with deny-path diagram."""
        content = README.read_text()
        assert re.search(r"contaminated.*context", content, re.IGNORECASE), (
            "README must have a Contaminated Context Control section"
        )
        # Must contain a deny-path diagram or description
        assert "deny" in content.lower(), (
            "Contaminated Context Control must reference the deny path"
        )

    # (f) Maturity ladder

    def test_maturity_ladder(self) -> None:
        """README contains a maturity ladder (Model → Shadow → Twin)."""
        content = README.read_text()
        assert "Model" in content, (
            "Maturity ladder must mention Model stage"
        )
        assert "Shadow" in content, (
            "Maturity ladder must mention Shadow stage"
        )
        assert "Twin" in content, (
            "Maturity ladder must mention Twin stage"
        )

    def test_currently_at_model_stage(self) -> None:
        """Maturity ladder states the system is currently at the Model stage."""
        content = README.read_text().lower()
        assert "model" in content and (
            "currently at" in content or "current stage" in content
            or "at the model" in content or "model stage" in content
        ), (
            "Maturity ladder must state the system is currently at the Model stage"
        )

    # (g) Measured summary

    def test_measured_summary_with_numbers(self) -> None:
        """README contains a measured summary with numbers from latest regression."""
        content = README.read_text()
        assert re.search(r"\d+\s+test", content, re.IGNORECASE), (
            "Measured summary must contain a test pass count"
        )

    # (h) Safety boundaries paragraph

    def test_safety_boundaries(self) -> None:
        """README contains a safety boundaries paragraph."""
        content = README.read_text()
        assert re.search(r"safet|boundar", content, re.IGNORECASE), (
            "README must contain a safety boundaries paragraph"
        )

    # Cross-cutting checks

    def test_all_dates_are_month_and_year(self) -> None:
        """All dates in README are written as month and year only."""
        content = README.read_text()
        # Must not contain full ISO dates (YYYY-MM-DD)
        assert not re.search(r"\d{4}-\d{2}-\d{2}", content), (
            "README must not contain full ISO dates (YYYY-MM-DD) — "
            "use month and year only"
        )

    def test_no_marketing_language(self) -> None:
        """README contains no marketing language."""
        content = README.read_text().lower()
        forbidden = [
            "best-in-class",
            "world-class",
            "industry-leading",
            "cutting-edge",
            "revolutionary",
            "game-changing",
            "next-generation",
            "best practices",
        ]
        for word in forbidden:
            assert word not in content, (
                f"README must not contain marketing language: {word!r}"
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

    def test_no_owner_agent_dialogue(self) -> None:
        """README contains no owner-agent dialogue text."""
        content = README.read_text().lower()
        assert "owner has instructed" not in content, (
            "README must not contain owner-agent dialogue text"
        )
        assert "awaiting owner" not in content, (
            "README must not contain owner-agent dialogue text"
        )

    def test_claim_links_present(self) -> None:
        """All public claims link to claim-ids."""
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

    def test_hardstop_report_links_through_p20(self) -> None:
        """README links to test_home/P1 through P20 Hard-Stop reports."""
        content = README.read_text()
        for phase in range(1, 21):
            pattern = rf"P{phase}/HARD_STOP_REPORT|test_home/P{phase}"
            assert re.search(pattern, content), (
                f"README must reference test_home/P{phase}"
            )
