"""F09: Concurrent requests at the budget boundary (G3.10).

Expected: Total reserved spend never exceeds the limit; excess
requests get GW-BUDGET-001 fallback.
"""

from __future__ import annotations

import uuid

from src.tokens.budget import BudgetGovernor, BudgetLevel
from src.tokens.fallback import FallbackReason

from tests.fault.infrastructure import ConcurrentBudgetBoundary


class TestF09ConcurrentBudgetBoundary:
    """F09: Concurrent requests at the budget boundary."""

    def test_total_reserved_never_exceeds_limit(self) -> None:
        """10 concurrent requests of 10 tokens each, budget=50.
        At most 5 can succeed; total reserved must be <= 50.
        """
        governor = BudgetGovernor(
            session_budget=1000,
            workflow_budget=50,
            capability_budget=1000,
        )
        boundary = ConcurrentBudgetBoundary(
            governor, BudgetLevel.WORKFLOW
        )
        result = boundary.concurrent_reserve(10, 10)

        assert result["successful_reservations"] <= 5
        assert result["total_reserved"] <= 50
        # The budget governor enforces atomicity: remaining never
        # goes negative, and total_reserved <= original budget.
        assert result["total_reserved"] <= 50

    def test_excess_requests_get_fallback(self) -> None:
        """Excess requests get the GW-BUDGET-001 fallback."""
        governor = BudgetGovernor(
            session_budget=1000,
            workflow_budget=50,
            capability_budget=1000,
        )
        boundary = ConcurrentBudgetBoundary(
            governor, BudgetLevel.WORKFLOW
        )
        result = boundary.concurrent_reserve(10, 10)
        assert result["failed_reservations"] > 0

        # Get the fallback for an excess request
        fallback = boundary.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
        )
        assert fallback.fallback_reason == (
            FallbackReason.BUDGET_SESSION_EXHAUSTED
        )
        assert fallback.tokens_used == 0

    def test_no_overspend_under_concurrency(self) -> None:
        """Budget governor's remaining must never go negative."""
        governor = BudgetGovernor(
            session_budget=1000,
            workflow_budget=30,
            capability_budget=1000,
        )
        boundary = ConcurrentBudgetBoundary(
            governor, BudgetLevel.WORKFLOW
        )
        result = boundary.concurrent_reserve(10, 6)
        assert governor.remaining(BudgetLevel.WORKFLOW) >= 0
        assert result["total_reserved"] <= 30

    def test_fallback_is_deterministic(self) -> None:
        """The fallback response is deterministic."""
        governor = BudgetGovernor(
            session_budget=1000,
            workflow_budget=0,
            capability_budget=1000,
        )
        boundary = ConcurrentBudgetBoundary(
            governor, BudgetLevel.WORKFLOW
        )
        f1 = boundary.get_fallback(uuid.uuid4(), 0)
        f2 = boundary.get_fallback(uuid.uuid4(), 0)
        assert f1.fallback_reason == f2.fallback_reason
        assert f1.tokens_used == 0
        assert f2.tokens_used == 0
