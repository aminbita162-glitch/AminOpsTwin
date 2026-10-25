"""G16.4 — Fixed-point paths clean and working calendar (P16).

Tests for the :class:`Fixed` fixed-point numeric type and the
:class:`WorkingCalendar` / :class:`MilliMinuteClock` working calendar.
Verifies that no float appears on the hashed state path and that
the working calendar correctly skips non-working intervals using
only integer arithmetic.
"""

from __future__ import annotations

import pytest
from aminopstwin.twin.fixed_point import (
    DEFAULT_SCALE,
    Fixed,
    detect_floats,
)
from aminopstwin.twin.integer_clock import (
    MilliMinuteClock,
    NonWorkingInterval,
    WorkingCalendar,
)


class TestFixed:
    """Fixed — scaled integer fixed-point type."""

    def test_construct_from_int(self) -> None:
        f = Fixed(5, scale=100)
        assert f.raw == 500
        assert f.scale == 100

    def test_construct_from_float(self) -> None:
        f = Fixed(1.5, scale=100)
        assert f.raw == 150
        assert f.scale == 100

    def test_default_scale(self) -> None:
        f = Fixed(1.0)
        assert f.raw == DEFAULT_SCALE
        assert f.scale == DEFAULT_SCALE

    def test_raw_is_int(self) -> None:
        f = Fixed(3.14, scale=100)
        assert isinstance(f.raw, int)
        assert not isinstance(f.raw, float)

    def test_to_dict_no_floats(self) -> None:
        f = Fixed(2.5)
        d = f.to_dict()
        # detect_floats returns empty list if no floats
        assert detect_floats(d) == []
        assert d == {"raw": f.raw, "scale": f.scale}

    def test_from_dict_roundtrip(self) -> None:
        f1 = Fixed(3.14, scale=100)
        d = f1.to_dict()
        f2 = Fixed.from_dict(d)
        assert f1 == f2

    def test_from_raw(self) -> None:
        f = Fixed.from_raw(500, scale=100)
        assert f.raw == 500
        assert isinstance(f.raw, int)

    def test_add(self) -> None:
        a = Fixed(1.5, scale=100)
        b = Fixed(2.5, scale=100)
        c = a + b
        assert c.raw == 400
        assert isinstance(c.raw, int)

    def test_sub(self) -> None:
        a = Fixed(3.0, scale=100)
        b = Fixed(1.0, scale=100)
        c = a - b
        assert c.raw == 200

    def test_mul(self) -> None:
        a = Fixed(2.5, scale=100)
        c = a * 3
        assert c.raw == 750

    def test_eq(self) -> None:
        a = Fixed(1.0, scale=100)
        b = Fixed(1.0, scale=100)
        assert a == b

    def test_neq_different_scale(self) -> None:
        a = Fixed(1.0, scale=100)
        b = Fixed(1.0, scale=1000)
        assert a != b

    def test_bool_rejected(self) -> None:
        with pytest.raises(TypeError):
            Fixed(True)

    def test_scale_must_be_positive(self) -> None:
        with pytest.raises(ValueError):
            Fixed(1, scale=0)

    def test_hash(self) -> None:
        a = Fixed(1.0, scale=100)
        b = Fixed(1.0, scale=100)
        assert hash(a) == hash(b)

    def test_repr(self) -> None:
        f = Fixed(1.5, scale=100)
        assert "Fixed(" in repr(f)


class TestFloatDetection:
    """detect_floats — recursively find floats in nested structures."""

    def test_no_floats(self) -> None:
        data = {"a": 1, "b": "str", "c": [1, 2, 3], "d": True}
        assert detect_floats(data) == []

    def test_detect_top_level_float(self) -> None:
        data = 1.5
        assert detect_floats(data) == ["<root>"]

    def test_detect_nested_float_in_dict(self) -> None:
        data = {"a": {"b": 1.5}}
        assert "a.b" in detect_floats(data)

    def test_detect_float_in_list(self) -> None:
        data = {"items": [1, 2, 3.0]}
        paths = detect_floats(data)
        assert any("items" in p for p in paths)

    def test_bool_not_flagged_as_float(self) -> None:
        data = {"a": True, "b": False}
        assert detect_floats(data) == []

    def test_int_not_flagged(self) -> None:
        data = {"a": 42}
        assert detect_floats(data) == []


class TestWorkingCalendar:
    """WorkingCalendar — non-working interval skipping."""

    def test_interval_contains(self) -> None:
        iv = NonWorkingInterval(start_mmin=100, end_mmin=200)
        assert iv.contains(100)
        assert iv.contains(150)
        assert iv.contains(199)
        assert not iv.contains(200)
        assert not iv.contains(99)

    def test_interval_validation(self) -> None:
        with pytest.raises(ValueError):
            NonWorkingInterval(start_mmin=-1, end_mmin=10)
        with pytest.raises(ValueError):
            NonWorkingInterval(start_mmin=10, end_mmin=10)
        with pytest.raises(ValueError):
            NonWorkingInterval(start_mmin=10, end_mmin=5)

    def test_is_working(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=100, end_mmin=200)]
        )
        assert cal.is_working(50)
        assert not cal.is_working(100)
        assert not cal.is_working(150)
        assert cal.is_working(200)

    def test_next_working(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=100, end_mmin=200)]
        )
        assert cal.next_working(50) == 50
        assert cal.next_working(100) == 200
        assert cal.next_working(150) == 200
        assert cal.next_working(200) == 200

    def test_clock_without_calendar(self) -> None:
        clock = MilliMinuteClock(start_mmin=0, step_mmin=10)
        assert clock.tick() == 10
        assert clock.tick() == 20

    def test_clock_with_calendar_skips(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=100, end_mmin=200)]
        )
        clock = MilliMinuteClock(
            start_mmin=0, step_mmin=50, calendar=cal
        )
        # 0 -> 50 (working)
        assert clock.tick() == 50
        # 50 -> 100, but 100 is non-working -> skip to 200
        assert clock.tick() == 200
        # 200 -> 250 (working)
        assert clock.tick() == 250

    def test_clock_start_in_non_working(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=0, end_mmin=100)]
        )
        clock = MilliMinuteClock(
            start_mmin=50, step_mmin=10, calendar=cal
        )
        # Start at 50 is non-working -> skip to 100
        assert clock.current == 100

    def test_clock_all_integers(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=100, end_mmin=200)]
        )
        clock = MilliMinuteClock(
            start_mmin=0, step_mmin=10, calendar=cal
        )
        for _ in range(20):
            t = clock.tick()
            assert isinstance(t, int)

    def test_calendar_to_dict_no_floats(self) -> None:
        cal = WorkingCalendar(
            [NonWorkingInterval(start_mmin=100, end_mmin=200)]
        )
        d = cal.to_dict()
        assert detect_floats(d) == []

    def test_multiple_intervals(self) -> None:
        cal = WorkingCalendar(
            [
                NonWorkingInterval(start_mmin=100, end_mmin=200),
                NonWorkingInterval(start_mmin=300, end_mmin=400),
            ]
        )
        clock = MilliMinuteClock(
            start_mmin=0, step_mmin=50, calendar=cal
        )
        assert clock.tick() == 50
        assert clock.tick() == 200  # skip to end of first interval
        assert clock.tick() == 250
        assert clock.tick() == 400  # skip to end of second interval

    def test_overlapping_rejected(self) -> None:
        with pytest.raises(ValueError):
            WorkingCalendar(
                [
                    NonWorkingInterval(start_mmin=100, end_mmin=300),
                    NonWorkingInterval(start_mmin=200, end_mmin=400),
                ]
            )


class TestFixedPointPathsClean:
    """G16.4 — No floats on the hashed state path."""

    def test_fixed_state_dict_no_floats(self) -> None:
        """A state dict built from Fixed values has no floats."""
        state = {
            "temperature": Fixed(23.5).to_dict(),
            "pressure": Fixed(1.013).to_dict(),
            "count": 42,
        }
        assert detect_floats(state) == []

    def test_sim_state_no_floats(self) -> None:
        """Simulation state uses only integers on the hashed path."""
        from aminopstwin.twin.entities import Queue, Site

        state = {
            "site": Site(
                site_id="s0", name="S0", capacity=10
            ).model_dump(),
            "queue": Queue(
                queue_id="q0",
                site_id="s0",
                name="Q0",
                current_length=5,
                total_arrivals=100,
                total_completions=95,
                capacity=10,
            ).model_dump(),
        }
        assert detect_floats(state) == []
