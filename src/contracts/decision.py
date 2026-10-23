"""DecisionRecord (§3.9) — exact output of the Policy Gateway's evaluation.

A DecisionRecord captures the result of a Gateway decision:
    decision (ALLOW|DENY), stage, reason_code, secondary_codes, policy_epoch,
    rule_ids, correlation_id, principal, payload_hash, decided_at.

A DENY always has a reason_code; an ALLOW never has one.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

__all__ = ["Decision", "Stage", "DecisionRecord"]


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"


class Stage(str, Enum):
    SCHEMA = "SCHEMA"
    GATEWAY = "GATEWAY"
    CACHE = "CACHE"
    INVARIANT = "INVARIANT"
    BUDGET = "BUDGET"
    OUTPUT = "OUTPUT"


class DecisionRecord(BaseModel):
    """Exact record of a single Gateway decision (§3.9)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    decision: Decision
    stage: Stage
    reason_code: str | None = None
    secondary_codes: list[str] = Field(default_factory=list)
    policy_epoch: int = Field(ge=0)
    rule_ids: list[str] = Field(default_factory=list)
    correlation_id: uuid.UUID
    principal: str
    payload_hash: str
    decided_at: datetime

    @field_validator("reason_code")
    @classmethod
    def _validate_reason_code(cls, v: str | None, info) -> str | None:  # type: ignore[no-untyped-def]
        # info.data has the validated values so far
        decision = info.data.get("decision")
        if decision == Decision.DENY and v is None:
            raise ValueError("a DENY must always have a reason_code")
        if decision == Decision.ALLOW and v is not None:
            raise ValueError("an ALLOW must never have a reason_code")
        return v

    @field_validator("decided_at")
    @classmethod
    def _validate_decided_at(cls, v: datetime) -> datetime:
        if v.tzinfo is None:
            raise ValueError("decided_at must be timezone-aware (UTC)")
        return v
