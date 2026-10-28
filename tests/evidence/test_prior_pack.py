"""Tests for the Public Prior Pack (G13.3).

Verifies that:
- the prior pack loads successfully
- the pack hash matches the manifest hash
- the pack is labelled SYNTHETIC
- the pack contains only aggregate statistics (no individual data)
- source references are documented in the allowlist
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aminopstwin.priors import (
    PriorPackError,
    PublicPriorPack,
    load_public_prior_pack_v1,
)

REPO_ROOT = Path(__file__).parent.parent.parent
PACK_PATH = (
    REPO_ROOT / "src" / "aminopstwin" / "priors" / "public_prior_pack_v1.json"
)


class TestPriorPack:
    """G13.3: Prior Pack loads and its hash matches the manifest."""

    def test_pack_file_exists(self) -> None:
        assert PACK_PATH.exists(), "public_prior_pack_v1.json must exist"

    def test_pack_loads_successfully(self) -> None:
        pack = load_public_prior_pack_v1()
        assert pack is not None
        assert isinstance(pack, PublicPriorPack)

    def test_pack_hash_matches_manifest(self) -> None:
        pack = load_public_prior_pack_v1()
        actual = pack.compute_pack_hash()
        expected = pack.manifest_hash
        assert actual == expected, (
            f"pack hash mismatch: expected={expected}, actual={actual}"
        )

    def test_pack_is_synthetic(self) -> None:
        pack = load_public_prior_pack_v1()
        assert pack.is_synthetic, (
            "prior pack must be labelled SYNTHETIC until real data is ingested"
        )

    def test_pack_has_aggregate_statistics(self) -> None:
        pack = load_public_prior_pack_v1()
        agg = pack.aggregate_statistics
        assert len(agg) > 0, "pack must contain aggregate statistics"
        for key, val in agg.items():
            assert isinstance(val, dict), (
                f"each aggregate statistic must be a dict: {key}"
            )
            assert "description" in val, (
                f"statistic {key} must have a description"
            )
            assert "distribution" in val, (
                f"statistic {key} must have a distribution type"
            )

    def test_pack_has_source_references(self) -> None:
        pack = load_public_prior_pack_v1()
        refs = pack.source_references
        assert len(refs) >= 1, "pack must have at least one source reference"
        for ref in refs:
            assert "source_id" in ref
            assert "license" in ref

    def test_pack_no_individual_data(self) -> None:
        """The pack must not contain any patient-level or individual data."""
        raw = PACK_PATH.read_text(encoding="utf-8")
        data = json.loads(raw)
        agg = data.get("aggregate_statistics", {})
        agg_str = json.dumps(agg)
        forbidden = [
            "patient_id",
            "patient_name",
            "diagnosis",
            "individual_risk",
            "health_status",
        ]
        for term in forbidden:
            assert term not in agg_str.lower(), (
                f"forbidden term '{term}' found in aggregate statistics"
            )

    def test_pack_manifest_has_owner_signature_placeholder(self) -> None:
        pack = load_public_prior_pack_v1()
        manifest = pack.manifest
        assert "owner_signature" in manifest
        assert manifest["owner_signature"] != ""

    def test_pack_id_is_consistent(self) -> None:
        pack = load_public_prior_pack_v1()
        assert pack.pack_id == "public_prior_pack_v1"
        assert pack.pack_version == "1.0"

    def test_load_nonexistent_pack_raises(self, tmp_path: Path) -> None:
        with pytest.raises(PriorPackError):
            load_public_prior_pack_v1(path=tmp_path / "nonexistent.json")

    def test_tampered_pack_hash_raises(self, tmp_path: Path) -> None:
        """If the pack content is modified, the hash should not match."""
        data = json.loads(PACK_PATH.read_text(encoding="utf-8"))
        data["aggregate_statistics"]["phase_duration_days"]["percentiles"]["p50"] = 999
        tampered = tmp_path / "tampered_pack.json"
        tampered.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        with pytest.raises(PriorPackError, match="hash mismatch"):
            load_public_prior_pack_v1(path=tampered)

    def test_source_allowlist_has_entries(self) -> None:
        """Source references in the pack should be in the allowlist."""
        import yaml

        allowlist_path = REPO_ROOT / "docs" / "source_allowlist.yaml"
        with allowlist_path.open("r", encoding="utf-8") as f:
            allowlist = yaml.safe_load(f)
        sources = allowlist.get("sources", [])
        assert len(sources) >= 2, (
            "source_allowlist must have at least 2 entries for prior pack sources"
        )
        source_ids = {s.get("source_id") for s in sources}
        assert "clinicaltrials-gov-aggregate" in source_ids
        assert "aact-aggregate" in source_ids
