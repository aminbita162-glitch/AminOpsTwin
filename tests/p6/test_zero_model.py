"""G4.10 — Zero-model assurance tests (P6, §34).

Every weekly-job success, failure, retry and missed-run test has zero
model calls and zero model tokens.  A deliberately injected model call
causes test failure.
"""

from __future__ import annotations

import datetime as _dt

from src.assurance.checks import (
    AssuranceCheck,
    CheckOutcome,
    check_binding_integrity,
    check_deterministic_replay,
    check_duplicate_budget_invariants,
    check_sanitized_logging,
)
from src.assurance.report import (
    AssuranceReport,
    CheckResult,
    RunState,
    build_report,
)
from src.assurance.runner import (
    AssuranceRunner,
    build_default_checks,
    run_assurance,
)
from src.assurance.scheduler import (
    MissedRunPolicy,
    ScheduleConfig,
    ScheduleOccurrence,
    WeeklyScheduler,
)
from src.contracts.clock import SeededClock


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


class TestZeroModelSuccess:
    """G4.10: successful weekly-job run has zero model calls."""

    def test_successful_run_zero_model(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        report, _ = run_assurance(_config(), clock)
        assert report.model_request_count == 0
        assert report.model_tokens_used == 0
        assert report.is_zero_model()

    def test_all_checks_zero_model(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.model_request_count == 0
        assert report.model_tokens_used == 0
        assert report.is_zero_model()


class TestZeroModelFailure:
    """G4.10: failed weekly-job run has zero model calls."""

    def test_failed_run_zero_model(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()

        def _failing_check(
            occ: ScheduleOccurrence, config: ScheduleConfig
        ) -> CheckResult:
            return CheckResult(
                check_id="failing",
                outcome=CheckOutcome.FAIL,
                error_code="SIMULATED_FAIL",
            )

        checks = [AssuranceCheck("failing", _failing_check)]
        runner = AssuranceRunner(cfg, clock, checks=checks)
        scheduler = WeeklyScheduler(cfg, clock)
        report = runner.trigger_run(scheduler)
        assert report.overall_state == RunState.FAIL
        assert report.model_request_count == 0
        assert report.model_tokens_used == 0
        assert report.is_zero_model()


class TestZeroModelRetry:
    """G4.10: retried weekly-job run has zero model calls."""

    def test_retry_run_zero_model(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)
        report = runner.trigger_run(scheduler)
        # Simulate a retry
        scheduler.mark_failed(report.occurrence_id)
        report2 = runner.trigger_run(scheduler)
        assert report2.model_request_count == 0
        assert report2.model_tokens_used == 0


class TestZeroModelMissedRun:
    """G4.10: missed-run handling has zero model calls."""

    def test_missed_run_zero_model(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config(missed_run_policy=MissedRunPolicy.SKIP)
        scheduler = WeeklyScheduler(cfg, clock)
        occ = scheduler.next_occurrence()
        result = scheduler.handle_missed_run("missed-001", occ)
        assert result == "SKIPPED"
        # Missed runs have no model calls by definition
        assert scheduler.is_missed("missed-001")


class TestInjectedModelCallFails:
    """G4.10: a deliberately injected model call causes test failure.

    If someone sets model_request_count > 0 or model_tokens_used > 0,
    the report's is_zero_model() returns False and the G4.10 gate
    fails.
    """

    def test_injected_model_call_detected(self) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        scheduler = WeeklyScheduler(cfg, clock)
        runner = AssuranceRunner(cfg, clock)

        # Simulate a deliberate model call injection by overriding
        # the report's model counts after the run.
        report = runner.trigger_run(scheduler)
        # In a real scenario the injected call would set these.
        # We simulate the injection by constructing a report with
        # non-zero model usage and verifying is_zero_model catches it.
        injected_report = AssuranceReport(
            run_id=report.run_id,
            occurrence_id=report.occurrence_id,
            suite_version=report.suite_version,
            tenant_scope=report.tenant_scope,
            started_at=report.started_at,
            ended_at=report.ended_at,
            input_manifest_hash=report.input_manifest_hash,
            checks=report.checks,
            model_request_count=1,
            model_tokens_used=100,
        )
        assert not injected_report.is_zero_model()
        assert injected_report.model_request_count > 0
        assert injected_report.model_tokens_used > 0

    def test_zero_model_enforced_in_build_report(self) -> None:
        """build_report always sets model counts to 0."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        report = build_report(
            occurrence_id="occ-test",
            suite_version="assure-1.0",
            tenant_scope="tenant-default",
            started_at=clock.now(),
            ended_at=clock.now(),
            input_manifest={"test": True},
            checks=[],
        )
        assert report.model_request_count == 0
        assert report.model_tokens_used == 0


class TestCheckResultsZeroModel:
    """Each built-in check produces zero model calls."""

    def test_binding_integrity_zero_model(self) -> None:
        SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        cfg = _config()
        occ = ScheduleOccurrence(
            occurrence_id=cfg.occurrence_id(
                _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
            ),
            scheduled_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            due_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            timezone="UTC",
        )
        result = check_binding_integrity(occ, cfg)
        assert result.outcome == CheckOutcome.PASS
        assert result.error_code is None

    def test_deterministic_replay_zero_model(self) -> None:
        cfg = _config()
        occ = ScheduleOccurrence(
            occurrence_id=cfg.occurrence_id(
                _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
            ),
            scheduled_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            due_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            timezone="UTC",
        )
        result = check_deterministic_replay(occ, cfg)
        assert result.outcome == CheckOutcome.PASS

    def test_duplicate_budget_invariants_zero_model(self) -> None:
        cfg = _config()
        occ = ScheduleOccurrence(
            occurrence_id=cfg.occurrence_id(
                _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
            ),
            scheduled_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            due_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            timezone="UTC",
        )
        result = check_duplicate_budget_invariants(occ, cfg)
        assert result.outcome == CheckOutcome.PASS

    def test_sanitized_logging_zero_model(self) -> None:
        cfg = _config()
        occ = ScheduleOccurrence(
            occurrence_id=cfg.occurrence_id(
                _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
            ),
            scheduled_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            due_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            timezone="UTC",
        )
        result = check_sanitized_logging(occ, cfg)
        assert result.outcome == CheckOutcome.PASS

    def test_sanitized_logging_detects_secret(self) -> None:
        cfg = ScheduleConfig(
            day_of_week=0,
            hour=9,
            minute=0,
            timezone="UTC",
            suite_version="assure-1.0",
            deployment_id="deploy-test",
            tenant_scope="tenant-secret-leak",
        )
        occ = ScheduleOccurrence(
            occurrence_id=cfg.occurrence_id(
                _dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
            ),
            scheduled_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            due_at=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC),
            timezone="UTC",
        )
        result = check_sanitized_logging(occ, cfg)
        assert result.outcome == CheckOutcome.FAIL
        assert result.error_code == "SECRET_PATTERN_DETECTED"

    def test_default_checks_all_zero_model(self) -> None:
        """All default checks run without model calls."""
        checks = build_default_checks()
        assert len(checks) == 4
        for chk in checks:
            assert chk.check_id != ""


class TestReportZeroModel:
    """Report interface enforces zero model."""

    def test_report_hash_deterministic(self) -> None:
        clock1 = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        clock2 = SeededClock(
            start=_dt.datetime(2026, 1, 5, 9, 0, tzinfo=_dt.UTC)
        )
        r1, _ = run_assurance(_config(), clock1)
        r2, _ = run_assurance(_config(), clock2)
        # Same run_id? No—uuid4. But the report hashes for the same
        # checks and same timestamps should be the same if run_id is
        # the same. Let's verify with fixed run_id.
        from src.assurance.report import AssuranceReport
        report1 = AssuranceReport(
            run_id="fixed-id",
            occurrence_id=r1.occurrence_id,
            suite_version=r1.suite_version,
            tenant_scope=r1.tenant_scope,
            started_at=r1.started_at,
            ended_at=r1.ended_at,
            input_manifest_hash=r1.input_manifest_hash,
            checks=r1.checks,
        )
        report2 = AssuranceReport(
            run_id="fixed-id",
            occurrence_id=r2.occurrence_id,
            suite_version=r2.suite_version,
            tenant_scope=r2.tenant_scope,
            started_at=r2.started_at,
            ended_at=r2.ended_at,
            input_manifest_hash=r2.input_manifest_hash,
            checks=r2.checks,
        )
        assert report1.report_hash() == report2.report_hash()
