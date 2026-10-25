"""Transparency contract for all response types (P8, G5.5, §4.5).

Every response type — including fallback, cache, deterministic, and
pipeline paths — must contain the unified transparency fields from
§4.5.  This module provides a reusable transparency response builder
and a verification function.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from aminopstwin.tokens.fallback import (
    FallbackReason,
    ReservationStatus,
)

__all__ = [
    "TransparencyResponse",
    "TransparencyError",
    "build_transparency_response",
    "TRANSPARENCY_REQUIRED_FIELDS",
]


class TransparencyError(Exception):
    """Raised when a response is missing required transparency fields."""


#: Required transparency fields (§4.5).
TRANSPARENCY_REQUIRED_FIELDS: tuple[str, ...] = (
    "correlation_id",
    "path",
    "cache_hit",
    "policy_decision",
    "policy_epoch",
    "fallback_reason",
    "reservation_status",
    "tokens_used",
    "tokens_budget_remaining",
)


class ResponsePath(StrEnum):
    """Path enum for transparency responses (§4.5)."""

    DETERMINISTIC = "deterministic"
    TEMPLATE = "template"
    CACHE = "cache"
    LLM = "llm"


@dataclass
class TransparencyResponse:
    """A response with all required transparency fields (§4.5).

    Every response type includes these unified metadata fields so
    that token usage, cache status, policy decision, and fallback
    reason are always visible.
    """

    correlation_id: str
    path: str
    cache_hit: bool
    policy_decision: str
    policy_epoch: int
    fallback_reason: str | None
    reservation_status: str
    tokens_used: int
    tokens_budget_remaining: int
    extra_fields: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "correlation_id": self.correlation_id,
            "path": self.path,
            "cache_hit": self.cache_hit,
            "policy_decision": self.policy_decision,
            "policy_epoch": self.policy_epoch,
            "fallback_reason": self.fallback_reason,
            "reservation_status": self.reservation_status,
            "tokens_used": self.tokens_used,
            "tokens_budget_remaining": self.tokens_budget_remaining,
            **self.extra_fields,
        }

    def verify(self) -> bool:
        """Verify that all required transparency fields are present."""
        for field_name in TRANSPARENCY_REQUIRED_FIELDS:
            value = getattr(self, field_name, None)
            if value is None and field_name not in (
                "fallback_reason",
            ):
                raise TransparencyError(
                    f"Missing required field: {field_name}"
                )
        return True


def build_transparency_response(
    *,
    correlation_id: str | uuid.UUID | None = None,
    path: str = "deterministic",
    cache_hit: bool = False,
    policy_decision: str = "ALLOW",
    policy_epoch: int = 0,
    fallback_reason: FallbackReason | str | None = None,
    reservation_status: ReservationStatus | str = ReservationStatus.NOT_REQUIRED,
    tokens_used: int = 0,
    tokens_budget_remaining: int = 0,
    **extra: Any,
) -> TransparencyResponse:
    """Build a transparency response with all required fields."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    elif isinstance(correlation_id, uuid.UUID):
        correlation_id = str(correlation_id)

    if isinstance(fallback_reason, FallbackReason):
        fallback_reason = fallback_reason.value

    if isinstance(reservation_status, ReservationStatus):
        reservation_status = reservation_status.value

    return TransparencyResponse(
        correlation_id=correlation_id,
        path=path,
        cache_hit=cache_hit,
        policy_decision=policy_decision,
        policy_epoch=policy_epoch,
        fallback_reason=fallback_reason,
        reservation_status=reservation_status,
        tokens_used=tokens_used,
        tokens_budget_remaining=tokens_budget_remaining,
        extra_fields=dict(extra),
    )
