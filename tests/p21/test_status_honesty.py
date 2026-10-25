"""P21 status honesty alignment test (G21.1).

Verifies that every phase row in the README status table matches
the actual evidence present under test_home/.  A phase may be marked
COMPLETE (CANDIDATE) only if a Hard-Stop Report exists at
test_home/P<n>/HARD_STOP_REPORT.md.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"
TEST_HOME = REPO_ROOT / "test_home"


def _extract_status_table(content: str) -> list[tuple[str, str, str]]:
    """Extract (phase, description, status) tuples from the README table."""
    rows: list[tuple[str, str, str]] = []
    for line in content.splitlines():
        line = line.strip()
        if line.startswith("| P") and "CANDIDATE" in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 3:
                rows.append((cells[0], cells[1] if len(cells) > 1 else "", cells[-1]))
    return rows


class TestStatusHonesty:
    """G21.1: every README phase row matches evidence under test_home/."""

    def test_readme_exists(self) -> None:
        assert README.exists(), "README.md must exist"

    def test_status_table_has_all_phases(self) -> None:
        """Status table includes P1 through P20."""
        content = README.read_text()
        rows = _extract_status_table(content)
        phases = {r[0] for r in rows}
        for phase_num in range(1, 21):
            assert f"P{phase_num}" in phases, (
                f"Status table must include P{phase_num}"
            )

    def test_every_candidate_phase_has_evidence(self) -> None:
        """Every phase marked COMPLETE (CANDIDATE) has a Hard-Stop Report."""
        content = README.read_text()
        rows = _extract_status_table(content)
        for phase_id, _desc, status in rows:
            if "CANDIDATE" in status:
                report_path = TEST_HOME / phase_id / "HARD_STOP_REPORT.md"
                assert report_path.exists(), (
                    f"{phase_id} is marked COMPLETE (CANDIDATE) but "
                    f"no Hard-Stop Report at {report_path}"
                )

    def test_no_phase_exceeds_evidence(self) -> None:
        """No phase in the table claims a status higher than evidence supports.

        The only allowed status vocabulary is COMPLETE (CANDIDATE) for
        phases with a Hard-Stop Report, or the absence of the row
        entirely for phases without evidence.
        """
        content = README.read_text()
        # Must not contain VERIFIED_CANDIDATE, VERIFIED, or PRODUCTION
        forbidden = [
            "VERIFIED_CANDIDATE",
            "VERIFIED",
            "PRODUCTION",
            "PRODUCTION READY",
            "CLINICALLY VALIDATED",
        ]
        for word in forbidden:
            assert word not in content, (
                f"README must not claim {word!r} — exceeds evidence"
            )

    def test_no_not_started_in_table(self) -> None:
        """No phase is marked NOT STARTED — all phases have evidence."""
        content = README.read_text()
        assert "NOT STARTED" not in content, (
            "README must not contain 'NOT STARTED' — all phases are complete"
        )

    def test_evidence_dirs_exist(self) -> None:
        """Evidence directories exist for P1 through P20."""
        for phase_num in range(1, 21):
            phase_dir = TEST_HOME / f"P{phase_num}"
            assert phase_dir.exists(), (
                f"Evidence directory missing: {phase_dir}"
            )
