"""Durable Executor (S2) — owns authoritative persisted workflow state.

References: §3.2, §3.6.

P1 skeleton: state machine definition. Full executor in P2.
"""

from __future__ import annotations

from enum import StrEnum

__all__ = ["ExecutorState", "ExecutorStateMachine"]


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
    ExecutorState.PENDING: frozenset({
        ExecutorState.RUNNING,
        ExecutorState.DENIED,
        ExecutorState.FAILED,
    }),
    ExecutorState.RUNNING: frozenset({
        ExecutorState.CHECKPOINTED,
        ExecutorState.DENIED,
        ExecutorState.FAILED,
    }),
    ExecutorState.CHECKPOINTED: frozenset({
        ExecutorState.COMMIT_INTENT,
        ExecutorState.DENIED,
        ExecutorState.FAILED,
    }),
    ExecutorState.COMMIT_INTENT: frozenset({
        ExecutorState.COMMITTED,
        ExecutorState.UNKNOWN,
        ExecutorState.DENIED,
    }),
    ExecutorState.UNKNOWN: frozenset({ExecutorState.RECONCILING}),
    ExecutorState.RECONCILING: frozenset({
        ExecutorState.COMMITTED,
        ExecutorState.FAILED,
    }),
    ExecutorState.COMMITTED: frozenset({ExecutorState.COMPLETED}),
    ExecutorState.COMPLETED: frozenset(),  # terminal
    ExecutorState.DENIED: frozenset(),  # terminal
    ExecutorState.FAILED: frozenset(),  # terminal
}


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
