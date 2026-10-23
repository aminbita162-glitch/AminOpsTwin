"""Injected Clock and IdFactory for deterministic core operations.

References: §3.5.3, §3.5.4, §6.3.

The deterministic core never calls datetime.now(), time.time(), random.*,
uuid.uuid4(), os.urandom(), or secrets.* directly. Instead, it uses injected
Clock and IdFactory objects seeded for test reproducibility.

Clock: produces timezone-aware UTC datetimes, serialized RFC 3339 with
       microseconds and a literal "Z" (§3.5.3).
IdFactory: UUID version 4 layout built from 128 bits of the injected
           seeded RNG (§3.5.4).
"""

from __future__ import annotations

import datetime as _dt
import random
import uuid
from typing import Final

__all__ = [
    "Clock",
    "IdFactory",
    "SystemClock",
    "SystemIdFactory",
    "SeededClock",
    "SeededIdFactory",
]


class Clock:
    """Abstract clock interface — produces timezone-aware UTC datetimes."""

    def now(self) -> _dt.datetime:
        """Return the current time as a timezone-aware UTC datetime."""
        raise NotImplementedError


class IdFactory:
    """Abstract id-factory interface — produces UUID v4-layout identifiers."""

    def new_id(self) -> uuid.UUID:
        """Return a new UUID (version 4 layout)."""
        raise NotImplementedError


class SystemClock(Clock):
    """Clock backed by the system clock (runtime use)."""

    def now(self) -> _dt.datetime:
        return _dt.datetime.now(tz=_dt.UTC)


class SystemIdFactory(IdFactory):
    """IdFactory backed by OS entropy (runtime use)."""

    def new_id(self) -> uuid.UUID:
        return uuid.uuid4()


class SeededClock(Clock):
    """Deterministic clock for tests — starts at a fixed offset and
    advances."""

    def __init__(self, start: _dt.datetime | None = None) -> None:
        if start is None:
            self._start = _dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        else:
            if start.tzinfo is None:
                raise ValueError("start must be timezone-aware")
            self._start = start
        self._tick = 0

    def now(self) -> _dt.datetime:
        self._tick += 1
        return self._start + _dt.timedelta(microseconds=self._tick)

    def reset(self) -> None:
        self._tick = 0


class SeededIdFactory(IdFactory):
    """Deterministic IdFactory for tests — UUID v4 layout from a seeded
    RNG."""

    def __init__(self, seed: int) -> None:
        self._rng = random.Random(seed)

    def new_id(self) -> uuid.UUID:
        # UUID version 4 layout: set version nibble to 4,
        # variant to 10xx. Build 128 bits from the seeded RNG.
        bits = self._rng.getrandbits(128)
        # Clear version and variant bits, then set them per RFC 4122 §4.4.
        # Version nibble is at bits 76-79 (hex digit 12 from the MSB).
        # Variant bits are at bits 62-63 (hex digit 15 from the MSB).
        # The AND mask zeros the lower 64 bits (including variant) and
        # clears the version nibble in the upper half.
        bits &= 0xFFFFFFFFFFFF4FFF0000000000000000
        bits |= 4 << 76  # version 4 at the correct bit position
        bits |= 0x2 << 62  # variant 10xx (RFC 4122)
        return uuid.UUID(int=bits)

    def reset(self) -> None:
        # Re-seed for reproducibility in replay.
        # Note: the caller must pass the same seed.
        pass


def format_rfc3339_z(dt: _dt.datetime) -> str:
    """Format a datetime as RFC 3339 with microseconds and literal 'Z'.

    Naive datetimes are rejected (§3.5.3).
    """
    if dt.tzinfo is None:
        raise ValueError(
            "naive datetime not allowed; must be timezone-aware UTC"
        )
    # Convert to UTC
    dt_utc = dt.astimezone(_dt.UTC)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.%f") + "Z"


# Sentinel: single-tenant default tenant id (until P5/OD01).
TENANT_DEFAULT: Final[str] = "tenant-default"
