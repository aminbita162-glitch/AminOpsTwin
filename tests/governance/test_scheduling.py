"""P20 deterministic resource-aware scheduling test (deliverable 4).

Verifies that scheduling decisions depend only on integer priorities
and budgets, and that identical inputs produce identical schedules.
"""

from __future__ import annotations

import pytest
from aminopstwin.scheduling import (
    ScheduleRequest,
    schedule_requests,
)


class TestDeterministicScheduling:
    """P20 deliverable 4: deterministic resource-aware scheduling."""

    def test_identical_inputs_produce_identical_schedules(self) -> None:
        """Same inputs produce same ScheduleOrder hash."""
        requests = [
            ScheduleRequest("r1", priority=5, budget_cost=10, tenant_id="tenant-test"),
            ScheduleRequest("r2", priority=3, budget_cost=5, tenant_id="tenant-test"),
            ScheduleRequest("r3", priority=7, budget_cost=15, tenant_id="tenant-test"),
        ]
        order1 = schedule_requests(requests, total_budget=100)
        order2 = schedule_requests(requests, total_budget=100)
        assert order1.hash == order2.hash

    def test_higher_priority_scheduled_first(self) -> None:
        """Higher priority requests are scheduled first."""
        requests = [
            ScheduleRequest("low", priority=1, budget_cost=5, tenant_id="tenant-test"),
            ScheduleRequest(
                "high", priority=10, budget_cost=5, tenant_id="tenant-test"
            ),
            ScheduleRequest("med", priority=5, budget_cost=5, tenant_id="tenant-test"),
        ]
        order = schedule_requests(requests, total_budget=100)
        ids = order.request_ids
        assert ids[0] == "high"
        assert ids[1] == "med"
        assert ids[2] == "low"

    def test_lower_budget_cost_breaks_ties(self) -> None:
        """Lower budget_cost breaks priority ties."""
        requests = [
            ScheduleRequest(
                "expensive", priority=5, budget_cost=20, tenant_id="tenant-test"
            ),
            ScheduleRequest(
                "cheap", priority=5, budget_cost=5, tenant_id="tenant-test"
            ),
        ]
        order = schedule_requests(requests, total_budget=100)
        ids = order.request_ids
        assert ids[0] == "cheap"
        assert ids[1] == "expensive"

    def test_request_id_is_stable_tiebreaker(self) -> None:
        """request_id is the final stable tiebreaker."""
        requests = [
            ScheduleRequest("zzz", priority=5, budget_cost=5, tenant_id="tenant-test"),
            ScheduleRequest("aaa", priority=5, budget_cost=5, tenant_id="tenant-test"),
            ScheduleRequest("mmm", priority=5, budget_cost=5, tenant_id="tenant-test"),
        ]
        order = schedule_requests(requests, total_budget=100)
        ids = order.request_ids
        assert ids == ["aaa", "mmm", "zzz"]

    def test_schedule_hash_is_deterministic(self) -> None:
        """Schedule hash is deterministic across calls."""
        requests = [
            ScheduleRequest("r1", priority=5, budget_cost=10, tenant_id="tenant-test"),
            ScheduleRequest("r2", priority=3, budget_cost=5, tenant_id="tenant-test"),
        ]
        order1 = schedule_requests(requests, total_budget=50)
        order2 = schedule_requests(requests, total_budget=50)
        assert order1.hash == order2.hash

    def test_empty_requests_produce_empty_schedule(self) -> None:
        """Empty request list produces empty schedule."""
        order = schedule_requests([], total_budget=100)
        assert order.entries == []
        assert order.request_ids == []

    def test_replay_confirms_schedule_identity(self) -> None:
        """Replay test: identical inputs produce identical schedule order."""
        requests = [
            ScheduleRequest(
                f"r{i}", priority=i * 2, budget_cost=i * 3, tenant_id="tenant-test"
            )
            for i in range(1, 11)
        ]
        order1 = schedule_requests(requests, total_budget=1000)
        order2 = schedule_requests(requests, total_budget=1000)
        # Position-by-position comparison
        for e1, e2 in zip(order1.entries, order2.entries, strict=True):
            assert e1.request_id == e2.request_id
            assert e1.position == e2.position
        assert order1.hash == order2.hash

    def test_total_budget_zero_admits_nothing_but_orders(self) -> None:
        """Budget=0 still produces a deterministic order."""
        requests = [
            ScheduleRequest("r1", priority=5, budget_cost=10, tenant_id="tenant-test"),
            ScheduleRequest("r2", priority=3, budget_cost=5, tenant_id="tenant-test"),
        ]
        order = schedule_requests(requests, total_budget=0)
        # All requests are still listed in order
        assert len(order.entries) == 2
        assert order.request_ids == ["r1", "r2"]

    def test_negative_budget_raises(self) -> None:
        """Negative total_budget raises ValueError."""
        with pytest.raises(ValueError):
            schedule_requests([], total_budget=-1)

    def test_schedule_order_to_dict(self) -> None:
        """ScheduleOrder.to_dict produces the expected structure."""
        requests = [
            ScheduleRequest("r1", priority=5, budget_cost=10, tenant_id="tenant-test"),
        ]
        order = schedule_requests(requests, total_budget=100)
        d = order.to_dict()
        assert "entries" in d
        assert len(d["entries"]) == 1
        assert d["entries"][0]["request_id"] == "r1"
