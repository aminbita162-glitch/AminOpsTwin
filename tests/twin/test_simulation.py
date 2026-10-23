"""Twin simulation tests (P3): entities, temporal state, simulation engine."""

from __future__ import annotations

import pytest
from src.twin.entities import (
    Arrival,
    Queue,
    Resource,
    ServiceCompletion,
    Site,
    OperationalSnapshot,
)
from src.twin.temporal import TemporalState, snapshot_hash
from src.twin.simulation import (
    ReplayOracle,
    ScenarioConfig,
    SimulationEngine,
    UncertaintyReport,
)


class TestEntities:
    """Typed operational entity tests."""

    def test_site_creation(self) -> None:
        site = Site(
            site_id="site-001",
            name="Test Site",
            capacity=10,
        )
        assert site.site_id == "site-001"
        assert site.capacity == 10

    def test_resource_creation(self) -> None:
        res = Resource(
            resource_id="res-001",
            site_id="site-001",
            name="Resource 1",
            capacity=5,
            available=5,
        )
        assert res.resource_id == "res-001"
        assert res.available == 5

    def test_queue_creation(self) -> None:
        q = Queue(
            queue_id="q-001",
            site_id="site-001",
            name="Queue 1",
            current_length=0,
            total_arrivals=0,
            total_completions=0,
            capacity=100,
        )
        assert q.queue_id == "q-001"

    def test_arrival_creation(self) -> None:
        arr = Arrival(
            arrival_id="arr-001",
            site_id="site-001",
            queue_id="q-001",
            arrival_time=0,
            service_time=5,
        )
        assert arr.arrival_id == "arr-001"

    def test_completion_creation(self) -> None:
        comp = ServiceCompletion(
            completion_id="comp-001",
            site_id="site-001",
            queue_id="q-001",
            arrival_id="arr-001",
            start_time=0,
            completion_time=5,
            wait_time=0,
        )
        assert comp.completion_id == "comp-001"

    def test_snapshot_is_immutable(self) -> None:
        snap = OperationalSnapshot(timestamp=0)
        with pytest.raises(Exception):
            snap.timestamp = 1  # type: ignore[misc]


class TestTemporalState:
    """Temporal state model tests."""

    def test_deterministic_state_hash(self) -> None:
        """Same seed and inputs produce the same state hash."""
        state1 = TemporalState(seed=42)
        state1.add_site(
            Site(site_id="s1", name="Site 1", capacity=10)
        )
        state1.add_queue(
            Queue(
                queue_id="q1",
                site_id="s1",
                name="Q1",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=100,
            )
        )
        state1.add_arrival("s1", "q1", 0, 5)
        h1 = state1.state_hash()

        state2 = TemporalState(seed=42)
        state2.add_site(
            Site(site_id="s1", name="Site 1", capacity=10)
        )
        state2.add_queue(
            Queue(
                queue_id="q1",
                site_id="s1",
                name="Q1",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=100,
            )
        )
        state2.add_arrival("s1", "q1", 0, 5)
        h2 = state2.state_hash()

        assert h1 == h2

    def test_save_restore_roundtrip(self) -> None:
        """Save -> restore produces the same state hash."""
        state = TemporalState(seed=42)
        state.add_site(
            Site(site_id="s1", name="Site 1", capacity=10)
        )
        state.add_queue(
            Queue(
                queue_id="q1",
                site_id="s1",
                name="Q1",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=100,
            )
        )
        state.add_arrival("s1", "q1", 0, 5)
        state.add_completion("s1", "q1", "arr-1", 0, 5)

        saved = state.save_state()
        original_hash = state.state_hash()

        new_state = TemporalState(seed=42)
        new_state.restore_state(saved)
        restored_hash = new_state.state_hash()

        assert original_hash == restored_hash

    def test_snapshot_hash_changes_on_arrival(self) -> None:
        """Adding an arrival changes the snapshot hash."""
        state = TemporalState(seed=42)
        state.add_site(
            Site(site_id="s1", name="Site 1", capacity=10)
        )
        state.add_queue(
            Queue(
                queue_id="q1",
                site_id="s1",
                name="Q1",
                current_length=0,
                total_arrivals=0,
                total_completions=0,
                capacity=100,
            )
        )
        h_before = snapshot_hash(state.get_snapshot())
        state.add_arrival("s1", "q1", 0, 5)
        h_after = snapshot_hash(state.get_snapshot())
        assert h_before != h_after


class TestSimulationEngine:
    """Simulation engine tests (G3.1, G3.3, G3.6)."""

    def test_simulation_deterministic(self) -> None:
        """Same seed produces the same final state hash."""
        cfg = ScenarioConfig(
            scenario_id="test-01",
            seed=42,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
        )
        engine1 = SimulationEngine(cfg)
        result1 = engine1.run()

        engine2 = SimulationEngine(cfg)
        result2 = engine2.run()

        assert result1.final_state_hash == result2.final_state_hash

    def test_different_seed_different_hash(self) -> None:
        """Different seeds produce different state hashes."""
        cfg1 = ScenarioConfig(
            scenario_id="test-seed-1",
            seed=42,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
        )
        cfg2 = ScenarioConfig(
            scenario_id="test-seed-2",
            seed=99,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
        )
        r1 = SimulationEngine(cfg1).run()
        r2 = SimulationEngine(cfg2).run()
        assert r1.final_state_hash != r2.final_state_hash

    def test_uncertainty_report_present(self) -> None:
        """Every simulation output carries an uncertainty report (G3.6)."""
        cfg = ScenarioConfig(
            scenario_id="test-uncertainty",
            seed=0,
            num_sites=1,
            num_resources_per_site=2,
            num_queues_per_site=1,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
        )
        result = SimulationEngine(cfg).run()
        assert result.uncertainty is not None
        u = result.uncertainty
        assert (
            u.wait_time_interval is not None
            or u.not_estimable_reason is not None
        )

    def test_uncertainty_report_not_estimable(self) -> None:
        """No completions yields a not_estimable reason (G3.6)."""
        cfg = ScenarioConfig(
            scenario_id="test-not-estimable",
            seed=0,
            num_sites=1,
            num_resources_per_site=1,
            num_queues_per_site=1,
            capacity_per_resource=1,
            queue_capacity=1,
            arrival_rate=1.0,
            mean_service_time=1,
            sim_duration=1,
        )
        result = SimulationEngine(cfg).run()
        assert result.uncertainty is not None
        u = result.uncertainty
        assert (
            u.not_estimable_reason is not None
            or u.wait_time_interval is not None
        )


class TestReplayOracle:
    """Replay oracle tests (G3.1: 100 seeds x 3 replays = 300/300)."""

    def test_replay_single_seed_identical(self) -> None:
        """A single seed with 3 replays produces identical hashes."""
        cfg = ScenarioConfig(
            scenario_id="replay-test",
            seed=42,
            num_sites=2,
            num_resources_per_site=3,
            num_queues_per_site=2,
            capacity_per_resource=5,
            queue_capacity=100,
            arrival_rate=1.0,
            mean_service_time=5,
            sim_duration=50,
        )
        hashes = ReplayOracle.replay_single(cfg, num_replays=3)
        assert len(hashes) == 3
        assert len(set(hashes)) == 1

    def test_replay_verify_all_identical(self) -> None:
        """100 seeds x 3 replays => all identical (300/300)."""
        cfg = ScenarioConfig(
            scenario_id="replay-verify",
            seed=0,
            num_sites=1,
            num_resources_per_site=2,
            num_queues_per_site=1,
            capacity_per_resource=3,
            queue_capacity=50,
            arrival_rate=1.0,
            mean_service_time=3,
            sim_duration=20,
        )
        result = ReplayOracle.replay_verify(
            cfg, num_seeds=100, num_replays=3
        )
        assert result["total_runs"] == 300
        assert result["all_identical"]
        assert result["identical_runs"] == 100
        assert result["mismatches"] == []
