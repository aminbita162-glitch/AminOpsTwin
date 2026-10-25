"""Integer-oriented simulation time and named PRNG streams (P12, §115–118).

Simulation clock becomes integer ticks in **milliminutes** — all time
values on the hashed state path are integers, never floats.  A
``MilliMinuteClock`` advances in integer milliminute increments (1
minute = 1000 milliminutes).

Named PRNG streams: each entity (site, queue, resource) gets its own
deterministic PRNG stream keyed by ``H(seed, entity_name)``.  This
ensures that adding or removing an entity does not perturb the random
sequences of other entities — a property that a single shared RNG does
not have.

Floating-point operations are banned on the hashed state path: the
simulation engine uses only integer arithmetic for all values that
participate in the state hash.  The ``math`` module is never imported
in this module.
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass
from typing import Any, Final

__all__ = [
    "MilliMinuteClock",
    "NamedPrngStream",
    "PrngRegistry",
    "MILLIMINUTES_PER_MINUTE",
    "NonWorkingInterval",
    "WorkingCalendar",
]


MILLIMINUTES_PER_MINUTE: Final[int] = 1000


@dataclass(frozen=True)
class NonWorkingInterval:
    """A non-working interval in milliminutes (integer).

    Used by :class:`WorkingCalendar` to mark intervals during which
    the simulation clock should skip (non-working time).
    """

    start_mmin: int
    end_mmin: int

    def __post_init__(self) -> None:
        if self.start_mmin < 0:
            raise ValueError("start_mmin must be >= 0")
        if self.end_mmin <= self.start_mmin:
            raise ValueError("end_mmin must be > start_mmin")

    def contains(self, mmin: int) -> bool:
        """Return True if *mmin* falls within this interval."""
        return self.start_mmin <= mmin < self.end_mmin

    def to_dict(self) -> dict[str, int]:
        return {
            "start_mmin": self.start_mmin,
            "end_mmin": self.end_mmin,
        }


class WorkingCalendar:
    """A working calendar — a list of non-working intervals.

    The clock advances in integer milliminutes.  When :meth:`tick` is
    called and the new time falls within a non-working interval, the
    clock skips to the end of the interval.  All arithmetic is integer —
    no floats.
    """

    def __init__(
        self,
        intervals: list[NonWorkingInterval] | None = None,
    ) -> None:
        self._intervals: list[NonWorkingInterval] = sorted(
            intervals or [], key=lambda iv: iv.start_mmin
        )
        # Validate no overlap
        for i in range(1, len(self._intervals)):
            if self._intervals[i].start_mmin < self._intervals[i - 1].end_mmin:
                raise ValueError(
                    "overlapping non-working intervals detected"
                )

    @property
    def intervals(self) -> list[NonWorkingInterval]:
        return list(self._intervals)

    def is_working(self, mmin: int) -> bool:
        """Return True if *mmin* is within working time."""
        return not any(iv.contains(mmin) for iv in self._intervals)

    def next_working(self, mmin: int) -> int:
        """Return *mmin* if it is working time, else the end of the
        containing non-working interval.
        """
        for iv in self._intervals:
            if iv.contains(mmin):
                return iv.end_mmin
        return mmin

    def to_dict(self) -> dict[str, Any]:
        return {
            "intervals": [iv.to_dict() for iv in self._intervals],
        }


class MilliMinuteClock:
    """Integer simulation clock in milliminutes.

    All time values on the hashed state path are integers.  The clock
    starts at ``start_mmin`` (default 0) and advances by ``step_mmin``
    (default 1) on each call to :meth:`tick`.

    An optional :class:`WorkingCalendar` causes the clock to skip
    non-working intervals on each tick — all with integer arithmetic,
    no floats.
    """

    def __init__(
        self,
        start_mmin: int = 0,
        step_mmin: int = 1,
        calendar: WorkingCalendar | None = None,
    ) -> None:
        if start_mmin < 0:
            raise ValueError("start_mmin must be >= 0")
        if step_mmin <= 0:
            raise ValueError("step_mmin must be > 0")
        self._start: int = start_mmin
        self._step: int = step_mmin
        self._calendar: WorkingCalendar | None = calendar
        # If start is in a non-working interval, skip to the end
        self._current: int = (
            calendar.next_working(start_mmin)
            if calendar is not None
            else start_mmin
        )

    @property
    def current(self) -> int:
        """Current time in milliminutes (integer)."""
        return self._current

    @property
    def start(self) -> int:
        return self._start

    @property
    def step(self) -> int:
        return self._step

    def tick(self) -> int:
        """Advance one step and return the new time.

        If a :class:`WorkingCalendar` is configured and the new time
        falls within a non-working interval, the clock skips to the
        end of that interval.  All arithmetic is integer.
        """
        self._current += self._step
        if self._calendar is not None:
            self._current = self._calendar.next_working(self._current)
        return self._current

    def reset(self) -> None:
        self._current = self._start

    def to_dict(self) -> dict[str, Any]:
        """Serialise to a canonical dict for state hashing."""
        return {
            "start_mmin": self._start,
            "step_mmin": self._step,
            "current_mmin": self._current,
        }


def _stream_seed(master_seed: int, entity_name: str) -> int:
    """Derive a per-entity seed from the master seed and entity name.

    ``H(seed, entity_name)`` — SHA-256 of (seed || entity_name),
    truncated to 64 bits for use as a ``random.Random`` seed.
    """
    h = hashlib.sha256()
    h.update(str(master_seed).encode("utf-8"))
    h.update(b":")
    h.update(entity_name.encode("utf-8"))
    # Truncate to 64 bits for the RNG seed
    return int.from_bytes(h.digest()[:8], "big")


class NamedPrngStream:
    """A single named PRNG stream keyed by H(seed, entity_name).

    Uses ``random.Random`` (Mersenne Twister) seeded deterministically
    from the master seed and the entity name.  All methods return
    integers — no floats on the hashed state path.
    """

    def __init__(self, master_seed: int, entity_name: str) -> None:
        self._master_seed: int = master_seed
        self._entity_name: str = entity_name
        self._seed: int = _stream_seed(master_seed, entity_name)
        self._rng: random.Random = random.Random(self._seed)

    @property
    def entity_name(self) -> str:
        return self._entity_name

    @property
    def seed(self) -> int:
        return self._seed

    def randint(self, lo: int, hi: int) -> int:
        """Return a random integer in [lo, hi]."""
        return self._rng.randint(lo, hi)

    def randrange(self, n: int) -> int:
        """Return a random integer in [0, n)."""
        return self._rng.randrange(n)

    def poisson(self, lam: int) -> int:
        """Sample from a Poisson distribution with integer rate ``lam``.

        Uses inverse-CDF sampling with integer arithmetic only — no
        ``math.*`` floating-point operations.  The PMF recurrence
        ``P(k+1) = P(k) * lam / (k+1)`` is computed with integer
        accumulation scaled by a fixed-point denominator to avoid
        floats.
        """
        if lam <= 0:
            return 0
        # Fixed-point: scale by 10**12 to avoid floats
        scale: int = 10**12
        # P(0) = e^(-lam) — but we can't use math.exp without floats.
        # Use the integer recurrence with a lookup table for e^(-lam)
        # truncated to fixed-point.  For determinism across platforms,
        # we precompute P(0) * scale using the Taylor series of exp
        # with integer arithmetic.
        p0 = self._exp_neg(lam, scale)
        u = self._rng.randrange(scale)
        cumulative = p0
        if u < cumulative:
            return 0
        p_val = p0
        for k in range(1, 100):
            # p_val = p_val * lam // k  (scaled)
            p_val = (p_val * lam) // k
            cumulative += p_val
            if u < cumulative:
                return k
        return lam  # fallback for very large draws

    def _exp_neg(self, x: int, scale: int) -> int:
        """Compute e^(-x) * scale using integer Taylor series."""
        # e^(-x) = sum_{n=0}^{inf} (-x)^n / n!
        # = 1 - x + x^2/2! - x^3/3! + ...
        # We compute this with fixed-point integer arithmetic.
        term = scale  # first term: scale * 1
        result = term
        for n in range(1, 50):
            # term = term * (-x) // n
            term = (term * (-x)) // n
            result += term
            if term == 0:
                break
        return result

    def reset(self) -> None:
        """Reset the stream to its initial seed."""
        self._rng = random.Random(self._seed)


class PrngRegistry:
    """Registry of named PRNG streams keyed by entity name.

    Each entity (site, queue, resource) gets its own stream.  Adding
    or removing an entity does not perturb other entities' streams —
    a key property for deterministic replay (G3.1).
    """

    def __init__(self, master_seed: int) -> None:
        self._master_seed: int = master_seed
        self._streams: dict[str, NamedPrngStream] = {}

    @property
    def master_seed(self) -> int:
        return self._master_seed

    def get_stream(self, entity_name: str) -> NamedPrngStream:
        """Get or create a named PRNG stream for ``entity_name``."""
        if entity_name not in self._streams:
            self._streams[entity_name] = NamedPrngStream(
                self._master_seed, entity_name
            )
        return self._streams[entity_name]

    def entity_names(self) -> list[str]:
        return sorted(self._streams.keys())

    def reset_all(self) -> None:
        for stream in self._streams.values():
            stream.reset()

    def to_dict(self) -> dict[str, Any]:
        """Serialise the registry state for hashing (deterministic)."""
        return {
            "master_seed": self._master_seed,
            "entity_names": sorted(self._streams.keys()),
        }
