"""Typed operational entities for the digital twin (P3, §3.1).

All entities are aggregate-only: no individual patient or staff data.
Each entity is a Pydantic v2 frozen, strict model with extra='forbid'.
Entities are serialised via the canonical contract (§3.5.2) for
deterministic state hashing.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

__all__ = [
    "EntityType",
    "Site",
    "Resource",
    "Queue",
    "Arrival",
    "ServiceCompletion",
    "OperationalSnapshot",
]


class EntityType(StrEnum):
    """Aggregate operational entity types (non-clinical, §2.7)."""

    SITE = "SITE"
    RESOURCE = "RESOURCE"
    QUEUE = "QUEUE"
    ARRIVAL = "ARRIVAL"
    SERVICE_COMPLETION = "SERVICE_COMPLETION"


class Site(BaseModel):
    """A generic operational site (e.g. research location)."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    site_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    capacity: int = Field(ge=0)
    active: bool = True


class Resource(BaseModel):
    """A generic operational resource at a site."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    resource_id: str = Field(min_length=1, max_length=64)
    site_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    capacity: int = Field(ge=0)
    available: int = Field(ge=0)
    active: bool = True


class Queue(BaseModel):
    """A generic operational queue at a site."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    queue_id: str = Field(min_length=1, max_length=64)
    site_id: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    current_length: int = Field(ge=0)
    total_arrivals: int = Field(ge=0)
    total_completions: int = Field(ge=0)
    capacity: int = Field(ge=0)


class Arrival(BaseModel):
    """A single arrival event in the simulation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    arrival_id: str = Field(min_length=1, max_length=64)
    site_id: str = Field(min_length=1, max_length=64)
    queue_id: str = Field(min_length=1, max_length=64)
    arrival_time: int = Field(ge=0)
    service_time: int = Field(ge=1)


class ServiceCompletion(BaseModel):
    """A single service completion event in the simulation."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    completion_id: str = Field(min_length=1, max_length=64)
    site_id: str = Field(min_length=1, max_length=64)
    queue_id: str = Field(min_length=1, max_length=64)
    arrival_id: str = Field(min_length=1, max_length=64)
    start_time: int = Field(ge=0)
    completion_time: int = Field(ge=0)
    wait_time: int = Field(ge=0)


class OperationalSnapshot(BaseModel):
    """An immutable snapshot of the full operational state at a time point."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    timestamp: int = Field(ge=0)
    sites: dict[str, Site] = Field(default_factory=dict)
    resources: dict[str, Resource] = Field(default_factory=dict)
    queues: dict[str, Queue] = Field(default_factory=dict)
    arrivals: list[Arrival] = Field(default_factory=list)
    completions: list[ServiceCompletion] = Field(default_factory=list)

    def to_canonical_dict(self) -> dict[str, Any]:
        """Serialise to a canonical JSON-serialisable dict for state hashing."""
        return {
            "timestamp": self.timestamp,
            "sites": {
                k: v.model_dump() for k, v in sorted(self.sites.items())
            },
            "resources": {
                k: v.model_dump() for k, v in sorted(self.resources.items())
            },
            "queues": {
                k: v.model_dump() for k, v in sorted(self.queues.items())
            },
            "arrivals": [a.model_dump() for a in self.arrivals],
            "completions": [
                c.model_dump() for c in self.completions
            ],
        }
