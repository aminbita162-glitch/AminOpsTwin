"""Backend report interface for assurance runs (P6, §34, G4.10, G4.11).

Report fields (§34):
    run_id, schedule occurrence, start/end, input manifest hash,
    suite version, per-check PASS/FAIL/NOT_RUN, measurements,
    evidence paths, error codes, model_request_count,
    model_tokens_used, and overall result.

Dashboard exposes the last successful run, latest attempt and next
configured occurrence separately.  Reports are rendered from fixed
English templates.  No LLM, embedding, model inference, generated
summary or model-based scheduling is allowed in this workflow.

A required unavailable check is NOT_RUN, not PASS.  Any required FAIL or
NOT_RUN prevents an overall PASS (G4.11).
"""

from __future__ import annotations

import datetime as _dt
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from src.contracts.canonical import canonical_hash

__all__ = [
    "RunState",
    "CheckResult",
    "AssuranceReport",
    "AssuranceRunSummary",
]


class RunState(StrEnum):
    """Overall run state of an assurance occurrence (§34, G4.11)."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


class CheckOutcome(StrEnum):
    """Per-check outcome (§34)."""

    PASS = "PASS"
    FAIL = "FAIL"
    NOT_RUN = "NOT_RUN"


@dataclass(frozen=True)
class CheckResult:
    """Result of a single assurance check (§34).

    A required FAIL or NOT_RUN prevents an overall PASS (G4.11).
    """

    check_id: str
    outcome: CheckOutcome
    measurements: dict[str, Any] = field(default_factory=dict)
    evidence_path: str | None = None
    error_code: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "outcome": self.outcome.value,
            "measurements": dict(self.measurements),
            "evidence_path": self.evidence_path,
            "error_code": self.error_code,
        }


@dataclass
class AssuranceReport:
    """Full assurance run report (§34).

    model_request_count and model_tokens_used are always 0 for the
    zero-model assurance workflow (G4.10).  A deliberately injected
    model call sets them to a non-zero value and causes G4.10 test
    failure.
    """

    run_id: str
    occurrence_id: str
    suite_version: str
    tenant_scope: str
    started_at: _dt.datetime
    ended_at: _dt.datetime
    input_manifest_hash: str
    checks: list[CheckResult] = field(default_factory=list)
    model_request_count: int = 0
    model_tokens_used: int = 0
    overall_state: RunState = RunState.NOT_RUN

    def __post_init__(self) -> None:
        if self.model_request_count < 0:
            raise ValueError("model_request_count must be >= 0")
        if self.model_tokens_used < 0:
            raise ValueError("model_tokens_used must be >= 0")
        if self.started_at.tzinfo is None:
            raise ValueError("started_at must be timezone-aware UTC")
        if self.ended_at.tzinfo is None:
            raise ValueError("ended_at must be timezone-aware UTC")

    def compute_overall(self) -> RunState:
        """Compute the overall run state from per-check outcomes (G4.11).

        Any FAIL → FAIL.  Otherwise any NOT_RUN → NOT_RUN.
        Otherwise PASS.  A required FAIL or NOT_RUN prevents overall
        PASS (G4.11).
        """
        if not self.checks:
            return RunState.NOT_RUN
        has_fail = any(c.outcome == CheckOutcome.FAIL for c in self.checks)
        has_not_run = any(c.outcome == CheckOutcome.NOT_RUN for c in self.checks)
        if has_fail:
            return RunState.FAIL
        if has_not_run:
            return RunState.NOT_RUN
        return RunState.PASS

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a canonical dict for report storage."""
        return {
            "run_id": self.run_id,
            "occurrence_id": self.occurrence_id,
            "suite_version": self.suite_version,
            "tenant_scope": self.tenant_scope,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat(),
            "input_manifest_hash": self.input_manifest_hash,
            "checks": [c.to_dict() for c in self.checks],
            "model_request_count": self.model_request_count,
            "model_tokens_used": self.model_tokens_used,
            "overall_state": self.overall_state.value,
        }

    def report_hash(self) -> str:
        """SHA-256 hash of the canonical report bytes (G4.11 evidence)."""
        return canonical_hash(self.to_dict())

    def is_zero_model(self) -> bool:
        """Return True iff model_request_count and model_tokens_used are 0 (G4.10)."""
        return self.model_request_count == 0 and self.model_tokens_used == 0


@dataclass
class AssuranceRunSummary:
    """Dashboard summary: latest attempt, last success, next occurrence (§34).

    The dashboard exposes the last successful run, latest attempt and
    next configured occurrence separately.
    """

    latest_attempt_id: str | None = None
    latest_attempt_state: RunState | None = None
    last_success_id: str | None = None
    last_success_at: _dt.datetime | None = None
    next_occurrence_id: str | None = None
    next_occurrence_at: _dt.datetime | None = None
    missed_count: int = 0
    failed_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_attempt_id": self.latest_attempt_id,
            "latest_attempt_state": (
                self.latest_attempt_state.value
                if self.latest_attempt_state is not None
                else None
            ),
            "last_success_id": self.last_success_id,
            "last_success_at": (
                self.last_success_at.isoformat()
                if self.last_success_at is not None
                else None
            ),
            "next_occurrence_id": self.next_occurrence_id,
            "next_occurrence_at": (
                self.next_occurrence_at.isoformat()
                if self.next_occurrence_at is not None
                else None
            ),
            "missed_count": self.missed_count,
            "failed_count": self.failed_count,
        }


def build_report(
    *,
    occurrence_id: str,
    suite_version: str,
    tenant_scope: str,
    started_at: _dt.datetime,
    ended_at: _dt.datetime,
    input_manifest: dict[str, Any],
    checks: list[CheckResult],
    run_id: str | None = None,
) -> AssuranceReport:
    """Build an :class:`AssuranceReport` with zero model usage (G4.10).

    The ``input_manifest_hash`` is the canonical hash of
    ``input_manifest``.  The overall state is computed from the
    per-check outcomes (G4.11).
    """
    if run_id is None:
        run_id = f"run-{occurrence_id}-{uuid.uuid4().hex[:12]}"
    manifest_hash = canonical_hash(input_manifest)
    report = AssuranceReport(
        run_id=run_id,
        occurrence_id=occurrence_id,
        suite_version=suite_version,
        tenant_scope=tenant_scope,
        started_at=started_at,
        ended_at=ended_at,
        input_manifest_hash=manifest_hash,
        checks=list(checks),
        model_request_count=0,
        model_tokens_used=0,
    )
    report.overall_state = report.compute_overall()
    return report
