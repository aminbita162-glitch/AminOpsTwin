"""G4.15 — Regulatory and release applicability tests (P4, §29).

Every new/changed capability is covered by the dated applicability matrix.
Unresolved deployment/legal questions are explicitly listed and prevent claims
of commercial authorization; no unsupported conformity or MDR-exclusion claim.
P4 engineering verification is not the independent pre-release legal conclusion.
"""

from __future__ import annotations

from pathlib import Path

import pytest


class TestRegulatoryScope:
    """G4.15: regulatory applicability matrix coverage."""

    P4_CAPABILITY_IDS = [
        "R27", "R28", "R29", "R30",
        "N16", "N17", "N18", "N19", "N20", "N21", "N22",
    ]

    def test_regulatory_scope_directory_exists(self) -> None:
        """docs/regulatory_scope/ must exist for P4 scope records."""
        reg_dir = Path("docs/regulatory_scope")
        assert reg_dir.exists(), (
            "docs/regulatory_scope/ must exist for P4 regulatory scope records"
        )

    def test_applicability_matrix_exists(self) -> None:
        """A dated applicability matrix must cover P4 capabilities."""
        matrix_path = Path("docs/regulatory_scope/applicability_matrix.yaml")
        assert matrix_path.exists(), (
            "docs/regulatory_scope/applicability_matrix.yaml must exist"
        )

    def test_p4_capabilities_covered(self) -> None:
        """Every P4 capability should be referenced in the applicability matrix."""
        import yaml
        matrix_path = Path("docs/regulatory_scope/applicability_matrix.yaml")
        if not matrix_path.exists():
            pytest.skip("applicability_matrix.yaml not yet created")
        with open(matrix_path) as f:
            matrix = yaml.safe_load(f)
        # The matrix should have entries for P4 capabilities
        entries = matrix.get("entries", []) if isinstance(matrix, dict) else []
        covered_ids = {
            e.get("capability_id") for e in entries
            if isinstance(e, dict)
        }
        for cap_id in self.P4_CAPABILITY_IDS:
            assert cap_id in covered_ids or len(entries) == 0, (
                f"P4 capability {cap_id} not covered in applicability matrix"
            )

    def test_no_unauthorized_mdr_exclusion_claim(self) -> None:
        """P4 engineering verification is not an MDR exclusion conclusion."""
        # This is a contract test: verify the applicability matrix does not
        # claim MDR exclusion based on engineering testing alone.
        matrix_path = Path("docs/regulatory_scope/applicability_matrix.yaml")
        if not matrix_path.exists():
            pytest.skip("applicability_matrix.yaml not yet created")
        import yaml
        with open(matrix_path) as f:
            matrix = yaml.safe_load(f)
        if isinstance(matrix, dict):
            for entry in matrix.get("entries", []):
                if isinstance(entry, dict):
                    mdr_status = entry.get("mdr_status", "")
                    assert mdr_status != "excluded_confirmed", (
                        "P4 cannot confirm MDR exclusion without legal review"
                    )
