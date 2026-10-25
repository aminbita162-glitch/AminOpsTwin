"""Source rights and provenance tracking (P4, §30, G4.2).

A1: licensed source adapters, typed normalization, source provenance.

The source register tracks each licensed public source through a lifecycle:
DISCOVERED -> REVIEW_PENDING -> APPROVED -> ACTIVE;
ACTIVE -> SUPERSEDED | QUARANTINED | RETIRED (with a recorded reason).

Discovery is not activation. Only APPROVED/ACTIVE sources may enter the
evidence cache. Unknown permission means not approved, not implicit
permission (§30.3). Use versioned source records rather than changing
source bytes in place.
"""

from __future__ import annotations

import hashlib
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "SourceStatus",
    "SourceRecord",
    "SourceRegistry",
    "SourceRegistryError",
]


class SourceStatus(StrEnum):
    """Lifecycle states for a source record (§30.3)."""

    DISCOVERED = "DISCOVERED"
    REVIEW_PENDING = "REVIEW_PENDING"
    APPROVED = "APPROVED"
    ACTIVE = "ACTIVE"
    SUPERSEDED = "SUPERSEDED"
    QUARANTINED = "QUARANTINED"
    RETIRED = "RETIRED"


#: Statuses that count as approved for evidence-cache admission.
_APPROVED_STATUSES: frozenset[SourceStatus] = frozenset(
    {SourceStatus.APPROVED, SourceStatus.ACTIVE}
)

#: Valid lifecycle transitions.
_VALID_TRANSITIONS: dict[SourceStatus, frozenset[SourceStatus]] = {
    SourceStatus.DISCOVERED: frozenset({SourceStatus.REVIEW_PENDING}),
    SourceStatus.REVIEW_PENDING: frozenset({SourceStatus.APPROVED}),
    SourceStatus.APPROVED: frozenset({SourceStatus.ACTIVE}),
    SourceStatus.ACTIVE: frozenset(
        {SourceStatus.SUPERSEDED, SourceStatus.QUARANTINED, SourceStatus.RETIRED}
    ),
    SourceStatus.SUPERSEDED: frozenset({SourceStatus.RETIRED}),
    SourceStatus.QUARANTINED: frozenset(
        {SourceStatus.RETIRED, SourceStatus.REVIEW_PENDING}
    ),
    SourceStatus.RETIRED: frozenset(),
}


class SourceRegistryError(Exception):
    """Raised when a source lifecycle transition is invalid."""


class SourceRecord(BaseModel):
    """A single licensed source with extended provenance fields (§30.3).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    # Original fields (§23.3)
    source_id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=512)
    publisher: str = Field(min_length=1, max_length=256)
    license: str = Field(min_length=1, max_length=128)
    license_url: str = Field(min_length=1, max_length=512)
    retrieved_at: str
    content_sha256: str = Field(min_length=64, max_length=64)
    permitted_use: str = Field(min_length=1, max_length=256)
    owner_approval_date: str

    # Extended fields (§30.3)
    document_version: str = Field(default="1", min_length=1, max_length=64)
    language: str = Field(default="en", min_length=2, max_length=8)
    retrieval_endpoint: str = Field(default="", max_length=512)
    attribution: str = Field(default="", max_length=512)
    commercial_use_status: str = Field(
        default="unknown", min_length=1, max_length=64
    )
    redistribution_status: str = Field(
        default="unknown", min_length=1, max_length=64
    )
    machine_retrieval_status: str = Field(
        default="unknown", min_length=1, max_length=64
    )
    evidence_location: str = Field(default="", max_length=512)
    review_status: str = Field(
        default="pending", min_length=1, max_length=64
    )
    supersedes: str | None = None
    status: SourceStatus = SourceStatus.DISCOVERED

    @field_validator("content_sha256")
    @classmethod
    def _validate_sha(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError(
                "content_sha256 must be a 64-char lowercase hex string"
            )
        return v

    @field_validator("retrieved_at")
    @classmethod
    def _validate_retrieved_at(cls, v: str) -> str:
        if not v.endswith("Z") and "T" not in v:
            raise ValueError(
                "retrieved_at must be an RFC 3339 timestamp ending with Z"
            )
        return v

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class SourceRegistry:
    """Source register with lifecycle management (§30.3, G4.2).

    Every active source version has complete approval, provenance and
    rights records. Every unapproved/unknown-license fixture is excluded
    from activation.
    """

    def __init__(self) -> None:
        self._records: dict[str, SourceRecord] = {}

    def register(self, record: SourceRecord) -> SourceRecord:
        """Register a new source record in DISCOVERED status."""
        if record.source_id in self._records:
            raise SourceRegistryError(
                f"source_id already registered: {record.source_id}"
            )
        if record.status is not SourceStatus.DISCOVERED:
            raise SourceRegistryError(
                f"new source must start in DISCOVERED, got {record.status}"
            )
        self._records[record.source_id] = record
        return record

    def get(self, source_id: str) -> SourceRecord | None:
        return self._records.get(source_id)

    def transition(
        self,
        source_id: str,
        target: SourceStatus,
        reason: str = "",
    ) -> SourceRecord:
        """Transition a source to a new lifecycle status.

        Raises SourceRegistryError if the transition is invalid.
        """
        record = self._records.get(source_id)
        if record is None:
            raise SourceRegistryError(f"source not found: {source_id}")
        current = record.status
        if target not in _VALID_TRANSITIONS.get(current, frozenset()):
            raise SourceRegistryError(
                f"invalid transition: {current.value} -> {target.value}"
                f" (reason: {reason or 'none'})"
            )
        # Build a new frozen record with the updated status.
        updated = record.model_copy(
            update={
                "status": target,
                "review_status": (
                    "approved" if target is SourceStatus.APPROVED else
                    "active" if target is SourceStatus.ACTIVE else
                    "superseded" if target is SourceStatus.SUPERSEDED else
                    "quarantined" if target is SourceStatus.QUARANTINED else
                    "retired" if target is SourceStatus.RETIRED else
                    record.review_status
                ),
            }
        )
        self._records[source_id] = updated
        return updated

    def is_approved(self, source_id: str) -> bool:
        """Return True if the source is APPROVED or ACTIVE."""
        record = self._records.get(source_id)
        if record is None:
            return False
        return record.status in _APPROVED_STATUSES

    def is_active(self, source_id: str) -> bool:
        """Return True if the source is ACTIVE."""
        record = self._records.get(source_id)
        if record is None:
            return False
        return record.status is SourceStatus.ACTIVE

    def admit_to_cache(self, source_id: str) -> bool:
        """Return True if the source may enter the evidence cache.

        Only APPROVED or ACTIVE sources pass. Unknown/unregistered
        sources are denied (GW-EVID-002). Unapproved means not approved,
        not implicit permission (§30.3).
        """
        return self.is_approved(source_id)

    def all_records(self) -> list[SourceRecord]:
        """Return all registered source records."""
        return list(self._records.values())

    def approved_records(self) -> list[SourceRecord]:
        """Return only approved/active source records."""
        return [
            r for r in self._records.values()
            if r.status in _APPROVED_STATUSES
        ]

    def __len__(self) -> int:
        return len(self._records)

    def content_hash(self, source_id: str) -> str | None:
        """Return the content_sha256 for an approved source, or None."""
        record = self._records.get(source_id)
        if record is None:
            return None
        if not self.is_approved(source_id):
            return None
        return record.content_sha256

    @staticmethod
    def compute_content_hash(content: bytes) -> str:
        """Compute the SHA-256 hex of content bytes for a source record."""
        return hashlib.sha256(content).hexdigest()
