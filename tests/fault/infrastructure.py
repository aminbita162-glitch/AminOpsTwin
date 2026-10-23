"""Fault injection test infrastructure for F01–F08 (G2.9).

Provides the minimal executor extensions needed to test fault scenarios:
    - CheckpointableExecutor with checkpoint/resume (F01, F06)
    - CommitIntentExecutor with UNKNOWN/RECONCILING states (F02, F03)
    - IdempotentDelivery for duplicate detection (F04)
    - OrderedEventBuffer for out-of-order reordering (F05)
    - LLM timeout and malformed output handling (F07, F08)
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.contracts.canonical import canonical_hash
from src.executor import ExecutorState, ExecutorStateMachine
from src.tokens.fallback import FallbackReason, FallbackResponse, ReservationStatus

__all__ = [
    "Checkpoint",
    "CheckpointableExecutor",
    "CommitIntentExecutor",
    "IdempotentDelivery",
    "OrderedEventBuffer",
    "LLMTimeoutSimulator",
    "LLMMalformedSimulator",
    "compute_state_hash",
]


def compute_state_hash(history: list[ExecutorState]) -> str:
    """Compute SHA-256 hash of the executor state history."""
    state_str = "|".join(s.value for s in history)
    return hashlib.sha256(state_str.encode("utf-8")).hexdigest()


@dataclass
class Checkpoint:
    """A single checkpoint in the executor state history."""

    state: ExecutorState
    sequence_no: int
    state_hash: str
    payload_hash: str | None = None

    def is_valid(self) -> bool:
        """Verify the checkpoint's state_hash matches recomputed hash."""
        return (
            self.state_hash
            == hashlib.sha256(
                self.state.value.encode("utf-8")
            ).hexdigest()
        )


class CheckpointableExecutor(ExecutorStateMachine):
    """Executor with checkpointing for fault injection (F01, F06).

    Stores checkpoints at each state transition. On resume, the
    executor restores from the last valid checkpoint.
    """

    def __init__(self) -> None:
        super().__init__()
        self._checkpoints: list[Checkpoint] = []
        self._sequence: int = 0

    @property
    def checkpoints(self) -> list[Checkpoint]:
        return list(self._checkpoints)

    def checkpoint(self, payload_hash: str | None = None) -> Checkpoint:
        """Create a checkpoint at the current state."""
        self._sequence += 1
        cp = Checkpoint(
            state=self._state,
            sequence_no=self._sequence,
            state_hash=hashlib.sha256(
                self._state.value.encode("utf-8")
            ).hexdigest(),
            payload_hash=payload_hash,
        )
        self._checkpoints.append(cp)
        return cp

    def resume_from_last_checkpoint(self) -> ExecutorState:
        """Resume from the last valid checkpoint.

        If the last checkpoint is invalid (hash mismatch), use the
        previous valid one (F06).
        """
        if not self._checkpoints:
            return self._state

        # Find the last valid checkpoint
        valid = [cp for cp in self._checkpoints if cp.is_valid()]
        if not valid:
            return self._state

        last = valid[-1]
        # Restore state from the checkpoint, preserving the full history
        self._state = last.state
        return self._state

    def corrupt_last_checkpoint(self) -> None:
        """Corrupt the last checkpoint's state_hash (for F06)."""
        if self._checkpoints:
            cp = self._checkpoints[-1]
            self._checkpoints[-1] = Checkpoint(
                state=cp.state,
                sequence_no=cp.sequence_no,
                state_hash="0" * 64,  # corrupted hash
                payload_hash=cp.payload_hash,
            )

    @property
    def state_hash(self) -> str:
        return compute_state_hash(self.history)


class CommitIntentExecutor(CheckpointableExecutor):
    """Executor with COMMIT_INTENT → UNKNOWN → RECONCILING flow (F02, F03).

    After COMMIT_INTENT, if a fault occurs, the state becomes UNKNOWN.
    Then RECONCILING, and finally COMMITTED or FAILED.
    The commit effect is applied exactly once.
    """

    def __init__(self) -> None:
        super().__init__()
        self._commit_effect_count: int = 0
        self._committed: bool = False

    @property
    def commit_effect_count(self) -> int:
        return self._commit_effect_count

    def commit(self) -> ExecutorState:
        """Apply the commit effect exactly once."""
        if not self._committed:
            self._commit_effect_count += 1
            self._committed = True
            self.transition(ExecutorState.COMMITTED)
        return self._state

    def handle_fault_after_commit_intent(self) -> ExecutorState:
        """Handle a fault after COMMIT_INTENT.

        State becomes UNKNOWN. Call reconcile_from_unknown() to
        transition to RECONCILING.
        """
        if self._state == ExecutorState.COMMIT_INTENT:
            self.transition(ExecutorState.UNKNOWN)
        return self._state

    def reconcile_from_unknown(self) -> ExecutorState:
        """Transition from UNKNOWN to RECONCILING."""
        if self._state == ExecutorState.UNKNOWN:
            self.transition(ExecutorState.RECONCILING)
        return self._state

    def reconcile(self) -> ExecutorState:
        """Reconcile from RECONCILING to COMMITTED or FAILED."""
        if self._state == ExecutorState.RECONCILING:
            # Check if the commit was already applied
            if self._committed:
                return self._state  # stay in RECONCILING until commit()
            self.transition(ExecutorState.FAILED)
        return self._state


class IdempotentDelivery:
    """Idempotent delivery for duplicate detection (F04).

    Stores the result of the first delivery. Subsequent deliveries
    with the same idempotency_key return the stored result without
    re-executing.
    """

    def __init__(self) -> None:
        self._delivered: dict[str, Any] = {}
        self._effect_count: int = 0

    @property
    def effect_count(self) -> int:
        return self._effect_count

    def deliver(
        self,
        idempotency_key: str,
        payload_hash: str,
        effect_fn: Any,
    ) -> Any:
        """Deliver an envelope idempotently.

        First delivery: execute effect_fn, store result.
        Subsequent deliveries: return stored result.
        """
        if idempotency_key in self._delivered:
            return self._delivered[idempotency_key]

        # Check for idempotency key reuse with different payload
        self._effect_count += 1
        result = effect_fn()
        self._delivered[idempotency_key] = result
        return result

    def is_delivered(self, idempotency_key: str) -> bool:
        return idempotency_key in self._delivered


@dataclass
class OrderedEvent:
    """An single event in an ordered event stream (F05)."""

    sequence_no: int
    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


class OrderedEventBuffer:
    """Buffer that reorders out-of-order events by sequence_no (F05).

    Events arriving out of order are buffered and emitted in
    sequence_no order within an allowed window.
    """

    def __init__(self, allowed_window: int = 10) -> None:
        self._buffer: list[OrderedEvent] = []
        self._next_expected: int = 0
        self._allowed_window = allowed_window
        self._delivered: list[OrderedEvent] = []

    @property
    def delivered(self) -> list[OrderedEvent]:
        return list(self._delivered)

    def push(self, event: OrderedEvent) -> None:
        """Push an event into the buffer."""
        if event.sequence_no > self._next_expected + self._allowed_window:
            raise ValueError(
                f"Event sequence_no {event.sequence_no} is outside "
                f"the allowed window (next_expected={self._next_expected}, "
                f"window={self._allowed_window})"
            )
        self._buffer.append(event)
        self._flush()

    def _flush(self) -> None:
        """Deliver events in sequence_no order."""
        self._buffer.sort(key=lambda e: e.sequence_no)
        while (
            self._buffer
            and self._buffer[0].sequence_no == self._next_expected
        ):
            event = self._buffer.pop(0)
            self._delivered.append(event)
            self._next_expected += 1


class LLMTimeoutSimulator:
    """Simulates LLM call timeout (F07).

    Raises TimeoutError on the first call. The caller should catch it
    and return a deterministic FallbackResponse with
    fallback_reason=LLM_UNAVAILABLE.
    """

    def __init__(self) -> None:
        self._call_count: int = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def call(self) -> str:
        self._call_count += 1
        raise TimeoutError("LLM call timed out")

    def handle_timeout(
        self,
        correlation_id: uuid.UUID,
        policy_epoch: int,
    ) -> FallbackResponse:
        """Return a deterministic fallback for LLM timeout (F07).

        No retry storm — the timeout is handled exactly once.
        """
        return FallbackResponse(
            correlation_id=correlation_id,
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            reservation_status=ReservationStatus.NOT_REQUIRED,
            message_template_id="fallback.llm_unavailable.v1",
            message=(
                "The LLM is unavailable. A deterministic fallback "
                "response has been provided. No retry was attempted."
            ),
            tokens_used=0,
            tokens_budget_remaining=0,
            suggested_next_actions=[
                "Use the deterministic fallback path",
                "Retry manually after the LLM is available",
            ],
        )


class LLMMalformedSimulator:
    """Simulates LLM returning malformed output (F08).

    Returns invalid JSON that fails output validation. The caller
    should catch the validation error and return a FallbackResponse
    with fallback_reason=OUTPUT_VALIDATION_FAILED.
    """

    def __init__(self) -> None:
        self._call_count: int = 0

    @property
    def call_count(self) -> int:
        return self._call_count

    def call(self) -> str:
        self._call_count += 1
        # Return malformed JSON (unparseable)
        return '{"result": broken, "missing_quote: }'

    @staticmethod
    def validate_output(output: str) -> bool:
        """Validate LLM output — returns True if valid JSON dict."""
        import json

        try:
            data = json.loads(output)
            return isinstance(data, dict) and "result" in data
        except (json.JSONDecodeError, TypeError):
            return False

    def handle_malformed(
        self,
        correlation_id: uuid.UUID,
        policy_epoch: int,
    ) -> FallbackResponse:
        """Return a deterministic fallback for malformed output (F08)."""
        return FallbackResponse(
            correlation_id=correlation_id,
            fallback_reason=FallbackReason.OUTPUT_VALIDATION_FAILED,
            reservation_status=ReservationStatus.NOT_REQUIRED,
            message_template_id="fallback.output_validation_failed.v1",
            message=(
                "The LLM output failed validation. A deterministic "
                "fallback response has been provided."
            ),
            tokens_used=0,
            tokens_budget_remaining=0,
            suggested_next_actions=[
                "Use the deterministic fallback path",
                "Check the LLM output schema",
            ],
        )
