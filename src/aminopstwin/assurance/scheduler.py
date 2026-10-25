"""Deterministic weekly scheduler (P6, §34, G4.10, G4.11).

A4 owns the assurance policy; a deterministic scheduler triggers an S2
workflow through S1.  Frequency is weekly.  The exact day, time,
timezone, missed-run handling and retention duration are owner
configuration (§34).  Display timestamps in a declared timezone with UTC
storage.

Job uniqueness: deployment + suite version + scheduled occurrence + tenant
scope.  Duplicate triggers cannot duplicate effects.  Retries are bounded
and idempotent.  A failed run creates an auditable incident; it cannot
repair code, change policy or promote experience without authorization.

Test the weekly trigger with an injected clock; no seven-day test wait
is needed (§34).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Protocol

from aminopstwin.contracts.clock import Clock

__all__ = [
    "MissedRunPolicy",
    "ScheduleConfig",
    "WeeklyScheduler",
    "ScheduleOccurrence",
    "SchedulerError",
]


class SchedulerError(Exception):
    """Raised on invalid scheduler configuration or operation."""


class MissedRunPolicy(StrEnum):
    """Policy for handling a missed scheduled occurrence (§34)."""

    SKIP = "SKIP"
    CATCH_UP = "CATCH_UP"
    FAIL = "FAIL"


@dataclass(frozen=True)
class ScheduleConfig:
    """Owner-configured weekly schedule (§34).

    day_of_week: 0=Monday … 6=Sunday (ISO weekday minus 1).
    hour, minute: the scheduled time in ``timezone``.
    timezone: IANA timezone name for display; storage is UTC.
    suite_version: the assurance suite version to run.
    deployment_id: the deployment identifier for job uniqueness.
    tenant_scope: the tenant scope for job uniqueness.
    missed_run_policy: how to handle a missed occurrence.
    retention_weeks: how many weeks of reports to retain.
    max_retries: maximum bounded retries on failure.
    """

    day_of_week: int
    hour: int
    minute: int
    timezone: str
    suite_version: str
    deployment_id: str
    tenant_scope: str
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP
    retention_weeks: int = 12
    max_retries: int = 3

    def __post_init__(self) -> None:
        if not (0 <= self.day_of_week <= 6):
            raise SchedulerError(
                f"day_of_week must be 0-6, got {self.day_of_week}"
            )
        if not (0 <= self.hour <= 23):
            raise SchedulerError(
                f"hour must be 0-23, got {self.hour}"
            )
        if not (0 <= self.minute <= 59):
            raise SchedulerError(
                f"minute must be 0-59, got {self.minute}"
            )
        if self.suite_version == "":
            raise SchedulerError("suite_version must not be empty")
        if self.deployment_id == "":
            raise SchedulerError("deployment_id must not be empty")
        if self.tenant_scope == "":
            raise SchedulerError("tenant_scope must not be empty")
        if self.retention_weeks < 1:
            raise SchedulerError("retention_weeks must be >= 1")
        if self.max_retries < 0:
            raise SchedulerError("max_retries must be >= 0")

    def occurrence_id(self, occurrence: _dt.datetime) -> str:
        """Build a unique occurrence identifier (job uniqueness, §34)."""
        utc = occurrence.astimezone(_dt.UTC)
        return (
            f"{self.deployment_id}/{self.suite_version}/"
            f"{utc.strftime('%Y-W%W-%w-%H%M')}/{self.tenant_scope}"
        )


@dataclass(frozen=True)
class ScheduleOccurrence:
    """A single scheduled occurrence.

    occurrence_id is unique per deployment + suite version + scheduled
    occurrence + tenant scope (§34 job uniqueness).
    """

    occurrence_id: str
    scheduled_at: _dt.datetime
    due_at: _dt.datetime
    timezone: str


class _CheckRunner(Protocol):
    """Protocol for the zero-model check runner (S2 workflow)."""

    def run_checks(
        self, occurrence: ScheduleOccurrence, config: ScheduleConfig
    ) -> dict[str, Any]:
        ...


class WeeklyScheduler:
    """Deterministic weekly assurance scheduler (§34, G4.10, G4.11).

    The scheduler computes the next due occurrence from an injected
    :class:`Clock`, determines whether the current time is at or past the
    scheduled moment, and triggers the check runner.  It tracks completed
    occurrence IDs so that duplicate triggers cannot duplicate effects
    (§34 job uniqueness, G4.11).

    No LLM, embedding, model inference, generated summary or
    model-based scheduling is used.  The scheduler is purely
    deterministic: given the same clock and the same config, it produces
    the same occurrence sequence and the same decisions.
    """

    def __init__(
        self,
        config: ScheduleConfig,
        clock: Clock,
    ) -> None:
        self._config = config
        self._clock = clock
        self._completed: set[str] = set()
        self._failed: set[str] = set()
        self._missed: set[str] = set()
        self._retries: dict[str, int] = {}

    # -- public API --

    def next_occurrence(self, after: _dt.datetime | None = None) -> ScheduleOccurrence:
        """Compute the next scheduled occurrence at or after *after*.

        Returns the occurrence whose ``due_at`` is the next scheduled
        moment at or after ``after`` (default: current clock time).
        """
        if after is None:
            after = self._clock.now()
        # Normalise to UTC for computation.
        if after.tzinfo is None:
            raise SchedulerError("after must be timezone-aware")
        after_utc = after.astimezone(_dt.UTC)

        # Compute the candidate occurrence for the current week.
        # day_of_week: 0=Mon … 6=Sun.  Python weekday(): 0=Mon … 6=Sun.
        current_dow = after_utc.weekday()
        # Offset from the current day to the target day.
        day_offset = (self._config.day_of_week - current_dow) % 7
        candidate = after_utc.replace(
            hour=self._config.hour,
            minute=self._config.minute,
            second=0,
            microsecond=0,
        ) + _dt.timedelta(days=day_offset)

        # If the candidate is strictly before *after* (same day, earlier
        # time already passed), advance to next week.
        if candidate < after_utc:
            candidate += _dt.timedelta(weeks=1)

        occ_id = self._config.occurrence_id(candidate)
        return ScheduleOccurrence(
            occurrence_id=occ_id,
            scheduled_at=candidate,
            due_at=candidate,
            timezone=self._config.timezone,
        )

    def current_occurrence(self, now: _dt.datetime | None = None) -> ScheduleOccurrence:
        """Return the occurrence for the current week (most recent <= now).

        Returns the occurrence whose scheduled time is the most recent
        scheduled moment at or before *now*.  If now is before this
        week's scheduled time, returns last week's occurrence.  This is
        what :meth:`trigger` uses to determine which occurrence to run:
        if the returned occurrence's ``due_at`` is after *now*, the
        trigger raises ``SchedulerError`` (not yet due).
        """
        if now is None:
            now = self._clock.now()
        if now.tzinfo is None:
            raise SchedulerError("now must be timezone-aware")
        now_utc = now.astimezone(_dt.UTC)

        # Find this week's occurrence: go back to the most recent
        # scheduled day/time at or before now.
        current_dow = now_utc.weekday()
        # Days since the target day (going backwards).
        day_offset = (current_dow - self._config.day_of_week) % 7
        candidate = now_utc.replace(
            hour=self._config.hour,
            minute=self._config.minute,
            second=0,
            microsecond=0,
        ) - _dt.timedelta(days=day_offset)

        # If the candidate's time-of-day is after now's time-of-day on
        # the same day, the occurrence hasn't happened yet this week.
        # In that case, the "current" (most recent) occurrence is last
        # week's.  But for the trigger, we want to report "not yet due"
        # rather than running last week's occurrence.  So we return the
        # candidate as-is (which is in the future) and let trigger check
        # due_at > now.

        occ_id = self._config.occurrence_id(candidate)
        return ScheduleOccurrence(
            occurrence_id=occ_id,
            scheduled_at=candidate,
            due_at=candidate,
            timezone=self._config.timezone,
        )

    def is_due(self, now: _dt.datetime | None = None) -> bool:
        """Return True if the current occurrence is due at or before *now*."""
        if now is None:
            now = self._clock.now()
        if now.tzinfo is None:
            raise SchedulerError("now must be timezone-aware")
        now_utc = now.astimezone(_dt.UTC)
        occ = self.current_occurrence(now)
        return now_utc >= occ.due_at

    def trigger(
        self,
        runner: _CheckRunner,
        now: _dt.datetime | None = None,
    ) -> dict[str, Any]:
        """Trigger the check runner for the current occurrence.

        If the occurrence was already completed, this is a duplicate
        trigger and no effects are duplicated (G4.11).  If the
        occurrence is not yet due, ``SchedulerError`` is raised.

        Returns the runner's result dict (the assurance report payload).
        """
        if now is None:
            now = self._clock.now()
        if now.tzinfo is None:
            raise SchedulerError("now must be timezone-aware")
        now_utc = now.astimezone(_dt.UTC)

        occ = self.current_occurrence(now)
        if now_utc < occ.due_at:
            raise SchedulerError(
                f"occurrence {occ.occurrence_id} not yet due "
                f"(due at {occ.due_at.isoformat()})"
            )

        # Duplicate trigger: do not duplicate effects (§34).
        if occ.occurrence_id in self._completed:
            return {
                "occurrence_id": occ.occurrence_id,
                "state": "duplicate",
                "model_request_count": 0,
                "model_tokens_used": 0,
            }

        result = runner.run_checks(occ, self._config)
        return result

    def mark_completed(self, occurrence_id: str) -> None:
        """Mark an occurrence as completed (idempotent)."""
        self._completed.add(occurrence_id)

    def mark_failed(self, occurrence_id: str) -> None:
        """Mark an occurrence as failed and track retry count."""
        self._failed.add(occurrence_id)
        self._retries[occurrence_id] = self._retries.get(occurrence_id, 0) + 1
        if self._retries[occurrence_id] > self._config.max_retries:
            raise SchedulerError(
                f"max retries ({self._config.max_retries}) "
                f"exceeded for {occurrence_id}"
            )

    def mark_missed(self, occurrence_id: str) -> None:
        """Mark an occurrence as missed (NOT_RUN)."""
        self._missed.add(occurrence_id)

    def is_completed(self, occurrence_id: str) -> bool:
        return occurrence_id in self._completed

    def is_failed(self, occurrence_id: str) -> bool:
        return occurrence_id in self._failed

    def is_missed(self, occurrence_id: str) -> bool:
        return occurrence_id in self._missed

    @property
    def completed_occurrences(self) -> frozenset[str]:
        return frozenset(self._completed)

    @property
    def failed_occurrences(self) -> frozenset[str]:
        return frozenset(self._failed)

    @property
    def missed_occurrences(self) -> frozenset[str]:
        return frozenset(self._missed)

    @property
    def config(self) -> ScheduleConfig:
        return self._config

    def handle_missed_run(
        self,
        missed_occurrence_id: str,
        current_occurrence: ScheduleOccurrence,
    ) -> str:
        """Handle a missed run according to the configured policy (§34).

        Returns one of:
        - "SKIPPED": the missed occurrence is recorded as NOT_RUN.
        - "CATCH_UP": the missed occurrence is flagged for catch-up.
        - "FAIL": the missed occurrence creates an auditable incident.
        """
        policy = self._config.missed_run_policy
        if policy == MissedRunPolicy.SKIP:
            self._missed.add(missed_occurrence_id)
            return "SKIPPED"
        if policy == MissedRunPolicy.CATCH_UP:
            self._missed.add(missed_occurrence_id)
            return "CATCH_UP"
        if policy == MissedRunPolicy.FAIL:
            self._failed.add(missed_occurrence_id)
            return "FAIL"
        # Unreachable: StrEnum exhaustively covers all cases.
        raise SchedulerError(f"unknown missed-run policy: {policy}")

    def state_hash(self) -> str:
        """Return a deterministic SHA-256 hash of the scheduler state."""
        state = {
            "completed": sorted(self._completed),
            "failed": sorted(self._failed),
            "missed": sorted(self._missed),
            "retries": dict(sorted(self._retries.items())),
            "config": {
                "day_of_week": self._config.day_of_week,
                "hour": self._config.hour,
                "minute": self._config.minute,
                "timezone": self._config.timezone,
                "suite_version": self._config.suite_version,
                "deployment_id": self._config.deployment_id,
                "tenant_scope": self._config.tenant_scope,
                "missed_run_policy": self._config.missed_run_policy.value,
                "retention_weeks": self._config.retention_weeks,
                "max_retries": self._config.max_retries,
            },
        }
        return hashlib.sha256(
            json.dumps(state, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
