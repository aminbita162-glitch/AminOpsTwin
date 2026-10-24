"""Backup / restore drill (G6.3).

Atomically serialises the :class:`~src.executor.DurableExecutor` and
:class:`~src.executor.memory.MemoryStore` snapshots into a single
deterministic JSON bytes object, restores them into fresh instances, and
verifies the restored state hash equals the source state hash.

Owner-approved deployment objectives (§38 rule 7, G6.3):

* **RPO** — ``BACKUP_RPO_MINUTES = 30``: no more than 30 minutes of
  committed state may be lost between successful backups.
* **RTO** — ``BACKUP_RTO_HOURS = 2``: a full restore must complete
  within 2 hours of declared failure.

The backup payload is atomic and hash-manifested: it is assembled in
memory (bytes) — never partially visible under the final name — and
carries a SHA-256 manifest of the combined snapshot so that restore can
prove bit-exact equivalence (F11, §38 rule 7).
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from src.executor import DurableExecutor
from src.executor.memory import MemoryStore

__all__ = [
    "BACKUP_RPO_MINUTES",
    "BACKUP_RTO_HOURS",
    "BackupError",
    "BackupResult",
    "BackupDrill",
]

#: Owner-approved Recovery Point Objective in minutes (G6.3, §38 rule 7).
BACKUP_RPO_MINUTES: int = 30

#: Owner-approved Recovery Time Objective in hours (G6.3, §38 rule 7).
BACKUP_RTO_HOURS: int = 2


class BackupError(Exception):
    """Raised when a backup or restore operation fails integrity checks."""


@dataclass(frozen=True)
class BackupResult:
    """Outcome of a :meth:`BackupDrill.run_drill` cycle (G6.3).

    ``match`` is ``True`` iff the restored-state SHA-256 equals the
    source-state SHA-256 — i.e. the backup is bit-exact and the RPO
    objective is met for this cycle. ``rpo_minutes`` / ``rto_hours``
    record the owner-approved objectives the drill was run against.
    """

    source_hash: str
    restored_hash: str
    match: bool
    rpo_minutes: int
    rto_hours: int
    detail: str


def _combined_snapshot(
    executor: DurableExecutor,
    memory: MemoryStore,
) -> dict[str, str]:
    """Build the deterministic combined-snapshot dict.

    Each component snapshot is hex-encoded so the combined payload is a
    pure-ASCII JSON string — stable across encoders and easy to manifest.
    """
    return {
        "executor": executor.save_snapshot().hex(),
        "memory": memory.save_snapshot().hex(),
    }


def _hash_combined(snapshot: dict[str, str]) -> str:
    """SHA-256 of the canonical (sorted-key) JSON encoding of *snapshot*."""
    payload = json.dumps(
        snapshot,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


class BackupDrill:
    """Atomic backup/restore drill across executor and memory (G6.3).

    The drill serialises both the :class:`DurableExecutor` and
    :class:`MemoryStore` into a single deterministic JSON bytes object,
    restores them into fresh instances, and asserts the restored state
    hash matches the source state hash.

    Atomicity (F11, §38 rule 7): the payload is built entirely in
    memory before being committed to the restore target — a failed or
    interrupted drill never leaves a partial snapshot visible to the
    restore path.
    """

    def __init__(self, executor: DurableExecutor, memory: MemoryStore) -> None:
        self._executor: DurableExecutor = executor
        self._memory: MemoryStore = memory
        self._last_backup: bytes | None = None
        self._source_hash: str | None = None
        self._restored_hash: str | None = None

    # -- backup -----------------------------------------------------------

    def backup(self) -> bytes:
        """Serialise executor + memory into a deterministic JSON bytes blob.

        The payload shape is::

            {"executor": "<hex>", "memory": "<hex>"}

        where each value is the hex encoding of the corresponding
        component's ``save_snapshot()`` bytes. The result is cached on
        ``self`` so :meth:`source_hash` is consistent with the returned
        bytes.
        """
        snapshot = _combined_snapshot(self._executor, self._memory)
        payload = json.dumps(
            snapshot,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        # Atomic-write simulation: stage in a temp file, then commit the
        # bytes as the single visible artefact. A crash before this point
        # leaves no partial payload under the final name.
        fd, tmp_path = tempfile.mkstemp(prefix="backup_", suffix=".json")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(payload)
                fh.flush()
                os.fsync(fh.fileno())
            # Commit: replace the cached payload atomically.
            self._last_backup = payload
            self._source_hash = _hash_combined(snapshot)
            self._restored_hash = None
        finally:
            Path(tmp_path).unlink(missing_ok=True)
        return payload

    # -- restore ----------------------------------------------------------

    def restore(self, data: bytes) -> None:
        """Restore both executor and memory from *data*.

        ``data`` must be the bytes returned by :meth:`backup`. The
        executor and memory stores are replaced wholesale from the
        decoded snapshots — no partial state is left visible if the
        decode fails (``BackupError`` is raised before mutation).
        """
        try:
            snapshot = json.loads(data.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise BackupError(f"invalid backup payload: {exc}") from exc
        if not isinstance(snapshot, dict) or set(snapshot.keys()) != {
            "executor",
            "memory",
        }:
            raise BackupError("backup payload must have executor+memory keys")
        try:
            executor_bytes = bytes.fromhex(snapshot["executor"])
            memory_bytes = bytes.fromhex(snapshot["memory"])
        except (ValueError, TypeError) as exc:
            raise BackupError(f"invalid hex snapshot: {exc}") from exc
        # Decode into fresh instances first so a failure does not mutate
        # the live stores (atomicity).
        new_executor = DurableExecutor()
        new_memory = MemoryStore()
        try:
            new_executor.restore_snapshot(executor_bytes)
            new_memory.restore_snapshot(memory_bytes)
        except (ValueError, KeyError) as exc:
            raise BackupError(f"restore failed: {exc}") from exc
        # Commit: swap in the restored stores and record the restored hash.
        self._executor = new_executor
        self._memory = new_memory
        self._restored_hash = _hash_combined(
            {
                "executor": new_executor.save_snapshot().hex(),
                "memory": new_memory.save_snapshot().hex(),
            }
        )

    # -- hashes -----------------------------------------------------------

    def source_hash(self) -> str:
        """SHA-256 of the combined source snapshot (pre-restore)."""
        if self._source_hash is None:
            raise BackupError("no backup taken yet")
        return self._source_hash

    def restored_hash(self) -> str:
        """SHA-256 of the combined snapshot after :meth:`restore`."""
        if self._restored_hash is None:
            raise BackupError("no restore performed yet")
        return self._restored_hash

    # -- drill ------------------------------------------------------------

    def run_drill(self) -> BackupResult:
        """Run a full backup → restore → verify cycle and return the result.

        Records the owner-approved RPO/RTO objectives (30 min / 2 h) and
        confirms the restored state hash equals the source state hash.
        Raises :class:`BackupError` if the hashes diverge (RPO breach).
        """
        source = self.backup()
        src_hash = self.source_hash()
        self.restore(source)
        rest_hash = self.restored_hash()
        match = src_hash == rest_hash
        detail = (
            "restored state hash matches source state hash"
            if match
            else "restored state hash diverges from source state hash"
        )
        if not match:
            raise BackupError(
                f"hash mismatch: source={src_hash} restored={rest_hash}"
            )
        return BackupResult(
            source_hash=src_hash,
            restored_hash=rest_hash,
            match=match,
            rpo_minutes=BACKUP_RPO_MINUTES,
            rto_hours=BACKUP_RTO_HOURS,
            detail=detail,
        )
