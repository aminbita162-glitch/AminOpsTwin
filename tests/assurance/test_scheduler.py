"""G4.10/G4.11 — Weekly scheduler tests (P6, §34).

Deterministic weekly scheduler with injected clock.  Test the weekly
trigger with an injected clock; no seven-day test wait is needed (§34).

G4.11 Assurance integrity: every declared schedule/restart/duplicate
fixture has the expected run state; required NOT_RUN/FAIL can never
produce overall PASS; evidence hashes verify.
"""

from __future__ import annotations

import datetime as _dt

import pytest
from aminopstwin.assurance.scheduler import (
    MissedRunPolicy,
    ScheduleConfig,
    ScheduleOccurrence,
    SchedulerError,
    WeeklyScheduler,
)
from aminopstwin.contracts.clock import SeededClock


def _config(
    *,
    day_of_week: int = 0,
    hour: int = 9,
    minute: int = 0,
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP,
    max_retries: int = 3,
) -> ScheduleConfig:
    return ScheduleConfig(
        day_of_week=day_of_week,
        hour=hour,
        minute=minute,
        timezone="UTC",
        suite_version="assure-1.0",
        deployment_id="deploy-test",
        tenant_scope="tenant-test",
        missed_run_policy=missed_run_policy,
        max_retries=max_retries,
    )


class TestScheduleConfig:
    """ScheduleConfig validation."""

    def test_valid_config(self) -> None:
        cfg = _config()
        assert cfg.day_of_week == 0
        assert cfg.hour == 9
        assert cfg.minute == 0

    def test_invalid_day_of_week(self) -> None:
        with pytest.raises(SchedulerError):
            _config(day_of_week=7)

    def test_invalid_day_negative(self) -> None:
        with pytest.raises(SchedulerError):
            _config(day_of_week=-1)

    def test_invalid_hour(self) -> None:
        with pytest.raises(SchedulerError):
            _config(hour=24)

    def test_invalid_minute(self) -> None:
        with pytest.raises(SchedulerError):
            _config(minute=60)

    def test_empty_suite_version(self) -> None:
        with pytest.raises(SchedulerError):
            ScheduleConfig(
                day_of_week=0,
                hour=9,
                minute=0,
                timezone="UTC",
                suite_version="",
                deployment_id="deploy-test",
                tenant_scope="tenant-test",
            )

    def test_empty_deployment_id(self) -> None:
        with pytest.raises(SchedulerError):
            ScheduleConfig(
                day_of_week=0,
                hour=9,
                minute=0,
                timezone="UTC",
                suite_version="assure-1.0",
                deployment_id="",
                tenant_scope="tenant-test",
            )

    def test_empty_tenant_scope(self) -> None:
        with pytest.raises(SchedulerError):
            ScheduleConfig(
                day_of_week=0,
                hour=9,
                minute=0,
                timezone="UTC",
                suite_version="assure-1.0",
                deployment_id="deploy-test",
                tenant_scope="",
            )

    def test_invalid_retention(self) -> None:
        with pytest.raises(SchedulerError):
            ScheduleConfig(
                day_of_week=0,
                hour=9,
                minute=0,
                timezone="UTC",
                suite_version="assure-1.0",
                deployment_id="deploy-test",
                tenant_scope="tenant-test",
                retention_weeks=0,
            )

    def test_invalid_max_retries(self) -> None:
        with pytest.raises(SchedulerError):
            _config(max_retries=-1)

    def test_occurrence_id_uniqueness(self) -> None:
        cfg = _config()
        t1 = _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)  # Monday
        t2 = _dt.datetime(2026, 1, 12, 9, 0, tzinfo=_dt.UTC)  # next Monday
        assert cfg.occurrence_id(t1) != cfg.occurrence_id(t2)


class TestNextOccurrence:
    """next_occurrence computes the correct next scheduled moment."""

    def test_next_occurrence_monday(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 8, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        # Monday Jan 5 2026 at 9:00 UTC
        assert occ.due_at == _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)

    def test_next_occurrence_past_time_same_day(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 10, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        # Already past 9:00 on Monday → next Monday
        assert occ.due_at == _dt.datetime(2026, 1, 12, 9, 0, tzinfo=_dt.UTC)

    def test_next_occurrence_different_day(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 6, 8, 0, tzinfo=_dt.UTC)  # Tuesday
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)  # Monday
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        # Next Monday is Jan 12
        assert occ.due_at == _dt.datetime(2026, 1, 12, 9, 0, tzinfo=_dt.UTC)

    def test_next_occurrence_deterministic(self) -> None:
        """Same clock + same config → same occurrence (determinism)."""
        for _seed in range(20):
            clock = SeededClock(
                start=_dt.datetime(2026, 1, 5, 8, 0, tzinfo=_dt.UTC)
            )
            cfg = _config()
            s1 = WeeklyScheduler(cfg, clock)
            clock2 = SeededClock(
                start=_dt.datetime(2026, 1, 5, 8, 0, tzinfo=_dt.UTC)
            )
            s2 = WeeklyScheduler(cfg, clock2)
            assert s1.next_occurrence().due_at == s2.next_occurrence().due_at
            assert (
                s1.next_occurrence().occurrence_id
                == s2.next_occurrence().occurrence_id
            )

    def test_is_due_at_scheduled_time(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)
        scheduler = WeeklyScheduler(cfg, clock)
        assert scheduler.is_due() is True

    def test_is_not_due_before_scheduled_time(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 8, 59, tzinfo=_dt.UTC)
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)
        scheduler = WeeklyScheduler(cfg, clock)
        assert scheduler.is_due() is False

    def test_naive_datetime_rejected(self) -> None:
        clock = SeededClock()
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        with pytest.raises(SchedulerError):
            scheduler.next_occurrence(
                after=_dt.datetime(2026, 1, 5, 9, 0)  # noqa: DTZ001
            )


class TestDuplicateTrigger:
    """Duplicate triggers cannot duplicate effects (§34, G4.11)."""

    def test_duplicate_trigger_no_effect(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)

        class _DummyRunner:
            def run_checks(
                self, occurrence: ScheduleOccurrence, config: ScheduleConfig
            ) -> dict[str, str]:
                return {
                    "occurrence_id": occurrence.occurrence_id,
                    "state": "completed",
                }

        runner = _DummyRunner()
        r1 = scheduler.trigger(runner)
        assert r1["state"] != "duplicate"
        occ = scheduler.current_occurrence()
        scheduler.mark_completed(occ.occurrence_id)
        r2 = scheduler.trigger(runner)
        assert r2["state"] == "duplicate"

    def test_duplicate_trigger_zero_model(self) -> None:
        """Duplicate trigger has zero model usage."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)

        class _DummyRunner:
            def run_checks(
                self, occurrence: ScheduleOccurrence, config: ScheduleConfig
            ) -> dict[str, str]:
                return {"state": "completed"}

        runner = _DummyRunner()
        scheduler.trigger(runner)
        occ = scheduler.current_occurrence()
        scheduler.mark_completed(occ.occurrence_id)
        r2 = scheduler.trigger(runner)
        assert r2["model_request_count"] == 0
        assert r2["model_tokens_used"] == 0


class TestMissedRunHandling:
    """Missed-run handling policies (§34)."""

    def test_skip_policy(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(missed_run_policy=MissedRunPolicy.SKIP)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        result = scheduler.handle_missed_run("missed-001", occ)
        assert result == "SKIPPED"
        assert scheduler.is_missed("missed-001")

    def test_catch_up_policy(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(missed_run_policy=MissedRunPolicy.CATCH_UP)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        result = scheduler.handle_missed_run("missed-002", occ)
        assert result == "CATCH_UP"
        assert scheduler.is_missed("missed-002")

    def test_fail_policy(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(missed_run_policy=MissedRunPolicy.FAIL)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        result = scheduler.handle_missed_run("missed-003", occ)
        assert result == "FAIL"
        assert scheduler.is_failed("missed-003")


class TestRetryBounds:
    """Retries are bounded and idempotent (§34)."""

    def test_retry_within_bounds(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(max_retries=3)
        scheduler = WeeklyScheduler(cfg, clock)
        for _ in range(3):
            scheduler.mark_failed("occ-retry-001")
        assert scheduler.is_failed("occ-retry-001")

    def test_retry_exceeds_bounds(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(max_retries=2)
        scheduler = WeeklyScheduler(cfg, clock)
        for _ in range(2):
            scheduler.mark_failed("occ-retry-002")
        with pytest.raises(SchedulerError):
            scheduler.mark_failed("occ-retry-002")

    def test_mark_completed_idempotent(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        scheduler.mark_completed("occ-001")
        scheduler.mark_completed("occ-001")
        assert scheduler.is_completed("occ-001")


class TestStateHash:
    """Scheduler state hash is deterministic."""

    def test_state_hash_deterministic(self) -> None:
        clock1 = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        clock2 = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        s1 = WeeklyScheduler(cfg, clock1)
        s2 = WeeklyScheduler(cfg, clock2)
        s1.mark_completed("occ-a")
        s2.mark_completed("occ-a")
        assert s1.state_hash() == s2.state_hash()

    def test_state_hash_changes_on_state_change(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        h_before = scheduler.state_hash()
        scheduler.mark_completed("occ-new")
        h_after = scheduler.state_hash()
        assert h_before != h_after


class TestTriggerNotDue:
    """Triggering before due raises SchedulerError."""

    def test_trigger_not_due_raises(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 8, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(day_of_week=0, hour=9, minute=0)
        scheduler = WeeklyScheduler(cfg, clock)

        class _DummyRunner:
            def run_checks(
                self, occurrence: ScheduleOccurrence, config: ScheduleConfig
            ) -> dict[str, str]:
                return {"state": "completed"}

        with pytest.raises(SchedulerError):
            scheduler.trigger(_DummyRunner())
