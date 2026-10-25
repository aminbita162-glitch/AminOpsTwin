"""F03: Database connection lost mid-transaction → UNKNOWN; no partial state (G2.9).

Scenario: During a transaction, the database connection is lost. The
state becomes UNKNOWN. No partial state is visible to observers — the
transaction is all-or-nothing.
"""

from __future__ import annotations

from aminopstwin.executor import ExecutorState

from tests.fault.infrastructure import CommitIntentExecutor


class TestF03DatabaseConnectionLost:
    """F03: Database connection lost mid-transaction → UNKNOWN; no partial state."""

    def test_state_becomes_unknown(self) -> None:
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)

        # Database connection lost — state becomes UNKNOWN
        executor.handle_fault_after_commit_intent()
        assert executor.state == ExecutorState.UNKNOWN

    def test_no_partial_state_visible(self) -> None:
        """No partial commit state is visible after the connection loss."""
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)

        # Before the fault, commit_effect_count is 0 (no partial state)
        assert executor.commit_effect_count == 0

        # Fault occurs
        executor.handle_fault_after_commit_intent()
        assert executor.state == ExecutorState.UNKNOWN

        # No partial commit visible — commit_effect_count is still 0
        assert executor.commit_effect_count == 0

        # The state is UNKNOWN, not COMMITTED
        assert executor.state != ExecutorState.COMMITTED

    def test_reconcile_to_committed(self) -> None:
        """After UNKNOWN, reconcile to COMMITTED with exactly one effect."""
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)
        executor.handle_fault_after_commit_intent()
        executor.reconcile_from_unknown()
        assert executor.state == ExecutorState.RECONCILING

        # Reconcile succeeds
        executor.commit()
        assert executor.state == ExecutorState.COMMITTED
        assert executor.commit_effect_count == 1
