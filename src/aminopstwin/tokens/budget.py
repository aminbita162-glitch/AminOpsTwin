"""Budget Governor (§4.2, G2.5) — three-level token budget enforcement.

Limits are checked at three levels: session, workflow, and capability.
Each reservation is atomic; when exhausted, the governor returns a
deterministic fallback response with zero LLM calls.
"""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import Final

from aminopstwin.tokens.fallback import (
    HONESTY_STATEMENT,
    FallbackReason,
    FallbackResponse,
    ReservationStatus,
)

__all__ = ["BudgetLevel", "BudgetGovernor"]

#: Default fallback message template id used by the governor.
_FALLBACK_TEMPLATE_ID: Final[str] = "fallback.budget_exhausted.v1"

#: Default fallback message body.
_FALLBACK_MESSAGE: Final[str] = (
    "The token budget for this request has been exhausted. "
    "No LLM call was made."
)


class BudgetLevel(StrEnum):
    """Three-level budget hierarchy (most to least granular)."""

    SESSION = "SESSION"
    WORKFLOW = "WORKFLOW"
    CAPABILITY = "CAPABILITY"


class BudgetGovernor:
    """Three-level token budget governor with atomic reservation.

    Tracks session, workflow, and capability budgets. When any level
    is exhausted, ``get_fallback`` returns a deterministic
    :class:`FallbackResponse` with zero LLM calls (G2.5).
    """

    def __init__(
        self,
        session_budget: int,
        workflow_budget: int,
        capability_budget: int,
    ) -> None:
        if session_budget < 0 or workflow_budget < 0 or capability_budget < 0:
            raise ValueError("budgets must be non-negative")
        self._session_budget: int = session_budget
        self._workflow_budget: int = workflow_budget
        self._capability_budget: int = capability_budget
        self._session_remaining: int = session_budget
        self._workflow_remaining: int = workflow_budget
        self._capability_remaining: int = capability_budget
        self._session_used: int = 0
        self._workflow_used: int = 0
        self._capability_used: int = 0

    @property
    def session_budget(self) -> int:
        return self._session_budget

    @property
    def workflow_budget(self) -> int:
        return self._workflow_budget

    @property
    def capability_budget(self) -> int:
        return self._capability_budget

    def _remaining_ref(self, level: BudgetLevel) -> int:
        if level is BudgetLevel.SESSION:
            return self._session_remaining
        if level is BudgetLevel.WORKFLOW:
            return self._workflow_remaining
        return self._capability_remaining

    def _set_remaining(self, level: BudgetLevel, value: int) -> None:
        if level is BudgetLevel.SESSION:
            self._session_remaining = value
        elif level is BudgetLevel.WORKFLOW:
            self._workflow_remaining = value
        else:
            self._capability_remaining = value

    def _used_ref(self, level: BudgetLevel) -> int:
        if level is BudgetLevel.SESSION:
            return self._session_used
        if level is BudgetLevel.WORKFLOW:
            return self._workflow_used
        return self._capability_used

    def _set_used(self, level: BudgetLevel, value: int) -> None:
        if level is BudgetLevel.SESSION:
            self._session_used = value
        elif level is BudgetLevel.WORKFLOW:
            self._workflow_used = value
        else:
            self._capability_used = value

    def remaining(self, level: BudgetLevel) -> int:
        """Return the remaining budget at *level*."""
        return self._remaining_ref(level)

    def is_exhausted(self, level: BudgetLevel) -> bool:
        """Return True if the budget at *level* is exhausted (remaining == 0)."""
        return self._remaining_ref(level) <= 0

    def reserve(self, level: BudgetLevel, amount: int) -> bool:
        """Atomically reserve *amount* tokens at *level*.

        Returns True if the reservation succeeded, False if the budget
        at *level* cannot accommodate the request.
        """
        if amount < 0:
            raise ValueError("amount must be non-negative")
        if amount == 0:
            return True
        if self._remaining_ref(level) < amount:
            return False
        self._set_remaining(level, self._remaining_ref(level) - amount)
        self._set_used(level, self._used_ref(level) + amount)
        return True

    def reconcile(self, level: BudgetLevel, amount: int, actual: int) -> None:
        """Reconcile actual usage after an LLM call.

        Releases the difference between the reserved *amount* and the
        *actual* tokens consumed back to the budget at *level*.
        """
        if actual < 0:
            raise ValueError("actual must be non-negative")
        if amount < 0:
            raise ValueError("amount must be non-negative")
        diff = amount - actual
        if diff > 0:
            self._set_remaining(level, self._remaining_ref(level) + diff)
        self._set_used(level, self._used_ref(level) - amount + actual)

    def get_fallback(
        self,
        correlation_id: uuid.UUID,
        policy_epoch: int,
        reason: FallbackReason | None = None,
    ) -> FallbackResponse:
        """Return a deterministic fallback response with zero LLM calls (G2.5)."""
        if reason is None:
            reason = FallbackReason.BUDGET_SESSION_EXHAUSTED
        return FallbackResponse(
            correlation_id=correlation_id,
            path="deterministic",
            cache_hit=False,
            policy_decision="DENY",
            policy_epoch=policy_epoch,
            fallback_reason=reason,
            reservation_status=ReservationStatus.DENIED,
            message_template_id=_FALLBACK_TEMPLATE_ID,
            message=_FALLBACK_MESSAGE,
            tokens_used=0,
            tokens_budget_remaining=self.remaining(BudgetLevel.SESSION),
            suggested_next_actions=[
                "Retry with a higher budget allocation",
                "Use deterministic fallback path",
            ],
            honesty_statement=HONESTY_STATEMENT,
        )
