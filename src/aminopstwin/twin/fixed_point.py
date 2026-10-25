"""Fixed-point numeric type for hashed state paths (P16, G16.4).

Any value that enters a hash (state hash, checkpoint hash, payload hash)
must be an integer or a :class:`Fixed` — never a ``float``.  ``Fixed``
is a scaled integer: ``Fixed(value, scale)`` stores ``value * scale``
as an integer.  All arithmetic is integer arithmetic.

This module also provides a float-detection test helper that the CI
uses to fail the build if any float appears on a hashed state path
(G16.4).
"""

from __future__ import annotations

from typing import Any, Final

__all__ = [
    "Fixed",
    "DEFAULT_SCALE",
    "detect_floats",
    "FloatDetectionError",
]

DEFAULT_SCALE: Final[int] = 1_000_000  # 6 decimal places


class Fixed:
    """A fixed-point number backed by a scaled integer.

    ``Fixed(value, scale)`` represents the real number ``value`` with
    ``scale`` decimal places of precision.  Internally it stores
    ``int(round(value * scale))`` as an integer.  All arithmetic is
    integer arithmetic — no floats are used after construction.

    The ``raw`` property returns the scaled integer.  The ``real``
    property returns the floating-point representation (for display
    only — never used on the hashed state path).
    """

    __slots__ = ("_raw", "_scale")

    def __init__(self, value: int | float, scale: int = DEFAULT_SCALE) -> None:
        if scale <= 0:
            raise ValueError("scale must be > 0")
        if isinstance(value, bool):
            raise TypeError("bool is not a Fixed value")
        if isinstance(value, int):
            self._raw: int = value * scale
        elif isinstance(value, float):
            self._raw = int(round(value * scale))
        else:
            raise TypeError(
                f"Fixed requires int or float, got {type(value).__name__}"
            )
        self._scale: int = scale

    @property
    def raw(self) -> int:
        """The scaled integer value (never a float)."""
        return self._raw

    @property
    def scale(self) -> int:
        return self._scale

    @property
    def real(self) -> float:
        """The floating-point representation (display only)."""
        return self._raw / self._scale

    def to_dict(self) -> dict[str, int]:
        """Serialise to a canonical dict for state hashing.

        Returns only integers — no floats.
        """
        return {"raw": self._raw, "scale": self._scale}

    @classmethod
    def from_dict(cls, d: dict[str, int]) -> Fixed:
        """Reconstruct from a canonical dict."""
        return cls.from_raw(d["raw"], d["scale"])

    @classmethod
    def from_raw(cls, raw: int, scale: int = DEFAULT_SCALE) -> Fixed:
        """Construct from a raw scaled integer (no conversion needed)."""
        if not isinstance(raw, int):
            raise TypeError(f"raw must be int, got {type(raw).__name__}")
        obj = cls.__new__(cls)
        obj._raw = raw
        obj._scale = scale
        return obj

    def __add__(self, other: Fixed) -> Fixed:
        if self._scale != other._scale:
            raise ValueError("cannot add Fixed with different scales")
        return Fixed.from_raw(self._raw + other._raw, self._scale)

    def __sub__(self, other: Fixed) -> Fixed:
        if self._scale != other._scale:
            raise ValueError("cannot subtract Fixed with different scales")
        return Fixed.from_raw(self._raw - other._raw, self._scale)

    def __mul__(self, other: int) -> Fixed:
        if not isinstance(other, int):
            raise TypeError("Fixed *= int only")
        return Fixed.from_raw(self._raw * other, self._scale)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Fixed):
            return NotImplemented
        return self._raw == other._raw and self._scale == other._scale

    def __hash__(self) -> int:
        return hash((self._raw, self._scale))

    def __repr__(self) -> str:
        return f"Fixed({self._raw}, scale={self._scale})"

    def __str__(self) -> str:
        return f"{self._raw / self._scale:.6f}"


class FloatDetectionError(Exception):
    """Raised when a float is detected on a hashed state path (G16.4)."""


def detect_floats(obj: Any, *, _path: str = "") -> list[str]:
    """Recursively detect floats in a nested structure.

    Returns a list of paths (dotted) where floats were found.
    An empty list means no floats detected — the path is clean.
    """
    found: list[str] = []
    if isinstance(obj, bool):
        pass  # bool is fine
    elif isinstance(obj, float):
        found.append(_path or "<root>")
    elif isinstance(obj, (int, str)):
        pass
    elif isinstance(obj, dict):
        for k, v in obj.items():
            child_path = f"{_path}.{k}" if _path else k
            found.extend(detect_floats(v, _path=child_path))
    elif isinstance(obj, (list, tuple)):
        for i, v in enumerate(obj):
            child_path = f"{_path}[{i}]" if _path else f"[{i}]"
            found.extend(detect_floats(v, _path=child_path))
    return found
