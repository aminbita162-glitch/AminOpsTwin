"""Data Contract v2 — versioned aggregate record schema (P19, G19.1).

Data Contract v2 is the **additive-only** successor to Data Contract v1
(§3.5, P13 ``shadow_gateway``).  The contract defines the canonical
shape of a weekly aggregate record and enforces the evolution rule:

**Evolution is additive optional fields only.**  A new version may add
optional fields; it may **never** remove, rename, or change the type of
an existing field.  This guarantees:

* an **old reader** (v1) accepts **new data** (v2) — unknown optional
  fields are ignored;
* a **new reader** (v2) accepts **old data** (v1) — optional fields added
  in v2 are absent and fall back to their default.

The contract is the basis for the synthetic generator (G19.1 part 2),
the read-only API (G19.3), and multi-version priors (G19.4).
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

__all__ = [
    "DataContractError",
    "DataContractVersion",
    "AggregateRecordV1",
    "AggregateRecordV2",
    "CONTRACT_V1_FIELDS",
    "CONTRACT_V2_FIELDS",
    "CONTRACT_V2_OPTIONAL_FIELDS",
    "validate_record_v1",
    "validate_record_v2",
    "validate_record",
    "is_backward_compatible",
    "DataReaderV1",
    "DataReaderV2",
]


class DataContractError(ValueError):
    """Raised when a record violates the Data Contract."""


class DataContractVersion(StrEnum):
    """Data Contract version identifier."""

    V1 = "1.0"
    V2 = "2.0"

    @property
    def numeric(self) -> tuple[int, int]:
        """Return the (major, minor) numeric version tuple."""
        major, minor = self.value.split(".")
        return int(major), int(minor)


# ---------------------------------------------------------------------
# Field registries — the contract surface
# ---------------------------------------------------------------------
#
# CONTRACT_V1_FIELDS is the set of fields defined by Data Contract v1.
# CONTRACT_V2_FIELDS is the superset: v1 fields + new optional v2 fields.
# CONTRACT_V2_OPTIONAL_FIELDS is the set of fields ADDED in v2 — every
# one of them must be optional with a default so that old (v1) data is
# still accepted by a v2 reader.

CONTRACT_V1_FIELDS: frozenset[str] = frozenset(
    {
        "week_start",
        "week_end",
        "metric_name",
        "metric_value",
        "site_count",
        "enrollment_count",
        "active_sites",
        "predicted_value",
        "actual_value",
        "variance",
        "n_observations",
    }
)

#: Fields added in v2 — every one is optional and defaults to None.
CONTRACT_V2_OPTIONAL_FIELDS: frozenset[str] = frozenset(
    {
        "forecast_confidence_lower",
        "forecast_confidence_upper",
        "drift_indicator",
        "data_quality_flag",
    }
)

#: Complete v2 field set (v1 ∪ v2 optional).
CONTRACT_V2_FIELDS: frozenset[str] = (
    CONTRACT_V1_FIELDS | CONTRACT_V2_OPTIONAL_FIELDS
)

#: Fields that are counts and used for k-min suppression (unchanged
#: from v1 — the count semantics are part of the contract surface).
COUNT_FIELDS: frozenset[str] = frozenset(
    {"site_count", "enrollment_count", "active_sites", "n_observations"}
)

#: Required fields in every aggregate record (v1 and v2).
REQUIRED_FIELDS: frozenset[str] = frozenset(
    {"week_start", "week_end", "metric_name"}
)

#: Patient-level / individual fields that must NEVER appear in any
#: aggregate record.  Reused from the shadow gateway boundary (§2.5).
PATIENT_LEVEL_FIELDS: frozenset[str] = frozenset(
    {
        "patient_id",
        "patient_name",
        "diagnosis",
        "prognosis",
        "treatment",
        "dose",
        "individual_risk",
        "health_status",
    }
)


# ---------------------------------------------------------------------
# Record models
# ---------------------------------------------------------------------


class _BaseAggregateRecord(BaseModel):
    """Common config for all aggregate record versions."""

    model_config = ConfigDict(
        extra="ignore",
        frozen=True,
        strict=True,
    )

    week_start: str
    week_end: str
    metric_name: str
    metric_value: int | None = None
    site_count: int | None = None
    enrollment_count: int | None = None
    active_sites: int | None = None
    predicted_value: int | None = None
    actual_value: int | None = None
    variance: int | None = None
    n_observations: int | None = None


class AggregateRecordV1(_BaseAggregateRecord):
    """Data Contract v1 aggregate record (P13, G13.4).

    Uses ``extra="ignore"`` so that a v1 reader accepts v2 data by
    ignoring the new optional fields (forward compatibility).
    """


class AggregateRecordV2(_BaseAggregateRecord):
    """Data Contract v2 aggregate record (P19, G19.1).

    Adds optional fields: ``forecast_confidence_lower``,
    ``forecast_confidence_upper``, ``drift_indicator``,
    ``data_quality_flag``.  Every new field defaults to ``None`` so
    that a v2 reader accepts v1 data (backward compatibility).
    """

    forecast_confidence_lower: int | None = None
    forecast_confidence_upper: int | None = None
    drift_indicator: int | None = None
    data_quality_flag: str | None = None


# ---------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------


def _check_patient_fields(record: dict[str, Any]) -> None:
    """Raise if any patient-level field is present."""
    present = set(record.keys()) & PATIENT_LEVEL_FIELDS
    if present:
        raise DataContractError(
            f"patient-level fields are forbidden in aggregate records: "
            f"{sorted(present)}"
        )


def validate_record_v1(record: dict[str, Any]) -> AggregateRecordV1:
    """Validate a dict against Data Contract v1 (G19.1).

    Raises :class:`DataContractError` if a patient-level field is
    present.  Unknown (v2) fields are ignored — a v1 reader accepts
    v2 data.
    """
    _check_patient_fields(record)
    try:
        return AggregateRecordV1(**record)
    except ValidationError as exc:
        raise DataContractError(str(exc)) from exc


def validate_record_v2(record: dict[str, Any]) -> AggregateRecordV2:
    """Validate a dict against Data Contract v2 (G19.1).

    Raises :class:`DataContractError` if a patient-level field is
    present or if a v1 field fails type validation.  v2 optional
    fields default to ``None`` when absent — a v2 reader accepts v1
    data.
    """
    _check_patient_fields(record)
    try:
        return AggregateRecordV2(**record)
    except ValidationError as exc:
        raise DataContractError(str(exc)) from exc


def validate_record(
    record: dict[str, Any],
    version: DataContractVersion = DataContractVersion.V2,
) -> _BaseAggregateRecord:
    """Validate a record against the named contract version."""
    if version == DataContractVersion.V1:
        return validate_record_v1(record)
    return validate_record_v2(record)


# ---------------------------------------------------------------------
# Evolution guard
# ---------------------------------------------------------------------


def is_backward_compatible(
    old_fields: frozenset[str],
    new_fields: frozenset[str],
    new_optional: frozenset[str],
) -> bool:
    """Check that a new field set is backward compatible with the old.

    A new version is backward compatible iff:
    1. every old field is still present (no removals); and
    2. every added field is in the ``new_optional`` set (additions are
       optional, never required).

    This is the formal expression of the "additive optional fields only"
    evolution rule (G19.1).
    """
    removed = old_fields - new_fields
    if removed:
        return False
    added = new_fields - old_fields
    non_optional_additions = added - new_optional
    return not non_optional_additions


# ---------------------------------------------------------------------
# Readers — the compatibility surface
# ---------------------------------------------------------------------


class DataReaderV1:
    """A v1 reader: accepts v1 data and ignores v2-only fields.

    The compatibility rule (G19.1) is: an old reader accepts new data
    by ignoring fields it does not know about.
    """

    @property
    def version(self) -> DataContractVersion:
        return DataContractVersion.V1

    def read(self, record: dict[str, Any]) -> AggregateRecordV1:
        """Read a record, ignoring unknown (v2) fields."""
        return validate_record_v1(record)

    def read_batch(
        self, records: list[dict[str, Any]]
    ) -> list[AggregateRecordV1]:
        """Read a batch of records, ignoring unknown fields in each."""
        return [self.read(r) for r in records]


class DataReaderV2:
    """A v2 reader: accepts v2 data and v1 data (optional fields absent).

    The compatibility rule (G19.1) is: a new reader accepts old data
    because the new fields it knows about are all optional.
    """

    @property
    def version(self) -> DataContractVersion:
        return DataContractVersion.V2

    def read(self, record: dict[str, Any]) -> AggregateRecordV2:
        """Read a record; v2 optional fields default to None if absent."""
        return validate_record_v2(record)

    def read_batch(
        self, records: list[dict[str, Any]]
    ) -> list[AggregateRecordV2]:
        """Read a batch of records; absent v2 fields default to None."""
        return [self.read(r) for r in records]
