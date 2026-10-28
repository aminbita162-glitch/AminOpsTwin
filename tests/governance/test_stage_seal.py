"""P20 Stage Seal test (G20.3).

Verifies that the Stage Seal verifies and matches the git tree hash.
"""

from __future__ import annotations

from pathlib import Path

from aminopstwin.stage_seal import (
    StageSeal,
    compute_tree_hash,
    generate_stage_seal,
    load_claim_ids,
    verify_stage_seal,
    write_seal,
)

REPO_ROOT = Path(__file__).parent.parent.parent
SIGNING_KEY = "test-stage3-seal-key-0123456789"


class TestStageSeal:
    """G20.3: Stage Seal verifies and matches the git tree hash."""

    def test_compute_tree_hash_returns_sha1_hex(self) -> None:
        """compute_tree_hash returns a 40-char hex string (git SHA-1)."""
        tree_hash = compute_tree_hash(REPO_ROOT)
        assert len(tree_hash) == 40, (
            f"Expected 40-char hex, got {len(tree_hash)}: {tree_hash}"
        )
        int(tree_hash, 16)  # valid hex

    def test_load_claim_ids_returns_non_empty(self) -> None:
        """load_claim_ids returns a non-empty list."""
        claim_ids = load_claim_ids()
        assert len(claim_ids) > 0, "No claim-ids found in claims.yaml"
        for cid in claim_ids:
            assert cid.startswith("CLAIM-"), (
                f"Invalid claim-id format: {cid}"
            )

    def test_generate_seal_creates_valid_seal(self) -> None:
        """generate_stage_seal creates a seal with valid signature."""
        seal = generate_stage_seal(
            SIGNING_KEY,
            repo_root=REPO_ROOT,
        )
        assert seal.tree_hash == compute_tree_hash(REPO_ROOT)
        assert len(seal.claim_ids) > 0
        assert len(seal.signature) == 64  # HMAC-SHA256 hex
        assert seal.verify()

    def test_seal_signature_is_valid(self) -> None:
        """The seal's signature is valid."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert seal.verify() is True

    def test_seal_with_wrong_key_fails_verification(self) -> None:
        """A seal with the wrong key fails verification."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        # Tamper: create a new seal with wrong key but same tree/claims
        bad_seal = StageSeal(
            tree_hash=seal.tree_hash,
            claim_ids=seal.claim_ids,
            signature=seal.signature,
            signing_key="wrong-key",
        )
        assert bad_seal.verify() is False

    def test_seal_matches_tree_hash(self) -> None:
        """verify_stage_seal with expected_tree_hash matches."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        tree_hash = compute_tree_hash(REPO_ROOT)
        assert verify_stage_seal(
            seal,
            expected_tree_hash=tree_hash,
        )

    def test_seal_does_not_match_wrong_tree_hash(self) -> None:
        """verify_stage_seal fails with wrong expected_tree_hash."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert not verify_stage_seal(
            seal,
            expected_tree_hash="0" * 40,
        )

    def test_seal_to_json_is_deterministic(self) -> None:
        """Seal JSON serialisation is deterministic."""
        seal1 = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        seal2 = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert seal1.to_json() == seal2.to_json()

    def test_seal_to_dict_has_required_fields(self) -> None:
        """Seal.to_dict has all required fields."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        d = seal.to_dict()
        assert "stage" in d
        assert "tree_hash" in d
        assert "claim_ids" in d
        assert "signature" in d
        assert d["stage"] == "3"

    def test_write_seal_writes_to_file(self, tmp_path: Path) -> None:
        """write_seal writes the seal JSON to a file."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        output = tmp_path / "stage3_seal.json"
        path = write_seal(seal, output)
        assert path.exists()
        import json
        data = json.loads(path.read_text())
        assert data["stage"] == "3"
        assert "tree_hash" in data
        assert "signature" in data

    def test_seal_claim_ids_match_claims_yaml(self) -> None:
        """Seal claim_ids match the claim-ids in claims.yaml."""
        seal = generate_stage_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        expected_ids = load_claim_ids()
        assert sorted(seal.claim_ids) == sorted(expected_ids)
