"""F06: Corrupted checkpoint (hash mismatch) → rejected; previous valid used (G2.9).

Scenario: A checkpoint is corrupted (its state_hash is modified). The
corrupted checkpoint is rejected and the previous valid checkpoint is
used instead.
"""

from __future__ import annotations

from src.executor import ExecutorState
from tests.fault.infrastructure import CheckpointableExecutor


class TestF06CorruptedCheckpoint:
    """F06: Corrupted checkpoint → rejected; previous valid used."""

    def test_corrupted_checkpoint_rejected(self) -> None:
        executor = CheckpointableExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.checkpoint()  # checkpoint 1 (RUNNING, valid)
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.checkpoint()  # checkpoint 2 (CHECKPOINTED, valid)
        executor.transition(ExecutorState.COMMIT_INTENT)

        # Corrupt the last checkpoint (checkpoint 2)
        executor.corrupt_last_checkpoint()
        assert not executor.checkpoints[-1].is_valid()

        # Resume should use the previous valid checkpoint (checkpoint 1)
        state = executor.resume_from_last_checkpoint()
        assert state == ExecutorState.RUNNING

    def test_previous_valid_checkpoint_used(self) -> None:
        executor = CheckpointableExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.checkpoint()  # cp1: RUNNING
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.checkpoint()  # cp2: CHECKPOINTED
        executor.transition(ExecutorState.COMMIT_INTENT)
        executor.checkpoint()  # cp3: COMMIT_INTENT

        # Corrupt the most recent checkpoint (cp3)
        executor.corrupt_last_checkpoint()
        assert not executor.checkpoints[-1].is_valid()

        # Resume should use cp2 (the last valid checkpoint)
        state = executor.resume_from_last_checkpoint()
        assert state == ExecutorState.CHECKPOINTED

    def test_uncorrupted_checkpoint_used(self) -> None:
        """Without corruption, the last checkpoint is used."""
        executor = CheckpointableExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.checkpoint()
        executor.transition(ExecutorState.CHECKPOINTED)
        executor.checkpoint()

        state = executor.resume_from_last_checkpoint()
        assert state == ExecutorState.CHECKPOINTED

    def test_all_checkpoints_corrupted(self) -> None:
        """If all checkpoints are corrupted, resume returns current state."""
        executor = CheckpointableExecutor()
        executor.transition(ExecutorState.RUNNING)
        executor.checkpoint()
        executor.corrupt_last_checkpoint()

        # All checkpoints are corrupted — resume returns current state
        state = executor.resume_from_last_checkpoint()
        # The current state is RUNNING (we transitioned there before checkpointing)
        assert state == ExecutorState.RUNNING
