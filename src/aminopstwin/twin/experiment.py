"""Bounded operational experiment designer (P5, §33.1, G4.7).

Input: approved baseline snapshot, allowed integer parameter ranges,
objective, constraints, experiment budget and seed. A2 enumerates or
generates a bounded candidate set deterministically and simulates it.
A5 coordinates via S1/S2.

Output: ranked scenario ids, metric deltas, constraints, uncertainty,
assumptions, source bindings and reproducibility hashes. Stable
tie-break rules are declared.

Prohibited specifications (clinical/medical, §2.2) are denied with
exact reason codes. Infeasible candidates never become recommendations.
Repeated seeded runs reproduce results (G4.7 acceptance).
"""

from __future__ import annotations

import itertools
import random
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.twin.simulation import (
    ScenarioConfig,
    ScenarioResult,
    SimulationEngine,
    UncertaintyReport,
)

__all__ = [
    "Objective",
    "ExperimentSpec",
    "ExperimentCandidate",
    "ExperimentResult",
    "ProhibitedSpecError",
    "ExperimentDesigner",
]

#: Parameters that may be varied in an experiment (integer-valued).
_ALLOWED_PARAMETERS: frozenset[str] = frozenset(
    {
        "num_sites",
        "num_resources_per_site",
        "num_queues_per_site",
        "capacity_per_resource",
        "mean_service_time",
    }
)

#: Terms that indicate a prohibited (clinical/medical) specification.
_PROHIBITED_TERMS: frozenset[str] = frozenset(
    {
        "patient",
        "diagnosis",
        "prognosis",
        "treatment",
        "dose",
        "eligibility",
        "triage",
        "physiology",
        "individual_risk",
        "health_status",
        "patient_state",
        "symptom",
    }
)


class Objective(StrEnum):
    """Objective direction for ranking candidates."""

    MINIMIZE_WAIT_TIME = "minimize_wait_time"
    MINIMIZE_MAX_QUEUE = "minimize_max_queue"
    MAXIMIZE_THROUGHPUT = "maximize_throughput"


class ProhibitedSpecError(Exception):
    """Raised when an experiment specification touches a prohibited
    clinical/medical category (§2.2, GW-CLIN-001 / GW-CLIN-002)."""


@dataclass(frozen=True)
class ExperimentSpec:
    """Specification for a bounded experiment (§33.1).

    parameter_ranges maps a parameter name to (min, max) inclusive
    integer bounds. experiment_budget is the maximum number of
    candidates to enumerate and simulate.
    """

    experiment_id: str
    baseline_scenario_id: str
    parameter_ranges: dict[str, tuple[int, int]]
    objective: Objective = Objective.MINIMIZE_WAIT_TIME
    constraints: dict[str, int] = field(default_factory=dict)
    experiment_budget: int = 100
    seed: int = 0
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "baseline_scenario_id": self.baseline_scenario_id,
            "parameter_ranges": dict(self.parameter_ranges),
            "objective": self.objective.value,
            "constraints": dict(self.constraints),
            "experiment_budget": self.experiment_budget,
            "seed": self.seed,
            "description": self.description,
        }


@dataclass
class ExperimentCandidate:
    """A single candidate scenario within an experiment."""

    scenario_id: str
    parameters: dict[str, int]
    result_hash: str
    metric_value: int
    feasible: bool
    constraints_satisfied: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "parameters": dict(self.parameters),
            "result_hash": self.result_hash,
            "metric_value": self.metric_value,
            "feasible": self.feasible,
            "constraints_satisfied": self.constraints_satisfied,
        }


@dataclass
class ExperimentResult:
    """Result of running a bounded experiment (§33.1).

    ranked_ids are the scenario ids sorted by the objective metric.
    Stable tie-break: ascending scenario_id for equal metrics.
    """

    experiment_id: str
    seed: int
    candidates: list[ExperimentCandidate] = field(default_factory=list)
    ranked_ids: list[str] = field(default_factory=list)
    baseline_metric: int = 0
    metric_deltas: dict[str, int] = field(default_factory=dict)
    uncertainty: UncertaintyReport | None = None
    assumptions: list[str] = field(default_factory=list)
    source_bindings: list[str] = field(default_factory=list)
    reproducibility_hash: str = ""
    prohibited_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "experiment_id": self.experiment_id,
            "seed": self.seed,
            "candidates": [c.to_dict() for c in self.candidates],
            "ranked_ids": list(self.ranked_ids),
            "baseline_metric": self.baseline_metric,
            "metric_deltas": dict(self.metric_deltas),
            "uncertainty": (
                self.uncertainty.to_dict()
                if self.uncertainty is not None
                else None
            ),
            "assumptions": list(self.assumptions),
            "source_bindings": list(self.source_bindings),
            "reproducibility_hash": self.reproducibility_hash,
            "prohibited_count": self.prohibited_count,
        }


class ExperimentDesigner:
    """Bounded operational experiment designer (§33.1, G4.7).

    Enumerates or generates a bounded candidate set deterministically
    from allowed integer parameter ranges, simulates each candidate,
    and ranks them by the objective metric. Prohibited specifications
    are denied. Repeated seeded runs reproduce results.
    """

    def __init__(
        self,
        baseline_config: ScenarioConfig,
    ) -> None:
        self._baseline = baseline_config

    def design(
        self,
        spec: ExperimentSpec,
    ) -> ExperimentResult:
        """Run the experiment and return ranked results."""
        self._validate_spec(spec)

        candidates_params = self._enumerate_candidates(spec)
        # Bound by experiment_budget.
        candidates_params = candidates_params[: spec.experiment_budget]

        candidates: list[ExperimentCandidate] = []
        metric_values: list[int] = []

        for idx, params in enumerate(candidates_params):
            scenario_id = (
                f"exp-{spec.experiment_id}-cand-{idx:04d}"
            )
            config = self._build_config(scenario_id, spec.seed, params)
            result = SimulationEngine(config).run()

            constraints_ok = self._check_constraints(params, spec)
            metric = self._compute_metric(result, spec.objective)
            candidates.append(
                ExperimentCandidate(
                    scenario_id=scenario_id,
                    parameters=dict(params),
                    result_hash=result.final_state_hash,
                    metric_value=metric,
                    feasible=constraints_ok,
                    constraints_satisfied=constraints_ok,
                )
            )
            metric_values.append(metric)

        # Compute baseline metric.
        baseline_result = SimulationEngine(self._baseline).run()
        baseline_metric = self._compute_metric(
            baseline_result, spec.objective
        )

        # Rank feasible candidates by metric (stable tie-break: scenario_id).
        feasible = [c for c in candidates if c.feasible]
        if spec.objective in (
            Objective.MINIMIZE_WAIT_TIME,
            Objective.MINIMIZE_MAX_QUEUE,
        ):
            ranked = sorted(
                feasible,
                key=lambda c: (c.metric_value, c.scenario_id),
            )
        else:
            ranked = sorted(
                feasible,
                key=lambda c: (-c.metric_value, c.scenario_id),
            )

        ranked_ids = [c.scenario_id for c in ranked]
        metric_deltas: dict[str, int] = {}
        for c in candidates:
            metric_deltas[c.scenario_id] = c.metric_value - baseline_metric

        # Uncertainty report.
        if metric_values:
            min_v = min(metric_values)
            max_v = max(metric_values)
            uncertainty = UncertaintyReport(
                wait_time_interval=(min_v, max_v),
                assumptions=[
                    f"Objective = {spec.objective.value}",
                    f"Seed = {spec.seed}",
                    f"Candidates enumerated = {len(candidates_params)}",
                    "Deterministic simulation (M/M/1 approximation)",
                ],
            )
        else:
            uncertainty = UncertaintyReport(
                not_estimable_reason=(
                    "No candidates generated; metric interval not estimable"
                ),
                assumptions=[f"Seed = {spec.seed}"],
            )

        exp_result = ExperimentResult(
            experiment_id=spec.experiment_id,
            seed=spec.seed,
            candidates=candidates,
            ranked_ids=ranked_ids,
            baseline_metric=baseline_metric,
            metric_deltas=metric_deltas,
            uncertainty=uncertainty,
            assumptions=uncertainty.assumptions,
            source_bindings=[
                f"baseline:{self._baseline.scenario_id}",
            ],
        )
        exp_result.reproducibility_hash = self._compute_hash(exp_result)
        return exp_result

    def _validate_spec(self, spec: ExperimentSpec) -> None:
        """Validate the experiment specification.

        Raises ProhibitedSpecError for clinical/medical terms.
        Raises ValueError for invalid parameter ranges.
        """
        # Check description for prohibited terms.
        text = spec.description.lower()
        for term in _PROHIBITED_TERMS:
            if term in text:
                raise ProhibitedSpecError(
                    f"prohibited term in description: {term!r} "
                    f"(GW-CLIN-001)"
                )
        # Check parameter names.
        for pname in spec.parameter_ranges:
            if pname not in _ALLOWED_PARAMETERS:
                if pname.lower() in _PROHIBITED_TERMS:
                    raise ProhibitedSpecError(
                        f"prohibited parameter: {pname!r} (GW-CLIN-002)"
                    )
                raise ValueError(
                    f"parameter not allowed: {pname!r}"
                )
        # Check ranges.
        for pname, (lo, hi) in spec.parameter_ranges.items():
            if lo < 0 or hi < lo:
                raise ValueError(
                    f"invalid range for {pname}: ({lo}, {hi})"
                )
            if lo < 1 and pname in (
                "num_sites",
                "num_resources_per_site",
                "num_queues_per_site",
                "capacity_per_resource",
                "mean_service_time",
            ):
                raise ValueError(
                    f"{pname} minimum must be >= 1, got {lo}"
                )
        if spec.experiment_budget < 1:
            raise ValueError(
                f"experiment_budget must be >= 1, got {spec.experiment_budget}"
            )

    def _enumerate_candidates(
        self, spec: ExperimentSpec
    ) -> list[dict[str, int]]:
        """Enumerate the Cartesian product of parameter ranges."""
        param_names = sorted(spec.parameter_ranges.keys())
        value_lists: list[list[int]] = []
        for pname in param_names:
            lo, hi = spec.parameter_ranges[pname]
            value_lists.append(list(range(lo, hi + 1)))
        candidates: list[dict[str, int]] = []
        for combo in itertools.product(*value_lists):
            params = dict(zip(param_names, combo, strict=True))
            candidates.append(params)
        # Deterministic shuffle using seeded RNG for stable ordering.
        rng = random.Random(spec.seed)
        rng.shuffle(candidates)
        return candidates

    def _build_config(
        self,
        scenario_id: str,
        seed: int,
        params: dict[str, int],
    ) -> ScenarioConfig:
        """Build a ScenarioConfig from baseline + varied parameters."""
        base = self._baseline
        return ScenarioConfig(
            scenario_id=scenario_id,
            seed=seed,
            num_sites=params.get(
                "num_sites", base.num_sites
            ),
            num_resources_per_site=params.get(
                "num_resources_per_site",
                base.num_resources_per_site,
            ),
            num_queues_per_site=params.get(
                "num_queues_per_site",
                base.num_queues_per_site,
            ),
            capacity_per_resource=params.get(
                "capacity_per_resource",
                base.capacity_per_resource,
            ),
            queue_capacity=base.queue_capacity,
            arrival_rate=base.arrival_rate,
            mean_service_time=params.get(
                "mean_service_time", base.mean_service_time
            ),
            sim_duration=base.sim_duration,
            description=f"experiment candidate: {params}",
        )

    def _check_constraints(
        self,
        params: dict[str, int],
        spec: ExperimentSpec,
    ) -> bool:
        """Check whether candidate parameters satisfy constraints."""
        for cname, cmax in spec.constraints.items():
            val = params.get(cname, 0)
            if val > cmax:
                return False
        return True

    @staticmethod
    def _compute_metric(
        result: ScenarioResult,
        objective: Objective,
    ) -> int:
        """Extract the objective metric from a simulation result."""
        if objective is Objective.MINIMIZE_WAIT_TIME:
            return result.mean_wait_time
        if objective is Objective.MINIMIZE_MAX_QUEUE:
            return result.max_queue_length
        # MAXIMIZE_THROUGHPUT
        return result.total_completions

    @staticmethod
    def _compute_hash(result: ExperimentResult) -> str:
        """Compute a reproducibility hash from the result."""
        return canonical_hash(result.to_dict())
