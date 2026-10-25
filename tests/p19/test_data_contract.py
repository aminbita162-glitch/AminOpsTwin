"""G19.1 — Data Contract v2 compatibility tests (P19).

Verifies the additive-only evolution rule:
  - old reader (v1) accepts new data (v2) by ignoring unknown fields;
  - new reader (v2) accepts old data (v1) with optional fields absent;
  - patient-level fields are always rejected;
  - the evolution guard flags non-additive changes.
"""

from __future__ import annotations

import pytest
from aminopstwin.contracts.data_contract import (
    CONTRACT_V1_FIELDS,
    CONTRACT_V2_FIELDS,
    CONTRACT_V2_OPTIONAL_FIELDS,
    DataContractError,
    DataContractVersion,
    DataReaderV1,
    DataReaderV2,
    is_backward_compatible,
    validate_record_v1,
    validate_record_v2,
)

# ---------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------

_V1_RECORD = {
    "week_start": "2026-01-06",
    "week_end": "2026-01-12",
    "metric_name": "enrollment_rate",
    "metric_value": 42,
    "site_count": 10,
    "enrollment_count": 120,
    "active_sites": 9,
    "predicted_value": 100,
    "actual_value": 110,
    "variance": 5,
    "n_observations": 30,
}

_V2_RECORD = {
    **_V1_RECORD,
    "forecast_confidence_lower": 95,
    "forecast_confidence_upper": 125,
    "drift_indicator": 1,
    "data_quality_flag": "OK",
}


# ---------------------------------------------------------------------
# Compatibility: old reader accepts new data
# ---------------------------------------------------------------------


class TestOldReaderAcceptsNewData:
    """A v1 reader accepts v2 data by ignoring v2-only fields."""

    def test_v1_reader_ignores_v2_fields(self) -> None:
        reader = DataReaderV1()
        rec = reader.read(_V2_RECORD)
        assert rec.week_start == "2026-01-06"
        assert rec.metric_name == "enrollment_rate"
        # v2-only fields are not on the v1 model
        assert not hasattr(rec, "forecast_confidence_lower")

    def test_v1_reader_batch_with_v2_data(self) -> None:
        reader = DataReaderV1()
        batch = reader.read_batch([_V2_RECORD, _V2_RECORD])
        assert len(batch) == 2
        assert all(r.metric_value == 42 for r in batch)

    def test_validate_v1_accepts_v2_record(self) -> None:
        rec = validate_record_v1(_V2_RECORD)
        assert rec.metric_name == "enrollment_rate"


# ---------------------------------------------------------------------
# Compatibility: new reader accepts old data
# ---------------------------------------------------------------------


class TestNewReaderAcceptsOldData:
    """A v2 reader accepts v1 data because v2 additions are optional."""

    def test_v2_reader_accepts_v1_record(self) -> None:
        reader = DataReaderV2()
        rec = reader.read(_V1_RECORD)
        assert rec.week_start == "2026-01-06"
        assert rec.forecast_confidence_lower is None
        assert rec.drift_indicator is None

    def test_v2_reader_batch_with_v1_data(self) -> None:
        reader = DataReaderV2()
        batch = reader.read_batch([_V1_RECORD, _V1_RECORD])
        assert len(batch) == 2
        assert all(r.data_quality_flag is None for r in batch)

    def test_validate_v2_accepts_v1_record(self) -> None:
        rec = validate_record_v2(_V1_RECORD)
        assert rec.metric_name == "enrollment_rate"
        assert rec.forecast_confidence_upper is None


# ---------------------------------------------------------------------
# Round-trip: v2 data through both readers
# ---------------------------------------------------------------------


class TestRoundTrip:
    """v2 data read by v1 then re-read by v2 is consistent."""

    def test_v1_then_v2_consistency(self) -> None:
        r1 = DataReaderV1().read(_V2_RECORD)
        r2 = DataReaderV2().read(_V1_RECORD)
        assert r1.week_start == r2.week_start
        assert r1.metric_value == r2.metric_value


# ---------------------------------------------------------------------
# Patient-level fields always rejected
# ---------------------------------------------------------------------


class TestPatientLevelRejection:
    """Patient-level fields are never accepted in any version."""

    @pytest.mark.parametrize(
        "field",
        [
            "patient_id",
            "patient_name",
            "diagnosis",
            "dose",
        ],
    )
    def test_v1_rejects_patient_field(self, field: str) -> None:
        bad = {**_V1_RECORD, field: "x"}
        with pytest.raises(DataContractError):
            validate_record_v1(bad)

    @pytest.mark.parametrize(
        "field",
        [
            "patient_id",
            "patient_name",
            "diagnosis",
            "dose",
        ],
    )
    def test_v2_rejects_patient_field(self, field: str) -> None:
        bad = {**_V2_RECORD, field: "x"}
        with pytest.raises(DataContractError):
            validate_record_v2(bad)


# ---------------------------------------------------------------------
# Evolution guard
# ---------------------------------------------------------------------


class TestEvolutionGuard:
    """The is_backward_compatible guard enforces additive-only evolution."""

    def test_v1_to_v2_is_compatible(self) -> None:
        assert is_backward_compatible(
            CONTRACT_V1_FIELDS,
            CONTRACT_V2_FIELDS,
            CONTRACT_V2_OPTIONAL_FIELDS,
        )

    def test_removed_field_is_incompatible(self) -> None:
        removed = CONTRACT_V1_FIELDS - {"variance"}
        assert not is_backward_compatible(
            CONTRACT_V1_FIELDS,
            removed,
            frozenset(),
        )

    def test_required_addition_is_incompatible(self) -> None:
        # If a new field is NOT in the optional set, the evolution
        # is incompatible.
        new_fields = CONTRACT_V1_FIELDS | {"new_required"}
        assert not is_backward_compatible(
            CONTRACT_V1_FIELDS,
            new_fields,
            frozenset(),
        )

    def test_optional_addition_is_compatible(self) -> None:
        new_fields = CONTRACT_V1_FIELDS | {"new_optional"}
        optional = frozenset({"new_optional"})
        assert is_backward_compatible(
            CONTRACT_V1_FIELDS,
            new_fields,
            optional,
        )


# ---------------------------------------------------------------------
# Version identifiers
# ---------------------------------------------------------------------


class TestVersionIdentifiers:
    """Version identifiers are stable and comparable."""

    def test_v1_version_string(self) -> None:
        assert DataContractVersion.V1.value == "1.0"

    def test_v2_version_string(self) -> None:
        assert DataContractVersion.V2.value == "2.0"

    def test_v2_is_newer_than_v1(self) -> None:
        assert DataContractVersion.V2.numeric > DataContractVersion.V1.numeric
