"""Synthetic aggregate generator — Data Contract v2 shaped records (P19, G19.1).

Produces **aggregate-only** weekly records whose shape matches the public
prior distributions in ``public_prior_pack_v1.json``.  Every record is:

* **aggregate-only** — no patient-level fields (verified against the
  Data Contract's patient-field deny-list);
* **labelled SYNTHETIC** — each record carries a ``data_label`` of
  ``"SYNTHETIC"`` and a provenance block identifying the generator;
* **contract-valid** — every record validates against Data Contract v2
  (:func:`~aminopstwin.contracts.data_contract.validate_record_v2`).

The generator is deterministic given a seed — the same seed always
produces the same records (N-15, integer-only state path).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import random
from typing import Any

from aminopstwin.contracts.data_contract import (
    PATIENT_LEVEL_FIELDS,
    DataContractError,
    DataContractVersion,
    validate_record_v2,
)

__all__ = [
    "SyntheticAggregateGenerator",
    "SyntheticAggregateRecord",
    "GENERATOR_ID",
    "GENERATOR_VERSION",
    "SYNTHETIC_LABEL",
]

GENERATOR_ID: str = "aminopstwin-synthetic-agg-v2"
GENERATOR_VERSION: str = "1.0.0"
SYNTHETIC_LABEL: str = "SYNTHETIC"

#: Metric names drawn from the prior pack's aggregate shapes.
_METRIC_NAMES: tuple[str, ...] = (
    "enrollment_rate",
    "site_activation_rate",
    "screen_failure_rate",
    "trial_start_delay",
    "phase_duration",
)

#: Fixed synthetic "created_at" so the generator is deterministic.
_FIXED_CREATED_AT: str = "2026-10-25T00:00:00Z"


class SyntheticAggregateRecord:
    """A single synthetic aggregate record (P19, G19.1).

    The record is aggregate-only, carries the SYNTHETIC label, and
    validates against Data Contract v2.
    """

    def __init__(
        self,
        data: dict[str, Any],
        *,
        seed: int,
        generator_id: str = GENERATOR_ID,
        generator_version: str = GENERATOR_VERSION,
    ) -> None:
        self._data = dict(data)
        self._provenance: dict[str, Any] = {
            "data_label": SYNTHETIC_LABEL,
            "generator_id": generator_id,
            "generator_version": generator_version,
            "seed": seed,
            "created_at": _FIXED_CREATED_AT,
        }

    @property
    def data(self) -> dict[str, Any]:
        return dict(self._data)

    @property
    def provenance(self) -> dict[str, Any]:
        return dict(self._provenance)

    @property
    def is_synthetic(self) -> bool:
        label = self._provenance.get("data_label")
        return label == SYNTHETIC_LABEL

    def to_dict(self) -> dict[str, Any]:
        """Return the record with its provenance block."""
        return {
            **self._data,
            "data_label": SYNTHETIC_LABEL,
            "_provenance": self._provenance,
        }

    def to_contract_record(self) -> dict[str, Any]:
        """Return the bare contract fields (no provenance block)."""
        return dict(self._data)


class SyntheticAggregateGenerator:
    """Deterministic generator of aggregate-only synthetic records (P19).

    Given a seed, produces N weekly aggregate records matching the shape
    of the public prior distributions.  Every record is aggregate-only
    (no patient-level fields), labelled SYNTHETIC, and contract-valid.

    The generator uses a named RNG stream derived from
    ``H(seed || stream_id)`` so that different streams are independent
    and the same seed always reproduces the same output (N-15).
    """

    def __init__(
        self,
        seed: int,
        *,
        version: DataContractVersion = DataContractVersion.V2,
        k_min: int = 5,
    ) -> None:
        if k_min < 1:
            raise ValueError(f"k_min must be >= 1, got {k_min}")
        self._seed = seed
        self._version = version
        self._k_min = k_min
        # Derive the RNG stream deterministically from the seed.
        stream_seed = hashlib.sha256(
            f"{seed}:synthetic-aggregate".encode()
        ).digest()
        self._rng: random.Random = random.Random(
            int.from_bytes(stream_seed, "big") % (2**63)
        )

    @property
    def seed(self) -> int:
        return self._seed

    @property
    def version(self) -> DataContractVersion:
        return self._version

    @property
    def k_min(self) -> int:
        return self._k_min

    def generate(self, n: int) -> list[SyntheticAggregateRecord]:
        """Generate ``n`` aggregate-only synthetic records.

        Each record has:
        - ``week_start`` / ``week_end`` — deterministic ISO date strings;
        - ``metric_name`` — one of the prior-shape metric names;
        - count fields (``site_count``, ``enrollment_count``,
          ``active_sites``, ``n_observations``) — integers >= k_min
          (no suppressed cells);
        - value fields (``metric_value``, ``predicted_value``,
          ``actual_value``, ``variance``) — integers;
        - v2 optional fields (``forecast_confidence_lower``,
          ``forecast_confidence_upper``, ``drift_indicator``,
          ``data_quality_flag``) — integers / ``"OK"``.

        Every record validates against Data Contract v2.
        """
        if n < 0:
            raise ValueError(f"n must be >= 0, got {n}")
        records: list[SyntheticAggregateRecord] = []
        for i in range(n):
            record = self._generate_one(i)
            records.append(record)
        return records

    def generate_validated(self, n: int) -> list[dict[str, Any]]:
        """Generate ``n`` records and return their contract-validated dicts.

        Each dict is validated by :func:`validate_record_v2` and
        guaranteed to contain no patient-level fields.
        """
        result: list[dict[str, Any]] = []
        for rec in self.generate(n):
            bare = rec.to_contract_record()
            # Validate against the contract — raises on failure.
            validate_record_v2(bare)
            # Double-check no patient-level fields leaked in.
            present = set(bare.keys()) & PATIENT_LEVEL_FIELDS
            if present:
                raise DataContractError(
                    f"patient-level fields leaked into synthetic record: "
                    f"{sorted(present)}"
                )
            result.append(bare)
        return result

    def _generate_one(self, index: int) -> SyntheticAggregateRecord:
        """Generate a single aggregate record (deterministic)."""
        # Deterministic week: start from a fixed Monday.
        base = _dt.date(2026, 1, 5)  # Monday
        week_start = base + _dt.timedelta(weeks=index)
        week_end = week_start + _dt.timedelta(days=6)
        metric_name = _METRIC_NAMES[self._rng.randint(0, len(_METRIC_NAMES) - 1)]

        # Count fields — always >= k_min so no suppression.
        site_count = self._rng.randint(self._k_min, self._k_min + 50)
        enrollment_count = self._rng.randint(self._k_min, self._k_min + 200)
        active_sites = max(self._k_min, site_count - self._rng.randint(0, 3))
        n_observations = self._rng.randint(self._k_min, self._k_min + 500)

        # Value fields.
        predicted_value = self._rng.randint(50, 500)
        actual_value = max(0, predicted_value + self._rng.randint(-20, 20))
        variance = abs(actual_value - predicted_value)
        metric_value = self._rng.randint(10, 300)

        # v2 optional fields.
        forecast_confidence_lower = max(0, predicted_value - self._rng.randint(5, 30))
        forecast_confidence_upper = predicted_value + self._rng.randint(5, 30)
        drift_indicator = 1 if variance > 10 else 0
        data_quality_flag = "OK" if variance <= 15 else "REVIEW"

        data: dict[str, Any] = {
            "week_start": week_start.isoformat(),
            "week_end": week_end.isoformat(),
            "metric_name": metric_name,
            "metric_value": metric_value,
            "site_count": site_count,
            "enrollment_count": enrollment_count,
            "active_sites": active_sites,
            "predicted_value": predicted_value,
            "actual_value": actual_value,
            "variance": variance,
            "n_observations": n_observations,
            "forecast_confidence_lower": forecast_confidence_lower,
            "forecast_confidence_upper": forecast_confidence_upper,
            "drift_indicator": drift_indicator,
            "data_quality_flag": data_quality_flag,
        }
        return SyntheticAggregateRecord(
            data,
            seed=self._seed,
            generator_id=GENERATOR_ID,
            generator_version=GENERATOR_VERSION,
        )
