"""Signed Assurance Pack — signed Evidence Pack generator (P18, G18.4).

Produces a directory of pack files plus a signed ``manifest.json`` whose
signature is an HMAC-SHA256 over the Merkle root using a provided
signing key.  The pack aggregates:

1. Gate status (gate_id -> PASS/FAIL/NOT_RUN with measurements)
2. Claim summary (from ClaimGraph — claim count, stale count, dependency count)
3. Drift metrics (state-hash stability, denial rate)
4. Assurance report (from AssuranceReport)
5. A Merkle root over every pack file (excluding the manifest itself)
6. An HMAC-SHA256 signature over the Merkle root

Verification re-hashes every pack file, rebuilds the Merkle root, and
checks the signature.  Tampering with any file (or the manifest) causes
:func:`verify_signed_pack` to return ``False``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aminopstwin.assurance.report import AssuranceReport
from aminopstwin.contracts.canonical import canonical_bytes
from aminopstwin.evidence.claim_graph import ClaimGraph
from aminopstwin.evidence.merkle_pack import (
    MerkleLeaf,
    MerkleTree,
    build_tree_from_directory,
    compute_file_sha256,
)

__all__ = [
    "PackManifest",
    "SignedAssurancePack",
    "generate_signed_pack",
    "verify_signed_pack",
]

PACK_VERSION: str = "aminops-pack-v1"
MANIFEST_FILE: str = "manifest.json"


# ---------------------------------------------------------------------
# Pack manifest
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class PackFile:
    """One file entry in the pack manifest."""

    file_name: str
    sha256: str


@dataclass(frozen=True)
class PackManifest:
    """Signed manifest describing an Evidence Pack (G18.4)."""

    pack_version: str
    generated_at: int
    files: list[PackFile]
    merkle_root: str
    signature: str
    claim_count: int
    stale_claim_count: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "pack_version": self.pack_version,
            "generated_at": self.generated_at,
            "files": [
                {"file_name": f.file_name, "sha256": f.sha256}
                for f in self.files
            ],
            "merkle_root": self.merkle_root,
            "signature": self.signature,
            "claim_count": self.claim_count,
            "stale_claim_count": self.stale_claim_count,
        }


# ---------------------------------------------------------------------
# Input shapes
# ---------------------------------------------------------------------


@dataclass(frozen=True)
class GateStatus:
    """Status of a single assurance gate (G18.4 part 1)."""

    gate_id: str
    state: str  # "PASS" | "FAIL" | "NOT_RUN"
    measurements: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DriftMetrics:
    """Drift metrics for the pack (G18.4 part 3).

    All values are integer-scaled (×10 000) to avoid float in canonical
    payloads (N-15).  ``state_hash_stability_scaled`` is 0–10 000 (0.0–1.0)
    and ``denial_rate_scaled`` is 0–10 000 (0.0–1.0).
    """

    state_hash_stability_scaled: int
    denial_rate_scaled: int
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "state_hash_stability_scaled": self.state_hash_stability_scaled,
            "denial_rate_scaled": self.denial_rate_scaled,
            **dict(self.extra),
        }


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _hmac_sign(key: str, message: str) -> str:
    """HMAC-SHA256 hex of *message* under *key*."""
    return hmac.new(
        key.encode("utf-8"),
        message.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def _hmac_verify(key: str, message: str, expected: str) -> bool:
    return hmac.compare_digest(
        _hmac_sign(key, message),
        expected,
    )


def _claim_summary(graph: ClaimGraph) -> tuple[int, int, int]:
    """Return (claim_count, stale_count, dependency_count) for *graph*."""
    claims = graph.claims
    claim_count = len(claims)
    stale_count = len(graph.detect_stale_claims())
    dependency_count = sum(len(c.depends_on) for c in claims)
    return claim_count, stale_count, dependency_count


def _write_json(path: Path, payload: Any) -> None:
    """Write *payload* as canonical JSON to *path*."""
    path.write_bytes(canonical_bytes(payload))


def _build_merkle_root(file_hashes: list[tuple[str, str]]) -> str:
    """Build a Merkle root from sorted (file_name, sha256) pairs."""
    if not file_hashes:
        return hashlib.sha256(b"").hexdigest()
    tree = MerkleTree(
        [MerkleLeaf(name, digest) for name, digest in file_hashes]
    )
    return tree.root_hash


# ---------------------------------------------------------------------
# SignedAssurancePack
# ---------------------------------------------------------------------


class SignedAssurancePack:
    """Build and verify signed Evidence Packs (G18.4).

    A pack is a directory containing:

    * ``gate_status.json`` — gate states with measurements
    * ``claim_summary.json`` — claim graph counts
    * ``drift_metrics.json`` — drift metrics
    * ``assurance_report.json`` — serialised AssuranceReport
    * ``manifest.json`` — file hashes, Merkle root, signature
    """

    GATE_STATUS_FILE = "gate_status.json"
    CLAIM_SUMMARY_FILE = "claim_summary.json"
    DRIFT_METRICS_FILE = "drift_metrics.json"
    REPORT_FILE = "assurance_report.json"
    PRIOR_VERSION_FILE = "prior_version.json"

    def __init__(
        self,
        *,
        assurance_report: AssuranceReport,
        claim_graph: ClaimGraph,
        gate_results: list[GateStatus],
        drift_metrics: DriftMetrics,
        signing_key: str,
        generated_at: int,
        prior_version_record: dict[str, Any] | None = None,
    ) -> None:
        self._assurance_report = assurance_report
        self._claim_graph = claim_graph
        self._gate_results = list(gate_results)
        self._drift_metrics = drift_metrics
        self._signing_key = signing_key
        self._generated_at = generated_at
        self._prior_version_record = prior_version_record

    # ------------------------------------------------------------------
    # Pack construction
    # ------------------------------------------------------------------

    def _gate_status_payload(self) -> dict[str, Any]:
        return {
            "gates": [
                {
                    "gate_id": g.gate_id,
                    "state": g.state,
                    "measurements": dict(g.measurements),
                }
                for g in self._gate_results
            ],
            "generated_at": self._generated_at,
        }

    def _claim_summary_payload(self) -> dict[str, Any]:
        claim_count, stale_count, dep_count = _claim_summary(
            self._claim_graph
        )
        return {
            "claim_count": claim_count,
            "stale_claim_count": stale_count,
            "dependency_count": dep_count,
            "generated_at": self._generated_at,
        }

    def _drift_metrics_payload(self) -> dict[str, Any]:
        return self._drift_metrics.to_dict() | {
            "generated_at": self._generated_at,
        }

    def _report_payload(self) -> dict[str, Any]:
        return self._assurance_report.to_dict()

    def _prior_version_payload(self) -> dict[str, Any]:
        """Return the prior version record payload (G19.4).

        If no prior version record was supplied, returns an empty record
        with a ``prior_version`` of ``"none"``.  When a record is
        supplied, it is passed through unchanged (the caller is
        responsible for its structure).
        """
        if self._prior_version_record is not None:
            return dict(self._prior_version_record)
        return {
            "prior_version": "none",
            "pack_id": "",
            "version_hash": "",
        }

    def _pack_files_payloads(self) -> list[tuple[str, dict[str, Any]]]:
        """Return (file_name, payload) pairs for every non-manifest file."""
        return [
            (self.GATE_STATUS_FILE, self._gate_status_payload()),
            (self.CLAIM_SUMMARY_FILE, self._claim_summary_payload()),
            (self.DRIFT_METRICS_FILE, self._drift_metrics_payload()),
            (self.REPORT_FILE, self._report_payload()),
            (self.PRIOR_VERSION_FILE, self._prior_version_payload()),
        ]

    def build_manifest(self) -> PackManifest:
        """Compute the signed manifest without writing files."""
        file_hashes: list[tuple[str, str]] = []
        for name, payload in self._pack_files_payloads():
            digest = hashlib.sha256(canonical_bytes(payload)).hexdigest()
            file_hashes.append((name, digest))
        file_hashes.sort()
        merkle_root = _build_merkle_root(file_hashes)
        claim_count, stale_count, _ = _claim_summary(self._claim_graph)
        signature = _hmac_sign(self._signing_key, merkle_root)
        return PackManifest(
            pack_version=PACK_VERSION,
            generated_at=self._generated_at,
            files=[PackFile(n, h) for n, h in file_hashes],
            merkle_root=merkle_root,
            signature=signature,
            claim_count=claim_count,
            stale_claim_count=stale_count,
        )

    # ------------------------------------------------------------------
    # Pack I/O
    # ------------------------------------------------------------------

    def write_to(self, output_dir: Path) -> Path:
        """Write all pack files + manifest to *output_dir*.

        Returns the path to ``manifest.json``.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        for name, payload in self._pack_files_payloads():
            _write_json(output_dir / name, payload)
        manifest = self.build_manifest()
        manifest_path = output_dir / MANIFEST_FILE
        manifest_path.write_bytes(canonical_bytes(manifest.to_dict()))
        return manifest_path


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------


def generate_signed_pack(
    output_dir: Path,
    *,
    assurance_report: AssuranceReport,
    claim_graph: ClaimGraph,
    gate_results: list[GateStatus],
    drift_metrics: DriftMetrics,
    signing_key: str,
    generated_at: int | None = None,
    prior_version_record: dict[str, Any] | None = None,
) -> Path:
    """Generate a signed Evidence Pack in *output_dir* (G18.4, G19.4).

    Writes ``gate_status.json``, ``claim_summary.json``,
    ``drift_metrics.json``, ``assurance_report.json``,
    ``prior_version.json`` and a signed ``manifest.json``.
    Returns the path to the manifest.

    When *prior_version_record* is provided, it is written to
    ``prior_version.json`` and its hash is included in the Merkle
    root, binding the chosen prior version to the Evidence Pack (G19.4).
    """
    if generated_at is None:
        # Use the report's started_at as a deterministic integer timestamp.
        started = assurance_report.started_at
        generated_at = int(started.timestamp())
    pack = SignedAssurancePack(
        assurance_report=assurance_report,
        claim_graph=claim_graph,
        gate_results=gate_results,
        drift_metrics=drift_metrics,
        signing_key=signing_key,
        generated_at=generated_at,
        prior_version_record=prior_version_record,
    )
    return pack.write_to(output_dir)


def _read_manifest(pack_dir: Path) -> dict[str, Any]:
    """Read and parse manifest.json from *pack_dir*."""
    manifest_path = pack_dir / MANIFEST_FILE
    data: dict[str, Any] = json.loads(manifest_path.read_text(encoding="utf-8"))
    return data


def verify_signed_pack(pack_dir: Path, signing_key: str) -> bool:
    """Verify a signed Evidence Pack (G18.4).

    Re-hashes every pack file listed in the manifest, rebuilds the
    Merkle root, checks the HMAC signature, and confirms each file's
    recorded hash matches its on-disk content.  Returns ``True`` only
    when every check passes.
    """
    manifest_path = pack_dir / MANIFEST_FILE
    if not manifest_path.exists():
        return False
    try:
        manifest = _read_manifest(pack_dir)
    except (json.JSONDecodeError, OSError):
        return False

    files = manifest.get("files")
    if not isinstance(files, list) or not files:
        return False

    expected_root = manifest.get("merkle_root")
    expected_sig = manifest.get("signature")
    if not isinstance(expected_root, str) or not isinstance(expected_sig, str):
        return False

    # 1. Verify each file's on-disk hash matches the manifest entry.
    file_hashes: list[tuple[str, str]] = []
    for entry in files:
        if not isinstance(entry, dict):
            return False
        file_name = entry.get("file_name")
        expected_hash = entry.get("sha256")
        if not isinstance(file_name, str) or not isinstance(expected_hash, str):
            return False
        file_path = pack_dir / file_name
        if not file_path.exists() or not file_path.is_file():
            return False
        actual = compute_file_sha256(file_path)
        if actual != expected_hash:
            return False
        file_hashes.append((file_name, actual))

    # 2. Rebuild the Merkle root over the (now-verified) file hashes.
    file_hashes.sort()
    # Build the Merkle tree from the pack directory *excluding* manifest.json,
    # matching the build order used at generation time.
    try:
        build_tree_from_directory(pack_dir)
    except ValueError:
        return False
    # build_tree_from_directory includes manifest.json; we must exclude it.
    # Rebuild using only the manifest-listed files.
    leaves = [
        MerkleLeaf(name, digest) for name, digest in file_hashes
    ]
    if not leaves:
        return False
    computed_tree = MerkleTree(leaves)
    if computed_tree.root_hash != expected_root:
        return False

    # 3. Verify the HMAC signature over the Merkle root.
    return _hmac_verify(signing_key, expected_root, expected_sig)


def compute_pack_merkle_root(pack_dir: Path) -> str:
    """Compute the Merkle root over pack files excluding manifest.json.

    Convenience for tests that want to compare against the manifest's
    ``merkle_root``.
    """
    files = sorted(
        (
            f for f in pack_dir.iterdir()
            if f.is_file() and f.name != MANIFEST_FILE
        ),
        key=lambda p: p.name,
    )
    leaves = [
        MerkleLeaf(f.name, compute_file_sha256(f)) for f in files
    ]
    if not leaves:
        return hashlib.sha256(b"").hexdigest()
    return MerkleTree(leaves).root_hash


def manifest_merkle_root(pack_dir: Path) -> str:
    """Return the merkle_root recorded in the pack manifest."""
    manifest = _read_manifest(pack_dir)
    root = manifest["merkle_root"]
    assert isinstance(root, str)
    return root
