"""Twin package — entities, temporal state, simulation, scenarios (P3)."""

from __future__ import annotations

from src.twin.delta import DeltaCompressor, StateDelta
from src.twin.entities import (
    Arrival,
    EntityType,
    OperationalSnapshot,
    Queue,
    Resource,
    ServiceCompletion,
    Site,
)
from src.twin.experiment import (
    ExperimentCandidate,
    ExperimentDesigner,
    ExperimentResult,
    ExperimentSpec,
    Objective,
    ProhibitedSpecError,
)
from src.twin.scenarios import (
    Scenario,
    ScenarioComparison,
    ScenarioLibrary,
)
from src.twin.selection import (
    BaselineComparison,
    CandidateExperiment,
    ExperimentSelector,
    SelectionError,
    SelectionOutcome,
    SelectionResult,
)
from src.twin.simulation import (
    ReplayOracle,
    ScenarioConfig,
    ScenarioResult,
    SimulationEngine,
    UncertaintyReport,
)
from src.twin.temporal import TemporalState, snapshot_hash

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
