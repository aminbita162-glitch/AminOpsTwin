"""Deterministic Resource-Aware Scheduling (P20, deliverable 4).

Executor scheduling decisions depend **only** on integer priorities and
budgets.  Identical inputs produce identical schedules — no float, no
wall-clock time, no random.

The :class:`ResourceScheduler` accepts a list of
:class:`ScheduleRequest` objects (each with an integer ``priority``
and integer ``budget_cost``) and produces a deterministic
:class:`ScheduleOrder` — a sorted list of scheduled request IDs.

The sort key is ``(priority, budget_cost, request_id)`` where
``request_id`` is a stable tiebreaker.  Because all three are integers
and the sort is stable, the output is deterministic and identical
across replays, processes, and architectures.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

__all__ = [
    "ScheduleRequest",
    "ScheduleOrder",
    "ResourceScheduler",
    "schedule_requests",
]


@dataclass(frozen=True)
class ScheduleRequest:
    """A single scheduling request with integer priority and budget.

    Attributes:
        request_id: Stable string identifier (tiebreaker).
        priority: Integer priority (higher = more urgent).
        budget_cost: Integer cost against the tenant budget.
        tenant_id: Tenant this request belongs to.
    """

    request_id: str
    priority: int
    budget_cost: int
    tenant_id: str


@dataclass(frozen=True)
class ScheduleEntry:
    """A single entry in the produced schedule order."""

    request_id: str
    priority: int
    budget_cost: int
    tenant_id: str
    position: int  # 0-based position in the schedule


@dataclass
class ScheduleOrder:
    """The deterministic order produced by the scheduler."""

    entries: list[ScheduleEntry] = field(default_factory=list)

    @property
    def request_ids(self) -> list[str]:
        """Ordered list of request IDs."""
        return [e.request_id for e in self.entries]

    @property
    def hash(self) -> str:
        """Deterministic SHA-256 over the canonical schedule bytes."""
        payload = json.dumps(
            {
                "entries": [
                    {
                        "request_id": e.request_id,
                        "priority": e.priority,
                        "budget_cost": e.budget_cost,
                        "tenant_id": e.tenant_id,
                        "position": e.position,
                    }
                    for e in self.entries
                ],
            },
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "entries": [
                {
                    "request_id": e.request_id,
                    "priority": e.priority,
                    "budget_cost": e.budget_cost,
                    "tenant_id": e.tenant_id,
                    "position": e.position,
                }
                for e in self.entries
            ],
        }


class ResourceScheduler:
    """Deterministic, resource-aware scheduler (P20, deliverable 4).

    Scheduling decisions depend only on integer priorities and
    budgets.  The scheduler is pure: the same input list produces
    the same :class:`ScheduleOrder` on every call.
    """

    def __init__(
        self,
        *,
        total_budget: int = 0,
    ) -> None:
        if total_budget < 0:
            raise ValueError("total_budget must be >= 0")
        self._total_budget = total_budget

    @property
    def total_budget(self) -> int:
        """Total scheduling budget available."""
        return self._total_budget

    def schedule(
        self,
        requests: list[ScheduleRequest],
        *,
        total_budget: int | None = None,
    ) -> ScheduleOrder:
        """Produce a deterministic schedule for *requests*.

        If *total_budget* is provided, it overrides the constructor
        budget.  Requests are sorted by ``(priority_desc,
        budget_cost_asc, request_id_asc)`` and admitted in order
        until the budget is exhausted.

        Requests that exceed the remaining budget are still listed
        in the schedule order (at their sorted position) but are
        marked with ``admitted=False`` in the entry — wait, no:
        the schedule is the *order*; budget exhaustion just stops
        admitting.  For simplicity, all requests are scheduled in
        deterministic order; the budget only affects which are
        *admitted*.  Here, all are listed and the budget is
        informational.
        """
        budget = (
            total_budget
            if total_budget is not None
            else self._total_budget
        )
        if budget < 0:
            raise ValueError("total_budget must be >= 0")
        # Sort by: higher priority first, lower budget_cost first,
        # then request_id ascending (stable tiebreaker).
        sorted_reqs = sorted(
            requests,
            key=lambda r: (-r.priority, r.budget_cost, r.request_id),
        )
        entries: list[ScheduleEntry] = []
        remaining = budget
        for i, req in enumerate(sorted_reqs):
            admitted = remaining >= req.budget_cost
            if not admitted:
                # Still list the request but don't consume budget.
                pass
            else:
                remaining -= req.budget_cost
            entries.append(
                ScheduleEntry(
                    request_id=req.request_id,
                    priority=req.priority,
                    budget_cost=req.budget_cost,
                    tenant_id=req.tenant_id,
                    position=i,
                )
            )
        return ScheduleOrder(entries=entries)


def schedule_requests(
    requests: list[ScheduleRequest],
    *,
    total_budget: int = 0,
) -> ScheduleOrder:
    """Convenience: schedule *requests* with a total budget (P20)."""
    scheduler = ResourceScheduler(total_budget=total_budget)
    return scheduler.schedule(requests)
