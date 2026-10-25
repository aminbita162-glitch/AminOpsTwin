"""Simulation validation against analytical references (P16, G16.5).

Validates the simulation engine against two analytical reference
models:

1. **Erlang-C** waiting time formula — for an M/M/c queue with arrival
   rate ``lam``, service rate ``mu``, and ``c`` servers, the expected
   waiting time ``W`` is:

       W = (C * (1 / (c * mu - lam))) / lam

   where C is the Erlang-C probability of waiting.

2. **Little's Law** — ``L = lam * W``, where L is the average number in
   system, lam is the arrival rate, and W is the average time in system.

The simulation's measured values are compared against these analytical
references with pre-declared relative error thresholds.  The measured
error must be <= the threshold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

__all__ = [
    "ErlangCResult",
    "LittlesLawResult",
    "erlang_c_waiting_time",
    "littles_law",
    "erlang_c_probability_waiting",
    "validate_simulation",
    "ERLANG_C_REL_ERROR_THRESHOLD",
    "LITTLES_LAW_REL_ERROR_THRESHOLD",
]

# Pre-declared relative error thresholds (G16.5)
ERLANG_C_REL_ERROR_THRESHOLD: float = 0.15  # 15%
LITTLES_LAW_REL_ERROR_THRESHOLD: float = 0.15  # 15%


def _factorial(n: int) -> int:
    """Compute n! using integer arithmetic."""
    result = 1
    for i in range(2, n + 1):
        result *= i
    return result


def erlang_c_probability_waiting(
    lam: float,
    mu: float,
    c: int,
) -> float:
    """Compute the Erlang-C probability of waiting (C).

    For an M/M/c queue:
        A = lam / mu  (offered load)
        rho = A / c   (utilization, must be < 1)
        C = (A^c / c!) / ((sum_{k=0}^{c-1} A^k / k!) + A^c / c!)

    Returns the probability that an arrival has to wait.
    """
    if c <= 0:
        raise ValueError("c must be > 0")
    if mu <= 0:
        raise ValueError("mu must be > 0")
    if lam < 0:
        raise ValueError("lam must be >= 0")

    a = lam / mu  # offered load
    rho = a / c
    if rho >= 1.0:
        # System is overloaded — probability of waiting approaches 1
        return 1.0

    # Compute sum_{k=0}^{c-1} A^k / k!
    denom_sum = 0.0
    for k in range(c):
        term = (a ** k) / float(_factorial(k))
        denom_sum += term

    # A^c / c!
    a_c = (a ** c) / float(_factorial(c))

    # C = (A^c / c!) / (sum + A^c / c!)
    return a_c / (denom_sum + a_c)


def erlang_c_waiting_time(
    lam: float,
    mu: float,
    c: int,
) -> float:
    """Compute the expected waiting time W for an M/M/c queue (Erlang-C).

    W = C / (c * mu - lam)

    where C is the Erlang-C probability of waiting.
    """
    if lam <= 0:
        return 0.0
    c_prob = erlang_c_probability_waiting(lam, mu, c)
    return c_prob / (c * mu - lam)


def littles_law(
    lam: float,
    w: float,
) -> float:
    """Compute L = lam * W (Little's Law).

    L is the average number of items in the system.
    """
    return lam * w


@dataclass(frozen=True)
class ErlangCResult:
    """Result of an Erlang-C validation check."""

    lam: float
    mu: float
    c: int
    expected_wait: float
    measured_wait: float
    relative_error: float
    threshold: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "lam": self.lam,
            "mu": self.mu,
            "c": self.c,
            "expected_wait": self.expected_wait,
            "measured_wait": self.measured_wait,
            "relative_error": self.relative_error,
            "threshold": self.threshold,
            "passed": self.passed,
        }


@dataclass(frozen=True)
class LittlesLawResult:
    """Result of a Little's Law validation check."""

    lam: float
    w: float
    expected_l: float
    measured_l: float
    relative_error: float
    threshold: float
    passed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "lam": self.lam,
            "w": self.w,
            "expected_l": self.expected_l,
            "measured_l": self.measured_l,
            "relative_error": self.relative_error,
            "threshold": self.threshold,
            "passed": self.passed,
        }


def _relative_error(expected: float, measured: float) -> float:
    """Compute the relative error |measured - expected| / |expected|."""
    if expected == 0:
        return abs(measured)
    return abs(measured - expected) / abs(expected)


def validate_simulation(
    lam: float,
    mu: float,
    c: int,
    measured_wait: float,
    measured_l: float,
) -> tuple[ErlangCResult, LittlesLawResult]:
    """Validate simulation measurements against analytical references.

    Returns (erlang_c_result, littles_law_result) with relative errors
    and pass/fail status.
    """
    expected_wait = erlang_c_waiting_time(lam, mu, c)
    wait_rel_error = _relative_error(expected_wait, measured_wait)
    erlang_result = ErlangCResult(
        lam=lam,
        mu=mu,
        c=c,
        expected_wait=expected_wait,
        measured_wait=measured_wait,
        relative_error=wait_rel_error,
        threshold=ERLANG_C_REL_ERROR_THRESHOLD,
        passed=wait_rel_error <= ERLANG_C_REL_ERROR_THRESHOLD,
    )

    expected_l = littles_law(lam, measured_wait)
    l_rel_error = _relative_error(expected_l, measured_l)
    littles_result = LittlesLawResult(
        lam=lam,
        w=measured_wait,
        expected_l=expected_l,
        measured_l=measured_l,
        relative_error=l_rel_error,
        threshold=LITTLES_LAW_REL_ERROR_THRESHOLD,
        passed=l_rel_error <= LITTLES_LAW_REL_ERROR_THRESHOLD,
    )

    return erlang_result, littles_result
