"""Merkle Evidence Pack — Merkle tree over pack files with partial proofs (P17, G17.2).

Builds a Merkle tree over the files in an evidence pack directory.
Each leaf is the SHA-256 of a file.  Interior nodes are SHA-256 of the
concatenation of child hashes.  A *partial proof* for a single file
contains the sibling hashes needed to reconstruct the root and verify
that the file is part of the tree without downloading the entire pack.

This module uses only stdlib (hashlib, json, pathlib) — no main
application imports — so it can be used by the offline verification kit.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

__all__ = [
    "MerkleLeaf",
    "MerkleNode",
    "MerkleTree",
    "MerkleProof",
    "MerkleProofStep",
    "MerkleProofError",
    "build_merkle_tree",
    "generate_partial_proof",
    "verify_partial_proof",
    "compute_file_sha256",
    "proof_to_dict",
    "proof_from_dict",
    "tree_to_dict",
    "build_tree_from_directory",
]


def compute_file_sha256(path: Path) -> str:
    """Compute SHA-256 hex of a file's bytes."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hash_pair(left: str, right: str) -> str:
    """Hash two hex strings together (interior node)."""
    return hashlib.sha256(
        (left + right).encode("utf-8"),
    ).hexdigest()


class _Hashable(Protocol):
    """Protocol for tree nodes that expose a hash."""

    @property
    def hash(self) -> str: ...


@dataclass(frozen=True)
class MerkleLeaf:
    """A leaf node in the Merkle tree.

    file_name:
        Relative path (from pack root) of the file.
    file_hash:
        SHA-256 hex of the file's bytes.
    """

    file_name: str
    file_hash: str

    @property
    def hash(self) -> str:
        """The hash of this leaf (same as file_hash)."""
        return self.file_hash


@dataclass(frozen=True)
class MerkleNode:
    """An interior node in the Merkle tree."""

    _hash: str
    left: Any
    right: Any

    @property
    def hash(self) -> str:
        """The Merkle hash of this interior node."""
        return self._hash


_TreeNode = "_TreeNodeAlias"


@dataclass
class MerkleProofStep:
    """One step in a Merkle proof path.

    sibling_hash:
        The hash of the sibling at this level.
    sibling_is_right:
        True if the sibling is the right child (the current node is the
        left child); False if the sibling is the left child (the current
        node is the right child).
    """

    sibling_hash: str
    sibling_is_right: bool


@dataclass
class MerkleProof:
    """A partial Merkle proof for a single file.

    file_name:
        The file being proven.
    leaf_hash:
        The SHA-256 of the file's bytes (the leaf hash).
    root_hash:
        The expected Merkle root hash.
    steps:
        The ordered list of proof steps (from leaf to root).
    """

    file_name: str
    leaf_hash: str
    root_hash: str
    steps: list[MerkleProofStep] = field(default_factory=list)


class MerkleProofError(Exception):
    """Raised when a Merkle proof fails to verify."""


# Type alias for tree node (leaf or interior).
# We use a union type at runtime; the dataclasses are frozen and
# structurally compatible via the ``hash`` property.
_TreeNodeAlias = Any  # type: ignore[assignment, unused-ignore]


class MerkleTree:
    """A Merkle tree over a set of files.

    Parameters
    ----------
    leaves:
        Ordered list of MerkleLeaf objects (one per file).
    """

    def __init__(self, leaves: list[MerkleLeaf]) -> None:
        if not leaves:
            raise ValueError("Merkle tree requires at least one leaf")
        self._leaves = list(leaves)
        self._root: MerkleNode | MerkleLeaf = self._build_tree()

    def _build_tree(self) -> _TreeNodeAlias:
        """Build the tree bottom-up and return the root."""
        level: list[_TreeNodeAlias] = list(self._leaves)
        while len(level) > 1:
            next_level: list[_TreeNodeAlias] = []
            i = 0
            while i < len(level):
                left = level[i]
                if i + 1 < len(level):
                    right = level[i + 1]
                    node_hash = _hash_pair(left.hash, right.hash)
                    next_level.append(MerkleNode(node_hash, left, right))
                    i += 2
                else:
                    # Odd node: duplicate-hash variant.
                    node_hash = _hash_pair(left.hash, left.hash)
                    next_level.append(MerkleNode(node_hash, left, left))
                    i += 1
            level = next_level
        return level[0]

    @property
    def root_hash(self) -> str:
        """The Merkle root hash (hex)."""
        return self._root.hash

    @property
    def leaves(self) -> list[MerkleLeaf]:
        """All leaf nodes."""
        return list(self._leaves)

    def leaf_index(self, file_name: str) -> int:
        """Return the index of the leaf with ``file_name``, or -1."""
        for i, leaf in enumerate(self._leaves):
            if leaf.file_name == file_name:
                return i
        return -1

    # ------------------------------------------------------------------
    # Proof generation
    # ------------------------------------------------------------------

    def generate_proof(self, file_name: str) -> MerkleProof:
        """Generate a partial Merkle proof for ``file_name``.

        Raises ``ValueError`` if the file is not in the tree.
        """
        idx = self.leaf_index(file_name)
        if idx < 0:
            raise ValueError(f"file not in tree: {file_name}")

        leaf = self._leaves[idx]
        steps: list[MerkleProofStep] = []

        # Walk the tree from leaf to root, collecting sibling hashes.
        # The tree pairs adjacent elements: (0,1), (2,3), etc.
        # At each level, the sibling of index i is i^1 (XOR with 1).
        # After processing, the next level's index is i // 2.
        current_idx = idx

        # Build level lists for traversal.
        level: list[MerkleNode | MerkleLeaf] = list(self._leaves)
        levels: list[list[MerkleNode | MerkleLeaf]] = [level]
        while len(level) > 1:
            next_level: list[MerkleNode | MerkleLeaf] = []
            i = 0
            while i < len(level):
                left = level[i]
                if i + 1 < len(level):
                    right = level[i + 1]
                    next_level.append(MerkleNode(
                        _hash_pair(left.hash, right.hash), left, right,
                    ))
                    i += 2
                else:
                    next_level.append(MerkleNode(
                        _hash_pair(left.hash, left.hash), left, left,
                    ))
                    i += 1
            levels.append(next_level)
            level = next_level

        # Walk from leaf level to root, collecting siblings.
        current_idx = idx
        for level_idx in range(len(levels) - 1):
            lvl = levels[level_idx]
            n = len(lvl)
            if current_idx % 2 == 0:
                # Current is the left child; sibling is to the right.
                sibling_idx = current_idx + 1
                if sibling_idx >= n:
                    # Odd node: sibling is itself (duplicated).
                    sibling_idx = current_idx
                steps.append(MerkleProofStep(
                    sibling_hash=lvl[sibling_idx].hash,
                    sibling_is_right=True,
                ))
            else:
                # Current is the right child; sibling is to the left.
                sibling_idx = current_idx - 1
                steps.append(MerkleProofStep(
                    sibling_hash=lvl[sibling_idx].hash,
                    sibling_is_right=False,
                ))
            current_idx = current_idx // 2

        return MerkleProof(
            file_name=file_name,
            leaf_hash=leaf.file_hash,
            root_hash=self.root_hash,
            steps=steps,
        )

    def _leaf_path_indices(self, leaf_idx: int, num_leaves: int) -> list[bool]:
        """Return the path of left/right choices from root to the leaf.

        True = go right, False = go left.
        """
        path: list[bool] = []
        n = num_leaves
        idx = leaf_idx
        while n > 1:
            half = (n + 1) // 2
            if idx >= half:
                path.append(True)
                idx -= half
            else:
                path.append(False)
            n = half
        return path


def build_merkle_tree(files: list[tuple[str, str]]) -> MerkleTree:
    """Build a MerkleTree from a list of (file_name, file_hash) pairs."""
    leaves = [MerkleLeaf(name, h) for name, h in files]
    return MerkleTree(leaves)


def generate_partial_proof(tree: MerkleTree, file_name: str) -> MerkleProof:
    """Generate a partial proof for ``file_name`` in ``tree``."""
    return tree.generate_proof(file_name)


def verify_partial_proof(proof: MerkleProof) -> bool:
    """Verify a partial Merkle proof.

    Returns True if the proof is valid (the computed root matches the
    recorded root_hash).  Raises ``MerkleProofError`` if the proof is
    malformed or verification fails.
    """
    current = proof.leaf_hash
    for step in proof.steps:
        if step.sibling_is_right:
            current = _hash_pair(current, step.sibling_hash)
        else:
            current = _hash_pair(step.sibling_hash, current)
    if current != proof.root_hash:
        raise MerkleProofError(
            f"Merkle proof verification failed: "
            f"computed root {current[:16]}… != expected {proof.root_hash[:16]}…"
        )
    return True


def build_tree_from_directory(pack_dir: Path) -> MerkleTree:
    """Build a MerkleTree from all files in ``pack_dir`` (recursive, sorted)."""
    files = sorted(
        (f for f in pack_dir.rglob("*") if f.is_file()),
        key=lambda p: p.as_posix(),
    )
    leaves = [
        MerkleLeaf(
            f.relative_to(pack_dir).as_posix(),
            compute_file_sha256(f),
        )
        for f in files
    ]
    return MerkleTree(leaves)


# ------------------------------------------------------------------
# Serialization
# ------------------------------------------------------------------


def proof_to_dict(proof: MerkleProof) -> dict[str, Any]:
    """Serialize a MerkleProof to a JSON-serializable dict."""
    return {
        "file_name": proof.file_name,
        "leaf_hash": proof.leaf_hash,
        "root_hash": proof.root_hash,
        "steps": [
            {
                "sibling_hash": s.sibling_hash,
                "sibling_is_right": s.sibling_is_right,
            }
            for s in proof.steps
        ],
    }


def proof_from_dict(data: dict[str, Any]) -> MerkleProof:
    """Deserialize a MerkleProof from a dict."""
    return MerkleProof(
        file_name=data["file_name"],
        leaf_hash=data["leaf_hash"],
        root_hash=data["root_hash"],
        steps=[
            MerkleProofStep(
                sibling_hash=s["sibling_hash"],
                sibling_is_right=s["sibling_is_right"],
            )
            for s in data["steps"]
        ],
    )


def tree_to_dict(tree: MerkleTree) -> dict[str, Any]:
    """Serialize a MerkleTree's manifest to a JSON-serializable dict."""
    return {
        "root_hash": tree.root_hash,
        "leaves": [
            {"file_name": l.file_name, "file_hash": l.file_hash}
            for l in tree.leaves
        ],
    }
