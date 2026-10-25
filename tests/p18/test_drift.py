"""Tests for drift detection (P18, G18.5, Deliverable 6)."""

from __future__ import annotations

import pytest
from aminopstwin.assurance.drift import (
    DriftAlert,
    DriftDetector,
    DriftMetric,
)


class TestDriftMetricAndAlert:
    """Frozen dataclass behaviour for DriftMetric / DriftAlert."""

    def test_drift_metric_is_frozen(self) -> None:
        import dataclasses

        m = DriftMetric(name="x", current_value=1, threshold=0, exceeded=False)
        with pytest.raises(
            dataclasses.FrozenInstanceError
        ):
            m.exceeded = True  # type: ignore[misc]

    def test_drift_alert_is_frozen(self) -> None:
        import dataclasses

        a = DriftAlert(
            alert_id="a",
            timestamp=1,
            metric_name="x",
            current_value=1,
            threshold=0,
            severity="WARNING",
            message="m",
        )
        with pytest.raises(
            dataclasses.FrozenInstanceError
        ):
            a.severity = "CRITICAL"  # type: ignore[misc]


class TestCounts:
    """DriftDetector counts total_requests/denials/allows."""

    def test_initial_counts_zero(self) -> None:
        d = DriftDetector()
        assert d.total_requests == 0
        assert d.total_denials == 0
        assert d.total_allows == 0

    def test_counts_after_records(self) -> None:
        d = DriftDetector()
        d.record_allow(timestamp=1)
        d.record_allow(timestamp=2)
        d.record_denial(timestamp=3, reason_code="GW-DEFAULT-001")
        d.record_denial(timestamp=4, reason_code="GW-SCHEMA-001")
        assert d.total_allows == 2
        assert d.total_denials == 2
        assert d.total_requests == 4

    def test_total_requests_equals_denials_plus_allows(self) -> None:
        d = DriftDetector()
        for i in range(3):
            d.record_allow(timestamp=i)
        for i in range(5):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        assert d.total_requests == d.total_denials + d.total_allows
        assert d.total_requests == 8


class TestDenialRate:
    """compute_denial_rate returns the correct ratio."""

    def test_no_requests_returns_zero(self) -> None:
        d = DriftDetector()
        assert d.compute_denial_rate() == 0.0

    def test_half_denial_rate(self) -> None:
        d = DriftDetector()
        d.record_allow(timestamp=1)
        d.record_allow(timestamp=2)
        d.record_denial(timestamp=3, reason_code="GW-CLIN-001")
        d.record_denial(timestamp=4, reason_code="GW-CLIN-002")
        assert d.compute_denial_rate() == 0.5

    def test_all_denials(self) -> None:
        d = DriftDetector()
        d.record_denial(timestamp=1, reason_code="GW-CLIN-001")
        d.record_denial(timestamp=2, reason_code="GW-CLIN-002")
        assert d.compute_denial_rate() == 1.0

    def test_all_allows(self) -> None:
        d = DriftDetector()
        d.record_allow(timestamp=1)
        d.record_allow(timestamp=2)
        assert d.compute_denial_rate() == 0.0


class TestStateHashStable:
    """state_hash_stable reports identical vs changed hashes."""

    def test_no_observations_is_stable(self) -> None:
        d = DriftDetector()
        assert d.state_hash_stable() is True

    def test_single_observation_is_stable(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        assert d.state_hash_stable() is True

    def test_identical_hashes_are_stable(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="abc")
        d.record_state_hash(timestamp=3, state_hash="abc")
        assert d.state_hash_stable() is True

    def test_changed_hashes_are_not_stable(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="def")
        assert d.state_hash_stable() is False


class TestStateHashDrift:
    """check_state_hash_drift detects consecutive changes."""

    def test_no_change_returns_false(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="abc")
        assert d.check_state_hash_drift() is False

    def test_change_returns_true(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="def")
        assert d.check_state_hash_drift() is True

    def test_single_observation_no_drift(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        assert d.check_state_hash_drift() is False

    def test_oscillating_change_detected(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="abc")
        d.record_state_hash(timestamp=3, state_hash="xyz")
        assert d.check_state_hash_drift() is True


class TestDenialRateDrift:
    """check_denial_rate_drift crosses the threshold."""

    def test_low_denial_rate_no_drift(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        for i in range(8):
            d.record_allow(timestamp=i)
        d.record_denial(timestamp=9, reason_code="GW-CLIN-001")
        # 1/9 ~ 0.111 < 0.5
        assert d.check_denial_rate_drift() is False

    def test_high_denial_rate_drift(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        for i in range(2):
            d.record_allow(timestamp=i)
        for i in range(8):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        # 8/10 = 0.8 > 0.5
        assert d.check_denial_rate_drift() is True

    def test_exact_threshold_not_exceeded(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        d.record_allow(timestamp=1)
        d.record_denial(timestamp=2, reason_code="GW-CLIN-001")
        # 0.5 == 0.5, not > 0.5
        assert d.check_denial_rate_drift() is False


class TestDetectDrift:
    """detect_drift returns DriftAlerts with correct severity."""

    def test_no_drift_when_stable(self) -> None:
        """No drift is detected when everything is stable."""
        d = DriftDetector(denial_rate_threshold=0.5)
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="abc")
        for i in range(10):
            d.record_allow(timestamp=i)
        assert d.detect_drift() == []

    def test_no_drift_with_no_observations(self) -> None:
        d = DriftDetector()
        assert d.detect_drift() == []

    def test_state_hash_drift_emits_warning(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=10, state_hash="abc")
        d.record_state_hash(timestamp=20, state_hash="def")
        alerts = d.detect_drift()
        assert len(alerts) == 1
        alert = alerts[0]
        assert alert.severity == "WARNING"
        assert alert.metric_name == "state_hash_drift"
        assert alert.timestamp == 20

    def test_denial_rate_drift_emits_warning_below_critical(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        # 6/10 = 0.6 -> WARNING (0.5 < 0.6 < 0.8)
        for i in range(4):
            d.record_allow(timestamp=i)
        for i in range(6):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        alerts = d.detect_drift()
        denial_alerts = [a for a in alerts if a.metric_name == "denial_rate_drift"]
        assert len(denial_alerts) == 1
        assert denial_alerts[0].severity == "WARNING"
        assert denial_alerts[0].current_value == 0.6
        assert denial_alerts[0].threshold == 0.5

    def test_denial_rate_drift_emits_critical_at_or_above_0_8(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        # 9/10 = 0.9 -> CRITICAL (>= 0.8)
        for i in range(1):
            d.record_allow(timestamp=i)
        for i in range(9):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        alerts = d.detect_drift()
        denial_alerts = [a for a in alerts if a.metric_name == "denial_rate_drift"]
        assert len(denial_alerts) == 1
        assert denial_alerts[0].severity == "CRITICAL"

    def test_denial_rate_exactly_0_8_is_critical(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        # 8/10 = 0.8 -> CRITICAL (>= 0.8)
        for i in range(2):
            d.record_allow(timestamp=i)
        for i in range(8):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        alerts = d.detect_drift()
        denial_alerts = [a for a in alerts if a.metric_name == "denial_rate_drift"]
        assert len(denial_alerts) == 1
        assert denial_alerts[0].severity == "CRITICAL"

    def test_both_drifts_emit_two_alerts(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="def")
        for i in range(1):
            d.record_allow(timestamp=i)
        for i in range(9):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        alerts = d.detect_drift()
        assert len(alerts) == 2
        severities = {a.severity for a in alerts}
        assert severities == {"WARNING", "CRITICAL"}

    def test_alerts_have_deterministic_ids(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="def")
        a1 = d.detect_drift()
        assert all(a.alert_id.startswith("drift-alert-") for a in a1)
        # alert ids are unique
        ids = [a.alert_id for a in a1]
        assert len(ids) == len(set(ids))


class TestGetMetrics:
    """get_metrics returns current metric values and exceeded status."""

    def test_metrics_when_stable(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="abc")
        for i in range(10):
            d.record_allow(timestamp=i)
        metrics = {m.name: m for m in d.get_metrics()}
        assert metrics["state_hash_drift"].exceeded is False
        assert metrics["denial_rate_drift"].exceeded is False
        assert metrics["denial_rate_drift"].current_value == 0.0

    def test_metrics_when_state_hash_drifted(self) -> None:
        d = DriftDetector()
        d.record_state_hash(timestamp=1, state_hash="abc")
        d.record_state_hash(timestamp=2, state_hash="def")
        metrics = {m.name: m for m in d.get_metrics()}
        assert metrics["state_hash_drift"].exceeded is True
        assert metrics["state_hash_drift"].current_value == 1

    def test_metrics_when_denial_rate_drifted(self) -> None:
        d = DriftDetector(denial_rate_threshold=0.5)
        for i in range(1):
            d.record_allow(timestamp=i)
        for i in range(9):
            d.record_denial(timestamp=i, reason_code="GW-CLIN-001")
        metrics = {m.name: m for m in d.get_metrics()}
        assert metrics["denial_rate_drift"].exceeded is True
        assert metrics["denial_rate_drift"].current_value == 0.9

    def test_get_metrics_returns_two_metrics(self) -> None:
        d = DriftDetector()
        assert len(d.get_metrics()) == 2
        names = {m.name for m in d.get_metrics()}
        assert names == {"state_hash_drift", "denial_rate_drift"}
