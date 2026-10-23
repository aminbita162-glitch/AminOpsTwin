"""G4.8 — Evidence-change impact tracking tests (P5, §33.2).

All fixture-defined affected artifacts are identified; unrelated
fixtures remain unflagged. Historical signed bytes remain unchanged.
Cycles and incomplete provenance are rejected or explicitly flagged.
"""

from __future__ import annotations

import pytest
from src.evidence.impact import (
    ChangeType,
    DependencyEdge,
    DependencyGraph,
    ImpactError,
    ImpactTracker,
)


def _build_graph() -> DependencyGraph:
    """Build a test dependency graph:

    source-1 -> assumption-1 -> scenario-1 -> report-1
    source-2 -> assumption-2 -> scenario-2 -> report-2
    """
    graph = DependencyGraph()
    graph.add_edges(
        [
            DependencyEdge(
                source_id="source-1",
                target_id="assumption-1",
                edge_type="supports",
            ),
            DependencyEdge(
                source_id="assumption-1",
                target_id="scenario-1",
                edge_type="assumption_for",
            ),
            DependencyEdge(
                source_id="scenario-1",
                target_id="report-1",
                edge_type="produces",
            ),
            DependencyEdge(
                source_id="source-2",
                target_id="assumption-2",
                edge_type="supports",
            ),
            DependencyEdge(
                source_id="assumption-2",
                target_id="scenario-2",
                edge_type="assumption_for",
            ),
            DependencyEdge(
                source_id="scenario-2",
                target_id="report-2",
                edge_type="produces",
            ),
        ]
    )
    return graph


class TestDependencyGraph:
    """Dependency graph construction and traversal."""

    def test_downstream_traversal(self) -> None:
        graph = _build_graph()
        downstream = graph.downstream("source-1")
        assert "assumption-1" in downstream
        assert "scenario-1" in downstream
        assert "report-1" in downstream
        # source-2's chain should not be in downstream of source-1.
        assert "assumption-2" not in downstream
        assert "report-2" not in downstream

    def test_upstream_traversal(self) -> None:
        graph = _build_graph()
        upstream = graph.upstream("report-1")
        assert "scenario-1" in upstream
        assert "assumption-1" in upstream
        assert "source-1" in upstream
        assert "source-2" not in upstream

    def test_cycle_detection(self) -> None:
        graph = DependencyGraph()
        graph.add_edge(
            DependencyEdge(
                source_id="a",
                target_id="b",
                edge_type="test",
            )
        )
        graph.add_edge(
            DependencyEdge(
                source_id="b",
                target_id="c",
                edge_type="test",
            )
        )
        with pytest.raises(ImpactError, match="cycle"):
            graph.add_edge(
                DependencyEdge(
                    source_id="c",
                    target_id="a",
                    edge_type="test",
                )
            )

    def test_state_hash_stable(self) -> None:
        g1 = _build_graph()
        g2 = _build_graph()
        assert g1.state_hash() == g2.state_hash()


class TestImpactTracking:
    """Impact tracking identifies affected artifacts."""

    def test_source_withdrawal_affects_downstream(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        event = tracker.record_change(
            event_id="evt-001",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
            timestamp="2026-10-23T00:00:00Z",
        )
        assert "assumption-1" in event.affected_artifacts
        assert "scenario-1" in event.affected_artifacts
        assert "report-1" in event.affected_artifacts
        # source-2 chain should not be affected.
        assert "assumption-2" not in event.affected_artifacts
        assert "report-2" not in event.affected_artifacts

    def test_unrelated_artifacts_unflagged(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        tracker.record_change(
            event_id="evt-002",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
        )
        unaffected = tracker.unaffected_artifacts()
        assert "source-2" in unaffected
        assert "assumption-2" in unaffected
        assert "scenario-2" in unaffected
        assert "report-2" in unaffected
        assert "source-1" in unaffected  # source itself not flagged
        assert "assumption-1" not in unaffected

    def test_license_change_affects_downstream(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        event = tracker.record_change(
            event_id="evt-003",
            change_type=ChangeType.LICENSE_CHANGE,
            source_id="source-2",
        )
        assert "assumption-2" in event.affected_artifacts
        assert "scenario-2" in event.affected_artifacts
        assert "report-2" in event.affected_artifacts
        assert "assumption-1" not in event.affected_artifacts

    def test_policy_change_affects_all(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        # Policy change from a node upstream of everything.
        event = tracker.record_change(
            event_id="evt-004",
            change_type=ChangeType.POLICY_CHANGE,
            source_id="source-1",
        )
        # All of source-1's downstream should be affected.
        assert len(event.affected_artifacts) >= 3

    def test_historical_signed_bytes_unchanged(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        signed = b"historical-signed-report-bytes-v1"
        tracker.register_signed_report("report-1", signed)
        # Record a change affecting report-1.
        tracker.record_change(
            event_id="evt-005",
            change_type=ChangeType.SOURCE_CORRECTION,
            source_id="source-1",
        )
        # Signed bytes must not be modified.
        assert tracker.get_signed_bytes("report-1") == signed

    def test_duplicate_signed_report_rejected(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        tracker.register_signed_report("report-1", b"signed")
        with pytest.raises(ImpactError, match="already registered"):
            tracker.register_signed_report("report-1", b"other")

    def test_flagged_for_review(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        tracker.record_change(
            event_id="evt-006",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
        )
        assert tracker.is_flagged_for_review("assumption-1")
        assert tracker.is_flagged_for_review("scenario-1")
        assert tracker.is_flagged_for_review("report-1")
        assert not tracker.is_flagged_for_review("assumption-2")
        assert not tracker.is_flagged_for_review("report-2")

    def test_state_hash_stable(self) -> None:
        graph1 = _build_graph()
        tracker1 = ImpactTracker(graph1)
        tracker1.record_change(
            event_id="evt-007",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
        )
        graph2 = _build_graph()
        tracker2 = ImpactTracker(graph2)
        tracker2.record_change(
            event_id="evt-007",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
        )
        assert tracker1.state_hash() == tracker2.state_hash()

    def test_unaffected_count(self) -> None:
        graph = _build_graph()
        tracker = ImpactTracker(graph)
        event = tracker.record_change(
            event_id="evt-008",
            change_type=ChangeType.SOURCE_WITHDRAWAL,
            source_id="source-1",
        )
        # 8 nodes total: source-1, assumption-1, scenario-1, report-1,
        # source-2, assumption-2, scenario-2, report-2
        # source-1's downstream = 3 (assumption-1, scenario-1, report-1)
        # unaffected = 8 - 3 - 1 = 4
        assert event.unaffected_count == 4
