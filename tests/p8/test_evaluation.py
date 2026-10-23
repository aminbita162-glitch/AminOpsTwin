"""G5.4 — Evaluation harness for all implemented capabilities (P8).

G5.4: Run every implemented capability and record pass/fail with
measured values.  The harness covers schema validation, policy gateway,
budget governor, simulation, token pipeline, memory store, and tenant
isolation.
"""

from __future__ import annotations

from src.enterprise.evaluation import EvaluationHarness, EvaluationReport


class TestEvaluationHarness:
    """G5.4: Evaluation harness covers all implemented capabilities."""

    def test_harness_runs_all_capabilities(self) -> None:
        """The harness runs and produces a report with results."""
        harness = EvaluationHarness()
        report = harness.run()
        assert isinstance(report, EvaluationReport)
        assert report.total > 0
        assert len(report.results) == report.total

    def test_all_capabilities_pass(self) -> None:
        """Every implemented capability passes evaluation."""
        harness = EvaluationHarness()
        report = harness.run()
        failed = [r for r in report.results if r.status != "PASS"]
        assert not failed, (
            f"Failed capabilities: {[(r.capability_id, r.detail) for r in failed]}"
        )
        assert report.failed == 0
        assert report.passed == report.total

    def test_report_has_measured_values(self) -> None:
        """Each result has a non-None measured_value."""
        harness = EvaluationHarness()
        report = harness.run()
        for r in report.results:
            assert r.measured_value is not None, (
                f"{r.capability_id}: measured_value is None"
            )

    def test_report_serialization(self) -> None:
        """Report serializes to JSON with required fields."""
        import json

        harness = EvaluationHarness()
        report = harness.run()
        json_str = report.to_json()
        data = json.loads(json_str)
        assert "results" in data
        assert "total" in data
        assert "passed" in data
        assert data["total"] == report.total
        assert data["passed"] == report.passed

    def test_capability_ids_covered(self) -> None:
        """All expected capability IDs are covered."""
        harness = EvaluationHarness()
        report = harness.run()
        ids = {r.capability_id for r in report.results}
        expected = {"R03", "R04", "R15", "R12", "R16", "R19", "N20"}
        assert expected.issubset(ids), (
            f"Missing capabilities: {expected - ids}"
        )

    def test_durations_recorded(self) -> None:
        """Each result has a non-negative duration."""
        harness = EvaluationHarness()
        report = harness.run()
        for r in report.results:
            assert r.duration_ms >= 0.0, (
                f"{r.capability_id}: negative duration {r.duration_ms}"
            )
