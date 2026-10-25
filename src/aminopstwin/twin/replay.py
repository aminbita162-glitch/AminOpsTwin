"""Bit-reproducible replay engine with checkpoint format (P16, G16.1).

The replay engine captures Executor and Twin state at a checkpoint, writes
it to disk in canonical bytes form, and restores it via
:func:`resume_from_checkpoint`.  The restored state's final hash must equal
a fresh run's final hash for the same inputs — this is the bit-reproducibility
contract.

Checkpoint format
-----------------
A checkpoint is a JSON document (canonical bytes, §3.5.2) containing:

    {
      "checkpoint_version": "1.0",
      "executor_state": <canonical dict from DurableExecutor.save_snapshot()>,
      "twin_state": <canonical dict from TemporalState.save_state()>,
      "executor_hash": <sha256 hex of executor_state bytes>,
      "twin_hash": <sha256 hex of twin_state bytes>,
      "signature": null  // placeholder for owner key signature (P19)
    }

The ``signature`` field is a placeholder — the owner key is outside the
repository (§19).  P19 fills it with a real signature; P16 leaves it null.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.executor import DurableExecutor
from aminopstwin.twin.temporal import TemporalState

__all__ = [
    "CheckpointFormat",
    "CheckpointData",
    "save_checkpoint",
    "resume_from_checkpoint",
    "checkpoint_hash",
]

CHECKPOINT_VERSION = "1.0"


class CheckpointFormat:
    """Checkpoint format — captures Executor and Twin state.

    The checkpoint is serialised to canonical bytes (§3.5.2) so that
    the same state produces the same bytes on every platform.  The
    ``signature`` field is a placeholder for an owner key signature
    (P19); it is ``None`` in P16.
    """

    def __init__(
        self,
        executor_state: dict[str, Any],
        twin_state: dict[str, Any],
    ) -> None:
        self._executor_state: dict[str, Any] = executor_state
        self._twin_state: dict[str, Any] = twin_state
        self._executor_hash: str = canonical_hash(executor_state)
        self._twin_hash: str = canonical_hash(twin_state)

    @property
    def executor_state(self) -> dict[str, Any]:
        return self._executor_state

    @property
    def twin_state(self) -> dict[str, Any]:
        return self._twin_state

    @property
    def executor_hash(self) -> str:
        return self._executor_hash

    @property
    def twin_hash(self) -> str:
        return self._twin_hash

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a canonical dict for on-disk storage."""
        return {
            "checkpoint_version": CHECKPOINT_VERSION,
            "executor_state": self._executor_state,
            "twin_state": self._twin_state,
            "executor_hash": self._executor_hash,
            "twin_hash": self._twin_hash,
            "signature": None,
        }

    def to_bytes(self) -> bytes:
        """Serialise to canonical bytes (§3.5.2)."""
        return json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")


class CheckpointData:
    """Restored checkpoint data — holds deserialised state for resumption."""

    def __init__(
        self,
        executor_state: dict[str, Any],
        twin_state: dict[str, Any],
        executor_hash: str,
        twin_hash: str,
    ) -> None:
        self._executor_state: dict[str, Any] = executor_state
        self._twin_state: dict[str, Any] = twin_state
        self._executor_hash: str = executor_hash
        self._twin_hash: str = twin_hash

    @property
    def executor_state(self) -> dict[str, Any]:
        return self._executor_state

    @property
    def twin_state(self) -> dict[str, Any]:
        return self._twin_state

    @property
    def executor_hash(self) -> str:
        return self._executor_hash

    @property
    def twin_hash(self) -> str:
        return self._twin_hash


def _state_to_bytes(state_dict: dict[str, Any]) -> bytes:
    """Serialise a state dict to canonical bytes."""
    return json.dumps(
        state_dict,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def save_checkpoint(
    executor: DurableExecutor,
    twin: TemporalState,
    path: str | Path,
) -> str:
    """Save a checkpoint of the executor and twin state to *path*.

    Returns the SHA-256 hex digest of the checkpoint bytes.
    """
    executor_bytes = executor.save_snapshot()
    twin_bytes = twin.save_state()
    executor_state = json.loads(executor_bytes.decode("utf-8"))
    twin_state = json.loads(twin_bytes.decode("utf-8"))
    cp = CheckpointFormat(executor_state, twin_state)
    cp_bytes = cp.to_bytes()
    Path(path).write_bytes(cp_bytes)
    return hashlib.sha256(cp_bytes).hexdigest()


def resume_from_checkpoint(
    path: str | Path,
    executor: DurableExecutor,
    twin: TemporalState,
) -> CheckpointData:
    """Resume executor and twin state from a checkpoint at *path*.

    Restores the executor and twin state from the checkpoint, verifying
    that the stored hashes match the restored state.  Returns a
    :class:`CheckpointData` with the restored state.
    """
    cp_bytes = Path(path).read_bytes()
    raw = json.loads(cp_bytes.decode("utf-8"))
    if raw.get("checkpoint_version") != CHECKPOINT_VERSION:
        raise ValueError(
            f"unsupported checkpoint version: "
            f"{raw.get('checkpoint_version')!r}"
        )
    executor_state = raw["executor_state"]
    twin_state = raw["twin_state"]
    stored_executor_hash = raw["executor_hash"]
    stored_twin_hash = raw["twin_hash"]

    # Verify hashes match the restored state
    actual_executor_hash = canonical_hash(executor_state)
    actual_twin_hash = canonical_hash(twin_state)
    if actual_executor_hash != stored_executor_hash:
        raise ValueError(
            "executor state hash mismatch: "
            f"expected {stored_executor_hash}, "
            f"got {actual_executor_hash}"
        )
    if actual_twin_hash != stored_twin_hash:
        raise ValueError(
            f"twin state hash mismatch: "
            f"expected {stored_twin_hash}, "
            f"got {actual_twin_hash}"
        )

    # Restore the state into the live objects
    executor.restore_snapshot(
        json.dumps(executor_state, sort_keys=True).encode("utf-8")
    )
    twin.restore_state(
        json.dumps(twin_state, sort_keys=True).encode("utf-8")
    )

    return CheckpointData(
        executor_state=executor_state,
        twin_state=twin_state,
        executor_hash=stored_executor_hash,
        twin_hash=stored_twin_hash,
    )


def checkpoint_hash(path: str | Path) -> str:
    """Return the SHA-256 hex digest of the checkpoint file at *path*."""
    cp_bytes = Path(path).read_bytes()
    return hashlib.sha256(cp_bytes).hexdigest()
