"""Tests for P26 deliverable 4: Revocation (ADR-003).

G26.5: revocation between CHECKPOINTED and COMMIT_INTENT -> 0 commits.
"""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.contracts.clock import SeededClock
from aminopstwin.executor import DurableExecutor, ExecutorState


class TestRevocation:
    """Tests for revocation semantics (ADR-003)."""

    def test_revoke_from_checkpointed(self) -> None:
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        result = executor.revoke(wf.workflow_id)
        assert result.state is ExecutorState.REVOKED

    def test_revoke_prevents_commit(self) -> None:
        """G26.5: revocation between CHECKPOINTED and COMMIT_INTENT -> 0 commits."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.revoke(wf.workflow_id)
        # After REVOKED, no commit is possible (terminal state).
        result = executor.get_workflow(wf.workflow_id)
        assert result is not None
        assert result.state is ExecutorState.REVOKED
        # Verify we cannot transition from REVOKED.
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.COMMIT_INTENT)

    def test_re_authorise_revoked(self) -> None:
        """Re-authorisation hook: if revoked, workflow goes to REVOKED."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        result = executor.re_authorise(wf.workflow_id, is_revoked=True)
        assert result.state is ExecutorState.REVOKED

    def test_re_authorise_not_revoked(self) -> None:
        """Re-authorisation hook: if not revoked, proceeds to COMMIT_INTENT."""
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        result = executor.re_authorise(wf.workflow_id, is_revoked=False)
        assert result.state is ExecutorState.COMMIT_INTENT

    def test_revoke_requires_checkpointed(self) -> None:
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        with pytest.raises(ValueError, match="revoke requires CHECKPOINTED"):
            executor.revoke(wf.workflow_id)

    def test_revoked_is_terminal(self) -> None:
        clock = SeededClock()
        executor = DurableExecutor(clock=clock)
        wf = executor.start(uuid.uuid4())
        executor.transition(wf.workflow_id, ExecutorState.RUNNING)
        executor.transition(wf.workflow_id, ExecutorState.CHECKPOINTED)
        executor.revoke(wf.workflow_id)
        with pytest.raises(ValueError, match="invalid transition"):
            executor.transition(wf.workflow_id, ExecutorState.COMMITTED)
