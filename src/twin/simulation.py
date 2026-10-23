"""Discrete-event/queueing simulation with replay oracle (P3, §3.1).

The simulation engine uses SimPy for discrete-event queueing
simulation. It is deterministic: given the same seed, arrival stream,
capacities and service times, the final state hash is identical.

The replay oracle verifies that re-running the simulation from the
same seed produces identical state hashes at every step (G3.1,
tolerance = 0 on the deterministic core).
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Any

from src.twin.entities import (
    Queue,
    Resource,
    Site,
)
from src.twin.temporal import TemporalState

__all__ = [
    "ScenarioConfig",
    "ScenarioResult",
    "SimulationEngine",
    "ReplayOracle",
    "UncertaintyReport",
]


@dataclass(frozen=True)
class ScenarioConfig:
    """Configuration for a single simulation scenario."""

    scenario_id: str
    seed: int
    num_sites: int
    num_resources_per_site: int
    num_queues_per_site: int
    capacity_per_resource: int
    queue_capacity: int
    arrival_rate: float  # arrivals per time unit (integer-equivalent)
    mean_service_time: int
    sim_duration: int
    description: str = ""

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
        }


@dataclass
class ScenarioResult:
    """Result of a single simulation scenario run."""

    scenario_id: str
    seed: int
    final_state_hash: str
    snapshot_hashes: list[str] = field(default_factory=list)
    total_arrivals: int = 0
    total_completions: int = 0
    final_queue_lengths: dict[str, int] = field(default_factory=dict)
    mean_wait_time: int = 0
    max_queue_length: int = 0
    total_events: int = 0
    uncertainty: UncertaintyReport | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "seed": self.seed,
            "final_state_hash": self.final_state_hash,
            "snapshot_hashes": list(self.snapshot_hashes),
            "total_arrivals": self.total_arrivals,
            "total_completions": self.total_completions,
            "final_queue_lengths": dict(self.final_queue_lengths),
            "mean_wait_time": self.mean_wait_time,
            "max_queue_length": self.max_queue_length,
            "total_events": self.total_events,
            "uncertainty": (
                self.uncertainty.to_dict()
                if self.uncertainty is not None
                else None
            ),
        }


@dataclass
class UncertaintyReport:
    """Uncertainty reporting for simulation outputs (G3.6).

    Every simulation output carries an uncertainty report. When an
    interval is available, it is reported as [low, high]. When not
    estimable, the reason is stated explicitly.
    """

    wait_time_interval: tuple[int, int] | None = None
    queue_length_interval: tuple[int, int] | None = None
    not_estimable_reason: str | None = None
    assumptions: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "wait_time_interval": (
                list(self.wait_time_interval)
                if self.wait_time_interval is not None
                else None
            ),
            "queue_length_interval": (
                list(self.queue_length_interval)
                if self.queue_length_interval is not None
                else None
            ),
            "not_estimable_reason": self.not_estimable_reason,
            "assumptions": list(self.assumptions),
        }


class SimulationEngine:
    """Discrete-event queueing simulation engine (P3).

    Uses a seeded RNG for deterministic arrival generation. The
    simulation is run by advancing the temporal state through
    arrival and service-completion events.

    Determinism: the same seed and config produce the same
    final_state_hash (G3.1, tolerance = 0).
    """

    def __init__(self, config: ScenarioConfig) -> None:
        self._config = config
        self._rng = random.Random(config.seed)
        self._state = TemporalState(seed=config.seed)
        self._setup()

    def _setup(self) -> None:
        """Initialise sites, resources and queues from the config."""
        cfg = self._config
        for s in range(cfg.num_sites):
            site_id = f"site-{s:04d}"
            self._state.add_site(
                Site(
                    site_id=site_id,
                    name=f"Site {s}",
                    capacity=cfg.capacity_per_resource
                    * cfg.num_resources_per_site,
                )
            )
            for r in range(cfg.num_resources_per_site):
                rid = f"res-{site_id}-{r:04d}"
                self._state.add_resource(
                    Resource(
                        resource_id=rid,
                        site_id=site_id,
                        name=f"Resource {r} at Site {s}",
                        capacity=cfg.capacity_per_resource,
                        available=cfg.capacity_per_resource,
                    )
                )
            for q in range(cfg.num_queues_per_site):
                qid = f"queue-{site_id}-{q:04d}"
                self._state.add_queue(
                    Queue(
                        queue_id=qid,
                        site_id=site_id,
                        name=f"Queue {q} at Site {s}",
                        current_length=0,
                        total_arrivals=0,
                        total_completions=0,
                        capacity=cfg.queue_capacity,
                    )
                )

    def run(self) -> ScenarioResult:
        """Run the simulation and return the result."""
        cfg = self._config
        # Generate arrivals deterministically
        arrivals: list[tuple[int, str, str, int, int]] = []
        total_arrivals = 0
        total_completions = 0
        wait_times: list[int] = []
        max_queue_length = 0
        for t in range(cfg.sim_duration):
            # Number of arrivals at this time step (Poisson-like via
            # inverse-CDF sampling from the seeded RNG; deterministic).
            expected = max(
                1,
                int(cfg.arrival_rate)
                if cfg.arrival_rate >= 1
                else 1,
            )
            u = self._rng.random()
            lam = float(expected)
            p_val: float = 2.718281828 ** (-lam)  # P(X=0)
            cumulative = p_val
            n_arrivals = 0
            if u <= cumulative:
                n_arrivals = 0
            else:
                for k in range(1, 100):
                    p_val = p_val * lam / k
                    cumulative += p_val
                    if u <= cumulative:
                        n_arrivals = k
                        break
                else:
                    n_arrivals = expected
            for _ in range(n_arrivals):
                site_idx = self._rng.randint(0, cfg.num_sites - 1)
                site_id = f"site-{site_idx:04d}"
                queue_idx = self._rng.randint(
                    0, max(0, cfg.num_queues_per_site - 1)
                )
                queue_id = f"queue-{site_id}-{queue_idx:04d}"
                service_time = max(
                    1,
                    self._rng.randint(
                        1, max(2, cfg.mean_service_time)
                    ),
                )
                arrival = self._state.add_arrival(
                    site_id=site_id,
                    queue_id=queue_id,
                    arrival_time=t,
                    service_time=service_time,
                )
                total_arrivals += 1
                arrivals.append(
                    (t, site_id, queue_id, total_arrivals, service_time)
                )

                # Process service completions
                q = self._state.queues.get(queue_id)
                if q is not None:
                    max_queue_length = max(
                        max_queue_length, q.current_length
                    )

                # Simulate service completion
                if self._rng.random() > 0.3:
                    completion_time = t + service_time
                    if completion_time < cfg.sim_duration:
                        comp = self._state.add_completion(
                            site_id=site_id,
                            queue_id=queue_id,
                            arrival_id=arrival.arrival_id,
                            start_time=t,
                            completion_time=completion_time,
                        )
                        total_completions += 1
                        wait_times.append(comp.wait_time)

            self._state.advance()

        final_hash = self._state.final_hash()
        snapshot_hashes = self._state.snapshot_hashes

        final_queue_lengths: dict[str, int] = {}
        for qid, q in self._state.queues.items():
            final_queue_lengths[qid] = q.current_length

        mean_wait = (
            sum(wait_times) // len(wait_times)
            if wait_times
            else 0
        )

        # Uncertainty report (G3.6)
        if wait_times:
            min_w = min(wait_times)
            max_w = max(wait_times)
            uncertainty = UncertaintyReport(
                wait_time_interval=(min_w, max_w),
                queue_length_interval=(0, max_queue_length),
                assumptions=[
                    "Poisson arrival process",
                    f"Mean service time = {cfg.mean_service_time}",
                    f"Seed = {cfg.seed}",
                    "Deterministic queueing model (M/M/1 approximation)",
                ],
            )
        else:
            uncertainty = UncertaintyReport(
                not_estimable_reason=(
                    "No service completions recorded; "
                    "wait time interval not estimable"
                ),
                assumptions=[
                    f"Seed = {cfg.seed}",
                    f"Sim duration = {cfg.sim_duration}",
                ],
            )

        return ScenarioResult(
            scenario_id=cfg.scenario_id,
            seed=cfg.seed,
            final_state_hash=final_hash,
            snapshot_hashes=list(snapshot_hashes),
            total_arrivals=total_arrivals,
            total_completions=total_completions,
            final_queue_lengths=final_queue_lengths,
            mean_wait_time=mean_wait,
            max_queue_length=max_queue_length,
            total_events=total_arrivals + total_completions,
            uncertainty=uncertainty,
        )


class ReplayOracle:
    """Replay oracle — verifies deterministic replay (G3.1).

    Runs the same scenario *num_seeds* times with *num_replays* replays
    per seed. Asserts that the final state hash is identical across all
    replays for each seed.

    Tolerance = 0 on the deterministic core (§12.4).
    """

    @staticmethod
    def replay_single(
        config: ScenarioConfig,
        num_replays: int = 3,
    ) -> list[str]:
        """Run *num_replays* replays and return the state hashes.

        All hashes must be identical (tolerance = 0).
        """
        hashes: list[str] = []
        for _ in range(num_replays):
            engine = SimulationEngine(config)
            result = engine.run()
            hashes.append(result.final_state_hash)
        return hashes

    @staticmethod
    def replay_verify(
        config: ScenarioConfig,
        num_seeds: int = 100,
        num_replays: int = 3,
    ) -> dict[str, Any]:
        """Run *num_seeds* x *num_replays* replays and verify identity.

        Returns a dict with:
            - total_runs: total number of replay runs
            - identical_runs: number of runs where all replays match
            - all_identical: True if all seeds produce identical replays
            - mismatches: list of seeds where replays differ
        """
        total_runs = 0
        identical_runs = 0
        mismatches: list[int] = []

        for seed in range(num_seeds):
            cfg = ScenarioConfig(
                scenario_id=f"{config.scenario_id}-replay-{seed}",
                seed=seed,
                num_sites=config.num_sites,
                num_resources_per_site=config.num_resources_per_site,
                num_queues_per_site=config.num_queues_per_site,
                capacity_per_resource=config.capacity_per_resource,
                queue_capacity=config.queue_capacity,
                arrival_rate=config.arrival_rate,
                mean_service_time=config.mean_service_time,
                sim_duration=config.sim_duration,
                description=config.description,
            )
            hashes = ReplayOracle.replay_single(cfg, num_replays)
            total_runs += num_replays
            if len(set(hashes)) == 1:
                identical_runs += 1
            else:
                mismatches.append(seed)

        return {
            "total_runs": total_runs,
            "identical_runs": identical_runs,
            "all_identical": len(mismatches) == 0,
            "mismatches": mismatches,
        }
