"""G19.1 part 2 — synthetic generator produces aggregate-only SYNTHETIC records.

The generator produces records matching the shape of public prior
distributions; every record is:
  - aggregate-only (no patient-level fields);
  - labelled SYNTHETIC with provenance;
  - valid against Data Contract v2.
"""

from __future__ import annotations

import pytest
from aminopstwin.contracts.data_contract import (
    PATIENT_LEVEL_FIELDS,
    validate_record_v2,
)
from aminopstwin.fixtures_gen.synthetic_priors import (
    SYNTHETIC_LABEL,
    SyntheticAggregateGenerator,
)


class TestSyntheticGenerator:
    """Synthetic generator produces aggregate-only SYNTHETIC records."""

    def test_generates_requested_count(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        records = gen.generate(10)
        assert len(records) == 10

    def test_every_record_is_synthetic(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        for rec in gen.generate(5):
            assert rec.is_synthetic
            assert rec.provenance["data_label"] == SYNTHETIC_LABEL

    def test_no_patient_level_fields(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        for rec in gen.generate(20):
            bare = rec.to_contract_record()
            present = set(bare.keys()) & PATIENT_LEVEL_FIELDS
            assert present == set(), f"patient fields: {present}"

    def test_all_records_validate_against_contract(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        for rec in gen.generate(20):
            bare = rec.to_contract_record()
            # Should not raise.
            validate_record_v2(bare)

    def test_generate_validated_returns_contract_dicts(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        dicts = gen.generate_validated(15)
        assert len(dicts) == 15
        for d in dicts:
            assert "week_start" in d
            assert "metric_name" in d
            assert "data_label" not in d  # bare contract dict

    def test_deterministic_same_seed_same_output(self) -> None:
        gen1 = SyntheticAggregateGenerator(seed=123)
        gen2 = SyntheticAggregateGenerator(seed=123)
        r1 = [r.to_contract_record() for r in gen1.generate(10)]
        r2 = [r.to_contract_record() for r in gen2.generate(10)]
        assert r1 == r2

    def test_different_seeds_different_output(self) -> None:
        gen1 = SyntheticAggregateGenerator(seed=1)
        gen2 = SyntheticAggregateGenerator(seed=2)
        r1 = [r.to_contract_record() for r in gen1.generate(10)]
        r2 = [r.to_contract_record() for r in gen2.generate(10)]
        assert r1 != r2

    def test_count_fields_meet_k_min(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42, k_min=10)
        count_fields = (
            "site_count",
            "enrollment_count",
            "active_sites",
            "n_observations",
        )
        for rec in gen.generate(10):
            bare = rec.to_contract_record()
            for field in count_fields:
                val: int | None = bare.get(field)  # type: ignore[assignment]
                if val is not None:
                    assert val >= 10, f"{field}={val} < k_min=10"

    def test_v2_optional_fields_present(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        rec = gen.generate(1)[0]
        bare = rec.to_contract_record()
        assert "forecast_confidence_lower" in bare
        assert "forecast_confidence_upper" in bare
        assert "drift_indicator" in bare
        assert "data_quality_flag" in bare

    def test_provenance_includes_generator_id(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        rec = gen.generate(1)[0]
        prov = rec.provenance
        assert "generator_id" in prov
        assert "generator_version" in prov
        assert "seed" in prov
        assert prov["seed"] == 42

    def test_zero_records(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        assert gen.generate(0) == []

    def test_negative_n_raises(self) -> None:
        gen = SyntheticAggregateGenerator(seed=42)
        with pytest.raises(ValueError):
            gen.generate(-1)

    def test_invalid_k_min_raises(self) -> None:
        with pytest.raises(ValueError):
            SyntheticAggregateGenerator(seed=42, k_min=0)
