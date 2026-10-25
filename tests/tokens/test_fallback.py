"""Tests for the FallbackResponse schema (§24.4).

Construction, validation, enum values.
"""

from __future__ import annotations

import uuid

import pytest
from aminopstwin.tokens.fallback import (
    HONESTY_STATEMENT,
    FallbackReason,
    FallbackResponse,
    ReservationStatus,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# FallbackResponse construction and field validation
# ---------------------------------------------------------------------------


class TestFallbackResponseConstruction:
    """FallbackResponse construction with required and optional fields."""

    @pytest.fixture
    def cid(self) -> uuid.UUID:
        return uuid.UUID("11111111-2222-3333-4444-555555555555")

    def test_minimal_construction(self, cid: uuid.UUID) -> None:
        fb = FallbackResponse(
            correlation_id=cid,
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            message_template_id="tmpl.unavailable.v1",
            message="LLM is currently unavailable.",
        )
        assert fb.correlation_id == cid
        assert fb.path == "deterministic"
        assert fb.cache_hit is False
        assert fb.policy_decision == "DENY"
        assert fb.policy_epoch == 0
        assert fb.fallback_reason is FallbackReason.LLM_UNAVAILABLE
        assert fb.reservation_status is ReservationStatus.NOT_REQUIRED
        assert fb.message_template_id == "tmpl.unavailable.v1"
        assert fb.tokens_used == 0
        assert fb.tokens_budget_remaining == 0
        assert fb.suggested_next_actions == []

    def test_full_construction(self, cid: uuid.UUID) -> None:
        fb = FallbackResponse(
            correlation_id=cid,
            cache_hit=True,
            policy_decision="DENY",
            policy_epoch=5,
            fallback_reason=FallbackReason.CACHE_STALE,
            reservation_status=ReservationStatus.RECONCILED,
            message_template_id="tmpl.cache.v2",
            message="Cache entry was stale.",
            tokens_used=0,
            tokens_budget_remaining=100,
            suggested_next_actions=["Refresh cache", "Retry"],
        )
        assert fb.cache_hit is True
        assert fb.policy_epoch == 5
        assert fb.reservation_status is ReservationStatus.RECONCILED
        assert fb.tokens_budget_remaining == 100
        assert fb.suggested_next_actions == ["Refresh cache", "Retry"]

    def test_path_is_literal_deterministic(self, cid: uuid.UUID) -> None:
        fb = FallbackResponse(
            correlation_id=cid,
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            message_template_id="t",
            message="m",
        )
        assert fb.path == "deterministic"

    def test_path_rejects_non_deterministic(self, cid: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=cid,
                path="llm",  # type: ignore[arg-type]
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
            )

    def test_negative_tokens_used_rejected(self, cid: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=cid,
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
                tokens_used=-1,
            )

    def test_negative_tokens_budget_remaining_rejected(
        self, cid: uuid.UUID
    ) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=cid,
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
                tokens_budget_remaining=-1,
            )

    def test_negative_policy_epoch_rejected(self, cid: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=cid,
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
                policy_epoch=-1,
            )

    def test_extra_field_rejected(self, cid: uuid.UUID) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=cid,
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
                extra_field="bad",  # type: ignore[call-arg]
            )

    def test_frozen_model(self, cid: uuid.UUID) -> None:
        fb = FallbackResponse(
            correlation_id=cid,
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            message_template_id="t",
            message="m",
        )
        with pytest.raises(ValidationError):
            fb.message = "changed"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# honesty_statement constant value
# ---------------------------------------------------------------------------


class TestHonestyStatement:
    """The honesty_statement constant has the exact required value."""

    def test_constant_value(self) -> None:
        assert (
            HONESTY_STATEMENT
            == "This is a limited deterministic response; its text was "
            "rendered from an approved template."
        )

    def test_default_on_response(self) -> None:
        fb = FallbackResponse(
            correlation_id=uuid.uuid4(),
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            message_template_id="t",
            message="m",
        )
        assert fb.honesty_statement == HONESTY_STATEMENT

    def test_rejects_wrong_honesty_statement(self) -> None:
        with pytest.raises(ValidationError):
            FallbackResponse(
                correlation_id=uuid.uuid4(),
                fallback_reason=FallbackReason.LLM_UNAVAILABLE,
                message_template_id="t",
                message="m",
                honesty_statement="This is a lie.",  # type: ignore[arg-type]
            )

    def test_honesty_statement_is_str(self) -> None:
        assert isinstance(HONESTY_STATEMENT, str)
        assert len(HONESTY_STATEMENT) > 0


# ---------------------------------------------------------------------------
# All FallbackReason enum values
# ---------------------------------------------------------------------------


class TestFallbackReasonEnum:
    """All FallbackReason values are present and correct."""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("BUDGET_SESSION_EXHAUSTED", "BUDGET_SESSION_EXHAUSTED"),
            ("BUDGET_WORKFLOW_EXHAUSTED", "BUDGET_WORKFLOW_EXHAUSTED"),
            ("BUDGET_CAPABILITY_EXHAUSTED", "BUDGET_CAPABILITY_EXHAUSTED"),
            ("LLM_UNAVAILABLE", "LLM_UNAVAILABLE"),
            ("POLICY_DENIED_FREE_TEXT", "POLICY_DENIED_FREE_TEXT"),
            ("CACHE_STALE", "CACHE_STALE"),
            ("OUTPUT_VALIDATION_FAILED", "OUTPUT_VALIDATION_FAILED"),
        ],
    )
    def test_reason_values(self, name: str, value: str) -> None:
        member = FallbackReason[name]
        assert member.value == value
        assert str(member) == value

    def test_reason_count(self) -> None:
        assert len(FallbackReason) == 7

    def test_reason_is_str_enum(self) -> None:
        assert isinstance(FallbackReason.LLM_UNAVAILABLE, str)

    def test_reason_lookup_by_value(self) -> None:
        assert (
            FallbackReason("LLM_UNAVAILABLE")
            is FallbackReason.LLM_UNAVAILABLE
        )


# ---------------------------------------------------------------------------
# All ReservationStatus enum values
# ---------------------------------------------------------------------------


class TestReservationStatusEnum:
    """All ReservationStatus values are present and correct."""

    @pytest.mark.parametrize(
        "name,value",
        [
            ("NOT_REQUIRED", "NOT_REQUIRED"),
            ("RESERVED", "RESERVED"),
            ("RECONCILED", "RECONCILED"),
            ("RELEASED", "RELEASED"),
            ("DENIED", "DENIED"),
        ],
    )
    def test_status_values(self, name: str, value: str) -> None:
        member = ReservationStatus[name]
        assert member.value == value
        assert str(member) == value

    def test_status_count(self) -> None:
        assert len(ReservationStatus) == 5

    def test_status_is_str_enum(self) -> None:
        assert isinstance(ReservationStatus.RESERVED, str)

    def test_status_lookup_by_value(self) -> None:
        assert (
            ReservationStatus("DENIED") is ReservationStatus.DENIED
        )


# ---------------------------------------------------------------------------
# Integration: FallbackResponse with all reason/status combinations
# ---------------------------------------------------------------------------


class TestFallbackResponseCombinations:
    """FallbackResponse works with all reason and status combinations."""

    @pytest.mark.parametrize("reason", list(FallbackReason))
    def test_all_reasons(self, reason: FallbackReason) -> None:
        fb = FallbackResponse(
            correlation_id=uuid.uuid4(),
            fallback_reason=reason,
            message_template_id="tmpl",
            message="msg",
        )
        assert fb.fallback_reason is reason

    @pytest.mark.parametrize("status", list(ReservationStatus))
    def test_all_statuses(self, status: ReservationStatus) -> None:
        fb = FallbackResponse(
            correlation_id=uuid.uuid4(),
            fallback_reason=FallbackReason.LLM_UNAVAILABLE,
            reservation_status=status,
            message_template_id="tmpl",
            message="msg",
        )
        assert fb.reservation_status is status
