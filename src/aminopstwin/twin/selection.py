"""Budgeted next-experiment selection (P5, §33.3, G4.9).

A2 selects the next simulation expected to reduce operational
uncertainty under a fixed computational budget. Uses an explicit
deterministic scoring formula, versioned integer/fixed-point inputs,
stable ties and a recorded seed.

If the uncertainty model cannot support an informative score, returns
NOT_ESTIMABLE. Compares against a fixed uniform-allocation baseline on
held-out synthetic cases.

Budget is never exceeded. Identical inputs produce identical selection.
No mandatory superiority percentage is invented without calibration
and approval.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash

__all__ = [
    "SelectionOutcome",
    "CandidateExperiment",
    "SelectionResult",
    "BaselineComparison",
    "ExperimentSelector",
    "SelectionError",
]


class SelectionError(Exception):
    """Raised when selection inputs are invalid."""


class SelectionOutcome(StrEnum):
    """Outcome of a next-experiment selection."""

    SELECTED = "SELECTED"
    NOT_ESTIMABLE = "NOT_ESTIMABLE"
    BUDGET_EXCEEDED = "BUDGET_EXCEEDED"
    NO_CANDIDATES = "NO_CANDIDATES"


@dataclass(frozen=True)
class CandidateExperiment:
    """A candidate experiment for selection (§33.3).

    All values are integer/fixed-point (no floats in hashed payloads,
    N-15). uncertainty_estimate is an integer representing the
    current uncertainty level (lower = less uncertain). expected_info_gain
    is the estimated reduction in uncertainty (integer). cost is the
    computational cost in integer units.
    """

    candidate_id: str
    uncertainty_estimate: int
    expected_info_gain: int
    cost: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "uncertainty_estimate": self.uncertainty_estimate,
            "expected_info_gain": self.expected_info_gain,
            "cost": self.cost,
        }


@dataclass
class SelectionResult:
    """Result of budgeted next-experiment selection (§33.3)."""

    outcome: SelectionOutcome
    selected_id: str | None = None
    selected_score: int = 0
    budget_used: int = 0
    budget_total: int = 0
    candidates_evaluated: int = 0
    seed: int = 0
    scoring_formula: str = ""
    reproducibility_hash: str = ""
    not_estimable_reason: str | None = None
    baseline_comparison: BaselineComparison | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome": self.outcome.value,
            "selected_id": self.selected_id,
            "selected_score": self.selected_score,
            "budget_used": self.budget_used,
            "budget_total": self.budget_total,
            "candidates_evaluated": self.candidates_evaluated,
            "seed": self.seed,
            "scoring_formula": self.scoring_formula,
            "reproducibility_hash": self.reproducibility_hash,
            "not_estimable_reason": self.not_estimable_reason,
            "baseline_comparison": (
                self.baseline_comparison.to_dict()
                if self.baseline_comparison is not None
                else None
            ),
        }


@dataclass
class BaselineComparison:
    """Comparison against a fixed uniform-allocation baseline.

    The uniform baseline allocates budget equally across candidates.
    The selected approach is compared against this baseline to report
    uncertainty reduction and compute cost, including cases with no
    advantage.
    """

    selected_uncertainty_reduction: int = 0
    baseline_uncertainty_reduction: int = 0
    selected_compute_cost: int = 0
    baseline_compute_cost: int = 0
    advantage: int = 0  # selected - baseline (can be negative)

    def to_dict(self) -> dict[str, Any]:
        return {
            "selected_uncertainty_reduction": (
                self.selected_uncertainty_reduction
            ),
            "baseline_uncertainty_reduction": (
                self.baseline_uncertainty_reduction
            ),
            "selected_compute_cost": self.selected_compute_cost,
            "baseline_compute_cost": self.baseline_compute_cost,
            "advantage": self.advantage,
        }


class ExperimentSelector:
    """Budgeted next-experiment selector (§33.3, G4.9).

    Uses an explicit deterministic scoring formula:
        score = expected_info_gain * 1000 // (cost + 1)
    Higher score = more information gain per unit cost.
    Stable tie-break: ascending candidate_id for equal scores.
    Budget is never exceeded. If all candidates have zero info gain or
    the uncertainty model cannot support an informative score, returns
    NOT_ESTIMABLE.
    """

    #: The scoring formula identifier (versioned).
    SCORING_FORMULA: str = "info_gain_per_cost_v1"

    def __init__(self, budget: int, seed: int = 0) -> None:
        if budget < 0:
            raise SelectionError(
                f"budget must be non-negative, got {budget}"
            )
        self._budget = budget
        self._seed = seed

    def select(
        self,
        candidates: list[CandidateExperiment],
    ) -> SelectionResult:
        """Select the best experiment within budget."""
        if not candidates:
            return SelectionResult(
                outcome=SelectionOutcome.NO_CANDIDATES,
                budget_total=self._budget,
                seed=self._seed,
                scoring_formula=self.SCORING_FORMULA,
            )

        # Check if any candidate has informative info gain.
        any_informative = any(
            c.expected_info_gain > 0 for c in candidates
        )
        if not any_informative:
            result = SelectionResult(
                outcome=SelectionOutcome.NOT_ESTIMABLE,
                budget_total=self._budget,
                candidates_evaluated=len(candidates),
                seed=self._seed,
                scoring_formula=self.SCORING_FORMULA,
                not_estimable_reason=(
                    "No candidate has positive expected_info_gain; "
                    "uncertainty model cannot support an informative score"
                ),
            )
            result.reproducibility_hash = self._compute_hash(
                result, candidates
            )
            return result

        # Score each candidate that fits within budget.
        scored: list[tuple[str, int, int, int]] = []
        # (candidate_id, score, info_gain, cost)
        for c in candidates:
            if c.cost > self._budget:
                continue
            if c.cost <= 0:
                # Avoid division by zero; use a high score for zero-cost.
                score = c.expected_info_gain * 1000
            else:
                score = c.expected_info_gain * 1000 // (c.cost + 1)
            scored.append((c.candidate_id, score, c.expected_info_gain, c.cost))

        if not scored:
            # All candidates exceed budget.
            result = SelectionResult(
                outcome=SelectionOutcome.BUDGET_EXCEEDED,
                budget_total=self._budget,
                candidates_evaluated=len(candidates),
                seed=self._seed,
                scoring_formula=self.SCORING_FORMULA,
                not_estimable_reason=(
                    "All candidates exceed the remaining budget"
                ),
            )
            result.reproducibility_hash = self._compute_hash(
                result, candidates
            )
            return result

        # Sort by score descending, then by candidate_id ascending (stable).
        scored.sort(key=lambda t: (-t[1], t[0]))

        best_id, best_score, best_gain, best_cost = scored[0]

        # Compare against uniform-allocation baseline.
        comparison = self._compare_baseline(
            candidates, best_id, best_gain, best_cost
        )

        result = SelectionResult(
            outcome=SelectionOutcome.SELECTED,
            selected_id=best_id,
            selected_score=best_score,
            budget_used=best_cost,
            budget_total=self._budget,
            candidates_evaluated=len(candidates),
            seed=self._seed,
            scoring_formula=self.SCORING_FORMULA,
            baseline_comparison=comparison,
        )
        result.reproducibility_hash = self._compute_hash(
            result, candidates
        )
        return result

    def _compare_baseline(
        self,
        candidates: list[CandidateExperiment],
        selected_id: str,
        selected_gain: int,
        selected_cost: int,
    ) -> BaselineComparison:
        """Compare selected approach against uniform-allocation baseline.

        The uniform baseline distributes budget equally among
        candidates that fit. Reports uncertainty reduction and compute
        cost for both, including cases with no advantage.
        """
        n = len(candidates)
        per_candidate_budget = self._budget // n if n > 0 else 0

        baseline_gain = 0
        baseline_cost = 0
        for c in candidates:
            if c.cost <= per_candidate_budget:
                baseline_gain += c.expected_info_gain
                baseline_cost += c.cost

        advantage = selected_gain - baseline_gain
        return BaselineComparison(
            selected_uncertainty_reduction=selected_gain,
            baseline_uncertainty_reduction=baseline_gain,
            selected_compute_cost=selected_cost,
            baseline_compute_cost=baseline_cost,
            advantage=advantage,
        )

    @staticmethod
    def _compute_hash(
        result: SelectionResult,
        candidates: list[CandidateExperiment],
    ) -> str:
        """Compute a reproducibility hash from result + candidates."""
        data = {
            "result": result.to_dict(),
            "candidates": [c.to_dict() for c in candidates],
        }
        return canonical_hash(data)
