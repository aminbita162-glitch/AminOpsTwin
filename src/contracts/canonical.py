"""Canonical serialization contract AMINOPS-C14N-1 (§3.5.2).

Deterministic payload serialization for the Envelope payload_hash.

Values: Unicode scalar strings in NFC, integers within ±(2^53-1), bool, null,
lists and dictionaries with string keys. All keys are NFC.

Reject non-NFC input instead of silently normalizing it; reject lone surrogates,
duplicate raw JSON keys, non-string keys, floats, NaN and Infinity. Integer
validation must not misclassify bool. Use integer fixed-point or schema-constrained
decimal strings for fractional data.

Bytes = json.dumps(payload, sort_keys=True, separators=(',', ':'),
ensure_ascii=False, allow_nan=False).encode('utf-8'), after validation.

Hash = SHA-256 hex of these bytes.

This is the project's deterministic serialization contract, NOT a general
RFC 8785/JCS implementation: Unicode property sorting differs. A later JCS
migration requires a new canonical contract version, an owner amendment and
cross-version fixtures, never an in-place change.
"""

from __future__ import annotations

import hashlib
import json
import unicodedata
from typing import Any, Final

__all__ = [
    "CanonicalError",
    "validate_canonical_value",
    "canonical_bytes",
    "canonical_hash",
]


class CanonicalError(Exception):
    """Raised when a payload value is not representable in the canonical form."""


# Integers must be within ±(2^53 - 1) (safe integer range for JSON).
_MAX_SAFE_INT: Final[int] = (2**53) - 1
_MIN_SAFE_INT: Final[int] = -((2**53) - 1)


def _is_nfc(s: str) -> bool:
    """Return True if *s* is in Unicode NFC form."""
    return unicodedata.normalize("NFC", s) == s


def _has_lone_surrogates(s: str) -> bool:
    """Return True if *s* contains lone (unpaired) surrogates."""
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            return True
    return False


def _validate_key(key: Any) -> str:
    """Validate a dictionary key: must be an NFC string, no lone surrogates."""
    if not isinstance(key, str):
        raise CanonicalError(f"non-string key not allowed: {type(key).__name__}")
    if not _is_nfc(key):
        raise CanonicalError(f"key is not in NFC form: {key!r}")
    if _has_lone_surrogates(key):
        raise CanonicalError("lone surrogate in key")
    return key


def validate_canonical_value(value: Any, *, _top: bool = True) -> Any:
    """Recursively validate a payload value against the canonical contract.

    Raises CanonicalError for any disallowed type or form.
    Returns the value unchanged if it passes.

    Allowed types:
    - None (null)
    - bool (true/false)
    - int (within ±(2^53-1); bool is NOT int)
    - str (NFC, no lone surrogates)
    - list (validated recursively)
    - dict (string keys in NFC, validated recursively)
    """
    # bool must be checked before int (bool is a subclass of int in Python).
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, int):
        if value < _MIN_SAFE_INT or value > _MAX_SAFE_INT:
            raise CanonicalError(f"integer out of safe range: {value}")
        return value
    if isinstance(value, float):
        raise CanonicalError(
            "float values are not allowed in canonical payloads (N-15)"
        )
    if isinstance(value, str):
        if not _is_nfc(value):
            raise CanonicalError(f"string is not in NFC form: {value!r}")
        if _has_lone_surrogates(value):
            raise CanonicalError("lone surrogate in string value")
        return value
    if isinstance(value, list):
        return [validate_canonical_value(v, _top=False) for v in value]
    if isinstance(value, dict):
        validated: dict[str, Any] = {}
        for k, v in value.items():
            vk = _validate_key(k)
            if vk in validated:
                raise CanonicalError(f"duplicate key after NFC normalization: {vk!r}")
            validated[vk] = validate_canonical_value(v, _top=False)
        return validated

    # Reject any other type (including complex, bytes, custom objects).
    raise CanonicalError(
        f"unsupported type in canonical payload: {type(value).__name__}"
    )


def canonical_bytes(payload: Any) -> bytes:
    """Serialize *payload* to canonical bytes (AMINOPS-C14N-1).

    Validates the payload first, then serializes with:
        json.dumps(payload, sort_keys=True, separators=(',', ':'),
                   ensure_ascii=False, allow_nan=False).encode('utf-8')
    """
    validated = validate_canonical_value(payload)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(payload: Any) -> str:
    """Return the SHA-256 hex digest of the canonical bytes of *payload*."""
    return hashlib.sha256(canonical_bytes(payload)).hexdigest()
