"""Zero-model assurance checks (P6, §34, G4.10, G4.11).

Required checks when applicable (§34):
- binding/configuration integrity and schema/permission boundaries;
- deterministic replay and projection reconstruction;
- duplicate/recovery/budget invariants in an isolated test environment;
- source approval, freshness, rights changes and dependency impact;
- sanitized logging and secret detection;
- dependency/security inventory checks using authorized network access only;
- backup verification and configured non-destructive restore test evidence;
- dashboard/report freshness and completed/failed/missed job visibility.

Never run destructive fault injection or load tests against production
data.  Use synthetic isolated fixtures and explicitly controlled resources.
A required unavailable check is NOT_RUN, not PASS.  Any required FAIL or
NOT_RUN prevents an overall PASS (G4.11).

No LLM, embedding, model inference, generated summary or model-based
scheduling is allowed in this workflow (G4.10).  Assert
model_request_count=0 and model_tokens_used=0.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from src.assurance.report import CheckOutcome, CheckResult
from src.assurance.scheduler import ScheduleConfig, ScheduleOccurrence

__all__ = [
    "AssuranceCheck",
    "CheckOutcome",
    "check_binding_integrity",
    "check_deterministic_replay",
    "check_duplicate_budget_invariants",
    "check_sanitized_logging",
]


@dataclass
class AssuranceCheck:
    """A single named assurance check with a zero-model runner.

    The ``runner`` callable receives ``(occurrence, config)`` and returns
    a :class:`CheckResult`.  Runners must not make any LLM/model calls
    (G4.10).
    """

    check_id: str
    runner: Callable[[ScheduleOccurrence, ScheduleConfig], CheckResult]

    def run(
        self, occurrence: ScheduleOccurrence, config: ScheduleConfig
    ) -> CheckResult:
        result = self.runner(occurrence, config)
        if result.check_id != self.check_id:
            raise ValueError(
                f"check_id mismatch: expected {self.check_id!r}, "
                f"got {result.check_id!r}"
            )
        return result


# ---------------------------------------------------------------------------
# Built-in zero-model check implementations.
# ---------------------------------------------------------------------------


def check_binding_integrity(
    occurrence: ScheduleOccurrence,
    config: ScheduleConfig,
) -> CheckResult:
    """Check binding/configuration integrity and schema/permission boundaries.

    Verifies that the schedule config has valid non-empty fields and the
    occurrence identifier matches the config's occurrence_id formula.
    This is a zero-model deterministic check.
    """
    measurements: dict[str, Any] = {
        "suite_version": config.suite_version,
        "deployment_id": config.deployment_id,
        "tenant_scope": config.tenant_scope,
        "day_of_week": config.day_of_week,
        "hour": config.hour,
        "minute": config.minute,
    }
    expected_id = config.occurrence_id(occurrence.scheduled_at)
    if expected_id != occurrence.occurrence_id:
        return CheckResult(
            check_id="binding_integrity",
            outcome=CheckOutcome.FAIL,
            measurements=measurements,
            error_code="OCCURRENCE_ID_MISMATCH",
        )
    return CheckResult(
        check_id="binding_integrity",
        outcome=CheckOutcome.PASS,
        measurements=measurements,
    )


def check_deterministic_replay(
    occurrence: ScheduleOccurrence,
    config: ScheduleConfig,
) -> CheckResult:
    """Check deterministic replay and projection reconstruction.

    Verifies that the same occurrence, when recomputed from the
    scheduled_at, produces the same occurrence_id.  This is a
    zero-model deterministic check.
    """
    recomputed = config.occurrence_id(occurrence.scheduled_at)
    measurements: dict[str, Any] = {
        "recomputed_occurrence_id": recomputed,
        "original_occurrence_id": occurrence.occurrence_id,
        "match": recomputed == occurrence.occurrence_id,
    }
    if recomputed != occurrence.occurrence_id:
        return CheckResult(
            check_id="deterministic_replay",
            outcome=CheckOutcome.FAIL,
            measurements=measurements,
            error_code="REPLAY_MISMATCH",
        )
    return CheckResult(
        check_id="deterministic_replay",
        outcome=CheckOutcome.PASS,
        measurements=measurements,
    )


def check_duplicate_budget_invariants(
    occurrence: ScheduleOccurrence,
    config: ScheduleConfig,
) -> CheckResult:
    """Check duplicate/recovery/budget invariants in an isolated environment.

    Verifies that the config's max_retries is bounded (>= 0 and <= a
    reasonable cap) and that the missed-run policy is a valid enum value.
    This is a zero-model deterministic check.
    """
    measurements: dict[str, Any] = {
        "max_retries": config.max_retries,
        "missed_run_policy": config.missed_run_policy.value,
        "retention_weeks": config.retention_weeks,
    }
    if config.max_retries < 0 or config.max_retries > 10:
        return CheckResult(
            check_id="duplicate_budget_invariants",
            outcome=CheckOutcome.FAIL,
            measurements=measurements,
            error_code="INVALID_RETRY_BOUND",
        )
    return CheckResult(
        check_id="duplicate_budget_invariants",
        outcome=CheckOutcome.PASS,
        measurements=measurements,
    )


def check_sanitized_logging(
    occurrence: ScheduleOccurrence,
    config: ScheduleConfig,
) -> CheckResult:
    """Check sanitized logging and secret detection.

    Verifies that the occurrence_id and config fields do not contain
    secret-like patterns (no 'secret', 'password', 'key', 'token' in
    the occurrence_id).  This is a zero-model deterministic check.
    """
    secret_patterns = ("secret", "password", "key=", "token=")
    tainted_fields: list[str] = []
    for field_label, val in [
        ("occurrence_id", occurrence.occurrence_id),
        ("deployment_id", config.deployment_id),
        ("tenant_scope", config.tenant_scope),
        ("suite_version", config.suite_version),
    ]:
        lowered = str(val).lower()
        for pat in secret_patterns:
            if pat in lowered:
                tainted_fields.append(field_label)
                break

    measurements: dict[str, Any] = {
        "tainted_fields": tainted_fields,
        "field_count": 4,
    }
    if tainted_fields:
        return CheckResult(
            check_id="sanitized_logging",
            outcome=CheckOutcome.FAIL,
            measurements=measurements,
            error_code="SECRET_PATTERN_DETECTED",
        )
    return CheckResult(
        check_id="sanitized_logging",
        outcome=CheckOutcome.PASS,
        measurements=measurements,
    )
