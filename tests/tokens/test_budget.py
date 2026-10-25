"""Tests for the Budget Governor (G2.5) and three-level budget enforcement."""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.tokens.budget import BudgetGovernor, BudgetLevel
from aminopstwin.tokens.fallback import (
    FallbackReason,
    FallbackResponse,
    ReservationStatus,
)

# ---------------------------------------------------------------------------
# Budget reservation and reconciliation
# ---------------------------------------------------------------------------


class TestBudgetReservation:
    """Reserve and reconcile tokens at each level."""

    def test_reserve_success(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        assert gov.reserve(BudgetLevel.SESSION, 30) is True
        assert gov.remaining(BudgetLevel.SESSION) == 70
        assert gov.reserve(BudgetLevel.WORKFLOW, 20) is True
        assert gov.remaining(BudgetLevel.WORKFLOW) == 30
        assert gov.reserve(BudgetLevel.CAPABILITY, 5) is True
        assert gov.remaining(BudgetLevel.CAPABILITY) == 5

    def test_reserve_exact(self) -> None:
        gov = BudgetGovernor(10, 10, 10)
        assert gov.reserve(BudgetLevel.SESSION, 10) is True
        assert gov.remaining(BudgetLevel.SESSION) == 0
        assert gov.is_exhausted(BudgetLevel.SESSION) is True

    def test_reserve_over_budget(self) -> None:
        gov = BudgetGovernor(10, 10, 10)
        assert gov.reserve(BudgetLevel.SESSION, 11) is False
        assert gov.remaining(BudgetLevel.SESSION) == 10

    def test_reserve_zero_amount(self) -> None:
        gov = BudgetGovernor(10, 10, 10)
        assert gov.reserve(BudgetLevel.SESSION, 0) is True
        assert gov.remaining(BudgetLevel.SESSION) == 10

    def test_reconcile_releases_difference(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        gov.reserve(BudgetLevel.SESSION, 50)
        assert gov.remaining(BudgetLevel.SESSION) == 50
        gov.reconcile(BudgetLevel.SESSION, 50, 20)
        assert gov.remaining(BudgetLevel.SESSION) == 80

    def test_reconcile_exact_usage(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        gov.reserve(BudgetLevel.WORKFLOW, 30)
        gov.reconcile(BudgetLevel.WORKFLOW, 30, 30)
        # 30 reserved, 30 used → 0 released → remaining stays at 70
        assert gov.remaining(BudgetLevel.WORKFLOW) == 70

    def test_reconcile_negative_actual_rejected(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        gov.reserve(BudgetLevel.SESSION, 10)
        with pytest.raises(ValueError):
            gov.reconcile(BudgetLevel.SESSION, 10, -1)

    def test_reserve_negative_rejected(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        with pytest.raises(ValueError):
            gov.reserve(BudgetLevel.SESSION, -1)

    def test_negative_budget_rejected(self) -> None:
        with pytest.raises(ValueError):
            BudgetGovernor(-1, 10, 10)


# ---------------------------------------------------------------------------
# is_exhausted and remaining
# ---------------------------------------------------------------------------


class TestBudgetExhausted:
    """is_exhausted and remaining at each level."""

    def test_is_exhausted_false_initially(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        assert gov.is_exhausted(BudgetLevel.SESSION) is False
        assert gov.is_exhausted(BudgetLevel.WORKFLOW) is False
        assert gov.is_exhausted(BudgetLevel.CAPABILITY) is False

    def test_is_exhausted_true_after_drain(self) -> None:
        gov = BudgetGovernor(10, 10, 10)
        gov.reserve(BudgetLevel.SESSION, 10)
        assert gov.is_exhausted(BudgetLevel.SESSION) is True

    def test_remaining_returns_budget(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        assert gov.remaining(BudgetLevel.SESSION) == 100
        assert gov.remaining(BudgetLevel.WORKFLOW) == 50
        assert gov.remaining(BudgetLevel.CAPABILITY) == 10


# ---------------------------------------------------------------------------
# Zero budget -> deterministic fallback with 0 LLM calls (G2.5)
# ---------------------------------------------------------------------------


class TestZeroBudgetFallback:
    """When budget is zero, get_fallback returns deterministic response (G2.5)."""

    def test_zero_budget_fallback(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        assert gov.is_exhausted(BudgetLevel.SESSION)
        cid = uuid.UUID("00000000-0000-0000-0000-000000000001")
        fb = gov.get_fallback(cid, policy_epoch=0)
        assert fb.tokens_used == 0
        assert fb.path == "deterministic"
        assert fb.fallback_reason is FallbackReason.BUDGET_SESSION_EXHAUSTED

    def test_fallback_is_deterministic(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        cid = uuid.uuid4()
        fb1 = gov.get_fallback(cid, policy_epoch=1)
        fb2 = gov.get_fallback(cid, policy_epoch=1)
        assert fb1 == fb2

    def test_fallback_has_honesty_statement(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        fb = gov.get_fallback(uuid.uuid4(), 0)
        assert "deterministic" in fb.honesty_statement.lower()
        assert "template" in fb.honesty_statement.lower()


# ---------------------------------------------------------------------------
# All three levels
# ---------------------------------------------------------------------------


class TestThreeLevels:
    """All three budget levels are independently tracked."""

    def test_session_level(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        gov.reserve(BudgetLevel.SESSION, 10)
        assert gov.remaining(BudgetLevel.SESSION) == 90
        assert gov.remaining(BudgetLevel.WORKFLOW) == 50
        assert gov.remaining(BudgetLevel.CAPABILITY) == 10

    def test_workflow_level(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        gov.reserve(BudgetLevel.WORKFLOW, 10)
        assert gov.remaining(BudgetLevel.WORKFLOW) == 40
        assert gov.remaining(BudgetLevel.SESSION) == 100

    def test_capability_level(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        gov.reserve(BudgetLevel.CAPABILITY, 3)
        assert gov.remaining(BudgetLevel.CAPABILITY) == 7
        assert gov.remaining(BudgetLevel.WORKFLOW) == 50

    def test_reserve_does_not_block_other_levels(self) -> None:
        """Reserve at one level does not decrement other levels."""
        gov = BudgetGovernor(100, 50, 10)
        gov.reserve(BudgetLevel.SESSION, 20)
        assert gov.remaining(BudgetLevel.SESSION) == 80
        assert gov.remaining(BudgetLevel.WORKFLOW) == 50
        assert gov.remaining(BudgetLevel.CAPABILITY) == 10

    def test_budget_properties(self) -> None:
        gov = BudgetGovernor(100, 50, 10)
        assert gov.session_budget == 100
        assert gov.workflow_budget == 50
        assert gov.capability_budget == 10


# ---------------------------------------------------------------------------
# FallbackResponse fields per §24.4
# ---------------------------------------------------------------------------


class TestFallbackResponseFields:
    """FallbackResponse from the governor has all §24.4 fields."""

    def test_fallback_fields_present(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        cid = uuid.uuid4()
        fb = gov.get_fallback(cid, policy_epoch=42)
        assert fb.correlation_id == cid
        assert fb.path == "deterministic"
        assert fb.cache_hit is False
        assert fb.policy_decision == "DENY"
        assert fb.policy_epoch == 42
        assert isinstance(fb.fallback_reason, FallbackReason)
        assert isinstance(fb.reservation_status, ReservationStatus)
        assert isinstance(fb.message_template_id, str)
        assert isinstance(fb.message, str)
        assert fb.tokens_used == 0
        assert fb.tokens_budget_remaining >= 0
        assert isinstance(fb.suggested_next_actions, list)
        assert isinstance(fb.honesty_statement, str)

    def test_fallback_reservation_status_denied(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        fb = gov.get_fallback(uuid.uuid4(), 0)
        assert fb.reservation_status is ReservationStatus.DENIED

    def test_fallback_is_fallback_response_type(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        fb = gov.get_fallback(uuid.uuid4(), 0)
        assert isinstance(fb, FallbackResponse)
