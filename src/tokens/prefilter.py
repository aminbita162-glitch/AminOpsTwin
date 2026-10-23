"""Pre-filter skeleton (§4.1) — mandatory non-bypassable pre-filter order.

The fixed order is:
    schema validation -> Policy Gateway -> evidence cache lookup ->
    invariant check -> budget check.

Only survivors reach an LLM. This module defines the order and the stage labels;
the actual budget and cache logic arrive in P2/P3.
"""

from __future__ import annotations

from enum import Enum

__all__ = ["PreFilterStage", "PREFILTER_ORDER"]


class PreFilterStage(str, Enum):
    """Stages of the mandatory pre-filter (§4.1), in fixed order."""

    SCHEMA = "schema"
    GATEWAY = "gateway"
    CACHE = "cache"
    INVARIANT = "invariant"
    BUDGET = "budget"
    OUTPUT = "output"


PREFILTER_ORDER: tuple[PreFilterStage, ...] = (
    PreFilterStage.SCHEMA,
    PreFilterStage.GATEWAY,
    PreFilterStage.CACHE,
    PreFilterStage.INVARIANT,
    PreFilterStage.BUDGET,
    PreFilterStage.OUTPUT,
)


def prefilter_order_valid(stages: list[PreFilterStage]) -> bool:
    """Return True if *stages* match the mandatory pre-filter order exactly."""
    return tuple(stages) == PREFILTER_ORDER
