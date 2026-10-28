"""G4.4, G4.5 — Memory isolation and reconstruction tests (P4, §31).

G4.4: all cross-tenant, cross-task and revoked-access fixtures denied;
      zero unauthorized memory reads or writes.
G4.5: event replay and projection rebuild reproduce expected ordered ids
      and state hashes exactly, including crash/duplicate cases.
"""

from __future__ import annotations

import hashlib

import pytest
from aminopstwin.executor.memory import (
    MemoryClass,
    MemoryStore,
    RetentionClass,
)


def _make_store(
    tenant: str = "tenant-test",
    epoch: int = 0,
) -> MemoryStore:
    store = MemoryStore()
    for i in range(5):
        store.write(
            record_id=f"rec-{i:04d}",
            memory_class=MemoryClass.M1_TASK_CONTEXT
            if i < 2
            else MemoryClass.M2_EXECUTION_HISTORY
            if i < 4
            else MemoryClass.M3_EVIDENCE,
            tenant_id=tenant,
            correlation_id=f"corr-{i:04d}",
            schema_id=f"schema.test@{i % 2 + 1}",
            payload_hash=hashlib.sha256(f"payload-{i}".encode()).hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
            policy_epoch=epoch,
        )
    return store


class TestMemoryIsolation:
    """G4.4: cross-tenant, cross-task, revoked-access denied."""

    def test_cross_tenant_denied(self) -> None:
        store = _make_store(tenant="tenant-a")
        # Try to read from a different tenant
        record = store.read("rec-0000", tenant_id="tenant-b", current_epoch=0)
        assert record is None

    def test_same_tenant_allowed(self) -> None:
        store = _make_store(tenant="tenant-a")
        record = store.read("rec-0000", tenant_id="tenant-a", current_epoch=0)
        assert record is not None
        assert record.record_id == "rec-0000"

    def test_cross_epoch_denied(self) -> None:
        store = _make_store(tenant="tenant-a", epoch=0)
        record = store.read("rec-0000", tenant_id="tenant-a", current_epoch=1)
        assert record is None

    def test_revoked_record_not_returned(self) -> None:
        store = _make_store()
        store.revoke("rec-0000")
        record = store.read(
            "rec-0000", tenant_id="tenant-test", current_epoch=0
        )
        assert record is None

    def test_read_class_isolated_by_tenant(self) -> None:
        store = MemoryStore()
        store.write(
            record_id="rec-a",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-a",
            correlation_id="corr-a",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"a").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        store.write(
            record_id="rec-b",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-b",
            correlation_id="corr-b",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"b").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        a_records = store.read_class(
            MemoryClass.M1_TASK_CONTEXT, "tenant-a", 0
        )
        b_records = store.read_class(
            MemoryClass.M1_TASK_CONTEXT, "tenant-b", 0
        )
        assert len(a_records) == 1
        assert len(b_records) == 1
        assert a_records[0].record_id == "rec-a"
        assert b_records[0].record_id == "rec-b"

    def test_correlation_id_alone_not_authorization(self) -> None:
        store = MemoryStore()
        store.write(
            record_id="rec-1",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-a",
            correlation_id="corr-shared",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"x").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        # Same correlation_id but different tenant -> denied
        records = store.read_by_correlation(
            "corr-shared", tenant_id="tenant-b", current_epoch=0
        )
        assert len(records) == 0

    def test_duplicate_write_rejected(self) -> None:
        store = MemoryStore()
        store.write(
            record_id="rec-1",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-a",
            correlation_id="corr-1",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"x").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        with pytest.raises(ValueError, match="already exists"):
            store.write(
                record_id="rec-1",
                memory_class=MemoryClass.M1_TASK_CONTEXT,
                tenant_id="tenant-a",
                correlation_id="corr-2",
                schema_id="schema.test@1",
                payload_hash=hashlib.sha256(b"y").hexdigest(),
                recorded_at="2026-10-23T00:00:00Z",
            )


class TestMemoryReconstruction:
    """G4.5: event replay and projection rebuild reproduce ordered ids."""

    def test_replay_ordered_ids(self) -> None:
        store = _make_store()
        ids = store.replay_ordered_ids()
        assert ids == ["rec-0000", "rec-0001", "rec-0002", "rec-0003", "rec-0004"]

    def test_replay_state_hashes_deterministic(self) -> None:
        store1 = _make_store()
        store2 = _make_store()
        hashes1 = store1.replay_state_hashes()
        hashes2 = store2.replay_state_hashes()
        assert hashes1 == hashes2

    def test_snapshot_save_restore(self) -> None:
        store = _make_store()
        snap = store.save_snapshot()
        store2 = MemoryStore()
        store2.restore_snapshot(snap)
        assert store.replay_ordered_ids() == store2.replay_ordered_ids()
        assert store.snapshot_hash() == store2.snapshot_hash()

    def test_snapshot_hash_deterministic(self) -> None:
        store1 = _make_store()
        store2 = _make_store()
        assert store1.snapshot_hash() == store2.snapshot_hash()

    def test_projection_reproducible(self) -> None:
        store = _make_store()
        ids_v1 = store.project(
            MemoryClass.M1_TASK_CONTEXT, "tenant-test", projection_version=1
        )
        # Same projection should be reproducible
        ids_v1_again = store.project(
            MemoryClass.M1_TASK_CONTEXT, "tenant-test", projection_version=1
        )
        assert ids_v1 == ids_v1_again
        assert len(ids_v1) == 2  # rec-0000, rec-0001

    def test_projection_isolated_by_tenant(self) -> None:
        store = MemoryStore()
        store.write(
            record_id="rec-a",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-a",
            correlation_id="corr-a",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"a").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
            projection_version=1,
        )
        store.write(
            record_id="rec-b",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-b",
            correlation_id="corr-b",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"b").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
            projection_version=1,
        )
        a_ids = store.project(MemoryClass.M1_TASK_CONTEXT, "tenant-a")
        b_ids = store.project(MemoryClass.M1_TASK_CONTEXT, "tenant-b")
        assert a_ids == ["rec-a"]
        assert b_ids == ["rec-b"]

    def test_crash_recovery_via_snapshot(self) -> None:
        """Simulate a crash: save snapshot, create new store, restore."""
        store = _make_store()
        snap = store.save_snapshot()
        # Simulate crash: new empty store
        new_store = MemoryStore()
        assert len(new_store) == 0
        new_store.restore_snapshot(snap)
        assert len(new_store) == 5
        assert new_store.replay_ordered_ids() == store.replay_ordered_ids()

    def test_state_hash_deterministic(self) -> None:
        store1 = _make_store()
        store2 = _make_store()
        assert store1.state_hash() == store2.state_hash()

    def test_read_class_sorted_deterministically(self) -> None:
        store = _make_store()
        records = store.read_class(
            MemoryClass.M2_EXECUTION_HISTORY, "tenant-test", 0
        )
        # Must be sorted by (sequence_no, record_id)
        seqs = [r.sequence_no for r in records]
        assert seqs == sorted(seqs)


class TestRetentionClasses:
    """Retention options (owner-confirmed, §37)."""

    @pytest.mark.parametrize(
        "cls,days",
        [
            (RetentionClass.SHORT_15, 15),
            (RetentionClass.SHORT_30, 30),
            (RetentionClass.MEDIUM_60, 60),
            (RetentionClass.LONG_180, 180),
        ],
    )
    def test_retention_days(self, cls: RetentionClass, days: int) -> None:
        assert cls.days == days

    def test_record_has_retention_class(self) -> None:
        store = MemoryStore()
        store.write(
            record_id="rec-ret",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-test",
            correlation_id="corr-ret",
            schema_id="schema.test@1",
            payload_hash=hashlib.sha256(b"x").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
            retention_class=RetentionClass.MEDIUM_60,
        )
        record = store.read(
            "rec-ret", "tenant-test", 0
        )
        assert record is not None
        assert record.retention_class is RetentionClass.MEDIUM_60
        assert record.retention_class.days == 60
