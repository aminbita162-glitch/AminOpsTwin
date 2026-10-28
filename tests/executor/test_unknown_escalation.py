"""Tests for P26 deliverable 5: UNKNOWN semantics (ADR-006).

ESCALATED state and its transitions.
"""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.executor import DurableExecutor, ExecutorState


class TestUnknownEscalation:
    """Tests for UNKNOWN -> ESCALATED transition (ADR-006)."""

    def test_unknown_to_escalated(self) -> None:
        executor = DurableExecutor(clock=SeededClock())
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-test")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)
        executor.mark_unknown(wf.workflow_id)
        result = executor.escalate(wf.workflow_id)
        assert result.state is ExecutorState.ESCALATED

    def test_escalated_is_terminal(self) -> None:
        executor = DurableExecutor(clock=SeededClock())
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-test")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)
        executor.mark_unknown(wf.workflow_id)
        executor.escalate(wf.workflow_id)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.COMMITTED)

    def test_escalate_requires_unknown(self) -> None:
        executor = DurableExecutor(clock=SeededClock())
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-test")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        with pytest.raises(ValueError, match="escalate requires UNKNOWN"):
            executor.escalate(wf.workflow_id)

    def test_unknown_can_reconcile_or_escalate(self) -> None:
        """UNKNOWN can go to RECONCILING or ESCALATED."""
        executor = DurableExecutor(clock=SeededClock())
        wf = executor.start(uuid.uuid4(), tenant_id="tenant-test")
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)
        executor.mark_unknown(wf.workflow_id)
        # Reconciliation path
        result = executor.reconcile(wf.workflow_id, committed=True)
        assert result.state is ExecutorState.COMMITTED
