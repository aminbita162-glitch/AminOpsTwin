"""Assurance runner — S2 workflow that A4 triggers through S1 (P6, §34).

The runner executes the zero-model assurance checks for a given
occurrence and produces an :class:`AssuranceReport`.  No LLM, embedding,
model inference, generated summary or model-based scheduling is allowed
(G4.10).  Assert model_request_count=0 and model_tokens_used=0.
"""

from __future__ import annotations

from typing import Any

from src.assurance.checks import (
    AssuranceCheck,
    check_binding_integrity,
    check_deterministic_replay,
    check_duplicate_budget_invariants,
    check_sanitized_logging,
)
from src.assurance.report import (
    AssuranceReport,
    AssuranceRunSummary,
    CheckOutcome,
    CheckResult,
    RunState,
    build_report,
)
from src.assurance.scheduler import (
    ScheduleConfig,
    ScheduleOccurrence,
    WeeklyScheduler,
)
from src.contracts.clock import Clock

__all__ = [
    "AssuranceRunner",
    "build_default_checks",
    "run_assurance",
]


def build_default_checks() -> list[AssuranceCheck]:
    """Build the default set of zero-model assurance checks (§34)."""
    return [
        AssuranceCheck("binding_integrity", check_binding_integrity),
        AssuranceCheck("deterministic_replay", check_deterministic_replay),
        AssuranceCheck("duplicate_budget_invariants", check_duplicate_budget_invariants),  # noqa: E501
        AssuranceCheck("sanitized_logging", check_sanitized_logging),
    ]


class AssuranceRunner:
    """S2 workflow runner for zero-model weekly assurance (§34, G4.10).

    The runner executes the configured checks for a given occurrence,
    builds an :class:`AssuranceReport`, and updates the scheduler state.
    No model calls are made; ``model_request_count`` and
    ``model_tokens_used`` are always 0 (G4.10).
    """

    def __init__(
        self,
        config: ScheduleConfig,
        clock: Clock,
        checks: list[AssuranceCheck] | None = None,
    ) -> None:
        self._config = config
        self._clock = clock
        self._checks = checks if checks is not None else build_default_checks()
        self._reports: list[AssuranceReport] = []

    @property
    def config(self) -> ScheduleConfig:
        return self._config

    @property
    def reports(self) -> list[AssuranceReport]:
        return list(self._reports)

    def run_checks(
        self,
        occurrence: ScheduleOccurrence,
        config: ScheduleConfig,
    ) -> dict[str, Any]:
        """Run all checks for *occurrence* and return the report dict.

        Implements the ``_CheckRunner`` protocol expected by
        :class:`WeeklyScheduler`.
        """
        started = self._clock.now()
        results: list[CheckResult] = []
        for chk in self._checks:
            try:
                result = chk.run(occurrence, config)
            except Exception as exc:
                result = CheckResult(
                    check_id=chk.check_id,
                    outcome=CheckOutcome.FAIL,
                    error_code=f"CHECK_EXCEPTION:{type(exc).__name__}",
                )
            results.append(result)
        ended = self._clock.now()

        manifest: dict[str, Any] = {
            "suite_version": config.suite_version,
            "deployment_id": config.deployment_id,
            "tenant_scope": config.tenant_scope,
            "checks": [c.check_id for c in self._checks],
        }
        report = build_report(
            occurrence_id=occurrence.occurrence_id,
            suite_version=config.suite_version,
            tenant_scope=config.tenant_scope,
            started_at=started,
            ended_at=ended,
            input_manifest=manifest,
            checks=results,
        )
        self._reports.append(report)
        return report.to_dict()

    def trigger_run(self, scheduler: WeeklyScheduler) -> AssuranceReport:
        """Trigger a run through the scheduler and return the report.

        The scheduler determines the current occurrence; the runner
        executes the checks and the scheduler marks the occurrence
        completed or failed.
        """
        now = self._clock.now()
        scheduler.trigger(self, now=now)
        # Reconstruct the AssuranceReport from the result dict.
        # The report was already stored in self._reports by run_checks.
        if self._reports:
            report = self._reports[-1]
        else:
            # Duplicate trigger: build a minimal NOT_RUN report.
            occ = scheduler.next_occurrence(now)
            report = build_report(
                occurrence_id=occ.occurrence_id,
                suite_version=self._config.suite_version,
                tenant_scope=self._config.tenant_scope,
                started_at=now,
                ended_at=now,
                input_manifest={},
                checks=[],
            )
        if report.overall_state == RunState.PASS:
            scheduler.mark_completed(report.occurrence_id)
        elif report.overall_state == RunState.FAIL:
            scheduler.mark_failed(report.occurrence_id)
        return report

    def build_summary(
        self,
        scheduler: WeeklyScheduler,
    ) -> AssuranceRunSummary:
        """Build a dashboard summary (§34).

        Exposes the last successful run, latest attempt and next
        configured occurrence separately.
        """
        last_success: AssuranceReport | None = None
        latest_attempt: AssuranceReport | None = None
        for r in self._reports:
            if r.overall_state == RunState.PASS:
                last_success = r
            latest_attempt = r
        next_occ = scheduler.next_occurrence()
        return AssuranceRunSummary(
            latest_attempt_id=(
                latest_attempt.run_id if latest_attempt else None
            ),
            latest_attempt_state=(
                latest_attempt.overall_state if latest_attempt else None
            ),
            last_success_id=(
                last_success.run_id if last_success else None
            ),
            last_success_at=(
                last_success.ended_at if last_success else None
            ),
            next_occurrence_id=next_occ.occurrence_id,
            next_occurrence_at=next_occ.scheduled_at,
            missed_count=len(scheduler.missed_occurrences),
            failed_count=len(scheduler.failed_occurrences),
        )


def run_assurance(
    config: ScheduleConfig,
    clock: Clock,
    checks: list[AssuranceCheck] | None = None,
) -> tuple[AssuranceReport, AssuranceRunSummary]:
    """Convenience: create scheduler + runner, trigger once, return report + summary."""
    scheduler = WeeklyScheduler(config, clock)
    runner = AssuranceRunner(config, clock, checks)
    report = runner.trigger_run(scheduler)
    summary = runner.build_summary(scheduler)
    return report, summary
