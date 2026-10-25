"""Tests for the Durable Executor (S2).

State machine, checkpoints, kill/restart (G2.2, G2.3).
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.executor import (
    Checkpoint,
    DurableExecutor,
    ExecutorState,
    WorkflowRecord,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def clock() -> SeededClock:
    return SeededClock(start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC))


@pytest.fixture
def executor(clock: SeededClock) -> DurableExecutor:
    return DurableExecutor(clock=clock)


@pytest.fixture
def cid() -> uuid.UUID:
    return uuid.UUID("12345678-1234-5678-1234-567812345678")


# ---------------------------------------------------------------------------
# State machine transitions — valid
# ---------------------------------------------------------------------------


class TestStateMachineValid:
    """Valid state machine transitions."""

    def test_start_creates_pending(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        assert wf.state is ExecutorState.PENDING
        assert wf.correlation_id == cid
        assert wf.tenant_id == "tenant-default"
        assert wf.policy_epoch == 0
        assert wf.history == [ExecutorState.PENDING]

    def test_pending_to_running(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wf = executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        assert wf.state is ExecutorState.RUNNING
        assert wf.history == [ExecutorState.PENDING, ExecutorState.RUNNING]

    def test_full_happy_path(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id

        wf = executor.transition(wid, ExecutorState.RUNNING)
        assert wf.state is ExecutorState.RUNNING

        wf = executor.transition(wid, ExecutorState.CHECKPOINTED)
        assert wf.state is ExecutorState.CHECKPOINTED

        wf = executor.commit_intent(wid, {"step": 1})
        assert wf.state is ExecutorState.COMMIT_INTENT

        wf = executor.commit(wid)
        assert wf.state is ExecutorState.COMMITTED

        wf = executor.complete(wid)
        assert wf.state is ExecutorState.COMPLETED
        assert wf.history[-1] is ExecutorState.COMPLETED

    def test_deny_from_pending(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wf = executor.deny(wf.workflow_id)
        assert wf.state is ExecutorState.DENIED

    def test_fail_from_running(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wf = executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        wf = executor.fail(wf.workflow_id)
        assert wf.state is ExecutorState.FAILED


# ---------------------------------------------------------------------------
# State machine transitions — invalid
# ---------------------------------------------------------------------------


class TestStateMachineInvalid:
    """Invalid transitions raise ValueError."""

    def test_pending_to_committed_invalid(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.COMMITTED)

    def test_running_to_completed_invalid(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.COMPLETED)

    def test_completed_to_pending_invalid(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"k": 1})
        executor.commit(wid)
        executor.complete(wid)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wid, ExecutorState.PENDING)

    def test_commit_requires_commit_intent(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        with pytest.raises(ValueError, match="commit requires"):
            executor.commit(wf.workflow_id)

    def test_complete_requires_committed(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        with pytest.raises(ValueError, match="complete requires"):
            executor.complete(wf.workflow_id)


# ---------------------------------------------------------------------------
# Terminal states not rewriteable
# ---------------------------------------------------------------------------


class TestTerminalStates:
    """Terminal states reject all transitions."""

    @pytest.mark.parametrize(
        "terminal_fn",
        ["fail", "deny"],
    )
    def test_terminal_blocks_transition(
        self,
        executor: DurableExecutor,
        cid: uuid.UUID,
        terminal_fn: str,
    ) -> None:
        wf = executor.start(cid)
        method = getattr(executor, terminal_fn)
        method(wf.workflow_id)  # reach terminal
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.RUNNING)

    def test_completed_blocks_transition(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"x": 1})
        executor.commit(wid)
        executor.complete(wid)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wid, ExecutorState.RUNNING)

    def test_failed_blocks_transition(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        executor.fail(wf.workflow_id)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(
                wf.workflow_id, ExecutorState.COMPLETED
            )


# ---------------------------------------------------------------------------
# Checkpoint creation and state hash computation
# ---------------------------------------------------------------------------


class TestCheckpoint:
    """Checkpoint creation and state hash computation."""

    def test_checkpoint_returns_checkpoint(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        cp = executor.checkpoint(wf.workflow_id, {"step": 1})
        assert isinstance(cp, Checkpoint)
        assert cp.sequence_no == 0
        assert cp.correlation_id == cid
        assert len(cp.state_hash) == 64
        assert cp.payload == {"step": 1}

    def test_checkpoint_state_hash_is_payload_hash(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        cp = executor.checkpoint(wf.workflow_id, {"a": 1})
        assert cp.state_hash == cp.payload_hash
        assert len(cp.state_hash) == 64

    def test_checkpoint_sequence_increments(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        cp0 = executor.checkpoint(wf.workflow_id, {"n": 0})
        cp1 = executor.checkpoint(wf.workflow_id, {"n": 1})
        cp2 = executor.checkpoint(wf.workflow_id, {"n": 2})
        assert cp0.sequence_no == 0
        assert cp1.sequence_no == 1
        assert cp2.sequence_no == 2

    def test_checkpoint_id_unique(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        cp0 = executor.checkpoint(wf.workflow_id, {"x": 1})
        cp1 = executor.checkpoint(wf.workflow_id, {"x": 2})
        assert cp0.checkpoint_id != cp1.checkpoint_id

    def test_get_state_hash_deterministic(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.checkpoint(wf.workflow_id, {"v": 1})
        h1 = executor.get_state_hash(wf.workflow_id)
        h2 = executor.get_state_hash(wf.workflow_id)
        assert h1 == h2
        assert len(h1) == 64

    def test_get_workflow_none_for_missing(
        self, executor: DurableExecutor
    ) -> None:
        assert executor.get_workflow(uuid.uuid4()) is None

    def test_get_workflow_returns_record(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        record = executor.get_workflow(wf.workflow_id)
        assert record is not None
        assert isinstance(record, WorkflowRecord)
        assert record.workflow_id == wf.workflow_id


# ---------------------------------------------------------------------------
# Kill/restart: save snapshot, create new executor, restore, verify state hash
# (G2.2)
# ---------------------------------------------------------------------------


class TestKillRestart:
    """Kill/restart simulation with snapshot/restore (G2.2)."""

    def test_save_restore_identical_state_hash(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.checkpoint(wid, {"step": 1})
        executor.transition(wid, ExecutorState.CHECKPOINTED)

        original_hash = executor.get_state_hash(wid)
        snapshot = executor.save_snapshot()

        # Simulate kill: create a new executor
        new_executor = DurableExecutor(clock=SeededClock())
        assert len(new_executor._store) == 0  # noqa: SLF001

        # Restore
        new_executor.restore_snapshot(snapshot)
        restored_hash = new_executor.get_state_hash(wid)
        assert restored_hash == original_hash

    def test_snapshot_is_bytes(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        executor.start(cid)
        snap = executor.save_snapshot()
        assert isinstance(snap, bytes)
        assert len(snap) > 0

    def test_snapshot_deterministic(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        executor.start(cid)
        s1 = executor.save_snapshot()
        s2 = executor.save_snapshot()
        assert s1 == s2

    def test_restore_multiple_workflows(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf1 = executor.start(cid)
        wf2 = executor.start(cid)
        executor.transition(wf1.workflow_id, ExecutorState.RUNNING)
        executor.checkpoint(wf2.workflow_id, {"k": 1})

        snapshot = executor.save_snapshot()
        new_executor = DurableExecutor(clock=SeededClock())
        new_executor.restore_snapshot(snapshot)

        r1 = new_executor.get_workflow(wf1.workflow_id)
        r2 = new_executor.get_workflow(wf2.workflow_id)
        assert r1 is not None
        assert r2 is not None
        assert r1.state is ExecutorState.RUNNING
        assert len(r2.checkpoints) == 1


# ---------------------------------------------------------------------------
# 5 distinct checkpoints with identical final state hash on restart
# ---------------------------------------------------------------------------


class TestFiveCheckpointsRestart:
    """Five distinct checkpoints; restored executor has identical state hash."""

    def test_five_checkpoints_same_state_hash_after_restart(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id

        payloads: list[dict[str, int | str]] = [
            {"step": 0, "label": "init"},
            {"step": 1, "label": "first"},
            {"step": 2, "label": "second"},
            {"step": 3, "label": "third"},
            {"step": 4, "label": "fourth"},
        ]
        for pl in payloads:
            executor.checkpoint(wid, pl)

        original_hash = executor.get_state_hash(wid)
        snapshot = executor.save_snapshot()

        # Kill and restart
        new_executor = DurableExecutor(clock=SeededClock())
        new_executor.restore_snapshot(snapshot)
        restored_hash = new_executor.get_state_hash(wid)

        assert restored_hash == original_hash

        # Verify all 5 checkpoints survived
        restored_wf = new_executor.get_workflow(wid)
        assert restored_wf is not None
        assert len(restored_wf.checkpoints) == 5
        for i, cp in enumerate(restored_wf.checkpoints):
            assert cp.sequence_no == i


# ---------------------------------------------------------------------------
# UNKNOWN -> RECONCILING -> COMMITTED | FAILED transitions (G2.3)
# ---------------------------------------------------------------------------


class TestUnknownRecovery:
    """UNKNOWN recovery path (G2.3)."""

    def test_mark_unknown_from_commit_intent(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"x": 1})
        wf = executor.mark_unknown(wid)
        assert wf.state is ExecutorState.UNKNOWN

    def test_reconcile_to_committed(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"x": 1})
        executor.mark_unknown(wid)
        wf = executor.reconcile(wid, committed=True)
        assert wf.state is ExecutorState.COMMITTED
        assert ExecutorState.RECONCILING in wf.history
        assert ExecutorState.COMMITTED in wf.history

    def test_reconcile_to_failed(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"x": 1})
        executor.mark_unknown(wid)
        wf = executor.reconcile(wid, committed=False)
        assert wf.state is ExecutorState.FAILED

    def test_reconcile_requires_unknown(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        with pytest.raises(ValueError, match="reconcile requires"):
            executor.reconcile(wf.workflow_id, committed=True)

    def test_reconcile_then_complete(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        wid = wf.workflow_id
        executor.transition(wid, ExecutorState.RUNNING)
        executor.transition(wid, ExecutorState.CHECKPOINTED)
        executor.commit_intent(wid, {"x": 1})
        executor.mark_unknown(wid)
        executor.reconcile(wid, committed=True)
        wf = executor.complete(wid)
        assert wf.state is ExecutorState.COMPLETED

    def test_mark_unknown_requires_commit_intent(
        self, executor: DurableExecutor, cid: uuid.UUID
    ) -> None:
        wf = executor.start(cid)
        with pytest.raises(ValueError, match="mark_unknown requires"):
            executor.mark_unknown(wf.workflow_id)


# ---------------------------------------------------------------------------
# Pydantic model validation
# ---------------------------------------------------------------------------


class TestPydanticModels:
    """Pydantic model validation for Checkpoint and WorkflowRecord."""

    def test_checkpoint_is_frozen(self) -> None:
        cp = Checkpoint(
            checkpoint_id="cp-test-000000",
            correlation_id=uuid.uuid4(),
            sequence_no=0,
            state_hash="a" * 64,
            payload={"k": 1},
            payload_hash="b" * 64,
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            version=0,
        )
        with pytest.raises(ValidationError):
            cp.checkpoint_id = "changed"  # type: ignore[misc]

    def test_checkpoint_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            Checkpoint(
                checkpoint_id="cp-test-000000",
                correlation_id=uuid.uuid4(),
                sequence_no=0,
                state_hash="a" * 64,
                payload={"k": 1},
                payload_hash="b" * 64,
                created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                version=0,
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_checkpoint_negative_sequence_rejected(self) -> None:
        with pytest.raises(ValidationError):
            Checkpoint(
                checkpoint_id="cp-test",
                correlation_id=uuid.uuid4(),
                sequence_no=-1,
                state_hash="a" * 64,
                payload={},
                payload_hash="b" * 64,
                created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                version=0,
            )

    def test_workflow_record_is_frozen(self) -> None:
        wf = WorkflowRecord(
            workflow_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            tenant_id="tenant-default",
            policy_epoch=0,
            state=ExecutorState.PENDING,
            checkpoints=[],
            history=[ExecutorState.PENDING],
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            updated_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        with pytest.raises(ValidationError):
            wf.tenant_id = "changed"  # type: ignore[misc]

    def test_workflow_record_rejects_extra_fields(self) -> None:
        with pytest.raises(ValidationError):
            WorkflowRecord(
                workflow_id=uuid.uuid4(),
                correlation_id=uuid.uuid4(),
                tenant_id="tenant-default",
                policy_epoch=0,
                state=ExecutorState.PENDING,
                checkpoints=[],
                history=[ExecutorState.PENDING],
                created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                updated_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                extra="bad",  # type: ignore[call-arg]
            )

    def test_workflow_record_default_tenant(self) -> None:
        wf = WorkflowRecord(
            workflow_id=uuid.uuid4(),
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
            state=ExecutorState.PENDING,
            created_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            updated_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
        )
        assert wf.tenant_id == "tenant-default"
