"""F05: Out-of-order events → reordered by sequence_no (G2.9).

Scenario: Events arrive out of order. The buffer reorders them by
sequence_no within the allowed window and delivers them in order.
"""

from __future__ import annotations

import pytest
from tests.fault.infrastructure import OrderedEvent, OrderedEventBuffer


class TestF05OutOfOrderEvents:
    """F05: Out-of-order events reordered by sequence_no."""

    def test_reorder_simple(self) -> None:
        buf = OrderedEventBuffer(allowed_window=10)
        buf.push(OrderedEvent(0, "start"))
        buf.push(OrderedEvent(2, "end"))
        buf.push(OrderedEvent(1, "middle"))

        delivered = buf.delivered
        assert len(delivered) == 3
        assert [e.sequence_no for e in delivered] == [0, 1, 2]
        assert [e.event_type for e in delivered] == ["start", "middle", "end"]

    def test_reorder_complex(self) -> None:
        buf = OrderedEventBuffer(allowed_window=20)
        # Push in reverse order
        for i in range(5, -1, -1):
            buf.push(OrderedEvent(i, f"event-{i}"))

        delivered = buf.delivered
        assert len(delivered) == 6
        assert [e.sequence_no for e in delivered] == [0, 1, 2, 3, 4, 5]

    def test_out_of_window_rejected(self) -> None:
        buf = OrderedEventBuffer(allowed_window=5)
        buf.push(OrderedEvent(0, "first"))
        # Event with sequence_no=10 is outside the window (0+5=5)
        with pytest.raises(ValueError):
            buf.push(OrderedEvent(10, "far_future"))

    def test_partial_delivery(self) -> None:
        """Events are delivered as they become contiguous."""
        buf = OrderedEventBuffer(allowed_window=10)
        buf.push(OrderedEvent(1, "second"))
        buf.push(OrderedEvent(2, "third"))
        # Event 0 hasn't arrived yet — nothing delivered
        assert len(buf.delivered) == 0

        buf.push(OrderedEvent(0, "first"))
        # Now all three can be delivered in order
        assert len(buf.delivered) == 3
        assert [e.sequence_no for e in buf.delivered] == [0, 1, 2]

    def test_delivered_in_order(self) -> None:
        buf = OrderedEventBuffer(allowed_window=100)
        events = [3, 1, 4, 1, 5, 9, 2, 6, 8, 0, 7]
        # Deduplicate — each sequence_no should be unique
        events = list(range(11))
        import random
        rng = random.Random(42)
        rng.shuffle(events)
        for seq in events:
            buf.push(OrderedEvent(seq, f"event-{seq}"))

        delivered = buf.delivered
        assert [e.sequence_no for e in delivered] == list(range(11))
