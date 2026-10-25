"""Scenario management for the digital twin (P3, §3.1).

A scenario is a fully-specified simulation configuration that can
be run deterministically and replayed. Scenarios are stored as
fixture files with provenance metadata (§23.1).

The scenario module provides:
    - Scenario definitions (loaded from fixtures)
    - Scenario execution with deterministic replay
    - Cross-scenario comparison (baseline vs delta)

All scenarios use synthetic data only (§23.1, N-11).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from aminopstwin.twin.simulation import (
    ScenarioConfig,
    ScenarioResult,
    SimulationEngine,
)

__all__ = [
    "Scenario",
    "ScenarioLibrary",
    "ScenarioComparison",
]


@dataclass(frozen=True)
class Scenario:
    """A fully-specified simulation scenario with provenance."""

    scenario_id: str
    seed: int
    num_sites: int
    num_resources_per_site: int
    num_queues_per_site: int
    capacity_per_resource: int
    queue_capacity: int
    arrival_rate: float
    mean_service_time: int
    sim_duration: int
    description: str
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_config(self) -> ScenarioConfig:
        return ScenarioConfig(
            scenario_id=self.scenario_id,
            seed=self.seed,
            num_sites=self.num_sites,
            num_resources_per_site=self.num_resources_per_site,
            num_queues_per_site=self.num_queues_per_site,
            capacity_per_resource=self.capacity_per_resource,
            queue_capacity=self.queue_capacity,
            arrival_rate=self.arrival_rate,
            mean_service_time=self.mean_service_time,
            sim_duration=self.sim_duration,
            description=self.description,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "num_sites": self.num_sites,
            "num_resources_per_site": self.num_resources_per_site,
            "num_queues_per_site": self.num_queues_per_site,
            "capacity_per_resource": self.capacity_per_resource,
            "queue_capacity": self.queue_capacity,
            "arrival_rate": self.arrival_rate,
            "mean_service_time": self.mean_service_time,
            "sim_duration": self.sim_duration,
            "description": self.description,
            "provenance": dict(self.provenance),
        }


@dataclass
class ScenarioComparison:
    """Result of comparing two scenarios (what-if delta)."""

    baseline_id: str
    alternative_id: str
    baseline_hash: str
    alternative_hash: str
    queue_length_delta: dict[str, int]
    total_arrivals_delta: int
    total_completions_delta: int
    mean_wait_time_delta: int
    max_queue_length_delta: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline_id": self.baseline_id,
            "alternative_id": self.alternative_id,
            "baseline_hash": self.baseline_hash,
            "alternative_hash": self.alternative_hash,
            "queue_length_delta": dict(self.queue_length_delta),
            "total_arrivals_delta": self.total_arrivals_delta,
            "total_completions_delta": self.total_completions_delta,
            "mean_wait_time_delta": self.mean_wait_time_delta,
            "max_queue_length_delta": self.max_queue_length_delta,
        }


class ScenarioLibrary:
    """Library of predefined and custom scenarios (P3).

    Scenarios are loaded from the fixtures directory (§23.1) or
    created programmatically. All scenarios use synthetic data.
    """

    def __init__(self) -> None:
        self._scenarios: dict[str, Scenario] = {}

    def add(self, scenario: Scenario) -> None:
        self._scenarios[scenario.scenario_id] = scenario

    def get(self, scenario_id: str) -> Scenario | None:
        return self._scenarios.get(scenario_id)

    def run(self, scenario_id: str) -> ScenarioResult:
        """Run a scenario by id and return the result."""
        sc = self._scenarios.get(scenario_id)
        if sc is None:
            raise KeyError(f"scenario not found: {scenario_id}")
        engine = SimulationEngine(sc.to_config())
        return engine.run()

    def run_all(self) -> dict[str, ScenarioResult]:
        """Run all scenarios and return a dict of results."""
        results: dict[str, ScenarioResult] = {}
        for sid in self._scenarios:
            results[sid] = self.run(sid)
        return results

    def compare(
        self,
        baseline_id: str,
        alternative_id: str,
    ) -> ScenarioComparison:
        """Compare two scenarios and return the delta (what-if).

        Both scenarios must have the same seed for a fair comparison.
        """
        base = self.run(baseline_id)
        alt = self.run(alternative_id)

        queue_delta: dict[str, int] = {}
        all_qids = set(base.final_queue_lengths) | set(
            alt.final_queue_lengths
        )
        for qid in all_qids:
            bl = base.final_queue_lengths.get(qid, 0)
            al = alt.final_queue_lengths.get(qid, 0)
            queue_delta[qid] = al - bl

        return ScenarioComparison(
            baseline_id=baseline_id,
            alternative_id=alternative_id,
            baseline_hash=base.final_state_hash,
            alternative_hash=alt.final_state_hash,
            queue_length_delta=queue_delta,
            total_arrivals_delta=(
                alt.total_arrivals - base.total_arrivals
            ),
            total_completions_delta=(
                alt.total_completions - base.total_completions
            ),
            mean_wait_time_delta=(
                alt.mean_wait_time - base.mean_wait_time
            ),
            max_queue_length_delta=(
                alt.max_queue_length - base.max_queue_length
            ),
        )

    @property
    def scenario_ids(self) -> list[str]:
        return sorted(self._scenarios.keys())

    def __len__(self) -> int:
        return len(self._scenarios)


def load_default_scenarios() -> ScenarioLibrary:
    """Load the default synthetic scenario library (P3 fixtures)."""
    lib = ScenarioLibrary()
    provenance: dict[str, Any] = {
        "synthetic": True,
        "generator_id": "aminopstwin-fixtures-gen-v1",
        "generator_version": "0.1.0",
        "seed": 0,
    }
    lib.add(
        Scenario(
            scenario_id="scen-baseline-01",
            seed=0,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
            description="Baseline: 2 sites, 3 resources each, "
            "arrival_rate=1.0, mean_service=5",
            provenance=provenance,
        )
    )
    lib.add(
        Scenario(
            scenario_id="scen-high-arrival-01",
            seed=0,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=3.0,
            mean_service_time=5,
            sim_duration=50,
            description="High arrival: same baseline but "
            "arrival_rate=3.0",
            provenance=provenance,
        )
    )
    lib.add(
        Scenario(
            scenario_id="scen-add-resource-01",
            seed=0,
            num_sites=2,
            num_resources_per_site=5,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
            description="Add resources: same baseline but "
            "5 resources per site",
            provenance=provenance,
        )
    )
    lib.add(
        Scenario(
            scenario_id="scen-long-service-01",
            seed=0,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=10,
            sim_duration=50,
            description="Long service: same baseline but "
            "mean_service_time=10",
            provenance=provenance,
        )
    )
    return lib
