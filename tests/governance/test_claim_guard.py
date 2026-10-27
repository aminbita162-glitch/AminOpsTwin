"""Claim guard test (G25.5).

Verifies that every README claim-id and invariant row maps to an
existing module path and an existing test id in docs/claims_map.yaml.
Fails if any mapped module or test does not exist, or if the README
contains a claim-id or invariant row that has no mapping.
"""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README = REPO_ROOT / "README.md"
CLAIMS_MAP = REPO_ROOT / "docs" / "claims_map.yaml"

CLAIM_ID_PATTERN = re.compile(r"CLAIM-\d+")


def _extract_claim_ids_from_readme(content: str) -> set[str]:
    """Extract all CLAIM-NNN ids from the README."""
    return set(CLAIM_ID_PATTERN.findall(content))


def _extract_invariant_rows_from_readme(content: str) -> set[str]:
    """Extract invariant row labels from the Non-Negotiable Invariants table."""
    rows: set[str] = set()
    in_table = False
    for line in content.splitlines():
        if "| Principle |" in line:
            in_table = True
            continue
        if in_table and line.startswith("|") and "---" not in line:
            cells = [c.strip() for c in line.strip("|").split("|")]
            if len(cells) >= 1 and cells[0] and cells[0] != "Principle":
                rows.add(cells[0])
        elif in_table and not line.startswith("|"):
            break
    return rows


class TestClaimGuard:
    """G25.5: every mapped module and test exists; no unmapped claim or row."""

    def test_claims_map_exists(self) -> None:
        assert CLAIMS_MAP.exists(), "docs/claims_map.yaml must exist"

    def test_readme_exists(self) -> None:
        assert README.exists(), "README.md must exist"

    def test_all_claim_modules_exist(self) -> None:
        """Every mapped module path exists."""
        import yaml

        data = yaml.safe_load(CLAIMS_MAP.read_text())
        claims = data.get("claims", {})
        for claim_id, entry in claims.items():
            module_path = REPO_ROOT / entry["module"]
            assert module_path.exists(), (
                f"{claim_id} maps to missing module: {entry['module']}"
            )

    def test_all_claim_tests_exist(self) -> None:
        """Every mapped test file exists."""
        import yaml

        data = yaml.safe_load(CLAIMS_MAP.read_text())
        claims = data.get("claims", {})
        for claim_id, entry in claims.items():
            test_ref = entry["test"]
            test_path = test_ref.split("::")[0]
            full_path = REPO_ROOT / test_path
            assert full_path.exists(), (
                f"{claim_id} maps to missing test: {test_path}"
            )

    def test_all_invariant_modules_exist(self) -> None:
        """Every invariant module path exists."""
        import yaml

        data = yaml.safe_load(CLAIMS_MAP.read_text())
        invariants = data.get("invariants", [])
        for inv in invariants:
            module_path = REPO_ROOT / inv["module"]
            assert module_path.exists(), (
                f"Invariant '{inv['row']}' maps to missing module: {inv['module']}"
            )

    def test_all_invariant_tests_exist(self) -> None:
        """Every invariant test file exists."""
        import yaml

        data = yaml.safe_load(CLAIMS_MAP.read_text())
        invariants = data.get("invariants", [])
        for inv in invariants:
            test_ref = inv["test"]
            test_path = test_ref.split("::")[0]
            full_path = REPO_ROOT / test_path
            assert full_path.exists(), (
                f"Invariant '{inv['row']}' maps to missing test: {test_path}"
            )

    def test_no_unmapped_claim_ids(self) -> None:
        """Every CLAIM-NNN in the README has a mapping in claims_map.yaml."""
        import yaml

        content = README.read_text()
        readme_ids = _extract_claim_ids_from_readme(content)
        data = yaml.safe_load(CLAIMS_MAP.read_text())
        mapped_ids = set(data.get("claims", {}).keys())
        unmapped = readme_ids - mapped_ids
        assert not unmapped, (
            f"README contains claim ids not in claims_map.yaml: {sorted(unmapped)}"
        )

    def test_no_unmapped_invariant_rows(self) -> None:
        """Every invariant row in the README has a mapping."""
        import yaml

        content = README.read_text()
        readme_rows = _extract_invariant_rows_from_readme(content)
        data = yaml.safe_load(CLAIMS_MAP.read_text())
        mapped_rows = {
            inv["row"] for inv in data.get("invariants", [])
        }
        unmapped = readme_rows - mapped_rows
        assert not unmapped, (
            f"README contains invariant rows not in claims_map.yaml: "
            f"{sorted(unmapped)}"
        )
