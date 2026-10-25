"""G19.4 — Multi-version priors: version hash recorded in every Evidence Pack (P19).

Tests:
  - PriorVersion enum has V1 and V2 with correct values;
  - load_public_prior_pack_v2 loads and verifies the v2 pack;
  - load_prior_pack_by_version selects the correct version;
  - MultiVersionPriorPack selects a preferred version;
  - version_hash is deterministic for the same pack version;
  - version_hash differs between v1 and v2;
  - to_evidence_record contains the version hash;
  - the version hash is recorded in a generated Evidence Pack's
    prior_version.json file;
  - verify_signed_pack passes for a pack with a prior version record;
  - changing the prior version changes the Merkle root (cryptographic
    binding).
"""

from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any

import pytest
from aminopstwin.assurance.report import (
    AssuranceReport,
    CheckOutcome,
    CheckResult,
    RunState,
)
from aminopstwin.assurance.signed_pack import (
    DriftMetrics,
    GateStatus,
    generate_signed_pack,
    verify_signed_pack,
)
from aminopstwin.evidence.claim_graph import ClaimGraph, ClaimRecord
from aminopstwin.priors import (
    MultiVersionPriorPack,
    PriorPackError,
    PriorVersion,
    load_multi_version_prior_pack,
    load_prior_pack_by_version,
    load_public_prior_pack_v1,
    load_public_prior_pack_v2,
)

_SIGNING_KEY = "test-signing-key-for-g19-4"
_TS = _dt.datetime(2026, 10, 25, 12, 0, 0, tzinfo=_dt.UTC)


def _make_claim_graph() -> ClaimGraph:
    """Build a minimal ClaimGraph with two claims."""
    claims = [
        ClaimRecord(
            claim_id="CLAIM-P19-001",
            text="P19 multi-version priors pass",
            evidence_path="tests/p19/test_multi_version_priors.py",
            hash="PLACEHOLDER",
            category="P19",
            depends_on=[],
        ),
        ClaimRecord(
            claim_id="CLAIM-P19-002",
            text="P19 version hash recorded in evidence pack",
            evidence_path="tests/p19/test_multi_version_priors.py",
            hash="PLACEHOLDER",
            category="P19",
            depends_on=["CLAIM-P19-001"],
        ),
    ]
    return ClaimGraph(claims=claims, repo_root=Path("."))


def _make_assurance_report() -> AssuranceReport:
    return AssuranceReport(
        run_id="run-p19-test-0001",
        occurrence_id="occ-p19-2026-10-25",
        suite_version="p19-v1",
        tenant_scope="tenant-default",
        started_at=_TS,
        ended_at=_TS,
        input_manifest_hash="0" * 64,
        checks=[
            CheckResult(
                check_id="G19.4",
                outcome=CheckOutcome.PASS,
                measurements={"violations": 0},
                evidence_path="test_home/P19/G19.4_multi_version.txt",
            ),
        ],
        model_request_count=0,
        model_tokens_used=0,
        overall_state=RunState.PASS,
    )


def _make_gate_results() -> list[GateStatus]:
    return [GateStatus(gate_id="G19.4", state="PASS", measurements={})]


def _make_drift_metrics() -> DriftMetrics:
    return DriftMetrics(
        state_hash_stability_scaled=10000,
        denial_rate_scaled=500,
    )


# ---------------------------------------------------------------------
# PriorVersion enum
# ---------------------------------------------------------------------


class TestPriorVersion:
    """The PriorVersion enum has correct values and ordering."""

    def test_v1_value(self) -> None:
        assert PriorVersion.V1.value == "1.0"

    def test_v2_value(self) -> None:
        assert PriorVersion.V2.value == "2.0"

    def test_v2_is_newer_than_v1(self) -> None:
        assert PriorVersion.V2.numeric > PriorVersion.V1.numeric

    def test_from_string(self) -> None:
        assert PriorVersion("1.0") == PriorVersion.V1
        assert PriorVersion("2.0") == PriorVersion.V2


# ---------------------------------------------------------------------
# V2 loader
# ---------------------------------------------------------------------


class TestV2Loader:
    """load_public_prior_pack_v2 loads and verifies the v2 pack."""

    def test_load_v2(self) -> None:
        pack = load_public_prior_pack_v2()
        assert pack.pack_version == "2.0"
        assert pack.is_synthetic
        assert pack.pack_id == "public_prior_pack_v2"

    def test_v2_manifest_hash_matches(self) -> None:
        pack = load_public_prior_pack_v2()
        assert pack.verify() is True
        assert pack.manifest_hash == pack.compute_pack_hash()

    def test_v2_has_revised_aggregates(self) -> None:
        pack = load_public_prior_pack_v2()
        agg = pack.aggregate_statistics
        phase = agg["phase_duration_days"]
        assert "v2 revised" in phase["description"]

    def test_v2_missing_file_raises(self, tmp_path: Path) -> None:
        bad = tmp_path / "nonexistent.json"
        with pytest.raises(PriorPackError):
            load_public_prior_pack_v2(bad)


# ---------------------------------------------------------------------
# load_prior_pack_by_version
# ---------------------------------------------------------------------


class TestLoadByVersion:
    """load_prior_pack_by_version selects the correct version."""

    def test_load_v1_by_version(self) -> None:
        pack = load_prior_pack_by_version(PriorVersion.V1)
        assert pack.pack_version == "1.0"

    def test_load_v2_by_version(self) -> None:
        pack = load_prior_pack_by_version(PriorVersion.V2)
        assert pack.pack_version == "2.0"

    def test_v1_and_v2_have_different_hashes(self) -> None:
        v1 = load_prior_pack_by_version(PriorVersion.V1)
        v2 = load_prior_pack_by_version(PriorVersion.V2)
        assert v1.compute_pack_hash() != v2.compute_pack_hash()
        assert v1.compute_version_hash() != v2.compute_version_hash()


# ---------------------------------------------------------------------
# MultiVersionPriorPack
# ---------------------------------------------------------------------


class TestMultiVersionPriorPack:
    """MultiVersionPriorPack loads all versions and selects one."""

    def test_load_all_versions(self) -> None:
        mvp = load_multi_version_prior_pack()
        assert sorted(mvp.available_versions) == ["1.0", "2.0"]

    def test_default_prefers_v2(self) -> None:
        mvp = load_multi_version_prior_pack()
        assert mvp.selected_version == PriorVersion.V2
        assert mvp.pack_version == "2.0"

    def test_prefer_v1(self) -> None:
        mvp = load_multi_version_prior_pack(preferred=PriorVersion.V1)
        assert mvp.selected_version == PriorVersion.V1
        assert mvp.pack_version == "1.0"

    def test_version_hash_is_deterministic(self) -> None:
        mvp1 = load_multi_version_prior_pack(preferred=PriorVersion.V2)
        mvp2 = load_multi_version_prior_pack(preferred=PriorVersion.V2)
        assert mvp1.version_hash == mvp2.version_hash

    def test_version_hash_differs_by_version(self) -> None:
        v1 = load_multi_version_prior_pack(preferred=PriorVersion.V1)
        v2 = load_multi_version_prior_pack(preferred=PriorVersion.V2)
        assert v1.version_hash != v2.version_hash

    def test_version_hash_is_sha256(self) -> None:
        mvp = load_multi_version_prior_pack()
        h = mvp.version_hash
        assert len(h) == 64
        int(h, 16)

    def test_to_evidence_record(self) -> None:
        mvp = load_multi_version_prior_pack()
        record = mvp.to_evidence_record()
        assert record["prior_version"] == "2.0"
        assert record["pack_id"] == "public_prior_pack_v2"
        assert record["version_hash"] == mvp.version_hash

    def test_get_pack(self) -> None:
        mvp = load_multi_version_prior_pack()
        v1 = mvp.get_pack("1.0")
        assert v1.pack_version == "1.0"
        v2 = mvp.get_pack("2.0")
        assert v2.pack_version == "2.0"

    def test_get_pack_unknown_raises(self) -> None:
        mvp = load_multi_version_prior_pack()
        with pytest.raises(PriorPackError):
            mvp.get_pack("99.0")

    def test_empty_packs_raises(self) -> None:
        with pytest.raises(PriorPackError):
            MultiVersionPriorPack({}, PriorVersion.V1)

    def test_selected_version_not_in_packs_raises(self) -> None:
        v1 = load_public_prior_pack_v1()
        packs_no_v2 = {"1.0": v1}
        with pytest.raises(PriorPackError):
            MultiVersionPriorPack(packs_no_v2, PriorVersion.V2)

    def test_pack_hash_matches_individual(self) -> None:
        mvp = load_multi_version_prior_pack(preferred=PriorVersion.V1)
        v1 = load_public_prior_pack_v1()
        assert mvp.pack_hash == v1.compute_pack_hash()

    def test_is_synthetic(self) -> None:
        mvp = load_multi_version_prior_pack()
        assert mvp.is_synthetic is True

    def test_aggregate_statistics_accessible(self) -> None:
        mvp = load_multi_version_prior_pack()
        agg = mvp.aggregate_statistics
        assert "phase_duration_days" in agg


# ---------------------------------------------------------------------
# Evidence Pack integration — version hash recorded in pack
# ---------------------------------------------------------------------


class TestEvidencePackPriorVersion:
    """The prior version hash is recorded in every Evidence Pack (G19.4)."""

    def test_prior_version_file_written(self, tmp_path: Path) -> None:
        mvp = load_multi_version_prior_pack()
        generate_signed_pack(
            tmp_path,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp.to_evidence_record(),
        )
        prior_path = tmp_path / "prior_version.json"
        assert prior_path.exists()
        data: dict[str, str] = json.loads(
            prior_path.read_text(encoding="utf-8")
        )
        assert data["prior_version"] == "2.0"
        assert data["pack_id"] == "public_prior_pack_v2"
        assert data["version_hash"] == mvp.version_hash

    def test_pack_verifies_with_prior_version(self, tmp_path: Path) -> None:
        mvp = load_multi_version_prior_pack()
        generate_signed_pack(
            tmp_path,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp.to_evidence_record(),
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is True

    def test_different_versions_different_merkle_root(
        self, tmp_path: Path
    ) -> None:
        """Different prior versions produce different Merkle roots."""
        mvp1 = load_multi_version_prior_pack(preferred=PriorVersion.V1)
        mvp2 = load_multi_version_prior_pack(preferred=PriorVersion.V2)

        dir_v1 = tmp_path / "v1"
        dir_v2 = tmp_path / "v2"

        generate_signed_pack(
            dir_v1,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp1.to_evidence_record(),
        )
        generate_signed_pack(
            dir_v2,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp2.to_evidence_record(),
        )

        m1 = json.loads(
            (dir_v1 / "manifest.json").read_text(encoding="utf-8")
        )
        m2 = json.loads(
            (dir_v2 / "manifest.json").read_text(encoding="utf-8")
        )
        assert m1["merkle_root"] != m2["merkle_root"]

    def test_prior_version_in_manifest_files(self, tmp_path: Path) -> None:
        """prior_version.json appears in the manifest's file list."""
        mvp = load_multi_version_prior_pack()
        generate_signed_pack(
            tmp_path,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp.to_evidence_record(),
        )
        manifest = json.loads(
            (tmp_path / "manifest.json").read_text(encoding="utf-8")
        )
        file_names = {f["file_name"] for f in manifest["files"]}
        assert "prior_version.json" in file_names

    def test_tampered_prior_version_fails_verification(
        self, tmp_path: Path
    ) -> None:
        """Tampering with prior_version.json after generation fails verify."""
        mvp = load_multi_version_prior_pack()
        generate_signed_pack(
            tmp_path,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
            prior_version_record=mvp.to_evidence_record(),
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is True
        (tmp_path / "prior_version.json").write_text(
            '{"prior_version": "TAMPERED"}', encoding="utf-8"
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is False

    def test_no_prior_version_record_still_validates(
        self, tmp_path: Path
    ) -> None:
        """A pack with no prior_version_record still validates."""
        generate_signed_pack(
            tmp_path,
            assurance_report=_make_assurance_report(),
            claim_graph=_make_claim_graph(),
            gate_results=_make_gate_results(),
            drift_metrics=_make_drift_metrics(),
            signing_key=_SIGNING_KEY,
            generated_at=1730000000,
        )
        assert verify_signed_pack(tmp_path, _SIGNING_KEY) is True
        prior_path = tmp_path / "prior_version.json"
        assert prior_path.exists()
        data2: dict[str, str] = json.loads(
            prior_path.read_text(encoding="utf-8")
        )
        assert data2["prior_version"] == "none"
