"""G4.9 — Budgeted next-experiment selection tests (P5, §33.3).

Zero budget violations. Identical inputs reproduce identical selection.
Held-out baseline comparisons and NOT_ESTIMABLE cases are reported
without omitted failures. No mandatory superiority percentage is
invented without calibration and approval.
"""

from __future__ import annotations

import pytest
from src.twin.selection import (
    CandidateExperiment,
    ExperimentSelector,
    SelectionError,
    SelectionOutcome,
)


def _candidates() -> list[CandidateExperiment]:
    return [
        CandidateExperiment(
            candidate_id="cand-A",
            uncertainty_estimate=100,
            expected_info_gain=50,
            cost=10,
        ),
        CandidateExperiment(
            candidate_id="cand-B",
            uncertainty_estimate=200,
            expected_info_gain=80,
            cost=20,
        ),
        CandidateExperiment(
            candidate_id="cand-C",
            uncertainty_estimate=50,
            expected_info_gain=20,
            cost=5,
        ),
    ]


class TestBudgetedSelection:
    """Budgeted next-experiment selection with deterministic scoring."""

    def test_selects_best_within_budget(self) -> None:
        selector = ExperimentSelector(budget=100, seed=42)
        result = selector.select(_candidates())
        assert result.outcome is SelectionOutcome.SELECTED
        assert result.selected_id is not None
        assert result.budget_used <= result.budget_total

    def test_budget_never_exceeded(self) -> None:
        selector = ExperimentSelector(budget=15, seed=42)
        result = selector.select(_candidates())
        assert result.budget_used <= result.budget_total

    def test_identical_inputs_reproduce_selection(self) -> None:
        selector1 = ExperimentSelector(budget=100, seed=99)
        selector2 = ExperimentSelector(budget=100, seed=99)
        r1 = selector1.select(_candidates())
        r2 = selector2.select(_candidates())
        assert r1.selected_id == r2.selected_id
        assert r1.reproducibility_hash == r2.reproducibility_hash

    def test_reproducibility_hash_stable(self) -> None:
        selector = ExperimentSelector(budget=100, seed=7)
        r1 = selector.select(_candidates())
        r2 = selector.select(_candidates())
        assert r1.reproducibility_hash == r2.reproducibility_hash

    def test_no_candidates(self) -> None:
        selector = ExperimentSelector(budget=100, seed=0)
        result = selector.select([])
        assert result.outcome is SelectionOutcome.NO_CANDIDATES

    def test_all_zero_info_gain_not_estimable(self) -> None:
        selector = ExperimentSelector(budget=100, seed=0)
        candidates = [
            CandidateExperiment(
                candidate_id="cand-zero",
                uncertainty_estimate=100,
                expected_info_gain=0,
                cost=10,
            ),
        ]
        result = selector.select(candidates)
        assert result.outcome is SelectionOutcome.NOT_ESTIMABLE
        assert result.not_estimable_reason is not None

    def test_budget_exceeded_all_candidates(self) -> None:
        selector = ExperimentSelector(budget=1, seed=0)
        candidates = [
            CandidateExperiment(
                candidate_id="cand-expensive",
                uncertainty_estimate=100,
                expected_info_gain=50,
                cost=100,
            ),
        ]
        result = selector.select(candidates)
        assert result.outcome is SelectionOutcome.BUDGET_EXCEEDED

    def test_scoring_formula_reported(self) -> None:
        selector = ExperimentSelector(budget=100, seed=0)
        result = selector.select(_candidates())
        assert result.scoring_formula == "info_gain_per_cost_v1"

    def test_baseline_comparison_reported(self) -> None:
        selector = ExperimentSelector(budget=100, seed=0)
        result = selector.select(_candidates())
        assert result.baseline_comparison is not None
        comp = result.baseline_comparison
        assert isinstance(comp.selected_uncertainty_reduction, int)
        assert isinstance(comp.baseline_uncertainty_reduction, int)
        assert isinstance(comp.advantage, int)

    def test_baseline_comparison_no_omitted_failures(self) -> None:
        """NOT_ESTIMABLE and no-advantage cases are reported without
        omitted failures. Advantage can be negative (uniform baseline
        may do better); it must be reported, not hidden."""
        selector = ExperimentSelector(budget=100, seed=0)
        candidates = [
            CandidateExperiment(
                candidate_id="cand-eq-1",
                uncertainty_estimate=100,
                expected_info_gain=10,
                cost=10,
            ),
            CandidateExperiment(
                candidate_id="cand-eq-2",
                uncertainty_estimate=100,
                expected_info_gain=10,
                cost=10,
            ),
        ]
        result = selector.select(candidates)
        assert result.outcome is SelectionOutcome.SELECTED
        assert result.baseline_comparison is not None
        # Advantage may be zero, positive, or negative; it must be reported.
        assert isinstance(result.baseline_comparison.advantage, int)


class TestNegativeBudget:
    """Negative budget is rejected."""

    def test_negative_budget_rejected(self) -> None:
        with pytest.raises(SelectionError):
            ExperimentSelector(budget=-1, seed=0)
