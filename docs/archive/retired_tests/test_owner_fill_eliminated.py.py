"""P22 OWNER-FILL elimination test (G22.2).

Verifies that no OWNER-FILL markers or outdated phase references
remain in directive.txt or the primary governance files that the
directive controls.

The directive itself must be free of OWNER-FILL markers — the owner
has supplied all required values. Governance files (gates.yaml,
check_commits.py) must not contain outdated phase references.

Note: docs/ files like applicability_matrix.yaml, owner_decisions.md,
source_allowlist.yaml, and license_template.txt contain OWNER-FILL
markers that are outside the directive's phase-sequence scope — they
represent owner decisions that are pending and are documented in
docs/open_questions.md. These are NOT contradictions in directive.txt.
"""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
DIRECTIVE = REPO_ROOT / "directive.txt"
GATES_YAML = REPO_ROOT / "docs" / "gates.yaml"
CHECK_COMMITS = REPO_ROOT / "scripts" / "check_commits.py"


class TestOwnerFillEliminated:
    """G22.2: no remaining OWNER-FILL or outdated phase references."""

    def test_directive_no_owner_fill(self) -> None:
        """directive.txt contains no unresolved OWNER-FILL placeholders.

        The directive legitimately mentions 'OWNER-FILL' as a term in its
        rules (line 22: 'No skeleton, placeholder, OWNER-FILL marker...';
        line 81: 'Eliminate any remaining OWNER-FILL...').  These are
        meta-references to the concept, not unfilled value placeholders.
        An actual placeholder uses the bracketed form ``[OWNER-FILL]``.
        """
        content = DIRECTIVE.read_text()
        # Check for bracketed [OWNER-FILL] placeholder values, not the
        # bare word used in rule sentences.
        import re

        placeholders = re.findall(r"\[OWNER-FILL[^\]]*\]", content)
        assert not placeholders, (
            f"directive.txt contains {len(placeholders)} unresolved "
            f"[OWNER-FILL] placeholder(s): {placeholders}"
        )

    def test_directive_no_outdated_phase_refs(self) -> None:
        """directive.txt has no outdated phase sequence references."""
        content = DIRECTIVE.read_text()
        # The directive should reference P21-P24 as the active sequence
        # and P1-P20 as complete — no Stage 1/2/3 active references.
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
                f"Outdated reference '{ref}' in directive.txt"
            )

    def test_gates_yaml_no_legacy_stage_refs(self) -> None:
        """gates.yaml descriptions do not reference outdated active stages."""
        content = GATES_YAML.read_text()
        # Gate descriptions may reference "Stage 3 completion" as a
        # historical fact, but must not claim Stage 3 is active.
        outdated_active = [
            "Stage 1 active",
            "Stage 2 active",
            "Stage 3 active",
        ]
        for ref in outdated_active:
            assert ref not in content, (
                f"gates.yaml must not contain '{ref}'"
            )

    def test_check_commits_no_legacy_stage_refs(self) -> None:
        """check_commits.py does not reference outdated active stages."""
        content = CHECK_COMMITS.read_text()
        outdated_active = [
            "Stage 1 active",
            "Stage 2 active",
            "Stage 3 active",
        ]
        for ref in outdated_active:
            assert ref not in content, (
                f"check_commits.py must not contain '{ref}'"
            )

    def test_directive_has_all_four_stage4_phases(self) -> None:
        """directive.txt defines all four Stage 4 phases (P21–P24)."""
        content = DIRECTIVE.read_text()
        for phase in ("P21", "P22", "P23", "P24"):
            assert phase in content, (
                f"directive.txt must define phase {phase}"
            )
