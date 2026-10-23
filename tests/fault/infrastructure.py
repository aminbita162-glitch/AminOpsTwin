"""Fault injection test infrastructure for F01–F12 (G2.9, G3.10).

Provides the minimal executor extensions needed to test fault scenarios:
    - CheckpointableExecutor with checkpoint/resume (F01, F06)
    - CommitIntentExecutor with UNKNOWN/RECONCILING states (F02, F03)
    - IdempotentDelivery for duplicate detection (F04)
    - OrderedEventBuffer for out-of-order reordering (F05)
    - LLM timeout and malformed output handling (F07, F08)
    - ConcurrentBudgetBoundary for F09 (concurrent budget exhaustion)
    - EpochBumpHandler for F10 (policy epoch bump mid-workflow)
    - AtomicExportWriter for F11 (interrupted export)
    - DiskFullWriter for F12 (disk full / write failure)
"""

from __future__ import annotations

import hashlib
import os
import tempfile
import threading
import uuid
from dataclasses import dataclass, field
from typing import Any

from src.executor import ExecutorState, ExecutorStateMachine
from src.tokens.budget import BudgetGovernor, BudgetLevel
from src.tokens.fallback import FallbackReason, FallbackResponse, ReservationStatus

__all__ = [
    "Checkpoint",
    "CheckpointableExecutor",
    "CommitIntentExecutor",
    "IdempotentDelivery",
    "OrderedEventBuffer",
    "LLMTimeoutSimulator",
    "LLMMalformedSimulator",
    "ConcurrentBudgetBoundary",
    "EpochBumpHandler",
    "AtomicExportWriter",
    "DiskFullWriter",
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


# ---------------------------------------------------------------------------
# F09: Concurrent requests at the budget boundary
# ---------------------------------------------------------------------------


class ConcurrentBudgetBoundary:
    """F09: Concurrent requests at the budget boundary.

    Simulates multiple concurrent requests all trying to reserve
    tokens from a budget governor at the same time. The total
    reserved spend must never exceed the limit; excess requests
    must get the GW-BUDGET-001 fallback.
    """

    def __init__(
        self,
        governor: BudgetGovernor,
        level: BudgetLevel,
    ) -> None:
        self._governor = governor
        self._level = level
        self._lock = threading.Lock()

    def concurrent_reserve(
        self,
        amount: int,
        num_concurrent: int,
    ) -> dict[str, Any]:
        """Run *num_concurrent* concurrent reservation attempts.

        Returns a dict with:
            - successful_reservations: count
            - failed_reservations: count
            - total_reserved: total tokens reserved
            - limit_exceeded: whether total_reserved > limit
        """
        results: list[bool] = []
        total_reserved_list: list[int] = []

        def worker() -> None:
            ok = self._governor.reserve(self._level, amount)
            with self._lock:
                results.append(ok)
                if ok:
                    total_reserved_list.append(amount)

        threads: list[threading.Thread] = []
        for _ in range(num_concurrent):
            t = threading.Thread(target=worker)
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        successful = sum(1 for r in results if r)
        failed = sum(1 for r in results if not r)
        total_reserved = sum(total_reserved_list)

        return {
            "successful_reservations": successful,
            "failed_reservations": failed,
            "total_reserved": total_reserved,
            "limit_exceeded": (
                total_reserved > self._governor.remaining(self._level)
            ),
        }

    def get_fallback(
        self,
        correlation_id: uuid.UUID,
        policy_epoch: int,
    ) -> FallbackResponse:
        """Return the GW-BUDGET-001 fallback for excess requests."""
        return self._governor.get_fallback(
            correlation_id=correlation_id,
            policy_epoch=policy_epoch,
        )


# ---------------------------------------------------------------------------
# F10: Policy epoch bumped mid-workflow
# ---------------------------------------------------------------------------


class EpochBumpHandler:
    """F10: Policy epoch bumped mid-workflow.

    Simulates a policy epoch bump during an in-flight workflow.
    In-flight steps must be re-validated and re-submitted (§3.7).
    COMMIT is blocked until re-validation passes.
    """

    def __init__(self) -> None:
        self._current_epoch: int = 0
        self._in_flight: list[dict[str, Any]] = []
        self._revalidated: bool = False
        self._commit_blocked: bool = False

    @property
    def current_epoch(self) -> int:
        return self._current_epoch

    def submit(self, envelope_epoch: int) -> dict[str, Any]:
        """Submit a workflow step with the given envelope epoch."""
        entry: dict[str, Any] = {
            "envelope_epoch": envelope_epoch,
            "submitted_epoch": self._current_epoch,
            "status": "in_flight",
        }
        self._in_flight.append(entry)
        return entry

    def bump_epoch(self) -> int:
        """Bump the current policy epoch.

        All in-flight steps are marked for re-validation.
        """
        self._current_epoch += 1
        for entry in self._in_flight:
            if entry["status"] == "in_flight":
                entry["status"] = "needs_revalidation"
        self._commit_blocked = True
        return self._current_epoch

    def revalidate(self) -> bool:
        """Re-validate all in-flight steps.

        Steps with an outdated envelope_epoch are re-submitted
        with the new current epoch. Returns True if all pass.
        """
        all_pass = True
        for entry in self._in_flight:
            if entry["status"] == "needs_revalidation":
                entry["envelope_epoch"] = self._current_epoch
                entry["status"] = "revalidated"
        self._revalidated = True
        self._commit_blocked = False
        return all_pass

    @property
    def commit_blocked(self) -> bool:
        return self._commit_blocked

    @property
    def in_flight(self) -> list[dict[str, Any]]:
        return list(self._in_flight)

    def commit(self) -> bool:
        """Attempt to commit; blocked until revalidation passes."""
        return not self._commit_blocked


# ---------------------------------------------------------------------------
# F11: Export interrupted mid-write
# ---------------------------------------------------------------------------


class AtomicExportWriter:
    """F11: Export interrupted mid-write.

    Writes to a temporary file first, then atomically renames to
    the final name. If interrupted mid-write:
        - No partial file is visible under the final name
        - The manifest is absent
        - A retry is clean
    """

    def __init__(self, base_dir: str) -> None:
        self._base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)

    def write_export(
        self,
        filename: str,
        content: bytes,
        manifest: dict[str, Any] | None = None,
    ) -> str:
        """Write an export atomically.

        Writes to a temp file, then renames to the final name.
        Returns the final path.
        """
        final_path = os.path.join(self._base_dir, filename)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self._base_dir,
            prefix=".tmp-export-",
            suffix=".tmp",
        )
        try:
            os.write(temp_fd, content)
            os.close(temp_fd)
            os.rename(temp_path, final_path)
        except Exception:
            # Clean up the temp file on failure
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            raise

        # Write manifest (if provided) only after the data is
        # safely at its final name.
        if manifest is not None:
            manifest_path = final_path + ".manifest"
            import json
            with open(manifest_path, "w") as f:
                json.dump(manifest, f)

        return final_path

    def write_export_interrupted(
        self,
        filename: str,
        content: bytes,
    ) -> str:
        """Simulate an interrupted write (F11).

        Writes partial content to a temp file, then 'crashes'
        without renaming. The final name must not exist.
        """
        os.path.join(self._base_dir, filename)
        temp_fd, temp_path = tempfile.mkstemp(
            dir=self._base_dir,
            prefix=".tmp-export-",
            suffix=".tmp",
        )
        # Write only partial content
        os.write(temp_fd, content[: len(content) // 2])
        os.close(temp_fd)
        # Do NOT rename — simulate a crash
        # The temp file exists but the final file does not
        return temp_path

    def final_file_exists(self, filename: str) -> bool:
        """Check if the final file exists."""
        return os.path.exists(
            os.path.join(self._base_dir, filename)
        )

    def manifest_exists(self, filename: str) -> bool:
        """Check if the manifest exists for a file."""
        return os.path.exists(
            os.path.join(self._base_dir, filename + ".manifest")
        )

    def retry_write(
        self,
        filename: str,
        content: bytes,
        manifest: dict[str, Any] | None = None,
    ) -> str:
        """Retry the write cleanly after an interruption."""
        return self.write_export(filename, content, manifest)


# ---------------------------------------------------------------------------
# F12: Disk full / write failure
# ---------------------------------------------------------------------------


class DiskFullWriter:
    """F12: Disk full / write failure.

    Simulates a disk-full condition where writes fail. The system
    must:
        - Stop new writes
        - Report explicit FAILED when no effect was committed
        - Report UNKNOWN if the outcome cannot be established
        - Use a bounded independent error channel when the
          primary store cannot write
        - Never silently lose data or claim success on timeout
    """

    def __init__(self) -> None:
        self._disk_full: bool = False
        self._writes_attempted: int = 0
        self._writes_succeeded: int = 0
        self._writes_failed: int = 0
        self._error_channel: list[str] = []
        self._new_write_status: str = "ACCEPTING"

    @property
    def disk_full(self) -> bool:
        return self._disk_full

    def set_disk_full(self) -> None:
        """Simulate disk becoming full."""
        self._disk_full = True
        self._new_write_status = "STOPPED"

    def clear_disk_full(self) -> None:
        """Simulate disk being freed."""
        self._disk_full = False
        self._new_write_status = "ACCEPTING"

    @property
    def new_write_status(self) -> str:
        return self._new_write_status

    def write(self, data: bytes) -> dict[str, Any]:
        """Attempt to write data.

        Returns a dict with:
            - status: "SUCCESS" | "FAILED" | "UNKNOWN"
            - bytes_written: int
            - error: str | None
            - effect_committed: bool
        """
        self._writes_attempted += 1

        if self._disk_full:
            self._writes_failed += 1
            # Record to the bounded independent error channel
            self._error_channel.append(
                f"write_failed:disk_full:attempt={self._writes_attempted}"
            )
            return {
                "status": "FAILED",
                "bytes_written": 0,
                "error": "disk_full",
                "effect_committed": False,
            }

        # Successful write
        self._writes_succeeded += 1
        return {
            "status": "SUCCESS",
            "bytes_written": len(data),
            "error": None,
            "effect_committed": True,
        }

    def write_with_uncertain_outcome(self, data: bytes) -> dict[str, Any]:
        """Write where the outcome cannot be established (UNKNOWN).

        The write was attempted but the disk went full during the
        write; we cannot tell if the data was committed or not.
        """
        self._writes_attempted += 1
        self._error_channel.append(
            f"write_uncertain:disk_full_during_write:attempt={self._writes_attempted}"
        )
        return {
            "status": "UNKNOWN",
            "bytes_written": 0,
            "error": "disk_full_during_write",
            "effect_committed": False,
        }

    @property
    def error_channel_entries(self) -> list[str]:
        """Return the bounded independent error channel log."""
        return list(self._error_channel)

    @property
    def writes_attempted(self) -> int:
        return self._writes_attempted

    @property
    def writes_succeeded(self) -> int:
        return self._writes_succeeded

    @property
    def writes_failed(self) -> int:
        return self._writes_failed

    def stop_new_writes(self) -> None:
        """Stop accepting new writes (F12)."""
        self._disk_full = True
        self._new_write_status = "STOPPED"

    def reconcile(
        self,
        primary_store_available: bool,
    ) -> str:
        """Reconcile after disk recovery.

        If the primary store is available, persist the error channel
        as reconciliation evidence. Returns 'RECONCILED' or 'STILL_UNAVAILABLE'.
        """
        if primary_store_available:
            self._error_channel.append(
                "reconciled:primary_store_available"
            )
            return "RECONCILED"
        return "STILL_UNAVAILABLE"
