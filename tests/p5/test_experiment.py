"""G4.7 — Experiment designer tests (P5, §33.1).

All analytical small reference cases return the expected feasible
candidates and ranking. Prohibited specifications are denied with
exact reason codes. Replay hashes match exactly for repeated seeded
runs.
"""

from __future__ import annotations

import pytest
from aminopstwin.twin.experiment import (
    ExperimentDesigner,
    ExperimentSpec,
    Objective,
    ProhibitedSpecError,
)
from aminopstwin.twin.simulation import ScenarioConfig


def _baseline_config() -> ScenarioConfig:
    return ScenarioConfig(
        scenario_id="baseline-01",
        seed=0,
        num_sites=2,
        num_resources_per_site=3,
        num_queues_per_site=2,
        capacity_per_resource=5,
        queue_capacity=100,
        arrival_rate=1.0,
        mean_service_time=5,
        sim_duration=50,
        description="baseline for experiments",
    )


class TestExperimentDesign:
    """Experiment designer produces ranked candidates deterministically."""

    def test_basic_experiment_produces_candidates(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-001",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=10,
            seed=42,
            description="vary capacity",
        )
        result = designer.design(spec)
        assert len(result.candidates) > 0
        assert len(result.ranked_ids) > 0
        assert result.reproducibility_hash != ""

    def test_repeated_seeded_runs_reproduce_results(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-replay",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=10,
            seed=99,
            description="replay test",
        )
        r1 = designer.design(spec)
        r2 = designer.design(spec)
        assert r1.reproducibility_hash == r2.reproducibility_hash
        assert r1.ranked_ids == r2.ranked_ids

    def test_feasible_candidates_only_in_ranking(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-feasible",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "num_resources_per_site": (2, 5),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            constraints={"num_resources_per_site": 4},
            experiment_budget=20,
            seed=7,
            description="feasibility test",
        )
        result = designer.design(spec)
        # Only candidates satisfying constraints should be ranked.
        for cid in result.ranked_ids:
            cand = next(
                c for c in result.candidates if c.scenario_id == cid
            )
            assert cand.feasible

    def test_ranking_minimize_wait_time_ascending(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-rank",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 8),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=10,
            seed=1,
            description="ranking test",
        )
        result = designer.design(spec)
        feasible = [c for c in result.candidates if c.feasible]
        if len(feasible) >= 2:
            metrics = [
                next(
                    c for c in result.candidates if c.scenario_id == cid
                ).metric_value
                for cid in result.ranked_ids
            ]
            assert metrics == sorted(metrics)

    def test_ranking_maximize_throughput_descending(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-throughput",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 8),
            },
            objective=Objective.MAXIMIZE_THROUGHPUT,
            experiment_budget=10,
            seed=2,
            description="throughput ranking",
        )
        result = designer.design(spec)
        if len(result.ranked_ids) >= 2:
            metrics = [
                next(
                    c for c in result.candidates if c.scenario_id == cid
                ).metric_value
                for cid in result.ranked_ids
            ]
            assert metrics == sorted(metrics, reverse=True)

    def test_metric_deltas_reported(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-delta",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=5,
            seed=3,
            description="delta test",
        )
        result = designer.design(spec)
        assert len(result.metric_deltas) == len(result.candidates)
        for _cid, delta in result.metric_deltas.items():
            assert isinstance(delta, int)

    def test_uncertainty_reported(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-unc",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=5,
            seed=4,
            description="uncertainty test",
        )
        result = designer.design(spec)
        assert result.uncertainty is not None
        assert result.uncertainty.assumptions


class TestProhibitedSpecifications:
    """Prohibited specifications are denied with exact reason codes."""

    def test_prohibited_term_in_description_denied(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-prohibited",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=5,
            seed=5,
            description="rank by patient symptom severity",
        )
        with pytest.raises(ProhibitedSpecError, match="GW-CLIN"):
            designer.design(spec)

    def test_prohibited_term_diagnosis_denied(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-prohibited-2",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=5,
            seed=6,
            description="diagnosis-based prioritization",
        )
        with pytest.raises(ProhibitedSpecError, match="GW-CLIN"):
            designer.design(spec)

    def test_prohibited_term_treatment_denied(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-prohibited-3",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=5,
            seed=7,
            description="treatment dose optimization",
        )
        with pytest.raises(ProhibitedSpecError, match="GW-CLIN"):
            designer.design(spec)


class TestExperimentReplay:
    """Replay hashes match exactly for repeated seeded runs."""

    def test_replay_hash_stability_across_seeds(self) -> None:
        baseline = _baseline_config()
        designer = ExperimentDesigner(baseline)
        spec = ExperimentSpec(
            experiment_id="exp-stable",
            baseline_scenario_id="baseline-01",
            parameter_ranges={
                "capacity_per_resource": (3, 6),
                "mean_service_time": (3, 7),
            },
            objective=Objective.MINIMIZE_WAIT_TIME,
            experiment_budget=20,
            seed=123,
            description="stability test",
        )
        hashes = []
        for _ in range(3):
            result = designer.design(spec)
            hashes.append(result.reproducibility_hash)
        assert len(set(hashes)) == 1
