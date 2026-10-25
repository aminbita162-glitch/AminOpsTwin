"""G16.5 — Simulation validation within thresholds (P16).

Tests the simulation against analytical references (Erlang-C waiting
time, Little's Law) with pre-declared relative error thresholds.
"""

from __future__ import annotations

from aminopstwin.twin.sim_validation import (
    ERLANG_C_REL_ERROR_THRESHOLD,
    LITTLES_LAW_REL_ERROR_THRESHOLD,
    erlang_c_probability_waiting,
    erlang_c_waiting_time,
    littles_law,
    validate_simulation,
)


class TestErlangC:
    """Erlang-C analytical reference."""

    def test_probability_waiting_low_load(self) -> None:
        """Low load -> low probability of waiting."""
        p = erlang_c_probability_waiting(lam=1.0, mu=2.0, c=1)
        # A = 0.5, rho = 0.5
        # C = (0.5^1 / 1!) / (1 + 0.5) = 0.5 / 1.5 = 1/3
        assert abs(p - (1.0 / 3.0)) < 0.01

    def test_probability_waiting_high_load(self) -> None:
        """High load -> high probability of waiting."""
        p = erlang_c_probability_waiting(lam=0.9, mu=1.0, c=1)
        # A = 0.9, rho = 0.9
        # C = 0.9 / (1 + 0.9) = 0.9 / 1.9
        assert p > 0.4

    def test_probability_waiting_overloaded(self) -> None:
        """Overloaded (rho >= 1) -> C approaches 1."""
        p = erlang_c_probability_waiting(lam=2.0, mu=1.0, c=1)
        assert p == 1.0

    def test_waiting_time(self) -> None:
        """Erlang-C waiting time W = C / (c*mu - lam)."""
        w = erlang_c_waiting_time(lam=0.5, mu=1.0, c=1)
        # C = 0.5 / 1.5 = 1/3
        # W = (1/3) / (1 - 0.5) = (1/3) / 0.5 = 2/3
        assert abs(w - (2.0 / 3.0)) < 0.01

    def test_waiting_time_zero_arrivals(self) -> None:
        """Zero arrivals -> zero waiting time."""
        w = erlang_c_waiting_time(lam=0, mu=1.0, c=1)
        assert w == 0.0


class TestLittlesLaw:
    """Little's Law L = lam * W."""

    def test_basic(self) -> None:
        result = littles_law(lam=5.0, w=2.0)
        assert result == 10.0

    def test_zero_arrivals(self) -> None:
        result = littles_law(lam=0.0, w=5.0)
        assert result == 0.0

    def test_zero_wait(self) -> None:
        result = littles_law(lam=5.0, w=0.0)
        assert result == 0.0


class TestSimulationValidation:
    """validate_simulation — measured vs analytical with thresholds."""

    def test_validation_passes_within_threshold(self) -> None:
        """When measured values are close to analytical, validation passes."""
        # Use Erlang-C to get the expected wait, then add small noise
        lam = 0.5
        mu = 1.0
        c = 1
        expected_w = erlang_c_waiting_time(lam, mu, c)
        expected_l = littles_law(lam, expected_w)

        # Measured values within 10% of expected
        measured_w = expected_w * 1.05
        measured_l = expected_l * 1.05

        erlang_result, littles_result = validate_simulation(
            lam=lam, mu=mu, c=c,
            measured_wait=measured_w,
            measured_l=measured_l,
        )
        assert erlang_result.relative_error <= ERLANG_C_REL_ERROR_THRESHOLD
        assert littles_result.relative_error <= LITTLES_LAW_REL_ERROR_THRESHOLD
        assert erlang_result.passed
        assert littles_result.passed

    def test_validation_fails_outside_threshold(self) -> None:
        """When measured values are far from analytical, validation fails."""
        lam = 0.5
        mu = 1.0
        c = 1
        expected_w = erlang_c_waiting_time(lam, mu, c)

        # Measured wait 50% off — outside the 15% threshold for Erlang-C
        measured_w = expected_w * 1.50

        erlang_result, _ = validate_simulation(
            lam=lam, mu=mu, c=c,
            measured_wait=measured_w,
            measured_l=littles_law(lam, measured_w),
        )
        assert not erlang_result.passed
        assert erlang_result.relative_error > ERLANG_C_REL_ERROR_THRESHOLD

    def test_thresholds_declared(self) -> None:
        """The thresholds are pre-declared and reasonable."""
        assert ERLANG_C_REL_ERROR_THRESHOLD > 0
        assert LITTLES_LAW_REL_ERROR_THRESHOLD > 0
        assert ERLANG_C_REL_ERROR_THRESHOLD <= 1.0
        assert LITTLES_LAW_REL_ERROR_THRESHOLD <= 1.0

    def test_result_to_dict(self) -> None:
        """Results have to_dict with all fields."""
        erlang_result, littles_result = validate_simulation(
            lam=0.5, mu=1.0, c=1,
            measured_wait=1.0,
            measured_l=0.5,
        )
        ed = erlang_result.to_dict()
        assert "lam" in ed
        assert "mu" in ed
        assert "c" in ed
        assert "passed" in ed

        ld = littles_result.to_dict()
        assert "lam" in ld
        assert "w" in ld
        assert "passed" in ld
