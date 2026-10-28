"""G17.2 — Merkle Evidence Pack: partial proof generation and verification (P17).

Tests that the Merkle tree over pack files correctly generates and
verifies partial proofs, and that a tampered file fails verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from aminopstwin.evidence.merkle_pack import (
    MerkleProof,
    MerkleProofError,
    build_merkle_tree,
    build_tree_from_directory,
    compute_file_sha256,
    generate_partial_proof,
    proof_from_dict,
    proof_to_dict,
    tree_to_dict,
    verify_partial_proof,
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class TestMerklePack:
    """G17.2: Merkle evidence pack with partial proofs."""

    def test_build_tree_from_hashes(self) -> None:
        """Build a tree from (name, hash) pairs and check root is deterministic."""
        leaves = [("a", _sha256(b"A")), ("b", _sha256(b"B"))]
        tree = build_merkle_tree(leaves)
        # Root should be deterministic.
        tree2 = build_merkle_tree(leaves)
        assert tree.root_hash == tree2.root_hash
        assert len(tree.root_hash) == 64

    def test_single_leaf_tree(self) -> None:
        """A single-leaf tree has root = leaf hash."""
        leaf_hash = _sha256(b"hello")
        tree = build_merkle_tree([("a", leaf_hash)])
        # With one leaf, the root is the leaf hash itself.
        assert tree.root_hash == leaf_hash

    def test_empty_tree_raises(self) -> None:
        """An empty tree raises ValueError."""
        with pytest.raises(ValueError, match="at least one leaf"):
            build_merkle_tree([])

    def test_partial_proof_verifies(self) -> None:
        """A partial proof for a valid file verifies."""
        leaves = [
            ("file_a", _sha256(b"A")),
            ("file_b", _sha256(b"B")),
            ("file_c", _sha256(b"C")),
            ("file_d", _sha256(b"D")),
        ]
        tree = build_merkle_tree(leaves)
        proof = generate_partial_proof(tree, "file_b")
        assert verify_partial_proof(proof) is True

    def test_partial_proof_all_leaves(self) -> None:
        """A partial proof for every leaf in a 7-leaf tree verifies."""
        leaves = [(f"f{i}", _sha256(f"data{i}".encode())) for i in range(7)]
        tree = build_merkle_tree(leaves)
        for name, _ in leaves:
            proof = generate_partial_proof(tree, name)
            assert verify_partial_proof(proof) is True, f"proof failed for {name}"

    def test_tampered_file_fails_verification(self) -> None:
        """A proof for a tampered file (wrong leaf hash) fails verification."""
        leaves = [("a", _sha256(b"A")), ("b", _sha256(b"B"))]
        tree = build_merkle_tree(leaves)
        proof = generate_partial_proof(tree, "a")
        # Tamper: change the leaf_hash to something wrong.
        tampered_proof = MerkleProof(
            file_name=proof.file_name,
            leaf_hash=_sha256(b"TAMPERED"),
            root_hash=proof.root_hash,
            steps=proof.steps,
        )
        with pytest.raises(MerkleProofError, match="verification failed"):
            verify_partial_proof(tampered_proof)

    def test_tampered_root_fails_verification(self) -> None:
        """A proof with a wrong root hash fails verification."""
        leaves = [("a", _sha256(b"A")), ("b", _sha256(b"B"))]
        tree = build_merkle_tree(leaves)
        proof = generate_partial_proof(tree, "a")
        tampered_proof = MerkleProof(
            file_name=proof.file_name,
            leaf_hash=proof.leaf_hash,
            root_hash="f" * 64,  # wrong root
            steps=proof.steps,
        )
        with pytest.raises(MerkleProofError, match="verification failed"):
            verify_partial_proof(tampered_proof)

    def test_file_not_in_tree_raises(self) -> None:
        """generate_proof for a non-existent file raises ValueError."""
        leaves = [("a", _sha256(b"A"))]
        tree = build_merkle_tree(leaves)
        with pytest.raises(ValueError, match="not in tree"):
            generate_partial_proof(tree, "nonexistent")

    def test_build_tree_from_directory(self, tmp_path: Path) -> None:
        """Build a tree from a directory of files."""
        d = tmp_path / "pack"
        d.mkdir()
        (d / "a.txt").write_text("AAA")
        (d / "b.txt").write_text("BBB")
        (d / "sub").mkdir()
        (d / "sub" / "c.txt").write_text("CCC")

        tree = build_tree_from_directory(d)
        assert len(tree.leaves) == 3
        # All proofs verify.
        for leaf in tree.leaves:
            proof = generate_partial_proof(tree, leaf.file_name)
            assert verify_partial_proof(proof) is True

    def test_proof_serialization_roundtrip(self) -> None:
        """proof_to_dict / proof_from_dict round-trips correctly."""
        leaves = [("a", _sha256(b"A")), ("b", _sha256(b"B")), ("c", _sha256(b"C"))]
        tree = build_merkle_tree(leaves)
        proof = generate_partial_proof(tree, "b")
        d = proof_to_dict(proof)
        # JSON round-trip.
        json_str = json.dumps(d)
        d2 = json.loads(json_str)
        proof2 = proof_from_dict(d2)
        assert proof2.file_name == proof.file_name
        assert proof2.leaf_hash == proof.leaf_hash
        assert proof2.root_hash == proof.root_hash
        assert len(proof2.steps) == len(proof.steps)
        assert verify_partial_proof(proof2) is True

    def test_tree_to_dict(self) -> None:
        """tree_to_dict serializes the tree manifest."""
        leaves = [("a", _sha256(b"A")), ("b", _sha256(b"B"))]
        tree = build_merkle_tree(leaves)
        d = tree_to_dict(tree)
        assert d["root_hash"] == tree.root_hash
        assert len(d["leaves"]) == 2

    def test_compute_file_sha256(self, tmp_path: Path) -> None:
        """compute_file_sha256 matches hashlib."""
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert compute_file_sha256(f) == hashlib.sha256(b"hello").hexdigest()

    def test_odd_number_of_leaves(self) -> None:
        """An odd number of leaves is handled (odd node is duplicated)."""
        leaves = [
            ("a", _sha256(b"A")),
            ("b", _sha256(b"B")),
            ("c", _sha256(b"C")),
        ]
        tree = build_merkle_tree(leaves)
        # All proofs verify.
        for name, _ in leaves:
            proof = generate_partial_proof(tree, name)
            assert verify_partial_proof(proof) is True

    def test_large_tree_all_proofs_verify(self) -> None:
        """A 16-leaf tree: all 16 partial proofs verify."""
        leaves = [(f"f{i:02d}", _sha256(f"data{i}".encode())) for i in range(16)]
        tree = build_merkle_tree(leaves)
        for name, _ in leaves:
            proof = generate_partial_proof(tree, name)
            assert verify_partial_proof(proof) is True

    def test_merkle_root_differs_on_different_data(self) -> None:
        """Different data produces different roots."""
        tree1 = build_merkle_tree([("a", _sha256(b"A"))])
        tree2 = build_merkle_tree([("a", _sha256(b"B"))])
        assert tree1.root_hash != tree2.root_hash
