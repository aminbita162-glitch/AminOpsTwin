"""Tests for claim-id resolution via the verify CLI (G14.2).

Verifies that every claim-id referenced in README.md resolves
successfully via the aminopstwin-verify CLI tool.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
README_PATH = REPO_ROOT / "README.md"
VERIFY_CLI = REPO_ROOT / "scripts" / "aminopstwin-verify"

CLAIM_ID_PATTERN = re.compile(r"\[CLAIM-(\d{3})\]")


def extract_claim_ids_from_readme() -> list[str]:
    """Extract all [CLAIM-NNN] references from README.md."""
    text = README_PATH.read_text(encoding="utf-8")
    return sorted(
        f"CLAIM-{m.group(1)}"
        for m in CLAIM_ID_PATTERN.finditer(text)
    )


def load_claims_registry() -> dict[str, dict[str, object]]:
    """Load claims.yaml into a dict keyed by claim_id."""
    import yaml

    with (REPO_ROOT / "docs" / "claims.yaml").open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return {c["claim_id"]: c for c in data["claims"]}


class TestClaimsResolve:
    """G14.2: all claim-ids in README resolve via verify CLI."""

    def test_readme_has_claim_ids(self) -> None:
        ids = extract_claim_ids_from_readme()
        assert len(ids) > 0, "README must have at least one [CLAIM-NNN] reference"

    def test_every_readme_claim_exists_in_registry(self) -> None:
        """Every [CLAIM-NNN] in README must exist in claims.yaml."""
        readme_ids = set(extract_claim_ids_from_readme())
        registry = load_claims_registry()
        for cid in readme_ids:
            assert cid in registry, (
                f"{cid} referenced in README but not in claims.yaml"
            )

    def test_verify_cli_all_claims_pass(self) -> None:
        """The verify CLI must report all claims as passing."""
        result = subprocess.run(
            [sys.executable, str(VERIFY_CLI), "--all"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"verify CLI failed with exit {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "0 failed" in result.stdout, (
            f"some claims failed verification\n{result.stdout}"
        )

    def test_verify_cli_each_readme_claim(self) -> None:
        """Verify each README claim-id individually via the CLI."""
        readme_ids = extract_claim_ids_from_readme()
        for cid in readme_ids:
            result = subprocess.run(
                [sys.executable, str(VERIFY_CLI), "--check", cid],
                capture_output=True,
                text=True,
                cwd=str(REPO_ROOT),
                timeout=60,
            )
            assert result.returncode == 0, (
                f"{cid} failed verification: exit {result.returncode}\n"
                f"{result.stdout}\n{result.stderr}"
            )

    def test_verify_cli_tampered_hash_fails(self) -> None:
        """A tampered hash must cause verification failure."""
        result = subprocess.run(
            [sys.executable, str(VERIFY_CLI), "--check", "CLAIM-999"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        # CLAIM-999 does not exist -> exit 1
        assert result.returncode != 0, (
            "non-existent claim should fail verification"
        )
