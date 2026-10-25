"""Raw JSON ingestion at the API edge (P12, §97–101, G12.1).

A FastAPI dependency that reads ``request.body()`` as raw bytes and
parses with strict rejection of floats, NaN, Infinity and duplicate
keys.  Every rejection carries an exact reason code so the caller can
distinguish the failure mode without guessing.

Reason codes (§6.4 domain INJ):
    GW-INJ-003  duplicate key in JSON object
    GW-INJ-004  float value in JSON (use integer or decimal string)
    GW-INJ-005  NaN literal in JSON
    GW-INJ-006  Infinity literal in JSON
    GW-INJ-007  -Infinity literal in JSON
    GW-INJ-008  malformed JSON

The parser is deterministic: the same bytes always produce the same
parsed object or the same rejection.
"""

from __future__ import annotations

import json
from typing import Any, Final

__all__ = [
    "RawJsonError",
    "parse_raw_json",
    "reject_float",
    "reject_constant",
    "detect_duplicates",
]


class RawJsonError(ValueError):
    """Raised when raw JSON is rejected at the API edge."""

    def __init__(self, reason_code: str, detail: str) -> None:
        super().__init__(f"{reason_code}: {detail}")
        self.reason_code = reason_code
        self.detail = detail


# Reason codes (§6.4, domain INJ)
R_DUPLICATE_KEY: Final[str] = "GW-INJ-003"
R_FLOAT: Final[str] = "GW-INJ-004"
R_NAN: Final[str] = "GW-INJ-005"
R_INFINITY: Final[str] = "GW-INJ-006"
R_NEG_INFINITY: Final[str] = "GW-INJ-007"
R_MALFORMED: Final[str] = "GW-INJ-008"


def reject_float(_val: str) -> float:
    """parse_float hook that rejects every float literal."""
    raise RawJsonError(R_FLOAT, f"float value not allowed: {_val!r}")


def reject_constant(val: str) -> Any:
    """parse_constant hook that rejects NaN, Infinity, -Infinity."""
    if val == "NaN":
        raise RawJsonError(R_NAN, "NaN literal not allowed")
    if val == "Infinity":
        raise RawJsonError(R_INFINITY, "Infinity literal not allowed")
    if val == "-Infinity":
        raise RawJsonError(R_NEG_INFINITY, "-Infinity literal not allowed")
    # Should not happen for well-formed JSON; treat as malformed.
    raise RawJsonError(R_MALFORMED, f"unexpected constant: {val!r}")


def detect_duplicates(
    pairs: list[tuple[str, Any]],
) -> dict[str, Any]:
    """``object_pairs_hook`` that rejects duplicate keys in an object.

    The hook receives a list of (key, value) pairs in source order.
    If the same key appears more than once, raise with the exact key.
    """
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise RawJsonError(
                R_DUPLICATE_KEY,
                f"duplicate key: {key!r}",
            )
        result[key] = value
    return result


def parse_raw_json(raw: bytes | str) -> dict[str, Any]:
    """Parse raw JSON bytes at the API edge (G12.1).

    Rejects:
      - float literals (``1.0``, ``1e3``, ``1.5e-2``)
      - NaN, Infinity, -Infinity literals
      - duplicate keys within an object
      - malformed JSON

    Returns a ``dict[str, Any]`` with only int/str/bool/None/list/dict
    values (no floats).

    Raises :class:`RawJsonError` with the exact reason code on
    rejection.
    """
    if isinstance(raw, bytes):
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RawJsonError(
                R_MALFORMED,
                f"not valid UTF-8: {exc}",
            ) from exc
    else:
        text = raw

    if not text.strip():
        raise RawJsonError(R_MALFORMED, "empty body")

    try:
        parsed = json.loads(
            text,
            object_pairs_hook=detect_duplicates,
            parse_float=reject_float,
            parse_constant=reject_constant,
        )
    except RawJsonError:
        raise
    except json.JSONDecodeError as exc:
        raise RawJsonError(
            R_MALFORMED,
            f"JSON decode error at line {exc.lineno} col {exc.colno}: {exc.msg}",
        ) from exc
    except ValueError as exc:
        # reject_float / reject_constant raise ValueError subclasses;
        # if not already a RawJsonError, wrap.
        if isinstance(exc, RawJsonError):
            raise
        raise RawJsonError(R_MALFORMED, str(exc)) from exc

    if not isinstance(parsed, dict):
        raise RawJsonError(
            R_MALFORMED,
            f"top-level JSON must be an object, got {type(parsed).__name__}",
        )

    return parsed
