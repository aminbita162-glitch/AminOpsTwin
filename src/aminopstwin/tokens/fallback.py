"""Fallback response schema (§24.4).

Deterministic response when LLM is unavailable or budget exhausted.
The fallback response is rendered from an approved template, never
from an LLM.  It carries an honesty statement disclosing its
deterministic nature.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = [
    "FallbackReason",
    "ReservationStatus",
    "FallbackResponse",
    "HONESTY_STATEMENT",
]

#: Constant honesty statement disclosing the deterministic nature (§24.4).
HONESTY_STATEMENT: str = (
    "This is a limited deterministic response; its text was rendered "
    "from an approved template."
)


class FallbackReason(StrEnum):
    """Reason the deterministic fallback path was taken."""

    BUDGET_SESSION_EXHAUSTED = "BUDGET_SESSION_EXHAUSTED"
    BUDGET_WORKFLOW_EXHAUSTED = "BUDGET_WORKFLOW_EXHAUSTED"
    BUDGET_CAPABILITY_EXHAUSTED = "BUDGET_CAPABILITY_EXHAUSTED"
    LLM_UNAVAILABLE = "LLM_UNAVAILABLE"
    POLICY_DENIED_FREE_TEXT = "POLICY_DENIED_FREE_TEXT"
    CACHE_STALE = "CACHE_STALE"
    OUTPUT_VALIDATION_FAILED = "OUTPUT_VALIDATION_FAILED"


class ReservationStatus(StrEnum):
    """Status of a token reservation during the budget lifecycle."""

    NOT_REQUIRED = "NOT_REQUIRED"
    RESERVED = "RESERVED"
    RECONCILED = "RECONCILED"
    RELEASED = "RELEASED"
    DENIED = "DENIED"


class FallbackResponse(BaseModel):
    """Deterministic fallback response rendered from an approved template (§24.4).

    Sent when the LLM path is unavailable or budget is exhausted.
    Contains zero LLM-generated content.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    correlation_id: UUID
    path: Literal["deterministic"] = "deterministic"
    cache_hit: bool = False
    policy_decision: str = "DENY"
    policy_epoch: int = Field(default=0, ge=0)
    fallback_reason: FallbackReason
    reservation_status: ReservationStatus = ReservationStatus.NOT_REQUIRED
    message_template_id: str
    message: str
    tokens_used: int = Field(default=0, ge=0)
    tokens_budget_remaining: int = Field(default=0, ge=0)
    suggested_next_actions: list[str] = Field(default_factory=list)
    honesty_statement: str = HONESTY_STATEMENT

    @field_validator("honesty_statement")
    @classmethod
    def _validate_honesty(cls, v: str) -> str:
        if v != HONESTY_STATEMENT:
            raise ValueError(
                f"honesty_statement must be the constant: {HONESTY_STATEMENT!r}"
            )
        return v
