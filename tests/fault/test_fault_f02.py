"""F02: Kill between COMMIT_INTENT and COMMITTED → UNKNOWN → RECONCILING (G2.9).

Scenario: The executor reaches COMMIT_INTENT. A fault occurs before
COMMITTED. The state becomes UNKNOWN, then RECONCILING. After
reconciliation, the commit effect is applied exactly once.
"""

from __future__ import annotations

from src.executor import ExecutorState
from tests.fault.infrastructure import CommitIntentExecutor


class TestF02CommitIntentFault:
    """F02: Kill between COMMIT_INTENT and COMMITTED → UNKNOWN → RECONCILING."""

    def test_unknown_then_reconciling(self) -> None:
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)

        # Fault occurs — state becomes UNKNOWN
        executor.handle_fault_after_commit_intent()
        assert executor.state == ExecutorState.UNKNOWN

        # Then RECONCILING
        executor.reconcile_from_unknown()
        assert executor.state == ExecutorState.RECONCILING

    def test_exactly_one_commit_effect(self) -> None:
        """After reconciliation, the commit effect is applied exactly once."""
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)

        # Fault
        executor.handle_fault_after_commit_intent()
        executor.reconcile_from_unknown()
        assert executor.state == ExecutorState.RECONCILING

        # Reconcile and commit
        executor.commit()

        # Commit again (idempotency check) — should not add another effect
        executor.commit()

        assert executor.commit_effect_count == 1

    def test_reconciling_state_reached(self) -> None:
        """After UNKNOWN, the state must reach RECONCILING."""
        executor = CommitIntentExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.transition(ExecutorState.COMMIT_INTENT)
        executor.handle_fault_after_commit_intent()
        executor.reconcile_from_unknown()
        states = executor.history
        assert ExecutorState.UNKNOWN in states
        assert ExecutorState.RECONCILING in states
