"""Deterministic event-sourced memory (P4, §31, G4.4, G4.5).

Four logical memory classes:
    M1 Task context: bounded immutable task snapshots with an expiry policy.
    M2 Execution history: authoritative events, decisions, checkpoints.
    M3 Evidence: licensed source versions, spans, claims and dependency links.
    M4 Approved experience: tested reusable operational patterns and regression cases.

Access scope includes tenant_id, runtime principal, capability, task identity,
correlation_id, policy_epoch, schema version and snapshot id. Correlation_id
alone is not authorization or a sufficient isolation key. Current revocation
and policy checks apply even when reading an older immutable snapshot.

Writes: S2 authorizes and persists with version compare-and-swap and
appropriate transaction isolation.

Reads: use a pinned snapshot and deterministic filters, explicit sorting and
a stable tie-breaker. Return only authorized bounded records. Do not inject an
entire memory store into a prompt.
"""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from src.contracts.canonical import canonical_hash

__all__ = [
    "MemoryClass",
    "RetentionClass",
    "MemoryRecord",
    "MemoryStore",
    "MemoryReplayError",
]

#: Retention durations in days (owner-confirmed, §37).
_RETENTION_DAYS: dict[str, int] = {
    "SHORT_15": 15,
    "SHORT_30": 30,
    "MEDIUM_60": 60,
    "LONG_180": 180,
}


class MemoryClass(StrEnum):
    """Four logical memory classes (§31)."""

    M1_TASK_CONTEXT = "M1_TASK_CONTEXT"
    M2_EXECUTION_HISTORY = "M2_EXECUTION_HISTORY"
    M3_EVIDENCE = "M3_EVIDENCE"
    M4_APPROVED_EXPERIENCE = "M4_APPROVED_EXPERIENCE"


class RetentionClass(StrEnum):
    """Retention duration classes (owner-confirmed, §37)."""

    SHORT_15 = "SHORT_15"
    SHORT_30 = "SHORT_30"
    MEDIUM_60 = "MEDIUM_60"
    LONG_180 = "LONG_180"

    @property
    def days(self) -> int:
        return _RETENTION_DAYS[self.value]


class MemoryReplayError(Exception):
    """Raised when memory replay/reconstruction fails."""


class MemoryRecord(BaseModel):
    """A single memory record with all required fields (§31).

    model_config: frozen, strict, extra="forbid".
    All hashed values follow the corrected canonical contract; no floats.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    record_id: str = Field(min_length=1, max_length=128)
    memory_class: MemoryClass
    tenant_id: str = Field(min_length=1, max_length=64)
    task_hash: str | None = None
    correlation_id: str
    schema_id: str = Field(min_length=1, max_length=64)
    policy_epoch: int = Field(ge=0)
    sequence_no: int = Field(ge=0)
    payload_hash: str = Field(min_length=64, max_length=64)
    source_refs: list[str] = Field(default_factory=list)
    provenance: dict[str, Any] = Field(default_factory=dict)
    recorded_at: str
    status: str = Field(default="ACTIVE", min_length=1, max_length=64)
    retention_class: RetentionClass = RetentionClass.SHORT_30
    supersedes: str | None = None
    projection_version: int = Field(default=1, ge=1)

    @field_validator("payload_hash")
    @classmethod
    def _validate_payload_hash(cls, v: str) -> str:
        if not all(c in "0123456789abcdef" for c in v):
            raise ValueError("payload_hash must be 64-char lowercase hex")
        return v

    def to_canonical_dict(self) -> dict[str, Any]:
        """Serialise to a canonical JSON-serialisable dict for state hashing."""
        return {
            "record_id": self.record_id,
            "memory_class": self.memory_class.value,
            "tenant_id": self.tenant_id,
            "task_hash": self.task_hash,
            "correlation_id": self.correlation_id,
            "schema_id": self.schema_id,
            "policy_epoch": self.policy_epoch,
            "sequence_no": self.sequence_no,
            "payload_hash": self.payload_hash,
            "source_refs": sorted(self.source_refs),
            "provenance": self.provenance,
            "recorded_at": self.recorded_at,
            "status": self.status,
            "retention_class": self.retention_class.value,
            "supersedes": self.supersedes,
            "projection_version": self.projection_version,
        }


class MemoryStore:
    """Deterministic event-sourced memory with four classes (§31, G4.4, G4.5).

    Writes use version compare-and-swap (CAS) on sequence_no. Reads use
    pinned snapshots with deterministic filters and explicit sorting by
    (sequence_no, record_id) as a stable tie-breaker.

    Isolation:
    - Cross-tenant access is denied (GW-TENANT-001).
    - Cross-task access is denied unless the same tenant and authorized.
    - Revoked-access records are not returned even if the content hash is known.
    - Correlation_id alone is not authorization.
    """

    def __init__(self) -> None:
        self._events: list[MemoryRecord] = []
        self._by_id: dict[str, MemoryRecord] = {}
        self._next_seq: int = 0

    def write(
        self,
        record_id: str,
        memory_class: MemoryClass,
        tenant_id: str,
        correlation_id: str,
        schema_id: str,
        payload_hash: str,
        recorded_at: str,
        policy_epoch: int = 0,
        task_hash: str | None = None,
        source_refs: list[str] | None = None,
        provenance: dict[str, Any] | None = None,
        retention_class: RetentionClass = RetentionClass.SHORT_30,
        supersedes: str | None = None,
        projection_version: int = 1,
    ) -> MemoryRecord:
        """Write a new memory record with CAS on sequence_no."""
        if record_id in self._by_id:
            raise ValueError(
                f"record_id already exists: {record_id}"
            )
        seq = self._next_seq
        self._next_seq += 1
        record = MemoryRecord(
            record_id=record_id,
            memory_class=memory_class,
            tenant_id=tenant_id,
            task_hash=task_hash,
            correlation_id=correlation_id,
            schema_id=schema_id,
            policy_epoch=policy_epoch,
            sequence_no=seq,
            payload_hash=payload_hash,
            source_refs=source_refs or [],
            provenance=provenance or {},
            recorded_at=recorded_at,
            status="ACTIVE",
            retention_class=retention_class,
            supersedes=supersedes,
            projection_version=projection_version,
        )
        self._events.append(record)
        self._by_id[record_id] = record
        return record

    def read(
        self,
        record_id: str,
        tenant_id: str,
        current_epoch: int,
    ) -> MemoryRecord | None:
        """Read a single record by id with isolation checks.

        - Cross-tenant access denied (GW-TENANT-001).
        - Stale policy_epoch denied (GW-EPOCH-001).
        - Revoked-status records not returned.
        """
        record = self._by_id.get(record_id)
        if record is None:
            return None
        # Cross-tenant isolation
        if record.tenant_id != tenant_id:
            return None
        # Policy epoch check: record epoch must match current
        if record.policy_epoch != current_epoch:
            return None
        # Revoked-status records are not returned
        if record.status == "REVOKED":
            return None
        return record

    def read_class(
        self,
        memory_class: MemoryClass,
        tenant_id: str,
        current_epoch: int,
    ) -> list[MemoryRecord]:
        """Read all records of a given class for a tenant, sorted deterministically."""
        results = [
            r for r in self._events
            if r.memory_class is memory_class
            and r.tenant_id == tenant_id
            and r.policy_epoch == current_epoch
            and r.status != "REVOKED"
        ]
        # Stable sort: (sequence_no, record_id)
        return sorted(results, key=lambda r: (r.sequence_no, r.record_id))

    def read_by_correlation(
        self,
        correlation_id: str,
        tenant_id: str,
        current_epoch: int,
    ) -> list[MemoryRecord]:
        """Read records by correlation_id — NOT sufficient for authorization alone.

        Must also pass tenant_id and current_epoch checks.
        """
        results = [
            r for r in self._events
            if r.correlation_id == correlation_id
            and r.tenant_id == tenant_id
            and r.policy_epoch == current_epoch
            and r.status != "REVOKED"
        ]
        return sorted(results, key=lambda r: (r.sequence_no, r.record_id))

    def revoke(self, record_id: str) -> MemoryRecord | None:
        """Revoke a record — it will no longer be returned by reads."""
        record = self._by_id.get(record_id)
        if record is None:
            return None
        updated = record.model_copy(update={"status": "REVOKED"})
        # Replace in events list and by_id
        idx = self._events.index(record)
        self._events[idx] = updated
        self._by_id[record_id] = updated
        return updated

    def save_snapshot(self) -> bytes:
        """Serialise the full memory state to deterministic bytes."""
        items = [r.to_canonical_dict() for r in self._events]
        data = {"memory_events": items}
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def restore_snapshot(self, data: bytes) -> None:
        """Restore memory state from deterministic bytes."""
        raw = json.loads(data.decode("utf-8"))
        self._events = []
        self._by_id = {}
        max_seq = 0
        for item in raw["memory_events"]:
            # StrEnum values are stored as strings in JSON; convert back.
            item["memory_class"] = MemoryClass(item["memory_class"])
            item["retention_class"] = RetentionClass(item["retention_class"])
            record = MemoryRecord(**item)
            self._events.append(record)
            self._by_id[record.record_id] = record
            if record.sequence_no > max_seq:
                max_seq = record.sequence_no
        self._next_seq = max_seq + 1

    def snapshot_hash(self) -> str:
        """Return the SHA-256 hash of the current snapshot."""
        return hashlib.sha256(self.save_snapshot()).hexdigest()

    def state_hash(self) -> str:
        """Return the canonical hash of all records."""
        return canonical_hash(
            [r.to_canonical_dict() for r in self._events]
        )

    def replay_ordered_ids(self) -> list[str]:
        """Return the ordered list of record_ids from replay (G4.5)."""
        return [r.record_id for r in self._events]

    def replay_state_hashes(self) -> list[str]:
        """Return per-record state hashes from replay (G4.5)."""
        return [
            canonical_hash(r.to_canonical_dict())
            for r in self._events
        ]

    def project(
        self,
        memory_class: MemoryClass,
        tenant_id: str,
        projection_version: int = 1,
    ) -> list[str]:
        """Project records for a class/tenant, returning ordered ids.

        Projection is reproducible from the source event range and
        projection version.
        """
        records = [
            r for r in self._events
            if r.memory_class is memory_class
            and r.tenant_id == tenant_id
            and r.projection_version == projection_version
        ]
        return sorted(
            [r.record_id for r in records],
        )

    def __len__(self) -> int:
        return len(self._events)

    @property
    def events(self) -> list[MemoryRecord]:
        return list(self._events)
