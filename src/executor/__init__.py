"""Durable Executor (S2) — owns authoritative persisted workflow state.

References: §3.2, §3.6.

P1 skeleton: state machine definition.
P2: full durable executor with checkpoints (G2.2), UNKNOWN recovery (G2.3),
kill/restart snapshot/restore, and canonical state hashing.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.contracts.canonical import canonical_hash
from src.contracts.clock import Clock, SeededClock
from src.executor.experience import (
    ExperienceRecord,
    ExperienceStatus,
    ExperienceStore,
)
from src.executor.memory import (
    MemoryClass,
    MemoryRecord,
    MemoryStore,
    RetentionClass,
)

__all__ = [
    "ExecutorState",
    "ExecutorStateMachine",
    "Checkpoint",
    "WorkflowRecord",
    "DurableExecutor",
    # P4 memory
    "MemoryClass",
    "RetentionClass",
    "MemoryRecord",
    "MemoryStore",
    # P4 experience
    "ExperienceStatus",
    "ExperienceRecord",
    "ExperienceStore",
]


class ExecutorState(StrEnum):
    """Executor state machine states (§3.6)."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    CHECKPOINTED = "CHECKPOINTED"
    COMMIT_INTENT = "COMMIT_INTENT"
    COMMITTED = "COMMITTED"
    COMPLETED = "COMPLETED"
    DENIED = "DENIED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILING = "RECONCILING"


# Valid transitions (§3.6)
_VALID_TRANSITIONS: dict[ExecutorState, frozenset[ExecutorState]] = {
    ExecutorState.PENDING: frozenset(
        {
            ExecutorState.RUNNING,
            ExecutorState.DENIED,
            ExecutorState.FAILED,
        }
    ),
    ExecutorState.RUNNING: frozenset(
        {
            ExecutorState.CHECKPOINTED,
            ExecutorState.DENIED,
            ExecutorState.FAILED,
        }
    ),
    ExecutorState.CHECKPOINTED: frozenset(
        {
            ExecutorState.COMMIT_INTENT,
            ExecutorState.DENIED,
            ExecutorState.FAILED,
        }
    ),
    ExecutorState.COMMIT_INTENT: frozenset(
        {
            ExecutorState.COMMITTED,
            ExecutorState.UNKNOWN,
            ExecutorState.DENIED,
        }
    ),
    ExecutorState.UNKNOWN: frozenset({ExecutorState.RECONCILING}),
    ExecutorState.RECONCILING: frozenset(
        {
            ExecutorState.COMMITTED,
            ExecutorState.FAILED,
        }
    ),
    ExecutorState.COMMITTED: frozenset({ExecutorState.COMPLETED}),
    ExecutorState.COMPLETED: frozenset(),  # terminal
    ExecutorState.DENIED: frozenset(),  # terminal
    ExecutorState.FAILED: frozenset(),  # terminal
}


class Checkpoint(BaseModel):
    """A durable checkpoint capturing workflow state at a point in time.

    The ``state_hash`` is the SHA-256 hash of the canonical bytes of the
    full workflow state at the time the checkpoint was created.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    checkpoint_id: str
    correlation_id: uuid.UUID
    sequence_no: int = Field(ge=0)
    state_hash: str = Field(min_length=64, max_length=64)
    payload: dict[str, Any]
    payload_hash: str
    created_at: _dt.datetime
    version: int = Field(ge=0)


class WorkflowRecord(BaseModel):
    """A durable workflow record with full state history and checkpoints.

    The ``state_hash`` of a :class:`WorkflowRecord` is recomputed from
    the canonical bytes of its full state via :meth:`DurableExecutor.get_state_hash`.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    workflow_id: uuid.UUID
    correlation_id: uuid.UUID
    tenant_id: str = "tenant-default"
    policy_epoch: int = Field(default=0, ge=0)
    state: ExecutorState
    checkpoints: list[Checkpoint] = Field(default_factory=list)
    history: list[ExecutorState] = Field(default_factory=list)
    created_at: _dt.datetime
    updated_at: _dt.datetime


def _workflow_to_canonical_dict(record: WorkflowRecord) -> dict[str, Any]:
    """Convert a WorkflowRecord to a canonical JSON-serialisable dict."""
    return {
        "workflow_id": str(record.workflow_id),
        "correlation_id": str(record.correlation_id),
        "tenant_id": record.tenant_id,
        "policy_epoch": record.policy_epoch,
        "state": record.state.value,
        "checkpoints": [
            {
                "checkpoint_id": cp.checkpoint_id,
                "correlation_id": str(cp.correlation_id),
                "sequence_no": cp.sequence_no,
                "state_hash": cp.state_hash,
                "payload": cp.payload,
                "payload_hash": cp.payload_hash,
                "created_at": cp.created_at.isoformat(),
                "version": cp.version,
            }
            for cp in record.checkpoints
        ],
        "history": [h.value for h in record.history],
        "created_at": record.created_at.isoformat(),
        "updated_at": record.updated_at.isoformat(),
    }


def _workflow_state_hash(record: WorkflowRecord) -> str:
    """SHA-256 hash of the canonical bytes of the full workflow state."""
    return canonical_hash(_workflow_to_canonical_dict(record))


class ExecutorStateMachine:
    """Minimal state machine for the Executor (§3.6)."""

    def __init__(self) -> None:
        self._state = ExecutorState.PENDING
        self._history: list[ExecutorState] = [
            ExecutorState.PENDING
        ]

    @property
    def state(self) -> ExecutorState:
        return self._state

    @property
    def history(self) -> list[ExecutorState]:
        return list(self._history)

    def transition(
        self, target: ExecutorState
    ) -> ExecutorState:
        if target not in _VALID_TRANSITIONS.get(
            self._state, frozenset()
        ):
            raise ValueError(
                f"invalid transition: {self._state.value} "
                f"-> {target.value}"
            )
        self._state = target
        self._history.append(target)
        return self._state

    def can_transition(
        self, target: ExecutorState
    ) -> bool:
        return target in _VALID_TRANSITIONS.get(
            self._state, frozenset()
        )


# ---------------------------------------------------------------------------
# DurableExecutor
# ---------------------------------------------------------------------------


class _MutableWorkflow:
    """Mutable companion to WorkflowRecord.

    WorkflowRecord is frozen (Pydantic), so we keep a mutable copy
    in the executor's store and rebuild the frozen record on each
    mutation.
    """

    __slots__ = (
        "workflow_id",
        "correlation_id",
        "tenant_id",
        "policy_epoch",
        "state",
        "checkpoints",
        "history",
        "created_at",
        "updated_at",
        "_next_seq",
        "_cp_counter",
    )

    def __init__(
        self,
        workflow_id: uuid.UUID,
        correlation_id: uuid.UUID,
        tenant_id: str,
        policy_epoch: int,
        state: ExecutorState,
        created_at: _dt.datetime,
        updated_at: _dt.datetime,
        history: list[ExecutorState] | None = None,
        checkpoints: list[Checkpoint] | None = None,
    ) -> None:
        self.workflow_id = workflow_id
        self.correlation_id = correlation_id
        self.tenant_id = tenant_id
        self.policy_epoch = policy_epoch
        self.state = state
        self.checkpoints: list[Checkpoint] = list(checkpoints or [])
        self.history: list[ExecutorState] = list(history or [])
        self.created_at = created_at
        self.updated_at = updated_at
        self._next_seq = len(self.checkpoints)
        self._cp_counter = 0

    def to_record(self) -> WorkflowRecord:
        return WorkflowRecord(
            workflow_id=self.workflow_id,
            correlation_id=self.correlation_id,
            tenant_id=self.tenant_id,
            policy_epoch=self.policy_epoch,
            state=self.state,
            checkpoints=list(self.checkpoints),
            history=list(self.history),
            created_at=self.created_at,
            updated_at=self.updated_at,
        )

    @classmethod
    def from_record(cls, record: WorkflowRecord) -> _MutableWorkflow:
        return cls(
            workflow_id=record.workflow_id,
            correlation_id=record.correlation_id,
            tenant_id=record.tenant_id,
            policy_epoch=record.policy_epoch,
            state=record.state,
            created_at=record.created_at,
            updated_at=record.updated_at,
            history=list(record.history),
            checkpoints=list(record.checkpoints),
        )


def _now(clock: Clock) -> _dt.datetime:
    """Get a timezone-aware UTC datetime from *clock*."""
    dt = clock.now()
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.UTC)
    return dt


class DurableExecutor:
    """Durable workflow executor with checkpoints and kill/restart support.

    The executor maintains an in-memory store of :class:`WorkflowRecord`
    instances, keyed by ``workflow_id``. Each mutation produces a new
    frozen record; the store is a ``dict[UUID, _MutableWorkflow]`` so
    that the frozen records can be rebuilt deterministically.

    Checkpoints capture the state hash at a point in time; the
    snapshot/restore pair serialises all workflow state deterministically
    so that a restarted executor produces the same state hashes (G2.2).
    """

    def __init__(
        self,
        *,
        clock: Clock | None = None,
    ) -> None:
        self._clock: Clock = clock if clock is not None else SeededClock()
        self._store: dict[uuid.UUID, _MutableWorkflow] = {}

    # -- public API --

    def start(
        self,
        correlation_id: uuid.UUID,
        tenant_id: str = "tenant-default",
        policy_epoch: int = 0,
    ) -> WorkflowRecord:
        """Start a new workflow in the PENDING state."""
        wf_id = uuid.uuid4()
        now = _now(self._clock)
        wf = _MutableWorkflow(
            workflow_id=wf_id,
            correlation_id=correlation_id,
            tenant_id=tenant_id,
            policy_epoch=policy_epoch,
            state=ExecutorState.PENDING,
            created_at=now,
            updated_at=now,
            history=[ExecutorState.PENDING],
        )
        self._store[wf_id] = wf
        return wf.to_record()

    def get_workflow(self, workflow_id: uuid.UUID) -> WorkflowRecord | None:
        """Return the workflow record for *workflow_id*, or None."""
        wf = self._store.get(workflow_id)
        if wf is None:
            return None
        return wf.to_record()

    def _require(self, workflow_id: uuid.UUID) -> _MutableWorkflow:
        wf = self._store.get(workflow_id)
        if wf is None:
            raise KeyError(f"workflow not found: {workflow_id}")
        return wf

    def _do_transition(
        self,
        workflow_id: uuid.UUID,
        target: ExecutorState,
    ) -> WorkflowRecord:
        wf = self._require(workflow_id)
        if target not in _VALID_TRANSITIONS.get(wf.state, frozenset()):
            raise ValueError(
                f"invalid transition: {wf.state.value} -> {target.value}"
            )
        wf.state = target
        wf.history.append(target)
        wf.updated_at = _now(self._clock)
        return wf.to_record()

    def transition(
        self,
        workflow_id: uuid.UUID,
        target_state: ExecutorState,
    ) -> WorkflowRecord:
        """Validate and apply a state transition, appending to history."""
        return self._do_transition(workflow_id, target_state)

    def checkpoint(
        self,
        workflow_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> Checkpoint:
        """Create a checkpoint at the current state.

        The ``state_hash`` is computed from
        :func:`canonical_hash(payload)` and the checkpoint's
        ``payload_hash`` is the canonical hash of the payload.
        """
        wf = self._require(workflow_id)
        payload_hash = canonical_hash(payload)
        state_hash = payload_hash  # state hash from payload canonical hash
        seq = wf._next_seq
        wf._next_seq = seq + 1
        wf._cp_counter += 1
        cp_id = f"cp-{wf.workflow_id}-{seq:06d}"
        cp = Checkpoint(
            checkpoint_id=cp_id,
            correlation_id=wf.correlation_id,
            sequence_no=seq,
            state_hash=state_hash,
            payload=dict(payload),
            payload_hash=payload_hash,
            created_at=_now(self._clock),
            version=wf._cp_counter,
        )
        wf.checkpoints.append(cp)
        wf.updated_at = _now(self._clock)
        return cp

    def commit_intent(
        self,
        workflow_id: uuid.UUID,
        payload: dict[str, Any],
    ) -> WorkflowRecord:
        """Transition to COMMIT_INTENT and create a checkpoint."""
        self.checkpoint(workflow_id, payload)
        return self._do_transition(workflow_id, ExecutorState.COMMIT_INTENT)

    def commit(self, workflow_id: uuid.UUID) -> WorkflowRecord:
        """Transition COMMIT_INTENT -> COMMITTED."""
        wf = self._require(workflow_id)
        if wf.state is not ExecutorState.COMMIT_INTENT:
            raise ValueError(
                f"commit requires COMMIT_INTENT, got {wf.state.value}"
            )
        return self._do_transition(workflow_id, ExecutorState.COMMITTED)

    def complete(self, workflow_id: uuid.UUID) -> WorkflowRecord:
        """Transition COMMITTED -> COMPLETED."""
        wf = self._require(workflow_id)
        if wf.state is not ExecutorState.COMMITTED:
            raise ValueError(
                f"complete requires COMMITTED, got {wf.state.value}"
            )
        return self._do_transition(workflow_id, ExecutorState.COMPLETED)

    def fail(self, workflow_id: uuid.UUID) -> WorkflowRecord:
        """Transition to FAILED (terminal)."""
        return self._do_transition(workflow_id, ExecutorState.FAILED)

    def deny(self, workflow_id: uuid.UUID) -> WorkflowRecord:
        """Transition to DENIED (terminal)."""
        return self._do_transition(workflow_id, ExecutorState.DENIED)

    def mark_unknown(self, workflow_id: uuid.UUID) -> WorkflowRecord:
        """Transition to UNKNOWN (from COMMIT_INTENT)."""
        wf = self._require(workflow_id)
        if wf.state is not ExecutorState.COMMIT_INTENT:
            raise ValueError(
                f"mark_unknown requires COMMIT_INTENT, got {wf.state.value}"
            )
        return self._do_transition(workflow_id, ExecutorState.UNKNOWN)

    def reconcile(
        self,
        workflow_id: uuid.UUID,
        committed: bool,
    ) -> WorkflowRecord:
        """Reconcile from UNKNOWN: UNKNOWN -> RECONCILING -> COMMITTED|FAILED."""
        wf = self._require(workflow_id)
        if wf.state is not ExecutorState.UNKNOWN:
            raise ValueError(
                f"reconcile requires UNKNOWN, got {wf.state.value}"
            )
        # UNKNOWN -> RECONCILING
        self._do_transition(workflow_id, ExecutorState.RECONCILING)
        # RECONCILING -> COMMITTED | FAILED
        target = ExecutorState.COMMITTED if committed else ExecutorState.FAILED
        return self._do_transition(workflow_id, target)

    def get_state_hash(self, workflow_id: uuid.UUID) -> str:
        """Return the SHA-256 hash of the canonical bytes of the full workflow state."""
        wf = self._require(workflow_id)
        return _workflow_state_hash(wf.to_record())

    def save_snapshot(self) -> bytes:
        """Return a deterministic serialisation of all workflow state."""
        items: list[dict[str, Any]] = []
        for wf_id in sorted(self._store.keys()):
            wf = self._store[wf_id]
            record = wf.to_record()
            items.append(_workflow_to_canonical_dict(record))
        data = {"workflows": items}
        return json.dumps(
            data,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")

    def restore_snapshot(self, data: bytes) -> None:
        """Restore all workflow state from a snapshot."""
        raw = json.loads(data.decode("utf-8"))
        new_store: dict[uuid.UUID, _MutableWorkflow] = {}
        for item in raw["workflows"]:
            wid = uuid.UUID(item["workflow_id"])
            checkpoints = [
                Checkpoint(
                    checkpoint_id=cp["checkpoint_id"],
                    correlation_id=uuid.UUID(cp["correlation_id"]),
                    sequence_no=cp["sequence_no"],
                    state_hash=cp["state_hash"],
                    payload=cp["payload"],
                    payload_hash=cp["payload_hash"],
                    created_at=_dt.datetime.fromisoformat(cp["created_at"]),
                    version=cp["version"],
                )
                for cp in item["checkpoints"]
            ]
            history = [ExecutorState(h) for h in item["history"]]
            wf = _MutableWorkflow(
                workflow_id=wid,
                correlation_id=uuid.UUID(item["correlation_id"]),
                tenant_id=item["tenant_id"],
                policy_epoch=item["policy_epoch"],
                state=ExecutorState(item["state"]),
                created_at=_dt.datetime.fromisoformat(item["created_at"]),
                updated_at=_dt.datetime.fromisoformat(item["updated_at"]),
                history=history,
                checkpoints=checkpoints,
            )
            wf._next_seq = len(checkpoints)
            wf._cp_counter = len(checkpoints)
            new_store[wid] = wf
        self._store = new_store

    def snapshot_hash(self) -> str:
        """Return the SHA-256 hash of the current snapshot bytes."""
        return hashlib.sha256(self.save_snapshot()).hexdigest()
