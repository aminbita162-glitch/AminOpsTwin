"""TOCTOU-safe policy epoch commit (P12, §107–111, G12.3).

The commit transaction must atomically verify that the policy epoch has
not changed between the time the step was read and the time it is
committed.  This closes the time-of-check-to-time-of-use (TOCTOU) gap
for ``policy_epoch``.

The SQL pattern (§109–110):

.. code-block:: sql

    UPDATE steps
       SET state='COMMITTED', version=version+1
     WHERE id=:id
       AND version=:v
       AND :epoch = (SELECT current_epoch FROM policy_state FOR SHARE);

Zero rows affected → the step was stale (epoch changed or version
mismatch) → retry or DENY with ``GW-EPOCH-001``.

This module provides an in-memory implementation of the same atomic
contract, backed by a ``PolicyStateStore`` that holds the current
epoch under a lock.  The ``toctou_commit`` function performs the
optimistic-concurrency update atomically and returns the outcome.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Final

__all__ = [
    "CommitOutcome",
    "CommitResult",
    "PolicyStateStore",
    "StepRecord",
    "StepState",
    "StaleEpochError",
    "toctou_commit",
]


R_STALE_EPOCH: Final[str] = "GW-EPOCH-001"
R_VERSION_MISMATCH: Final[str] = "GW-EPOCH-003"


class StepState(StrEnum):
    """States for a step in the TOCTOU commit model."""

    PENDING = "PENDING"
    COMMITTED = "COMMITTED"
    DENIED = "DENIED"


class CommitOutcome(StrEnum):
    """Outcome of a TOCTOU commit attempt."""

    COMMITTED = "COMMITTED"
    RETRY = "RETRY"
    DENIED = "DENIED"


class StaleEpochError(Exception):
    """Raised when a commit is attempted with a stale policy epoch."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


@dataclass
class StepRecord:
    """A single step record with version and epoch for OCC."""

    step_id: str
    state: StepState = StepState.PENDING
    version: int = 0
    policy_epoch: int = 0
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class CommitResult:
    """Result of a toctou_commit call."""

    outcome: CommitOutcome
    step_id: str
    new_version: int = 0
    reason_code: str | None = None
    detail: str | None = None


class PolicyStateStore:
    """Thread-safe store holding the current policy epoch and steps.

    The ``current_epoch`` is protected by a lock so that the TOCTOU
    check-and-commit is atomic: no thread can change the epoch between
    the read and the write.
    """

    def __init__(self, initial_epoch: int = 0) -> None:
        self._lock = threading.Lock()
        self._current_epoch: int = initial_epoch
        self._steps: dict[str, StepRecord] = {}

    @property
    def current_epoch(self) -> int:
        with self._lock:
            return self._current_epoch

    def set_epoch(self, epoch: int) -> None:
        with self._lock:
            self._current_epoch = epoch

    def advance_epoch(self) -> int:
        with self._lock:
            self._current_epoch += 1
            return self._current_epoch

    def put_step(self, step: StepRecord) -> None:
        with self._lock:
            self._steps[step.step_id] = step

    def get_step(self, step_id: str) -> StepRecord | None:
        with self._lock:
            return self._steps.get(step_id)

    def all_steps(self) -> list[StepRecord]:
        with self._lock:
            return list(self._steps.values())

    def commit_step(
        self,
        step_id: str,
        expected_version: int,
        expected_epoch: int,
    ) -> CommitResult:
        """Atomically commit a step if version and epoch still match.

        This is the in-memory equivalent of the SQL UPDATE...WHERE
        pattern (§109–110).  Under the lock:
          1. Read the step and the current epoch.
          2. If the step's version != expected_version → VERSION_MISMATCH.
          3. If the current_epoch != expected_epoch → STALE_EPOCH.
          4. Otherwise: set state=COMMITTED, version += 1.
          5. Return COMMITTED or the failure reason.
        """
        with self._lock:
            step = self._steps.get(step_id)
            if step is None:
                return CommitResult(
                    outcome=CommitOutcome.DENIED,
                    step_id=step_id,
                    reason_code="GW-EPOCH-004",
                    detail=f"step not found: {step_id}",
                )

            current = self._current_epoch

            # Check epoch atomically (the TOCTOU guard)
            if current != expected_epoch:
                return CommitResult(
                    outcome=CommitOutcome.RETRY,
                    step_id=step_id,
                    reason_code=R_STALE_EPOCH,
                    detail=(
                        f"epoch changed: expected {expected_epoch}, "
                        f"current {current}"
                    ),
                )

            # Check version (optimistic concurrency)
            if step.version != expected_version:
                return CommitResult(
                    outcome=CommitOutcome.DENIED,
                    step_id=step_id,
                    reason_code=R_VERSION_MISMATCH,
                    detail=(
                        f"version mismatch: expected "
                        f"{expected_version}, actual {step.version}"
                    ),
                )

            # Atomically commit
            step.state = StepState.COMMITTED
            step.version += 1
            return CommitResult(
                outcome=CommitOutcome.COMMITTED,
                step_id=step_id,
                new_version=step.version,
            )


def toctou_commit(
    store: PolicyStateStore,
    step_id: str,
    expected_version: int,
    expected_epoch: int,
    max_retries: int = 0,
) -> CommitResult:
    """Attempt a TOCTOU-safe commit, optionally retrying on epoch change.

    If the epoch changed between read and commit, the result is RETRY
    (unless ``max_retries`` is exhausted).  If the version mismatched
    (step was already committed by a concurrent attempt), the result is
    DENIED with ``GW-EPOCH-003``.
    """
    last_result: CommitResult | None = None
    for _attempt in range(max_retries + 1):
        last_result = store.commit_step(
            step_id, expected_version, expected_epoch
        )
        if last_result.outcome is not CommitOutcome.RETRY:
            return last_result
        # On retry, re-read the current epoch for the next attempt
        expected_epoch = store.current_epoch

    # Unreachable: the loop runs at least once, so last_result is set.
    assert last_result is not None
    return last_result
