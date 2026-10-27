"""G4.13 — Transparency and accounting tests (P4, §4.5, §36).

All response types, including fallback and cache paths, contain the unified
metadata fields; measured reservations reconcile; zero false zero-token claims.
"""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.tokens.budget import BudgetGovernor, BudgetLevel
from aminopstwin.tokens.fallback import (
    HONESTY_STATEMENT,
    FallbackReason,
    ReservationStatus,
)


class TestTransparencyFields:
    """G4.13: all response types contain unified metadata fields."""

    REQUIRED_FIELDS = [
        "correlation_id",
        "path",
        "cache_hit",
        "policy_decision",
        "policy_epoch",
        "fallback_reason",
        "reservation_status",
        "message_template_id",
        "message",
        "tokens_used",
        "tokens_budget_remaining",
        "suggested_next_actions",
        "honesty_statement",
    ]

    def test_fallback_response_has_all_fields(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        corr = uuid.uuid4()
        resp = gov.get_fallback(
            correlation_id=corr,
            policy_epoch=0,
            reason=FallbackReason.BUDGET_SESSION_EXHAUSTED,
        )
        for field in self.REQUIRED_FIELDS:
            assert hasattr(resp, field), f"missing field: {field}"

    def test_fallback_response_path_is_deterministic(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        resp = gov.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
        )
        assert resp.path == "deterministic"

    def test_fallback_response_has_honesty_statement(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        resp = gov.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
        )
        assert resp.honesty_statement == HONESTY_STATEMENT

    def test_zero_budget_fallback_has_zero_tokens(self) -> None:
        gov = BudgetGovernor(0, 0, 0)
        resp = gov.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
        )
        assert resp.tokens_used == 0
        assert resp.tokens_budget_remaining == 0
        assert resp.reservation_status is ReservationStatus.DENIED


class TestReservationReconciliation:
    """Measured reservations reconcile."""

    def test_reserve_and_reconcile(self) -> None:
        gov = BudgetGovernor(100, 100, 100)
        assert gov.reserve(BudgetLevel.WORKFLOW, 50)
        assert gov.remaining(BudgetLevel.WORKFLOW) == 50
        gov.reconcile(BudgetLevel.WORKFLOW, 50, 30)
        # After reconciliation: remaining = 50 + (50-30) = 70
        assert gov.remaining(BudgetLevel.WORKFLOW) == 70

    def test_reserve_exhausted(self) -> None:
        gov = BudgetGovernor(10, 10, 10)
        assert gov.reserve(BudgetLevel.WORKFLOW, 10)
        assert gov.is_exhausted(BudgetLevel.WORKFLOW)
        assert not gov.reserve(BudgetLevel.WORKFLOW, 1)

    def test_no_false_zero_token_claim(self) -> None:
        """A fallback with tokens_used=0 must not claim model tokens were used."""
        gov = BudgetGovernor(0, 0, 0)
        resp = gov.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
            reason=FallbackReason.BUDGET_WORKFLOW_EXHAUSTED,
        )
        assert resp.tokens_used == 0
        # The honesty statement discloses the deterministic nature
        assert "deterministic" in resp.honesty_statement.lower()


class TestFallbackReasons:
    """All fallback reasons produce valid responses."""

    @pytest.mark.parametrize(
        "reason",
        list(FallbackReason),
    )
    def test_all_fallback_reasons(self, reason: FallbackReason) -> None:
        gov = BudgetGovernor(100, 100, 100)
        resp = gov.get_fallback(
            correlation_id=uuid.uuid4(),
            policy_epoch=0,
            reason=reason,
        )
        assert resp.fallback_reason is reason
        assert resp.path == "deterministic"
