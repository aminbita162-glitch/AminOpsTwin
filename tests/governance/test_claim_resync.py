"""P24 claim register resync test (G24.2).

Verifies that every claim in ``docs/claims.yaml`` has an evidence path
that exists and whose SHA-256 hash matches the recorded hash — i.e. the
claim register is resynced and fresh.  Uses the standalone
``scripts/aminopstwin-verify`` CLI so the check mirrors the real
verification path.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent.parent.parent
CLAIMS_PATH = REPO_ROOT / "docs" / "claims.yaml"
VERIFY_CLI = REPO_ROOT / "scripts" / "aminopstwin-verify"


def _load_claims() -> list[dict[str, str]]:
    import yaml

    with CLAIMS_PATH.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data["claims"]


class TestClaimResync:
    """G24.2: claim register resync — every claim hash matches its evidence."""

    def test_claims_yaml_exists(self) -> None:
        assert CLAIMS_PATH.exists(), "docs/claims.yaml must exist"

    def test_claims_non_empty(self) -> None:
        claims = _load_claims()
        assert len(claims) > 0, "claims.yaml must have at least one claim"

    def test_every_claim_has_required_fields(self) -> None:
        claims = _load_claims()
        for c in claims:
            assert "claim_id" in c, f"claim missing claim_id: {c}"
            assert "evidence_path" in c, (
                f"{c.get('claim_id')} missing evidence_path"
            )
            assert "hash" in c, f"{c['claim_id']} missing hash"

    def test_every_claim_hash_is_not_placeholder(self) -> None:
        claims = _load_claims()
        for c in claims:
            assert c["hash"] != "PLACEHOLDER", (
                f"{c['claim_id']} hash is PLACEHOLDER — not resynced"
            )

    def test_verify_cli_all_claims_pass(self) -> None:
        """The verify CLI must report 0 failures for all claims."""
        result = subprocess.run(
            [sys.executable, str(VERIFY_CLI), "--all"],
            capture_output=True,
            text=True,
            cwd=str(REPO_ROOT),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"verify CLI failed (exit {result.returncode})\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert "0 failed" in result.stdout, (
            f"some claims failed verification\n{result.stdout}"
        )

    def test_claim_count_matches_registry(self) -> None:
        """The number of claims in the registry is consistent."""
        claims = _load_claims()
        claim_ids = [c["claim_id"] for c in claims]
        # No duplicate claim-ids
        assert len(claim_ids) == len(set(claim_ids)), (
            "Duplicate claim-ids found in claims.yaml"
        )

    def test_readme_claim_ids_subset_of_registry(self) -> None:
        """Every [CLAIM-NNN] referenced in README.md exists in the registry."""
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        readme_ids = set(re.findall(r"\[CLAIM-\d{3}\]", readme))
        registry_ids = {c["claim_id"] for c in _load_claims()}
        for ref in readme_ids:
            cid = ref.strip("[]")
            assert cid in registry_ids, (
                f"{ref} referenced in README but not in claims.yaml"
            )
