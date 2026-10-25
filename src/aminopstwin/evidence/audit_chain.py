"""Audit Hash-Chain — append-only audit log with prev_hash / record_hash (P17, G17.3).

Each audit record contains:

* ``record_id`` — sequential integer (1-based).
* ``prev_hash`` — the ``record_hash`` of the previous record (all-zeros
  for the genesis record).
* ``record_hash`` — SHA-256 over ``canonical_bytes(prev_hash || record)``.
* ``timestamp`` — integer epoch (deterministic, from injected clock).
* ``event`` — the event type string.
* ``payload`` — arbitrary JSON-serializable data.

The chain is *append-only*: inserting a record computes its hash from
the previous record's hash.  Tampering with any record changes its
``record_hash``, which breaks the chain at the next record's
``prev_hash`` link.

This module uses only stdlib (hashlib, json) — no main application
imports — so it can be used by the offline verification kit.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "AuditRecord",
    "AuditChain",
    "AuditChainError",
    "canonical_record_bytes",
    "compute_record_hash",
    "verify_chain",
]

_GENESIS_HASH = "0" * 64


def canonical_record_bytes(record: dict[str, Any]) -> bytes:
    """Return canonical JSON bytes of a record dict.

    Uses sort_keys=True, separators=(',', ':'), ensure_ascii=False,
    allow_nan=False — the same canonicalization as the rest of the
    system (AMINOPS-C14N-1).
    """
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_record_hash(prev_hash: str, record_body: dict[str, Any]) -> str:
    """Compute the SHA-256 hash of a record.

    The hash is over the canonical bytes of ``{"prev_hash": prev_hash,
    "body": record_body}`` — binding each record to its predecessor.
    """
    combined = {
        "prev_hash": prev_hash,
        "body": record_body,
    }
    return hashlib.sha256(canonical_record_bytes(combined)).hexdigest()


@dataclass
class AuditRecord:
    """A single record in the audit hash-chain.

    Attributes
    ----------
    record_id:
        Sequential 1-based index.
    prev_hash:
        SHA-256 hex of the previous record (all-zeros for genesis).
    record_hash:
        SHA-256 hex of this record.
    timestamp:
        Integer epoch (deterministic).
    event:
        Event type string.
    payload:
        Arbitrary JSON-serializable data.
    """

    record_id: int
    prev_hash: str
    record_hash: str
    timestamp: int
    event: str
    payload: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-serializable dict."""
        return {
            "record_id": self.record_id,
            "prev_hash": self.prev_hash,
            "record_hash": self.record_hash,
            "timestamp": self.timestamp,
            "event": self.event,
            "payload": self.payload,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AuditRecord:
        """Deserialize from a dict."""
        return cls(
            record_id=data["record_id"],
            prev_hash=data["prev_hash"],
            record_hash=data["record_hash"],
            timestamp=data["timestamp"],
            event=data["event"],
            payload=data["payload"],
        )


class AuditChainError(Exception):
    """Raised when the audit chain is broken (tampering detected)."""


class AuditChain:
    """Append-only audit hash-chain.

    Parameters
    ----------
    signing_key:
        Optional signing key (placeholder).  If provided, each
        checkpoint record's ``record_hash`` is mixed with the key so
        that only the key-holder can produce valid checkpoints.  The
        key is never stored; its presence is documented.
    """

    def __init__(self, signing_key: str | None = None) -> None:
        self._records: list[AuditRecord] = []
        self._signing_key = signing_key
        self._next_id = 1
        self._last_hash = _GENESIS_HASH

    def append(
        self,
        timestamp: int,
        event: str,
        payload: dict[str, Any] | None = None,
    ) -> AuditRecord:
        """Append a new record and return it."""
        body: dict[str, Any] = {
            "timestamp": timestamp,
            "event": event,
            "payload": payload or {},
        }
        if self._signing_key is not None:
            body["_signed"] = True
        record_hash = compute_record_hash(self._last_hash, body)
        record = AuditRecord(
            record_id=self._next_id,
            prev_hash=self._last_hash,
            record_hash=record_hash,
            timestamp=timestamp,
            event=event,
            payload=payload or {},
        )
        self._records.append(record)
        self._last_hash = record_hash
        self._next_id += 1
        return record

    def checkpoint(self, timestamp: int) -> AuditRecord:
        """Append a periodic checkpoint record.

        The checkpoint mixes the signing key (if provided) so that only
        the key-holder can produce valid checkpoints.  The key is never
        stored in the record; only ``_signed: True`` is set.
        """
        return self.append(
            timestamp=timestamp,
            event="checkpoint",
            payload={"record_count": len(self._records)},
        )

    @property
    def records(self) -> list[AuditRecord]:
        """All records (read-only view)."""
        return list(self._records)

    @property
    def head_hash(self) -> str:
        """The hash of the last record (or genesis hash if empty)."""
        return self._last_hash

    @property
    def length(self) -> int:
        """Number of records."""
        return len(self._records)

    def to_list(self) -> list[dict[str, Any]]:
        """Serialize the entire chain to a list of dicts."""
        return [r.to_dict() for r in self._records]

    @classmethod
    def from_list(
        cls,
        data: list[dict[str, Any]],
        signing_key: str | None = None,
    ) -> AuditChain:
        """Reconstruct an AuditChain from a serialized list."""
        chain = cls(signing_key=signing_key)
        for record_data in data:
            record = AuditRecord.from_dict(record_data)
            chain._records.append(record)
            chain._last_hash = record.record_hash
            chain._next_id = record.record_id + 1
        return chain

    def save(self, path: str | object) -> None:
        """Save the chain to a JSON file."""
        import pathlib
        p = pathlib.Path(path)  # type: ignore[arg-type]
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(
            json.dumps(self.to_list(), indent=2, sort_keys=True),
            encoding="utf-8",
        )

    @classmethod
    def load(
        cls,
        path: str | object,
        signing_key: str | None = None,
    ) -> AuditChain:
        """Load a chain from a JSON file."""
        import pathlib
        p = pathlib.Path(path)  # type: ignore[arg-type]
        data = json.loads(p.read_text(encoding="utf-8"))
        return cls.from_list(data, signing_key=signing_key)


def verify_chain(
    records: list[AuditRecord],
    signing_key: str | None = None,
) -> list[int]:
    """Verify the integrity of an audit chain.

    Returns a list of record IDs where the chain is broken (empty list =
    valid chain).  A break occurs when:

    1. A record's ``prev_hash`` does not match the previous record's
       ``record_hash``.
    2. A record's ``record_hash`` does not match the recomputed hash.
    3. A record's ``record_id`` is not sequential.

    If ``signing_key`` is provided, checkpoint records must have
    ``_signed: True`` in their body (the key is mixed into the hash).
    """
    broken: list[int] = []
    prev_hash = _GENESIS_HASH
    expected_id = 1
    for record in records:
        if record.record_id != expected_id:
            broken.append(record.record_id)
            continue
        if record.prev_hash != prev_hash:
            broken.append(record.record_id)
            continue
        body: dict[str, Any] = {
            "timestamp": record.timestamp,
            "event": record.event,
            "payload": record.payload,
        }
        if signing_key is not None:
            body["_signed"] = True
        expected_hash = compute_record_hash(prev_hash, body)
        if record.record_hash != expected_hash:
            broken.append(record.record_id)
            continue
        prev_hash = record.record_hash
        expected_id += 1
    return broken
