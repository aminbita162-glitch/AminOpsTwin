"""G6.3 — Backup/restore drill tests (P9).

G6.3: restored state hash equals the source state hash.
Records RPO/RTO against owner-approved deployment objectives.
"""

from __future__ import annotations

import hashlib
import json
import uuid

import pytest
from src.contracts.clock import SeededClock
from src.executor import DurableExecutor
from src.executor.memory import MemoryClass, MemoryStore
from src.integration.backup import (
    BACKUP_RPO_MINUTES,
    BACKUP_RTO_HOURS,
    BackupDrill,
    BackupError,
)


class TestBackupDrill:
    """G6.3: Backup/restore drill — restored hash equals source hash."""

    def _make_executor_with_state(self) -> DurableExecutor:
        """Create an executor with a workflow and checkpoint."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        executor.start(uuid.UUID("00000000-0000-4000-8000-000000000001"))
        return executor

    def _make_memory_with_state(self) -> MemoryStore:
        """Create a memory store with a record."""
        store = MemoryStore()
        store.write(
            record_id="backup-rec-001",
            memory_class=MemoryClass.M1_TASK_CONTEXT,
            tenant_id="tenant-default",
            correlation_id="corr-backup-001",
            schema_id="schema.backup@1",
            payload_hash=hashlib.sha256(b"backup").hexdigest(),
            recorded_at="2026-10-23T00:00:00Z",
        )
        return store

    def test_backup_produces_bytes(self) -> None:
        """backup() returns deterministic bytes."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        data = drill.backup()
        assert isinstance(data, bytes)
        assert len(data) > 0

    def test_source_hash_is_deterministic(self) -> None:
        """source_hash() is deterministic for the same state.

        Two drills backed by the same executor and memory instances
        produce the same combined snapshot hash.
        """
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill1 = BackupDrill(executor, memory)
        drill1.backup()

        drill2 = BackupDrill(executor, memory)
        drill2.backup()

        assert drill1.source_hash() == drill2.source_hash()

    def test_run_drill_hash_match(self) -> None:
        """G6.3: restored state hash equals the source state hash."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        result = drill.run_drill()
        assert result.match is True
        assert result.source_hash == result.restored_hash

    def test_run_drill_records_rpo_rto(self) -> None:
        """Run drill records RPO=30min, RTO=2h."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        result = drill.run_drill()
        assert result.rpo_minutes == BACKUP_RPO_MINUTES
        assert result.rto_hours == BACKUP_RTO_HOURS
        assert result.rpo_minutes == 30
        assert result.rto_hours == 2

    def test_backup_restore_roundtrip(self) -> None:
        """backup → restore produces identical state hash."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        drill.backup()
        source = drill.source_hash()
        data = drill.backup()
        # Restore into fresh instances
        new_executor = DurableExecutor(clock=SeededClock())
        new_memory = MemoryStore()
        restore_drill = BackupDrill(new_executor, new_memory)
        restore_drill.restore(data)
        restored = restore_drill.restored_hash()
        assert source == restored

    def test_backup_error_on_corrupted_data(self) -> None:
        """Restore of corrupted data raises BackupError."""
        executor = DurableExecutor(clock=SeededClock())
        memory = MemoryStore()
        drill = BackupDrill(executor, memory)
        with pytest.raises(BackupError):
            drill.restore(b"not valid json")

    def test_backup_result_has_detail(self) -> None:
        """BackupResult has a detail string."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        result = drill.run_drill()
        assert isinstance(result.detail, str)
        assert len(result.detail) > 0
        assert result.source_hash != ""

    def test_empty_state_backup(self) -> None:
        """Backup of empty state works and hash is deterministic."""
        executor = DurableExecutor(clock=SeededClock())
        memory = MemoryStore()
        drill1 = BackupDrill(executor, memory)
        drill1.backup()

        drill2 = BackupDrill(executor, memory)
        drill2.backup()

        assert drill1.source_hash() == drill2.source_hash()
        result = drill1.run_drill()
        assert result.match is True

    def test_backup_atomicity(self) -> None:
        """Backup data is a complete JSON object, not partial."""
        executor = self._make_executor_with_state()
        memory = self._make_memory_with_state()
        drill = BackupDrill(executor, memory)
        data = drill.backup()
        parsed = json.loads(data.decode("utf-8"))
        assert "executor" in parsed
        assert "memory" in parsed

    def test_source_hash_requires_backup(self) -> None:
        """source_hash() raises BackupError if no backup taken yet."""
        executor = DurableExecutor(clock=SeededClock())
        memory = MemoryStore()
        drill = BackupDrill(executor, memory)
        with pytest.raises(BackupError):
            drill.source_hash()

    def test_restored_hash_requires_restore(self) -> None:
        """restored_hash() raises BackupError if no restore done yet."""
        executor = DurableExecutor(clock=SeededClock())
        memory = MemoryStore()
        drill = BackupDrill(executor, memory)
        with pytest.raises(BackupError):
            drill.restored_hash()

    def test_rpo_rto_constants(self) -> None:
        """RPO=30 minutes, RTO=2 hours (§37 owner defaults)."""
        assert BACKUP_RPO_MINUTES == 30
        assert BACKUP_RTO_HOURS == 2
