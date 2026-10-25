"""Synthetic data generator skeleton (§23.1).

Every synthetic record or fixture file has provenance metadata:
    _provenance: {synthetic: true, generator_id, generator_version, seed, created_at}

Source documents instead have licensed source provenance; approved future Profile B
data have a separate origin. Never falsely label a published document or real
observation synthetic.
"""

from __future__ import annotations

import datetime as _dt
from typing import Any

__all__ = ["SyntheticRecord", "GENERATOR_ID", "GENERATOR_VERSION"]


GENERATOR_ID: str = "aminopstwin-fixtures-gen-v1"
GENERATOR_VERSION: str = "0.1.0"


class SyntheticRecord:
    """A synthetic operational record with provenance (§23.1)."""

    def __init__(
        self,
        data: dict[str, Any],
        *,
        generator_id: str = GENERATOR_ID,
        generator_version: str = GENERATOR_VERSION,
        seed: int,
        created_at: _dt.datetime | None = None,
    ) -> None:
        self.data = data
        self._provenance: dict[str, Any] = {
            "synthetic": True,
            "generator_id": generator_id,
            "generator_version": generator_version,
            "seed": seed,
            "created_at": (created_at or _dt.datetime.now(tz=_dt.UTC)).isoformat(),
        }

    @property
    def provenance(self) -> dict[str, Any]:
        return dict(self._provenance)

    def to_dict(self) -> dict[str, Any]:
        return {
            **self.data,
            "_provenance": self._provenance,
        }
