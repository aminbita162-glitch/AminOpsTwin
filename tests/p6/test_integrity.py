"""G4.11 — Assurance integrity tests (P6, §34).

Every declared schedule/restart/duplicate fixture has the expected run
state; required NOT_RUN/FAIL can never produce overall PASS; evidence
hashes verify.
"""

from __future__ import annotations

import datetime as _dt

import pytest
from aminopstwin.assurance.checks import (
    AssuranceCheck,
    CheckOutcome,
    CheckResult,
)
from aminopstwin.assurance.report import (
    AssuranceReport,
    AssuranceRunSummary,
    RunState,
    build_report,
)
from aminopstwin.assurance.runner import (
    AssuranceRunner,
    run_assurance,
)
from aminopstwin.assurance.scheduler import (
    MissedRunPolicy,
    ScheduleConfig,
    ScheduleOccurrence,
    WeeklyScheduler,
)
from aminopstwin.contracts.clock import SeededClock


def _config(
    *,
    missed_run_policy: MissedRunPolicy = MissedRunPolicy.SKIP,
) -> ScheduleConfig:
    return ScheduleConfig(
        day_of_week=0,
        hour=9,
        minute=0,
        timezone="UTC",
        suite_version="assure-1.0",
        deployment_id="deploy-test",
        tenant_scope="tenant-default",
        missed_run_policy=missed_run_policy,
    )


class TestOverallStateIntegrity:
    """G4.11: required NOT_RUN/FAIL can never produce overall PASS."""

    def test_all_pass_produces_pass(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        report, _ = run_assurance(_config(), clock)
        assert report.overall_state == RunState.PASS

    def test_any_fail_prevents_pass(self) -> None:
        """A single FAIL check makes overall FAIL, never PASS."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _pass_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="passing",
                outcome=CheckOutcome.PASS,
            )

        def _fail_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="failing",
                outcome=CheckOutcome.FAIL,
                error_code="SIMULATED_FAIL",
            )

        checks = [
            AssuranceCheck("passing", _pass_check),
            AssuranceCheck("failing", _fail_check),
        ]
        runner = AssuranceRunner(cfg, clock, checks=checks)
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.FAIL
        assert report.overall_state != RunState.PASS

    def test_any_not_run_prevents_pass(self) -> None:
        """A NOT_RUN check makes overall NOT_RUN, never PASS."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _pass_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="passing",
                outcome=CheckOutcome.PASS,
            )

        def _not_run_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="unavailable",
                outcome=CheckOutcome.NOT_RUN,
                error_code="CHECK_UNAVAILABLE",
            )

        checks = [
            AssuranceCheck("passing", _pass_check),
            AssuranceCheck("unavailable", _not_run_check),
        ]
        runner = AssuranceRunner(cfg, clock, checks=checks)
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.NOT_RUN
        assert report.overall_state != RunState.PASS

    def test_fail_overrides_not_run(self) -> None:
        """FAIL takes precedence over NOT_RUN in overall computation."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _fail_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="failing",
                outcome=CheckOutcome.FAIL,
            )

        def _not_run_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="unavailable",
                outcome=CheckOutcome.NOT_RUN,
            )

        checks = [
            AssuranceCheck("failing", _fail_check),
            AssuranceCheck("unavailable", _not_run_check),
        ]
        runner = AssuranceRunner(cfg, clock, checks=checks)
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.FAIL

    def test_empty_checks_not_run(self) -> None:
        """No checks → overall NOT_RUN, never PASS."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        runner = AssuranceRunner(cfg, clock, checks=[])
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.NOT_RUN


class TestEvidenceHashIntegrity:
    """G4.11: evidence hashes verify."""

    def test_report_hash_stable(self) -> None:
        """Same report → same hash."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        runner = AssuranceRunner(cfg, clock)
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        h1 = report.report_hash()
        h2 = report.report_hash()
        assert h1 == h2
        assert len(h1) == 64

    def test_report_hash_changes_on_different_content(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        r1 = build_report(
            occurrence_id="occ-a",
            suite_version="v1",
            tenant_scope="t1",
            started_at=clock.now(),
            ended_at=clock.now(),
            input_manifest={"a": 1},
            checks=[],
        )
        r2 = build_report(
            occurrence_id="occ-b",
            suite_version="v1",
            tenant_scope="t1",
            started_at=clock.now(),
            ended_at=clock.now(),
            input_manifest={"b": 2},
            checks=[],
        )
        assert r1.report_hash() != r2.report_hash()

    def test_input_manifest_hash_recorded(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        report, _ = run_assurance(_config(), clock)
        assert report.input_manifest_hash != ""
        assert len(report.input_manifest_hash) == 64


class TestRunStateIntegrity:
    """G4.11: declared schedule/restart/duplicate fixtures have expected run state."""

    def test_completed_occurrence_state(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.PASS
        assert scheduler.is_completed(report.occurrence_id)

    def test_failed_occurrence_state(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _fail_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="failing",
                outcome=CheckOutcome.FAIL,
            )

        runner = AssuranceRunner(
            cfg, clock, checks=[AssuranceCheck("failing", _fail_check)]
        )
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.FAIL
        assert scheduler.is_failed(report.occurrence_id)

    def test_duplicate_trigger_state(self) -> None:
        """Duplicate trigger produces 'duplicate' state, not a new run."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert scheduler.is_completed(report.occurrence_id)
        # Second trigger is a duplicate
        result = scheduler.trigger(runner)
        assert result["state"] == "duplicate"


class TestDashboardSummary:
    """Dashboard summary exposes latest attempt, last success, next occurrence."""

    def test_summary_fields(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)
        report = runner.trigger_run(scheduler)
        summary = runner.build_summary(scheduler)
        assert summary.latest_attempt_id == report.run_id
        assert summary.latest_attempt_state == RunState.PASS
        assert summary.last_success_id == report.run_id
        assert summary.last_success_at is not None
        assert summary.next_occurrence_id is not None
        assert summary.next_occurrence_at is not None
        assert summary.missed_count == 0
        assert summary.failed_count == 0

    def test_summary_after_failure(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _fail_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="failing",
                outcome=CheckOutcome.FAIL,
            )

        runner = AssuranceRunner(
            cfg, clock, checks=[AssuranceCheck("failing", _fail_check)]
        )
        scheduler = WeeklyScheduler(cfg, clock)
        runner.trigger_run(scheduler)
        summary = runner.build_summary(scheduler)
        assert summary.latest_attempt_state == RunState.FAIL
        assert summary.last_success_id is None
        assert summary.failed_count == 1

    def test_summary_to_dict(self) -> None:
        summary = AssuranceRunSummary(
            latest_attempt_id="run-001",
            latest_attempt_state=RunState.PASS,
            last_success_id="run-001",
            last_success_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            next_occurrence_id="occ-next",
            next_occurrence_at=_dt.datetime(2026, 1, 12, 9, 0, tzinfo=_dt.UTC),
            missed_count=0,
            failed_count=0,
        )
        d = summary.to_dict()
        assert d["latest_attempt_id"] == "run-001"
        assert d["latest_attempt_state"] == "PASS"
        assert d["last_success_id"] == "run-001"
        assert d["missed_count"] == 0


class TestReportSerialization:
    """Report to_dict and serialisation integrity."""

    def test_to_dict_has_all_fields(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        report, _ = run_assurance(_config(), clock)
        d = report.to_dict()
        required = {
            "run_id",
            "occurrence_id",
            "suite_version",
            "tenant_scope",
            "started_at",
            "ended_at",
            "input_manifest_hash",
            "checks",
            "model_request_count",
            "model_tokens_used",
            "overall_state",
        }
        assert required.issubset(set(d.keys()))

    def test_naive_datetime_rejected(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(
                run_id="r1",
                occurrence_id="o1",
                suite_version="v1",
                tenant_scope="t1",
                started_at=_dt.datetime(2026, 1, 1),  # naive
                ended_at=_dt.datetime(2026, 1, 1),
                input_manifest_hash="a" * 64,
            )

    def test_negative_model_count_rejected(self) -> None:
        with pytest.raises(ValueError):
            AssuranceReport(
                run_id="r1",
                occurrence_id="o1",
                suite_version="v1",
                tenant_scope="t1",
                started_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                ended_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                input_manifest_hash="a" * 64,
                model_request_count=-1,
            )
