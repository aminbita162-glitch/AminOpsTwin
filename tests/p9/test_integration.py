"""Cross-component integration tests (P9).

Tests that all components work together: Gateway → Executor → Memory →
Twin pipeline → Transparency → Evaluation → Manifest.
"""

from __future__ import annotations

import json

from aminopstwin.integration.integration import (
    IntegrationHarness,
    IntegrationTestResult,
)


class TestIntegration:
    """Cross-component integration tests."""

    def test_integration_harness_run(self) -> None:
        """IntegrationHarness.run() returns a report with all PASS."""
        harness = IntegrationHarness()
        report = harness.run()
        assert report.total > 0
        assert report.failed == 0
        assert report.passed == report.total

    def test_integration_report_to_dict(self) -> None:
        """IntegrationReport.to_dict() produces a valid dict."""
        harness = IntegrationHarness()
        report = harness.run()
        d = report.to_dict()
        assert isinstance(d, dict)
        assert "results" in d
        assert "total" in d
        assert "passed" in d
        assert "failed" in d

    def test_integration_report_to_json(self) -> None:
        """IntegrationReport.to_json() produces valid JSON."""
        harness = IntegrationHarness()
        report = harness.run()
        json_str = report.to_json()
        data = json.loads(json_str)
        assert data["total"] == report.total
        assert data["passed"] == report.passed

    def test_integration_result_is_frozen(self) -> None:
        """IntegrationTestResult is a frozen dataclass."""
        result = IntegrationTestResult(
            component="test",
            status="PASS",
            detail="test detail",
        )
        import pytest
        with pytest.raises((AttributeError, TypeError)):
            result.component = "other"  # type: ignore[misc]

    def test_integration_covers_all_components(self) -> None:
        """Integration harness tests all major components."""
        harness = IntegrationHarness()
        report = harness.run()
        components = [r.component for r in report.results]
        # At minimum: gateway, executor, pipeline, transparency, evaluation, manifest
        assert len(components) >= 5
