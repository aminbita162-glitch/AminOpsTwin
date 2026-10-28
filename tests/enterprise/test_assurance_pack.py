"""G18.4 — Signed Assurance Pack: Evidence Pack generation and verification (P18).

Tests that the signed Evidence Pack generator produces a valid pack
directory containing gate status, claim summary, drift metrics, and an
assurance report, with a Merkle root and HMAC signature that verify
correctly.  Tampering with any file causes verification to fail.
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path

from aminopstwin.assurance.report import (
    AssuranceReport,
    CheckOutcome,
    CheckResult,
    RunState,
)
from aminopstwin.assurance.signed_pack import (
    DriftMetrics,
    GateStatus,
    PackManifest,
    SignedAssurancePack,
    compute_pack_merkle_root,
    generate_signed_pack,
    manifest_merkle_root,
    verify_signed_pack,
)
from aminopstwin.evidence.claim_graph import ClaimGraph, ClaimRecord


def _make_claim_graph() -> ClaimGraph:
    """Build a minimal ClaimGraph with two claims and no stale entries."""
    claims = [
        ClaimRecord(
            claim_id="CLAIM-P18-001",
            text="P18 isolation suite passes",
            evidence_path="tests/enterprise/test_isolation.py",
            hash="PLACEHOLDER",
            category="P18",
            depends_on=[],
        ),
        ClaimRecord(
            claim_id="CLAIM-P18-002",
            text="P18 quota engine enforced",
            evidence_path="tests/enterprise/test_quota.py",
            hash="PLACEHOLDER",
            category="P18",
            depends_on=["CLAIM-P18-001"],
        ),
    ]
    return ClaimGraph(claims=claims, repo_root=Path("."))


def _make_assurance_report() -> AssuranceReport:
    """Build a minimal valid AssuranceReport (zero-model)."""
    ts = _dt.datetime(2026, 10, 25, 12, 0, 0, tzinfo=_dt.UTC)
    return AssuranceReport(
        run_id="run-p18-test-0001",
        occurrence_id="occ-p18-2026-10-25",
        suite_version="p18-v1",
        tenant_scope="tenant-default",
        started_at=ts,
        ended_at=ts,
        input_manifest_hash="0" * 64,
        checks=[
            CheckResult(
                check_id="G18.1",
                outcome=CheckOutcome.PASS,
                measurements={"violations": 0},
                evidence_path="test_home/P18/G18.1_isolation.txt",
            ),
        ],
        model_request_count=0,
        model_tokens_used=0,
        overall_state=RunState.PASS,
    )


def _make_gate_results() -> list[GateStatus]:
    return [
        GateStatus(
            gate_id="G18.1",
            state="PASS",
            measurements={"violations": 0},
        ),
        GateStatus(
            gate_id="G18.2",
            state="PASS",
            measurements={"denials": 10},
        ),
        GateStatus(
            gate_id="G18.3",
            state="PASS",
            measurements={"leaks": 0},
        ),
        GateStatus(
            gate_id="G18.4",
            state="PASS",
            measurements={"valid": True},
        ),
    ]


def _make_drift_metrics() -> DriftMetrics:
    return DriftMetrics(
        state_hash_stability_scaled=10000,
        denial_rate_scaled=1000,
        extra={"total_requests": 100, "total_denials": 10},
    )


_SIGNING_KEY = "test-signing-key-p18-0123456789abcdef"


class TestSignedAssurancePack:
    """G18.4: Signed Evidence Pack generation and verification."""

    def test_generate_creates_pack_directory(self, tmp_path: Path) -> None:
        """generate_signed_pack creates a valid pack directory."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        manifest_path = generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        assert manifest_path.exists()
        assert manifest_path.name == "manifest.json"
        # Pack files exist.
        for name in (
            "gate_status.json",
            "claim_summary.json",
            "drift_metrics.json",
            "assurance_report.json",
            "prior_version.json",
        ):
            assert (tmp_path / name).exists()

    def test_pack_validates_with_offline_kit(self, tmp_path: Path) -> None:
        """The generated pack validates with verify_signed_pack."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is True

    def test_merkle_root_in_manifest_matches_computed(self, tmp_path: Path) -> None:
        """The merkle_root in the manifest matches compute_pack_merkle_root."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        computed = compute_pack_merkle_root(tmp_path)
        recorded = manifest_merkle_root(tmp_path)
        assert computed == recorded

    def test_tampered_file_fails_verification(self, tmp_path: Path) -> None:
        """Tampering with a pack file causes verification to fail."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        # Tamper with gate_status.json.
        gate_path = tmp_path / "gate_status.json"
        tampered = json.loads(gate_path.read_text(encoding="utf-8"))
        tampered["tampered"] = True
        gate_path.write_text(
            json.dumps(tampered, sort_keys=True),
            encoding="utf-8",
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is False

    def test_tampered_manifest_fails_verification(self, tmp_path: Path) -> None:
        """A tampered manifest (wrong signature) fails verification."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        # Wrong signing key.
        assert verify_signed_pack(tmp_path, "wrong-key") is False

    def test_pack_contains_gate_status(self, tmp_path: Path) -> None:
        """The pack contains gate status data."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        gate_data = json.loads(
            (tmp_path / "gate_status.json").read_text(encoding="utf-8")
        )
        assert "gates" in gate_data
        assert len(gate_data["gates"]) == 4
        assert gate_data["gates"][0]["gate_id"] == "G18.1"

    def test_pack_contains_claim_summary(self, tmp_path: Path) -> None:
        """The pack contains claim summary data."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        claim_data = json.loads(
            (tmp_path / "claim_summary.json").read_text(encoding="utf-8")
        )
        assert "claim_count" in claim_data
        assert claim_data["claim_count"] == 2

    def test_pack_contains_drift_metrics(self, tmp_path: Path) -> None:
        """The pack contains drift metrics."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        drift_data = json.loads(
            (tmp_path / "drift_metrics.json").read_text(encoding="utf-8")
        )
        assert "state_hash_stability_scaled" in drift_data
        assert "denial_rate_scaled" in drift_data

    def test_manifest_has_required_fields(self, tmp_path: Path) -> None:
        """The manifest contains all required fields."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        manifest_path = generate_signed_pack(
            tmp_path,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert manifest["pack_version"] == "aminops-pack-v1"
        assert manifest["generated_at"] == 1730000000
        assert "files" in manifest
        assert "merkle_root" in manifest
        assert "signature" in manifest
        assert "claim_count" in manifest
        assert "stale_claim_count" in manifest

    def test_build_manifest_returns_pack_manifest(self, tmp_path: Path) -> None:
        """build_manifest returns a PackManifest with correct fields."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        pack = SignedAssurancePack(
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        manifest = pack.build_manifest()
        assert isinstance(manifest, PackManifest)
        assert manifest.pack_version == "aminops-pack-v1"
        assert manifest.generated_at == 1730000000
        assert len(manifest.files) == 5
        assert len(manifest.merkle_root) == 64
        assert len(manifest.signature) == 64
        assert manifest.claim_count == 2

    def test_missing_manifest_fails_verification(self, tmp_path: Path) -> None:
        """A missing manifest.json causes verification to return False."""
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is False

    def test_repeated_generation_is_deterministic(self, tmp_path: Path) -> None:
        """Two packs generated with the same inputs produce identical manifests."""
        report = _make_assurance_report()
        graph = _make_claim_graph()
        gates = _make_gate_results()
        drift = _make_drift_metrics()
        dir_a = tmp_path / "a"
        dir_b = tmp_path / "b"
        generate_signed_pack(
            dir_a,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        generate_signed_pack(
            dir_b,
            assurance_report=report,
            claim_graph=graph,
            gate_results=gates,
            drift_metrics=drift,
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        manifest_a = json.loads(
            (dir_a / "manifest.json").read_text(encoding="utf-8")
        )
        manifest_b = json.loads(
            (dir_b / "manifest.json").read_text(encoding="utf-8")
        )
        assert manifest_a == manifest_b
