"""Test PostgreSQL-backed idempotency: 100 concurrent same-key requests (P27, G27.2).

100 concurrent requests with the same idempot key must produce exactly
one effect (ADR-004).  The PgIdempotencyStore uses SELECT ... FOR UPDATE
and a unique constraint on (tenant, principal, key) to serialise
concurrent inserts.

G27.2: 100 concurrent same-key requests on PostgreSQL -> 1 effect.
"""

from __future__ import annotations

import hashlib
import threading
from concurrent.futures import ThreadPoolExecutor

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from aminopstwin.contracts.idempotency import IdempotencyStatus
from aminopstwin.persistence.models import IdempotencyKeyModel
from aminopstwin.persistence.pg_idempotency import PgIdempotencyStore


def _fingerprint(payload: dict[str, str]) -> str:
    return hashlib.sha256(repr(sorted(payload.items())).encode()).hexdigest()


class TestPostgresIdempotency:
    """G27.2 — 100 concurrent same-key requests on PostgreSQL -> 1 effect."""

    def test_100_concurrent_same_key_one_effect(
        self,
        pg_session_factory: sessionmaker[Session],
    ) -> None:
        """100 threads with the same key produce exactly one IN_PROGRESS."""
        store = PgIdempotencyStore(pg_session_factory)
        payload = {"action": "test", "value": "42"}
        fp = _fingerprint(payload)
        tenant = "tenant-g27-2"
        principal = "principal-a"
        key = "concurrent-key-001"

        started_count = 0
        lock = threading.Lock()

        def _attempt() -> bool:
            nonlocal started_count
            _, created = store.get_or_start(
                tenant_id=tenant,
                principal=principal,
                key=key,
                fingerprint=fp,
            )
            if created:
                with lock:
                    started_count += 1
            return created

        with ThreadPoolExecutor(max_workers=20) as pool:
            results = list(pool.submit(_attempt) for _ in range(100))
            for r in results:
                r.result()

        assert started_count == 1, (
            f"Expected exactly 1 created, got {started_count} — "
            "concurrent same-key requests produced duplicate effects"
        )

        with pg_session_factory() as session:
            rows = session.execute(
                select(IdempotencyKeyModel).where(
                    IdempotencyKeyModel.tenant_id == tenant,
                    IdempotencyKeyModel.principal == principal,
                    IdempotencyKeyModel.key == key,
                )
            ).scalars().all()
            assert len(rows) == 1, (
                f"Expected 1 row, got {len(rows)} — duplicate idempotency keys"
            )
            assert rows[0].status == IdempotencyStatus.IN_PROGRESS.value

    def test_same_key_different_fingerprint_raises_gw_idemp_002(
        self,
        pg_session_factory: sessionmaker[Session],
    ) -> None:
        """Same key with a different payload fingerprint is denied."""
        from aminopstwin.contracts.idempotency import IdempotencyError

        store = PgIdempotencyStore(pg_session_factory)
        tenant = "tenant-g27-2b"
        principal = "principal-b"
        key = "conflict-key-001"

        fp1 = _fingerprint({"a": "1"})
        fp2 = _fingerprint({"a": "2"})

        store.get_or_start(tenant, principal, key, fp1)

        raised = False
        try:
            store.get_or_start(tenant, principal, key, fp2)
        except IdempotencyError:
            raised = True

        assert raised, (
            "Expected IdempotencyError (GW-IDEMP-002) for same key "
            "with different fingerprint"
        )
