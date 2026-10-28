"""Request context — explicit tenant and causation propagation (P26).

Every agent and every Gateway call receives a RequestContext that
carries the tenant_id and the causation_id. The tenant is never
hard-coded; it comes from the caller's context.

The previous hard-coded tenant default was removed (P26).
The caller must supply the tenant_id explicitly via RequestContext.
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
