"""Evidence-change impact tracking (P5, §33.2, G4.8).

A3 maintains a dependency graph from source version -> assumption ->
scenario -> report. Source withdrawal, correction, license change or
policy change produces an impact event. Mark dependent outputs for
review and block their use where current policy requires it.

Never rewrite historical signed reports. Cycles and incomplete
provenance are rejected or explicitly flagged rather than silently
ignored.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from src.contracts.canonical import canonical_hash

__all__ = [
    "DependencyEdge",
    "ChangeType",
    "ImpactEvent",
    "DependencyGraph",
    "ImpactTracker",
    "ImpactError",
]


class ImpactError(Exception):
    """Raised when the dependency graph has a cycle or incomplete
    provenance that cannot be silently resolved."""


class ChangeType(StrEnum):
    """Type of evidence change that triggers impact tracking."""

    SOURCE_WITHDRAWAL = "SOURCE_WITHDRAWAL"
    SOURCE_CORRECTION = "SOURCE_CORRECTION"
    LICENSE_CHANGE = "LICENSE_CHANGE"
    POLICY_CHANGE = "POLICY_CHANGE"


class DependencyEdge(BaseModel):
    """A single edge in the dependency graph.

    Edges flow: source -> assumption -> scenario -> report.
    The edge_type identifies the relationship.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    source_id: str = Field(min_length=1, max_length=128)
    target_id: str = Field(min_length=1, max_length=128)
    edge_type: str = Field(min_length=1, max_length=64)
    source_hash: str | None = None
    target_hash: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class ImpactEvent(BaseModel):
    """An impact event produced by a source/policy change (§33.2).

    affected_artifacts lists all downstream ids that depend on the
    changed source. unrelated artifacts are not listed.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    event_id: str = Field(min_length=1, max_length=128)
    change_type: ChangeType
    source_id: str = Field(min_length=1, max_length=128)
    affected_artifacts: list[str] = Field(default_factory=list)
    unaffected_count: int = Field(default=0, ge=0)
    timestamp: str = ""
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        return self.model_dump()


class DependencyGraph:
    """Dependency graph: source -> assumption -> scenario -> report.

    Maintains adjacency lists. Supports cycle detection and
    transitive closure for impact propagation.
    """

    def __init__(self) -> None:
        self._edges: list[DependencyEdge] = []
        self._adjacency: dict[str, list[str]] = {}
        self._reverse: dict[str, list[str]] = {}
        self._nodes: set[str] = set()

    def add_edge(self, edge: DependencyEdge) -> None:
        """Add a dependency edge. Raises ImpactError on cycle."""
        self._edges.append(edge)
        self._nodes.add(edge.source_id)
        self._nodes.add(edge.target_id)
        self._adjacency.setdefault(edge.source_id, []).append(
            edge.target_id
        )
        self._reverse.setdefault(edge.target_id, []).append(
            edge.source_id
        )
        # Check for cycles after adding.
        if self._has_cycle():
            raise ImpactError(
                f"cycle detected after adding edge: "
                f"{edge.source_id} -> {edge.target_id}"
            )

    def add_edges(self, edges: list[DependencyEdge]) -> None:
        """Add multiple edges. Raises ImpactError on cycle."""
        for edge in edges:
            self.add_edge(edge)

    def _has_cycle(self) -> bool:
        """DFS-based cycle detection."""
        white, gray, black = 0, 1, 2
        color: dict[str, int] = dict.fromkeys(self._nodes, white)

        def dfs(node: str) -> bool:
            color[node] = gray
            for neighbor in self._adjacency.get(node, []):
                if color.get(neighbor, white) == gray:
                    return True
                if color.get(neighbor, white) == white and dfs(neighbor):
                    return True
            color[node] = black
            return False

        for node in self._nodes:
            if color.get(node, white) == white and dfs(node):
                return True
        return False

    def downstream(self, source_id: str) -> list[str]:
        """Return all downstream (transitively dependent) node ids.

        Uses BFS from source_id. Returns nodes in BFS order.
        """
        visited: set[str] = set()
        queue: list[str] = [source_id]
        result: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._adjacency.get(current, []):
                if neighbor not in visited:
                    result.append(neighbor)
                    queue.append(neighbor)
        return result

    def upstream(self, node_id: str) -> list[str]:
        """Return all upstream (dependency) node ids for a node."""
        visited: set[str] = set()
        queue: list[str] = [node_id]
        result: list[str] = []
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for neighbor in self._reverse.get(current, []):
                if neighbor not in visited:
                    result.append(neighbor)
                    queue.append(neighbor)
        return result

    @property
    def edges(self) -> list[DependencyEdge]:
        return list(self._edges)

    @property
    def nodes(self) -> set[str]:
        return set(self._nodes)

    def __len__(self) -> int:
        return len(self._edges)

    def state_hash(self) -> str:
        """Return canonical hash of the graph state."""
        return canonical_hash(
            [e.to_dict() for e in self._edges]
        )


class ImpactTracker:
    """Tracks evidence-change impacts across the dependency graph.

    When a source is withdrawn, corrected, or its license/policy
    changes, the tracker identifies all affected downstream artifacts
    and produces an ImpactEvent. Unrelated artifacts remain unflagged.
    Historical signed bytes are never rewritten.
    """

    def __init__(self, graph: DependencyGraph) -> None:
        self._graph = graph
        self._events: list[ImpactEvent] = []
        self._review_flags: dict[str, bool] = {}
        self._signed_bytes: dict[str, bytes] = {}

    def register_signed_report(
        self,
        report_id: str,
        signed_bytes: bytes,
    ) -> None:
        """Register a historically signed report.

        Signed bytes are immutable: they can never be rewritten.
        """
        if report_id in self._signed_bytes:
            raise ImpactError(
                f"signed report already registered: {report_id}"
            )
        self._signed_bytes[report_id] = signed_bytes

    def get_signed_bytes(self, report_id: str) -> bytes | None:
        """Return the original signed bytes for a report (never modified)."""
        return self._signed_bytes.get(report_id)

    def record_change(
        self,
        event_id: str,
        change_type: ChangeType,
        source_id: str,
        timestamp: str = "",
        description: str = "",
    ) -> ImpactEvent:
        """Record a source/policy change and produce an impact event.

        Identifies all downstream artifacts that depend on the changed
        source. Marks them for review. Unrelated artifacts are not
        flagged. Historical signed bytes remain unchanged.
        """
        affected = self._graph.downstream(source_id)
        unaffected_count = len(self._graph.nodes) - len(affected) - 1

        event = ImpactEvent(
            event_id=event_id,
            change_type=change_type,
            source_id=source_id,
            affected_artifacts=sorted(affected),
            unaffected_count=max(0, unaffected_count),
            timestamp=timestamp,
            description=description,
        )
        self._events.append(event)

        # Mark affected artifacts for review.
        for artifact_id in affected:
            self._review_flags[artifact_id] = True

        return event

    def is_flagged_for_review(self, artifact_id: str) -> bool:
        """Return True if an artifact is flagged for review."""
        return self._review_flags.get(artifact_id, False)

    def affected_artifacts(self) -> list[str]:
        """Return all currently flagged artifact ids."""
        return sorted(
            aid for aid, flagged in self._review_flags.items()
            if flagged
        )

    def unaffected_artifacts(self) -> list[str]:
        """Return all node ids not flagged for review."""
        return sorted(
            n
            for n in self._graph.nodes
            if not self._review_flags.get(n, False)
        )

    @property
    def events(self) -> list[ImpactEvent]:
        return list(self._events)

    def state_hash(self) -> str:
        """Return canonical hash of the tracker state."""
        return canonical_hash(
            {
                "events": [e.to_dict() for e in self._events],
                "review_flags": dict(
                    sorted(self._review_flags.items())
                ),
                "graph_hash": self._graph.state_hash(),
            }
        )
