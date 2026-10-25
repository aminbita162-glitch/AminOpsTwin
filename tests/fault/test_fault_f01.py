"""F01: Process killed during RUNNING → resume from last checkpoint (G2.9).

Scenario: An executor is running and has checkpointed state. The process
is killed (simulated). On resume, the executor restores from the last
valid checkpoint and the final state hash is identical to a clean run.
"""

from __future__ import annotations

from aminopstwin.executor import ExecutorState

from tests.fault.infrastructure import CheckpointableExecutor


class TestF01ResumeFromCheckpoint:
    """F01: Process killed during RUNNING → resume from checkpoint."""

    def test_resume_from_checkpoint_identical_state_hash(self) -> None:
        # --- Clean run (reference) ---
        clean = CheckpointableExecutor()
        clean.transition(ExecutorState.RUNNING)
        clean.checkpoint()
        clean.transition(ExecutorState.CHECKPOINTED)
        clean.checkpoint()
        clean.transition(ExecutorState.COMMIT_INTENT)
        clean.checkpoint()
        clean.transition(ExecutorState.COMMITTED)
        clean.checkpoint()
        clean.transition(ExecutorState.COMPLETED)
        clean_state_hash = clean.state_hash

        # --- Faulty run (killed during RUNNING, then resumed) ---
        faulty = CheckpointableExecutor()
        faulty.transition(ExecutorState.RUNNING)
        faulty.checkpoint()  # checkpoint while RUNNING
        # Process killed here — simulate by resuming from checkpoint
        resumed_state = faulty.resume_from_last_checkpoint()
        assert resumed_state == ExecutorState.RUNNING
        # Continue the workflow from the checkpoint
        faulty.transition(ExecutorState.CHECKPOINTED)
        faulty.checkpoint()
        faulty.transition(ExecutorState.COMMIT_INTENT)
        faulty.checkpoint()
        faulty.transition(ExecutorState.COMMITTED)
        faulty.checkpoint()
        faulty.transition(ExecutorState.COMPLETED)
        faulty_state_hash = faulty.state_hash

        # The final state hash must be identical (F01)
        assert faulty_state_hash == clean_state_hash
        assert faulty.state == ExecutorState.COMPLETED

    def test_checkpoint_created_before_kill(self) -> None:
        """A checkpoint was created before the kill, so it can be resumed."""
        exec_state = CheckpointableExecutor()
        exec_state.transition(ExecutorState.RUNNING)
        cp = exec_state.checkpoint()
        assert cp.state == ExecutorState.RUNNING
        assert cp.is_valid()

    def test_resume_without_checkpoint_returns_current(self) -> None:
        exec_state = CheckpointableExecutor()
        # No checkpoints — resume returns current state (PENDING)
        state = exec_state.resume_from_last_checkpoint()
        assert state == ExecutorState.PENDING
