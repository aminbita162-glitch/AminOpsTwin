"""Assurance package — weekly zero-model assurance interface (P6, §34, G4.10, G4.11).

Deterministic weekly scheduler (A4) triggers an S2 workflow through S1.
No LLM, embedding, model inference, generated summary or model-based
scheduling is allowed in this workflow.  Assert ``model_request_count=0``
and ``model_tokens_used=0``.

G4.10 Zero-model assurance: every weekly-job success, failure, retry and
missed-run test has zero model calls and zero model tokens.  A
deliberately injected model call causes test failure.

G4.11 Assurance integrity: every declared schedule/restart/duplicate
fixture has the expected run state; required NOT_RUN/FAIL can never
produce overall PASS; evidence hashes verify.
"""

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
    AssuranceRunSummary,
    RunState,
)
from src.assurance.runner import (
    AssuranceRunner,
    build_default_checks,
    run_assurance,
)
from src.assurance.scheduler import (
    MissedRunPolicy,
    ScheduleConfig,
    WeeklyScheduler,
)

__all__ = [
    # scheduler
    "ScheduleConfig",
    "MissedRunPolicy",
    "WeeklyScheduler",
    # report
    "AssuranceReport",
    "AssuranceRunSummary",
    "RunState",
    # checks
    "AssuranceCheck",
    "CheckOutcome",
    "check_binding_integrity",
    "check_deterministic_replay",
    "check_duplicate_budget_invariants",
    "check_sanitized_logging",
    # runner
    "AssuranceRunner",
    "build_default_checks",
    "run_assurance",
]
