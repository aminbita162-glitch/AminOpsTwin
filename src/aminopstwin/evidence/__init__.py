"""Evidence package — source rights, ingestion, registry with cache binding (P4).

Source rights and provenance (§30, G4.2): SourceRegistry with lifecycle.
Ingestion security (§30.4, G4.3): SourceIngestor with injection guards.
Evidence registry (§3.10, G2.4): EvidenceRegistry with cache binding.
"""

from aminopstwin.evidence.impact import (
    ChangeType,
    DependencyEdge,
    DependencyGraph,
    ImpactError,
    ImpactEvent,
    ImpactTracker,
)
from aminopstwin.evidence.ingestion import (
    IngestionOutcome,
    IngestionResult,
    SourceIngestor,
)
from aminopstwin.evidence.registry import (
    EvidenceEntry,
    EvidenceKey,
    EvidenceRegistry,
)
from aminopstwin.evidence.source_rights import (
    SourceRecord,
    SourceRegistry,
    SourceRegistryError,
    SourceStatus,
)

__all__ = [
    # source rights
    "SourceStatus",
    "SourceRecord",
    "SourceRegistry",
    "SourceRegistryError",
    # ingestion
    "SourceIngestor",
    "IngestionResult",
    "IngestionOutcome",
    # evidence registry
    "EvidenceKey",
    "EvidenceEntry",
    "EvidenceRegistry",
    # impact tracking (P5)
    "ChangeType",
    "DependencyEdge",
    "DependencyGraph",
    "ImpactEvent",
    "ImpactTracker",
    "ImpactError",
]
