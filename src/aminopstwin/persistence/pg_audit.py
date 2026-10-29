"""PostgreSQL adapter for the audit chain (ADR-005, P27).

Append-only table: the application role has no UPDATE or DELETE
privileges.  The hash chain is persisted.  Merkle batching is done
every 15 minutes or every 1000 events.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select

from aminopstwin.persistence.models import AuditEventModel, MerkleBatchModel

__all__ = [
    "PgAuditStore",
    "MERKLE_BATCH_SIZE",
    "MERKLE_BATCH_INTERVAL_SECONDS",
]

_GENESIS_HASH = "0" * 64

MERKLE_BATCH_SIZE = 1000
MERKLE_BATCH_INTERVAL_SECONDS = 900  # 15 minutes


def _canonical_bytes(record: dict[str, Any]) -> bytes:
    return json.dumps(
        record,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _compute_record_hash(prev_hash: str, body: dict[str, Any]) -> str:
    combined = {"prev_hash": prev_hash, "body": body}
    return hashlib.sha256(_canonical_bytes(combined)).hexdigest()


class PgAuditStore:
    """PostgreSQL append-only audit store (ADR-005).

    The hash chain is persisted.  No role may UPDATE or DELETE
    audit_events (enforced by database privileges on the application
    role — the application role lacks UPDATE and DELETE).
    """

    def __init__(self, session_factory: Any) -> None:
        self._session_factory = session_factory

    def append(
        self,
        timestamp: int,
        event: str,
        tenant_id: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Append an audit event and return it as a dict."""
        with self._session_factory() as session:
            last_model = session.execute(
                select(AuditEventModel)
                .order_by(AuditEventModel.record_id.desc())
                .limit(1)
            ).scalar_one_or_none()
            if last_model is None:
                prev_hash = _GENESIS_HASH
                next_id = 1
            else:
                prev_hash = last_model.record_hash
                next_id = last_model.record_id + 1
            body: dict[str, Any] = {
                "timestamp": timestamp,
                "event": event,
                "tenant_id": tenant_id,
                "payload": payload or {},
            }
            record_hash = _compute_record_hash(prev_hash, body)
            model = AuditEventModel(
                record_id=next_id,
                prev_hash=prev_hash,
                record_hash=record_hash,
                timestamp=timestamp,
                event=event,
                tenant_id=tenant_id,
                payload=json.dumps(payload or {}, sort_keys=True),
            )
            session.add(model)
            session.commit()
            return {
                "record_id": next_id,
                "prev_hash": prev_hash,
                "record_hash": record_hash,
                "timestamp": timestamp,
                "event": event,
                "tenant_id": tenant_id,
                "payload": payload or {},
            }

    def get_all(self, tenant_id: str | None = None) -> list[dict[str, Any]]:
        """Return all audit events (optionally filtered by tenant_id)."""
        with self._session_factory() as session:
            if tenant_id is not None:
                stmt = (
                    select(AuditEventModel)
                    .where(AuditEventModel.tenant_id == tenant_id)
                    .order_by(AuditEventModel.record_id)
                )
            else:
                stmt = select(AuditEventModel).order_by(
                    AuditEventModel.record_id
                )
            models = session.execute(stmt).scalars().all()
            return [
                {
                    "record_id": m.record_id,
                    "prev_hash": m.prev_hash,
                    "record_hash": m.record_hash,
                    "timestamp": m.timestamp,
                    "event": m.event,
                    "tenant_id": m.tenant_id,
                    "payload": json.loads(m.payload),
                }
                for m in models
            ]

    def verify_chain(self) -> list[int]:
        """Verify the hash chain. Return broken record IDs (empty = valid)."""
        events = self.get_all()
        broken: list[int] = []
        prev_hash = _GENESIS_HASH
        expected_id = 1
        for ev in events:
            if ev["record_id"] != expected_id:
                broken.append(ev["record_id"])
                continue
            if ev["prev_hash"] != prev_hash:
                broken.append(ev["record_id"])
                continue
            body = {
                "timestamp": ev["timestamp"],
                "event": ev["event"],
                "tenant_id": ev["tenant_id"],
                "payload": ev["payload"],
            }
            expected_hash = _compute_record_hash(prev_hash, body)
            if ev["record_hash"] != expected_hash:
                broken.append(ev["record_id"])
                continue
            prev_hash = ev["record_hash"]
            expected_id += 1
        return broken

    def maybe_build_merkle_batch(self) -> str | None:
        """Build a Merkle batch if there are enough unbatched events.

        Batches are built every MERKLE_BATCH_SIZE events.
        Returns the batch_id if a batch was built, or None.
        """
        with self._session_factory() as session:
            last_batch = session.execute(
                select(MerkleBatchModel)
                .order_by(MerkleBatchModel.id.desc())
                .limit(1)
            ).scalar_one_or_none()
            start_id = (
                last_batch.last_event_id + 1
                if last_batch is not None
                else 1
            )
            unbatched = session.execute(
                select(AuditEventModel)
                .where(AuditEventModel.record_id >= start_id)
                .order_by(AuditEventModel.record_id)
                .limit(MERKLE_BATCH_SIZE)
            ).scalars().all()
            if len(unbatched) < MERKLE_BATCH_SIZE:
                session.rollback()
                return None
            leaves = [
                hashlib.sha256(
                    f"{m.record_id}:{m.record_hash}".encode()
                ).hexdigest()
                for m in unbatched
            ]
            root = _build_merkle_root(leaves)
            batch_id = hashlib.sha256(
                f"batch:{start_id}:{start_id + len(unbatched) - 1}".encode()
            ).hexdigest()
            batch_model = MerkleBatchModel(
                batch_id=batch_id,
                root_hash=root,
                event_count=len(unbatched),
                first_event_id=start_id,
                last_event_id=start_id + len(unbatched) - 1,
            )
            session.add(batch_model)
            session.commit()
            return batch_id


def _build_merkle_root(leaves: list[str]) -> str:
    """Build a Merkle root from a list of leaf hashes."""
    if not leaves:
        return _GENESIS_HASH
    level = list(leaves)
    while len(level) > 1:
        next_level: list[str] = []
        for i in range(0, len(level), 2):
            left = level[i]
            right = level[i + 1] if i + 1 < len(level) else level[i]
            next_level.append(
                hashlib.sha256(
                    (left + right).encode("utf-8")
                ).hexdigest()
            )
        level = next_level
    return level[0]
