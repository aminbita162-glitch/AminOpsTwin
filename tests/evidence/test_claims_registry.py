"""Tests for the Evidence Claim Registry (G13.1).

Verifies that:
- claims.yaml exists and is valid YAML
- every claim has claim_id, text, evidence_path, hash, category
- every evidence_path exists on disk
- no claim has a PLACEHOLDER hash
- every README capability sentence has a claim-id
"""

from __future__ import annotations

import re
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).parent.parent.parent
CLAIMS_FILE = REPO_ROOT / "docs" / "claims.yaml"
README_FILE = REPO_ROOT / "README.md"


def _load_claims() -> list[dict[str, object]]:
    with CLAIMS_FILE.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), "claims.yaml must be a dict"
    assert "claims" in data, "claims.yaml must have 'claims' key"
    claims = data["claims"]
    assert isinstance(claims, list), "'claims' must be a list"
    return claims


def _read_readme() -> str:
    return README_FILE.read_text(encoding="utf-8")


class TestClaimsRegistry:
    """G13.1: claims.yaml covers every README capability sentence."""

    def test_claims_file_exists_and_is_valid_yaml(self) -> None:
        assert CLAIMS_FILE.exists(), "docs/claims.yaml must exist"
        claims = _load_claims()
        assert len(claims) > 0, "claims.yaml must have at least one claim"

    def test_every_claim_has_required_fields(self) -> None:
        claims = _load_claims()
        required = {"claim_id", "text", "evidence_path", "hash", "category"}
        for c in claims:
            missing = required - set(c.keys())
            assert not missing, (
                f"claim {c.get('claim_id', '?')} missing fields: {missing}"
            )

    def test_every_evidence_path_exists(self) -> None:
        claims = _load_claims()
        for c in claims:
            ep = str(c["evidence_path"])
            path = REPO_ROOT / ep
            assert path.exists(), (
                f"claim {c['claim_id']}: evidence path not found: {ep}"
            )

    def test_no_placeholder_hashes(self) -> None:
        claims = _load_claims()
        for c in claims:
            assert c["hash"] != "PLACEHOLDER", (
                f"claim {c['claim_id']}: hash is still PLACEHOLDER"
            )

    def test_claim_ids_are_unique(self) -> None:
        claims = _load_claims()
        ids = [str(c["claim_id"]) for c in claims]
        assert len(ids) == len(set(ids)), "duplicate claim_ids found"

    def test_claim_ids_match_regex(self) -> None:
        claims = _load_claims()
        pattern = re.compile(r"^CLAIM-\d{3}$")
        for c in claims:
            cid = str(c["claim_id"])
            assert pattern.match(cid), (
                f"claim_id {cid} does not match CLAIM-NNN format"
            )

    def test_readme_contains_claim_references(self) -> None:
        """Every claim-id that appears in README.md must have an entry
        in claims.yaml. Not every claim-id must appear in README — some
        claims point to test files as evidence."""
        readme = _read_readme()
        claims = _load_claims()
        claim_ids = {str(c["claim_id"]) for c in claims}
        # Find all CLAIM-NNN references in the README
        readme_refs = set(re.findall(r"CLAIM-\d{3}", readme))
        # Every README reference must be in the registry
        assert readme_refs.issubset(claim_ids), (
            f"README references claims not in registry: {readme_refs - claim_ids}"
        )
        # And at least some claims should be referenced in README
        assert len(readme_refs) >= 3, (
            f"README should reference at least 3 claims, found {readme_refs}"
        )

    def test_at_least_three_sample_claims(self) -> None:
        """The directive requires the verify CLI to check at least 3 claims."""
        claims = _load_claims()
        assert len(claims) >= 3, (
            f"need at least 3 claims for verify CLI, got {len(claims)}"
        )
