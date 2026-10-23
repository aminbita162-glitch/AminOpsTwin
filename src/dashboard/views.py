"""Dashboard view data providers (P7, §35, G4.12).

Seven required views (§35):
    - Overview: synthetic/demo status, resource capacity, queues,
      scenario status.
    - Scenario comparison: baseline, deltas, assumptions,
      uncertainty and constraints.
    - Evidence: source versions, rights status and claim-to-source
      paths.
    - Workflow: current state, UNKNOWN/reconciliation and execution
      receipts.
    - Budget: remaining/reserved/actual counters and deterministic
      fallback status.
    - Assurance: latest attempt, last successful check, failures
      and stale status.
    - Experience: candidate versus active versions and promotion
      evidence.

The provider aggregates data from existing subsystems into
serialisable view models.  No raw database access or private signing
keys are exposed to the browser (§35).  Stale, incomplete, unknown,
failed and not-run states are displayed distinctly.

All actions and reads require server-side controls through existing
contracts — hiding buttons is not authorization (§35).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

from src.dashboard.accessibility import StatusIndicator
from src.dashboard.wallboard import WallboardConfig

__all__ = [
    "ViewKey",
    "OverviewView",
    "ScenarioComparisonView",
    "EvidenceView",
    "WorkflowView",
    "BudgetView",
    "AssuranceView",
    "ExperienceView",
    "DashboardData",
    "DashboardDataProvider",
]


class ViewKey(StrEnum):
    """Keys for the seven required dashboard views (§35)."""

    OVERVIEW = "overview"
    SCENARIO_COMPARISON = "scenario_comparison"
    EVIDENCE = "evidence"
    WORKFLOW = "workflow"
    BUDGET = "budget"
    ASSURANCE = "assurance"
    EXPERIENCE = "experience"


@dataclass
class OverviewView:
    """Overview: synthetic/demo status, resource capacity, queues (§35)."""

    demo_status: str = "Synthetic scenario - not live organizational data"
    is_synthetic: bool = True
    sites: list[dict[str, Any]] = field(default_factory=list)
    resources: list[dict[str, Any]] = field(default_factory=list)
    queues: list[dict[str, Any]] = field(default_factory=list)
    scenario_count: int = 0
    last_updated: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "demo_status": self.demo_status,
            "is_synthetic": self.is_synthetic,
            "sites": list(self.sites),
            "resources": list(self.resources),
            "queues": list(self.queues),
            "scenario_count": self.scenario_count,
            "last_updated": self.last_updated,
        }


@dataclass
class ScenarioComparisonView:
    """Scenario comparison: baseline, deltas, assumptions (§35)."""

    comparisons: list[dict[str, Any]] = field(default_factory=list)
    baseline_id: str = ""
    delta_count: int = 0
    has_uncertainty: bool = False
    not_estimable_reason: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "comparisons": list(self.comparisons),
            "baseline_id": self.baseline_id,
            "delta_count": self.delta_count,
            "has_uncertainty": self.has_uncertainty,
            "not_estimable_reason": self.not_estimable_reason,
        }


@dataclass
class EvidenceView:
    """Evidence: source versions, rights status, claim paths (§35)."""

    sources: list[dict[str, Any]] = field(default_factory=list)
    approved_count: int = 0
    active_count: int = 0
    pending_count: int = 0
    rights_status: str = ""
    claim_paths: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "sources": list(self.sources),
            "approved_count": self.approved_count,
            "active_count": self.active_count,
            "pending_count": self.pending_count,
            "rights_status": self.rights_status,
            "claim_paths": list(self.claim_paths),
        }


@dataclass
class WorkflowView:
    """Workflow: current state, UNKNOWN/reconciliation, receipts (§35)."""

    current_state: str = "PENDING"
    states: list[dict[str, Any]] = field(default_factory=list)
    unknown_count: int = 0
    reconciling_count: int = 0
    execution_receipts: list[dict[str, Any]] = field(default_factory=list)
    state_indicator: StatusIndicator = StatusIndicator.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "current_state": self.current_state,
            "states": list(self.states),
            "unknown_count": self.unknown_count,
            "reconciling_count": self.reconciling_count,
            "execution_receipts": list(self.execution_receipts),
            "state_indicator": self.state_indicator.value,
            "state_label": self.state_indicator.label,
            "state_icon": self.state_indicator.icon,
        }


@dataclass
class BudgetView:
    """Budget: remaining/reserved/actual counters, fallback status (§35)."""

    session_remaining: int = 0
    session_reserved: int = 0
    session_used: int = 0
    workflow_remaining: int = 0
    workflow_reserved: int = 0
    workflow_used: int = 0
    capability_remaining: int = 0
    capability_reserved: int = 0
    capability_used: int = 0
    fallback_active: bool = False
    fallback_reason: str | None = None
    indicator: StatusIndicator = StatusIndicator.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_remaining": self.session_remaining,
            "session_reserved": self.session_reserved,
            "session_used": self.session_used,
            "workflow_remaining": self.workflow_remaining,
            "workflow_reserved": self.workflow_reserved,
            "workflow_used": self.workflow_used,
            "capability_remaining": self.capability_remaining,
            "capability_reserved": self.capability_reserved,
            "capability_used": self.capability_used,
            "fallback_active": self.fallback_active,
            "fallback_reason": self.fallback_reason,
            "indicator": self.indicator.value,
            "indicator_label": self.indicator.label,
            "indicator_icon": self.indicator.icon,
        }


@dataclass
class AssuranceView:
    """Assurance: latest attempt, last success, failures, stale (§35)."""

    latest_attempt_id: str | None = None
    latest_attempt_state: str | None = None
    last_success_id: str | None = None
    last_success_at: str | None = None
    next_occurrence_id: str | None = None
    next_occurrence_at: str | None = None
    missed_count: int = 0
    failed_count: int = 0
    checks: list[dict[str, Any]] = field(default_factory=list)
    is_stale: bool = False
    indicator: StatusIndicator = StatusIndicator.NOT_RUN

    def to_dict(self) -> dict[str, Any]:
        return {
            "latest_attempt_id": self.latest_attempt_id,
            "latest_attempt_state": self.latest_attempt_state,
            "last_success_id": self.last_success_id,
            "last_success_at": self.last_success_at,
            "next_occurrence_id": self.next_occurrence_id,
            "next_occurrence_at": self.next_occurrence_at,
            "missed_count": self.missed_count,
            "failed_count": self.failed_count,
            "checks": list(self.checks),
            "is_stale": self.is_stale,
            "indicator": self.indicator.value,
            "indicator_label": self.indicator.label,
            "indicator_icon": self.indicator.icon,
        }


@dataclass
class ExperienceView:
    """Experience: candidate versus active, promotion evidence (§35)."""

    records: list[dict[str, Any]] = field(default_factory=list)
    active_count: int = 0
    candidate_count: int = 0
    promoted_count: int = 0
    promotion_evidence: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": list(self.records),
            "active_count": self.active_count,
            "candidate_count": self.candidate_count,
            "promoted_count": self.promoted_count,
            "promotion_evidence": list(self.promotion_evidence),
        }


@dataclass
class DashboardData:
    """Aggregated dashboard data for all seven views (§35)."""

    overview: OverviewView = field(default_factory=OverviewView)
    scenario_comparison: ScenarioComparisonView = field(
        default_factory=ScenarioComparisonView
    )
    evidence: EvidenceView = field(default_factory=EvidenceView)
    workflow: WorkflowView = field(default_factory=WorkflowView)
    budget: BudgetView = field(default_factory=BudgetView)
    assurance: AssuranceView = field(default_factory=AssuranceView)
    experience: ExperienceView = field(default_factory=ExperienceView)
    wallboard: WallboardConfig = field(default_factory=WallboardConfig)
    view_keys: list[str] = field(default_factory=lambda: [v.value for v in ViewKey])

    def to_dict(self) -> dict[str, Any]:
        return {
            "overview": self.overview.to_dict(),
            "scenario_comparison": self.scenario_comparison.to_dict(),
            "evidence": self.evidence.to_dict(),
            "workflow": self.workflow.to_dict(),
            "budget": self.budget.to_dict(),
            "assurance": self.assurance.to_dict(),
            "experience": self.experience.to_dict(),
            "wallboard": self.wallboard.to_dict(),
            "view_keys": list(self.view_keys),
        }

    def view_by_key(self, key: str) -> dict[str, Any] | None:
        """Return a single view's data by key, or None if unknown."""
        mapping: dict[str, Any] = {
            ViewKey.OVERVIEW.value: self.overview.to_dict(),
            ViewKey.SCENARIO_COMPARISON.value: self.scenario_comparison.to_dict(),
            ViewKey.EVIDENCE.value: self.evidence.to_dict(),
            ViewKey.WORKFLOW.value: self.workflow.to_dict(),
            ViewKey.BUDGET.value: self.budget.to_dict(),
            ViewKey.ASSURANCE.value: self.assurance.to_dict(),
            ViewKey.EXPERIENCE.value: self.experience.to_dict(),
        }
        return mapping.get(key)


class _ScenarioProvider(Protocol):
    """Protocol for scenario data (duck-typed)."""

    def run_all(self) -> dict[str, Any]: ...


class _BudgetProvider(Protocol):
    """Protocol for budget governor data."""

    def remaining(self, level: Any) -> int: ...
    def is_exhausted(self, level: Any) -> bool: ...


class DashboardDataProvider:
    """Aggregate data from existing subsystems into dashboard views (§35).

    No new agents or services.  The provider reads from existing
    subsystems and maps their data into view models.  All reads are
    server-side — the browser never touches raw storage (§35).

    Any subsystem may be None; the provider returns empty/default
    views in that case (stale/incomplete state is displayed
    distinctly, not hidden).
    """

    def __init__(
        self,
        scenario_library: Any | None = None,
        budget_governor: Any | None = None,
        memory_store: Any | None = None,
        experience_store: Any | None = None,
        source_registry: Any | None = None,
        assurance_runner: Any | None = None,
        scheduler: Any | None = None,
        wallboard_config: WallboardConfig | None = None,
    ) -> None:
        self._scenario_library = scenario_library
        self._budget_governor = budget_governor
        self._memory_store = memory_store
        self._experience_store = experience_store
        self._source_registry = source_registry
        self._assurance_runner = assurance_runner
        self._scheduler = scheduler
        self._wallboard_config = wallboard_config or WallboardConfig()

    def build(self) -> DashboardData:
        """Build the full dashboard data from all subsystems."""
        data = DashboardData()
        data.wallboard = self._wallboard_config
        data.overview = self._build_overview()
        data.scenario_comparison = self._build_scenario_comparison()
        data.evidence = self._build_evidence()
        data.workflow = self._build_workflow()
        data.budget = self._build_budget()
        data.assurance = self._build_assurance()
        data.experience = self._build_experience()
        return data

    def build_view(self, key: str) -> dict[str, Any] | None:
        """Build and return a single view by key (for per-view endpoints)."""
        data = self.build()
        return data.view_by_key(key)

    def _build_overview(self) -> OverviewView:
        view = OverviewView()
        if self._scenario_library is not None:
            try:
                results = self._scenario_library.run_all()
                view.scenario_count = len(results)
                for sid, result in results.items():
                    view.sites.append({
                        "scenario_id": sid,
                        "state_hash": getattr(result, "final_state_hash", ""),
                        "total_arrivals": getattr(result, "total_arrivals", 0),
                        "total_completions": getattr(result, "total_completions", 0),
                        "indicator": StatusIndicator.DEMO.value,
                    })
            except Exception:
                view.scenario_count = 0
        view.demo_status = "Synthetic scenario - not live organizational data"
        view.is_synthetic = True
        return view

    def _build_scenario_comparison(self) -> ScenarioComparisonView:
        view = ScenarioComparisonView()
        if self._scenario_library is not None:
            try:
                results = self._scenario_library.run_all()
                ids = sorted(results.keys())
                if len(ids) >= 2:
                    view.baseline_id = ids[0]
                    for sid in ids[1:]:
                        result = results[sid]
                        view.comparisons.append({
                            "scenario_id": sid,
                            "baseline_id": view.baseline_id,
                            "mean_wait_time": getattr(result, "mean_wait_time", 0),
                            "max_queue_length": getattr(result, "max_queue_length", 0),
                            "total_completions": getattr(
                                result, "total_completions", 0
                            ),
                        })
                    view.delta_count = len(view.comparisons)
                    # Check uncertainty
                    first_result = results[ids[0]]
                    unc = getattr(first_result, "uncertainty", None)
                    if unc is not None:
                        view.has_uncertainty = True
                        reason = getattr(unc, "not_estimable_reason", None)
                        view.not_estimable_reason = reason
            except Exception:
                pass
        return view

    def _build_evidence(self) -> EvidenceView:
        view = EvidenceView()
        if self._source_registry is not None:
            try:
                records = self._source_registry.all_records()
                for r in records:
                    status_raw = getattr(r, "status", None)
                    status_val: str = (
                        status_raw.value
                        if status_raw is not None and hasattr(status_raw, "value")
                        else str(status_raw)
                    )
                    view.sources.append({
                        "source_id": getattr(r, "source_id", ""),
                        "title": getattr(r, "title", ""),
                        "license": getattr(r, "license", ""),
                        "status": status_val,
                        "review_status": getattr(r, "review_status", "pending"),
                    })
                view.approved_count = len(self._source_registry.approved_records())
                view.active_count = sum(
                    1 for r in records
                    if getattr(r, "status", None) is not None
                    and str(
                        getattr(r.status, "value", r.status)
                    ) == "ACTIVE"
                )
                view.pending_count = max(view.approved_count - view.active_count, 0)
                view.rights_status = "approved" if view.approved_count > 0 else "none"
            except Exception:
                pass
        return view

    def _build_workflow(self) -> WorkflowView:
        view = WorkflowView()
        if self._memory_store is not None:
            try:
                events = self._memory_store.events()
                for e in events:
                    state = getattr(e, "status", "ACTIVE")
                    view.states.append({
                        "record_id": getattr(e, "record_id", ""),
                        "state": state,
                        "sequence_no": getattr(e, "sequence_no", 0),
                    })
                view.current_state = (
                    view.states[-1]["state"] if view.states else "PENDING"
                )
                view.unknown_count = sum(
                    1 for s in view.states if s["state"] == "UNKNOWN"
                )
                view.reconciling_count = sum(
                    1 for s in view.states if s["state"] == "RECONCILING"
                )
                view.execution_receipts = [
                    {"record_id": s["record_id"], "sequence_no": s["sequence_no"]}
                    for s in view.states
                ]
                if view.unknown_count > 0:
                    view.state_indicator = StatusIndicator.UNKNOWN
                elif view.reconciling_count > 0:
                    view.state_indicator = StatusIndicator.RECONCILING
                else:
                    view.state_indicator = StatusIndicator.COMPLETED
            except Exception:
                view.current_state = "PENDING"
                view.state_indicator = StatusIndicator.PENDING
        return view

    def _build_budget(self) -> BudgetView:
        view = BudgetView()
        if self._budget_governor is not None:
            from src.tokens.budget import BudgetLevel
            view.session_remaining = (
                self._budget_governor.remaining(BudgetLevel.SESSION)
            )
            view.workflow_remaining = (
                self._budget_governor.remaining(BudgetLevel.WORKFLOW)
            )
            view.capability_remaining = (
                self._budget_governor.remaining(BudgetLevel.CAPABILITY)
            )
            if self._budget_governor.is_exhausted(BudgetLevel.SESSION):
                view.fallback_active = True
                view.fallback_reason = "BUDGET_SESSION_EXHAUSTED"
                view.indicator = StatusIndicator.EXHAUSTED
            elif self._budget_governor.is_exhausted(BudgetLevel.WORKFLOW):
                view.fallback_active = True
                view.fallback_reason = "BUDGET_WORKFLOW_EXHAUSTED"
                view.indicator = StatusIndicator.EXHAUSTED
            elif self._budget_governor.is_exhausted(BudgetLevel.CAPABILITY):
                view.fallback_active = True
                view.fallback_reason = "BUDGET_CAPABILITY_EXHAUSTED"
                view.indicator = StatusIndicator.EXHAUSTED
            else:
                view.indicator = StatusIndicator.ACTIVE
        return view

    def _build_assurance(self) -> AssuranceView:
        view = AssuranceView()
        if self._assurance_runner is not None and self._scheduler is not None:
            try:
                summary = self._assurance_runner.build_summary(self._scheduler)
                view.latest_attempt_id = summary.latest_attempt_id
                view.latest_attempt_state = (
                    summary.latest_attempt_state.value
                    if summary.latest_attempt_state is not None
                    else None
                )
                view.last_success_id = summary.last_success_id
                view.last_success_at = (
                    summary.last_success_at.isoformat()
                    if summary.last_success_at is not None
                    else None
                )
                view.next_occurrence_id = summary.next_occurrence_id
                view.next_occurrence_at = (
                    summary.next_occurrence_at.isoformat()
                    if summary.next_occurrence_at is not None
                    else None
                )
                view.missed_count = summary.missed_count
                view.failed_count = summary.failed_count
                # Build check-level data from the latest report
                reports = self._assurance_runner.reports
                if reports:
                    latest = reports[-1]
                    for chk in latest.checks:
                        view.checks.append(chk.to_dict())
                    if latest.overall_state.value == "PASS":
                        view.indicator = StatusIndicator.PASS
                    elif latest.overall_state.value == "FAIL":
                        view.indicator = StatusIndicator.FAIL
                    else:
                        view.indicator = StatusIndicator.NOT_RUN
                else:
                    view.indicator = StatusIndicator.NOT_RUN
            except Exception:
                view.indicator = StatusIndicator.NOT_RUN
        else:
            view.indicator = StatusIndicator.NOT_RUN
        return view

    def _build_experience(self) -> ExperienceView:
        view = ExperienceView()
        if self._experience_store is not None:
            try:
                records = self._experience_store.all_records()
                for r in records:
                    status_raw = getattr(r, "status", None)
                    status_val: str = (
                        status_raw.value
                        if status_raw is not None and hasattr(status_raw, "value")
                        else str(status_raw)
                    )
                    view.records.append({
                        "experience_id": getattr(r, "experience_id", ""),
                        "task_category": getattr(r, "task_category", ""),
                        "selected_method": getattr(r, "selected_method", ""),
                        "test_outcome": getattr(r, "test_outcome", ""),
                        "status": status_val,
                    })
                    if status_val == "ACTIVE":
                        view.active_count += 1
                    elif status_val == "CANDIDATE":
                        view.candidate_count += 1
                    elif status_val == "OWNER_APPROVED":
                        view.promoted_count += 1
            except Exception:
                pass
        return view
