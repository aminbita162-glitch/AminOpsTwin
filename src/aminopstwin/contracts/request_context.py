"""Request context — explicit tenant and causation propagation (P26).

Every agent and every Gateway call receives a RequestContext that
carries the tenant_id and the causation_id. The tenant is never
hard-coded; it comes from the caller's context.

This replaces the previous hard-coded ``"tenant-default"`` default
(ADR-008, ADR-007). The single-tenant sentinel ``TENANT_DEFAULT`` in
clock.py remains as a constant, but it is no longer the implicit default
for agent and gateway calls — the caller must supply it explicitly.
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

__all__ = ["RequestContext"]


class RequestContext(BaseModel):
    """Explicit request context carrying tenant and causation (P26).

    model_config: frozen, strict, extra="forbid".

    The tenant_id comes from the caller, never from a hard-coded
    default. The causation_id propagates from the parent envelope.
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    tenant_id: str = Field(min_length=1, max_length=64)
    causation_id: uuid.UUID | None = None
    policy_epoch: int = Field(default=0, ge=0)
