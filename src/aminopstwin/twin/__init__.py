"""Twin package — entities, temporal state, simulation, scenarios (P3)."""

from __future__ import annotations

from aminopstwin.twin.delta import DeltaCompressor, StateDelta
from aminopstwin.twin.entities import (
    Arrival,
    EntityType,
    OperationalSnapshot,
    Queue,
    Resource,
    ServiceCompletion,
    Site,
)
from aminopstwin.twin.experiment import (
    ExperimentCandidate,
    ExperimentDesigner,
    ExperimentResult,
    ExperimentSpec,
    Objective,
    ProhibitedSpecError,
)
from aminopstwin.twin.scenarios import (
    Scenario,
    ScenarioComparison,
    ScenarioLibrary,
)
from aminopstwin.twin.selection import (
    BaselineComparison,
    CandidateExperiment,
    ExperimentSelector,
    SelectionError,
    SelectionOutcome,
    SelectionResult,
)
from aminopstwin.twin.simulation import (
    ReplayOracle,
    ScenarioConfig,
    ScenarioResult,
    SimulationEngine,
    UncertaintyReport,
)
from aminopstwin.twin.temporal import TemporalState, snapshot_hash

__all__ = [
    # entities
    "EntityType",
    "Site",
    "Resource",
    "Queue",
    "Arrival",
    "ServiceCompletion",
    "OperationalSnapshot",
    # temporal
    "TemporalState",
    "snapshot_hash",
    # simulation
    "ScenarioConfig",
    "ScenarioResult",
    "SimulationEngine",
    "ReplayOracle",
    "UncertaintyReport",
    # delta
    "DeltaCompressor",
    "StateDelta",
    # scenarios
    "Scenario",
    "ScenarioComparison",
    "ScenarioLibrary",
    # experiment designer (P5)
    "Objective",
    "ExperimentSpec",
    "ExperimentCandidate",
    "ExperimentResult",
    "ProhibitedSpecError",
    "ExperimentDesigner",
    # selection (P5)
    "SelectionOutcome",
    "CandidateExperiment",
    "SelectionResult",
    "BaselineComparison",
    "ExperimentSelector",
    "SelectionError",
]
