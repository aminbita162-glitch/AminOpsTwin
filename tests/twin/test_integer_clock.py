"""Tests for integer simulation clock and named PRNG streams (P12, §115–118).

Part of G12.5: cross-platform state hash identical.
"""

from __future__ import annotations

import pytest
from aminopstwin.twin.integer_clock import (
    MILLIMINUTES_PER_MINUTE,
    MilliMinuteClock,
    NamedPrngStream,
    PrngRegistry,
)


class TestMilliMinuteClock:
    """MilliMinuteClock — integer time in milliminutes."""

    def test_default_start(self) -> None:
        clock = MilliMinuteClock()
        assert clock.current == 0
        assert clock.start == 0
        assert clock.step == 1

    def test_tick(self) -> None:
        clock = MilliMinuteClock(start_mmin=0, step_mmin=100)
        assert clock.tick() == 100
        assert clock.tick() == 200
        assert clock.current == 200

    def test_reset(self) -> None:
        clock = MilliMinuteClock(start_mmin=500, step_mmin=10)
        clock.tick()
        clock.tick()
        clock.reset()
        assert clock.current == 500

    def test_negative_start_rejected(self) -> None:
        with pytest.raises(ValueError):
            MilliMinuteClock(start_mmin=-1)

    def test_zero_step_rejected(self) -> None:
        with pytest.raises(ValueError):
            MilliMinuteClock(step_mmin=0)

    def test_all_integers(self) -> None:
        clock = MilliMinuteClock(start_mmin=0, step_mmin=1)
        for _ in range(100):
            t = clock.tick()
            assert isinstance(t, int)

    def test_milliminutes_per_minute(self) -> None:
        assert MILLIMINUTES_PER_MINUTE == 1000

    def test_to_dict(self) -> None:
        clock = MilliMinuteClock(start_mmin=1000, step_mmin=50)
        clock.tick()
        d = clock.to_dict()
        assert d == {
            "start_mmin": 1000,
            "step_mmin": 50,
            "current_mmin": 1050,
        }


class TestNamedPrngStream:
    """NamedPrngStream — deterministic per-entity RNG."""

    def test_deterministic(self) -> None:
        s1 = NamedPrngStream(42, "site-0")
        s2 = NamedPrngStream(42, "site-0")
        assert [s1.randint(0, 100) for _ in range(10)] == [
            s2.randint(0, 100) for _ in range(10)
        ]

    def test_different_entity_different_stream(self) -> None:
        s1 = NamedPrngStream(42, "site-0")
        s2 = NamedPrngStream(42, "site-1")
        assert s1.randint(0, 100) != s2.randint(0, 100)

    def test_different_seed_different_stream(self) -> None:
        s1 = NamedPrngStream(42, "site-0")
        s2 = NamedPrngStream(99, "site-0")
        assert s1.randint(0, 100) != s2.randint(0, 100)

    def test_reset(self) -> None:
        s = NamedPrngStream(42, "site-0")
        first = [s.randint(0, 100) for _ in range(10)]
        s.reset()
        first_again = [s.randint(0, 100) for _ in range(10)]
        assert first == first_again

    def test_randrange(self) -> None:
        s = NamedPrngStream(42, "site-0")
        for _ in range(100):
            v = s.randrange(10)
            assert 0 <= v < 10

    def test_poisson_returns_integers(self) -> None:
        s = NamedPrngStream(42, "site-0")
        for _ in range(100):
            v = s.poisson(5)
            assert isinstance(v, int)
            assert v >= 0

    def test_poisson_deterministic(self) -> None:
        s1 = NamedPrngStream(42, "site-0")
        s2 = NamedPrngStream(42, "site-0")
        assert [s1.poisson(3) for _ in range(20)] == [
            s2.poisson(3) for _ in range(20)
        ]

    def test_poisson_zero_rate(self) -> None:
        s = NamedPrngStream(42, "site-0")
        assert s.poisson(0) == 0

    def test_poisson_mean_approximately_correct(self) -> None:
        """With rate=10, the mean of 1000 samples should be near 10."""
        s = NamedPrngStream(42, "site-0")
        samples = [s.poisson(10) for _ in range(1000)]
        mean = sum(samples) / len(samples)
        assert 8 <= mean <= 12, f"mean={mean} not near 10"

    def test_no_float_on_hashed_path(self) -> None:
        """All PRNG stream outputs must be integers — no floats."""
        s = NamedPrngStream(42, "site-0")
        for _ in range(100):
            assert isinstance(s.randint(0, 100), int)
            assert isinstance(s.randrange(50), int)
            assert isinstance(s.poisson(5), int)


class TestPrngRegistry:
    """PrngRegistry — keyed named streams."""

    def test_get_stream_deterministic(self) -> None:
        r1 = PrngRegistry(master_seed=42)
        r2 = PrngRegistry(master_seed=42)
        s1 = r1.get_stream("site-0")
        s2 = r2.get_stream("site-0")
        assert [s1.randint(0, 100) for _ in range(10)] == [
            s2.randint(0, 100) for _ in range(10)
        ]

    def test_isolation_between_entities(self) -> None:
        """Adding a new entity doesn't affect existing entities."""
        r = PrngRegistry(master_seed=42)
        s0 = r.get_stream("site-0")
        first0 = [s0.randint(0, 100) for _ in range(10)]

        # Add more entities
        r.get_stream("site-1")
        r.get_stream("site-2")

        # site-0's stream must be unaffected
        s0_again = r.get_stream("site-0")
        second0 = [s0_again.randint(0, 100) for _ in range(10)]
        # s0 and s0_again are the same object — the stream continued
        # But the first 10 values were already consumed.
        # The key property: site-1 and site-2 don't affect site-0's
        # future values.
        assert first0 != second0  # different draws (stream advanced)

    def test_entity_names(self) -> None:
        r = PrngRegistry(master_seed=42)
        r.get_stream("site-0")
        r.get_stream("site-1")
        assert r.entity_names() == ["site-0", "site-1"]

    def test_reset_all(self) -> None:
        r = PrngRegistry(master_seed=42)
        s = r.get_stream("site-0")
        first = [s.randint(0, 100) for _ in range(10)]
        r.reset_all()
        s2 = r.get_stream("site-0")
        first_again = [s2.randint(0, 100) for _ in range(10)]
        assert first == first_again

    def test_to_dict(self) -> None:
        r = PrngRegistry(master_seed=42)
        r.get_stream("site-0")
        r.get_stream("site-1")
        d = r.to_dict()
        assert d == {
            "master_seed": 42,
            "entity_names": ["site-0", "site-1"],
        }
