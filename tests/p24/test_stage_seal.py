"""P24 Stage Seal test (G24.3).

Verifies that the Stage 4 Seal document exists, verifies, and matches
the git tree hash and active claim-ids.
"""

from __future__ import annotations

from pathlib import Path

from aminopstwin.stage4_seal import (
    Stage4Seal,
    compute_tree_hash,
    generate_stage4_seal,
    load_claim_ids,
    verify_stage4_seal,
    write_stage4_seal,
)

REPO_ROOT = Path(__file__).parent.parent.parent
SIGNING_KEY = "test-stage4-seal-key-0123456789"


class TestStage4Seal:
    """G24.3: Stage 4 Seal verifies and matches the git tree hash."""

    def test_compute_tree_hash_returns_sha1_hex(self) -> None:
        tree_hash = compute_tree_hash(REPO_ROOT)
        assert len(tree_hash) == 40, (
            f"Expected 40-char hex, got {len(tree_hash)}: {tree_hash}"
        )
        int(tree_hash, 16)  # valid hex

    def test_load_claim_ids_returns_non_empty(self) -> None:
        claim_ids = load_claim_ids()
        assert len(claim_ids) > 0, "No claim-ids found in claims.yaml"
        for cid in claim_ids:
            assert cid.startswith("CLAIM-"), (
                f"Invalid claim-id format: {cid}"
            )

    def test_generate_seal_creates_valid_seal(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert seal.tree_hash == compute_tree_hash(REPO_ROOT)
        assert len(seal.claim_ids) > 0
        assert len(seal.signature) == 64  # HMAC-SHA256 hex
        assert seal.verify()
        assert seal.stage == "4"

    def test_seal_signature_is_valid(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert seal.verify() is True

    def test_seal_with_wrong_key_fails_verification(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        bad_seal = Stage4Seal(
            tree_hash=seal.tree_hash,
            claim_ids=seal.claim_ids,
            signature=seal.signature,
            signing_key="wrong-key",
        )
        assert bad_seal.verify() is False

    def test_seal_matches_tree_hash(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        tree_hash = compute_tree_hash(REPO_ROOT)
        assert verify_stage4_seal(seal, expected_tree_hash=tree_hash)

    def test_seal_does_not_match_wrong_tree_hash(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert not verify_stage4_seal(seal, expected_tree_hash="0" * 40)

    def test_seal_to_json_is_deterministic(self) -> None:
        seal1 = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        seal2 = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        assert seal1.to_json() == seal2.to_json()

    def test_seal_to_dict_has_required_fields(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        d = seal.to_dict()
        assert d["stage"] == "4"
        assert "tree_hash" in d
        assert "claim_ids" in d
        assert "signature" in d

    def test_write_seal_writes_to_file(self, tmp_path: Path) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        output = tmp_path / "stage4_seal.json"
        path = write_stage4_seal(seal, output)
        assert path.exists()
        import json

        data = json.loads(path.read_text())
        assert data["stage"] == "4"
        assert "tree_hash" in data
        assert "signature" in data

    def test_seal_claim_ids_match_claims_yaml(self) -> None:
        seal = generate_stage4_seal(SIGNING_KEY, repo_root=REPO_ROOT)
        expected_ids = load_claim_ids()
        assert sorted(seal.claim_ids) == sorted(expected_ids)

    def test_committed_stage4_seal_exists(self) -> None:
        """The committed Stage 4 seal document exists at docs/stage4_seal.json."""
        seal_path = REPO_ROOT / "docs" / "stage4_seal.json"
        assert seal_path.exists(), (
            "docs/stage4_seal.json must exist (Stage Seal deliverable)"
        )
        import json

        data = json.loads(seal_path.read_text(encoding="utf-8"))
        assert data["stage"] == "4"
        assert len(data["tree_hash"]) == 40
        assert len(data["claim_ids"]) > 0
        assert len(data["signature"]) == 64
