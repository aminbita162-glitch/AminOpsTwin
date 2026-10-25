"""Canonical serializer differential test (P16, G16.5... actually item 6).

A second pure-Python reference implementation of the canonical JSON
serializer, compared against the production
:func:`aminopstwin.contracts.canonical.canonical_bytes` on a large
corpus of >= 10 000 random + fixed vectors.  Byte equality is asserted.

The reference implementation uses an independent code path (manual
recursion + ``json.dumps`` with identical parameters) to detect any
divergence in the production serializer's NFC handling, key sorting,
or encoding.
"""

from __future__ import annotations

import hashlib
import json
import random
import unicodedata
from typing import Any

from aminopstwin.contracts.canonical import canonical_bytes

__all__ = [
    "reference_canonical_bytes",
    "generate_corpus",
    "differential_check",
]


def _is_nfc(s: str) -> bool:
    return unicodedata.normalize("NFC", s) == s


def _has_lone_surrogates(s: str) -> bool:
    for ch in s:
        cp = ord(ch)
        if 0xD800 <= cp <= 0xDFFF:
            return True
    return False


def _reference_serialize(value: Any) -> Any:
    """Independent reference implementation of canonical value validation.

    Mirrors the production validator but is written separately so that
    a bug in one is unlikely to appear in both.
    """
    if isinstance(value, bool):
        return value
    if value is None:
        return None
    if isinstance(value, int):
        # Check safe integer range (±2^53 - 1)
        if value < -((2**53) - 1) or value > (2**53) - 1:
            raise ValueError(f"integer out of safe range: {value}")
        return value
    if isinstance(value, float):
        raise ValueError("float not allowed in canonical payload")
    if isinstance(value, str):
        if not _is_nfc(value):
            raise ValueError("string not in NFC form")
        if _has_lone_surrogates(value):
            raise ValueError("lone surrogate in string")
        return value
    if isinstance(value, list):
        return [_reference_serialize(v) for v in value]
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for k, v in value.items():
            if not isinstance(k, str):
                raise ValueError("non-string key")
            if not _is_nfc(k):
                raise ValueError("key not in NFC form")
            if _has_lone_surrogates(k):
                raise ValueError("lone surrogate in key")
            if k in result:
                raise ValueError(f"duplicate key: {k!r}")
            result[k] = _reference_serialize(v)
        return result
    raise ValueError(f"unsupported type: {type(value).__name__}")


def reference_canonical_bytes(payload: Any) -> bytes:
    """Reference implementation of canonical bytes serialization.

    Uses an independent code path from the production
    :func:`canonical_bytes` to detect divergence.
    """
    validated = _reference_serialize(payload)
    return json.dumps(
        validated,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _fixed_vectors() -> list[Any]:
    """Return a fixed set of edge-case vectors."""
    return [
        {},
        {"a": 1},
        {"b": True, "a": False},
        {"z": None, "a": [1, 2, 3]},
        {"nested": {"deep": {"deeper": {"deepest": 42}}}},
        {"empty_list": []},
        {"unicode": "café"},
        {"mixed": [1, True, None, "str", {"k": "v"}]},
        {"key1": "val1", "key2": "val2", "key3": "val3"},
        {"num": 0},
        {"neg": -1},
        {"big": 2**53 - 1},
        {"neg_big": -(2**53) + 1},
        {"str": "hello"},
        {"bool_true": True},
        {"bool_false": False},
        {"nested_list": [[1, 2], [3, 4], [5, 6]]},
        {"deeply_nested": {"a": {"b": {"c": {"d": {"e": "end"}}}}}},
        {"special": "äöü"},
        {"empty_str": ""},
        {"spaces": "  "},
        {"numbers": [0, 1, -1, 1000, -1000]},
        {"sorted": {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}},
        {"reverse_sorted_input": {"e": 5, "d": 4, "c": 3, "b": 2, "a": 1}},
        {"types": [None, True, False, 0, 1, "str", [], {}]},
        {"level1": {"level2": [{"level3": {"key": "val"}}]}},
    ]


def generate_corpus(count: int = 10_000) -> list[Any]:
    """Generate a corpus of *count* vectors for differential testing.

    Includes fixed edge-case vectors plus random vectors generated
    deterministically from a seeded RNG (no Hypothesis dependency
    required — this is a pure-Python generator).
    """
    corpus: list[Any] = list(_fixed_vectors())
    rng = random.Random(12345)

    keys = ["a", "b", "c", "d", "e", "f", "g", "h", "i", "j",
            "key1", "key2", "name", "value", "data", "type"]
    str_vals = ["", "hello", "world", "café", "test", "x", "y",
                "αβγ", "nfc", "sorted", "nested", "deep"]
    int_vals = [0, 1, -1, 2, -2, 10, 100, 1000, -1000,
                2**53 - 1, -(2**53) + 1, 42, 7, 99]

    while len(corpus) < count:
        depth = rng.randint(0, 3)
        corpus.append(_generate_random_vector(rng, depth, keys, str_vals, int_vals))

    return corpus[:count]


def _generate_random_vector(
    rng: random.Random,
    depth: int,
    keys: list[str],
    str_vals: list[str],
    int_vals: list[int],
) -> Any:
    """Generate a single random vector deterministically."""
    if depth <= 0:
        choice = rng.randint(0, 3)
        if choice == 0:
            return rng.choice(str_vals)
        elif choice == 1:
            return rng.choice(int_vals)
        elif choice == 2:
            return rng.choice([True, False, None])
        else:
            return rng.choice(str_vals)

    size = rng.randint(0, 5)
    result: dict[str, Any] = {}
    for _ in range(size):
        k = rng.choice(keys)
        r = rng.randint(0, 2)
        if r == 0:
            result[k] = rng.choice(str_vals)
        elif r == 1:
            result[k] = rng.choice(int_vals)
        else:
            result[k] = _generate_random_vector(
                rng, depth - 1, keys, str_vals, int_vals
            )
    return result


def differential_check(count: int = 10_000) -> dict[str, Any]:
    """Run the differential check on *count* vectors.

    Returns a dict with:
        - total: total vectors checked
        - passed: number that produced identical bytes
        - failed: number that diverged
        - mismatches: list of (vector, prod_hash, ref_hash) for failures
    """
    corpus = generate_corpus(count)
    passed = 0
    failed = 0
    mismatches: list[tuple[Any, str, str]] = []

    for vector in corpus:
        try:
            prod_bytes = canonical_bytes(vector)
            ref_bytes = reference_canonical_bytes(vector)
            if prod_bytes == ref_bytes:
                passed += 1
            else:
                failed += 1
                mismatches.append(
                    (vector, hashlib.sha256(prod_bytes).hexdigest(),
                     hashlib.sha256(ref_bytes).hexdigest())
                )
        except Exception:
            # Both should raise or both should succeed — if only one
            # raises, that's a divergence.
            try:
                prod_bytes = canonical_bytes(vector)
                # Production succeeded but reference failed
                failed += 1
                mismatches.append(
                    (vector, hashlib.sha256(prod_bytes).hexdigest(), "<error>")
                )
            except Exception:
                try:
                    ref_bytes = reference_canonical_bytes(vector)
                    # Reference succeeded but production failed
                    failed += 1
                    mismatches.append(
                        (vector, "<error>",
                         hashlib.sha256(ref_bytes).hexdigest())
                    )
                except Exception:
                    # Both raised — consistent
                    passed += 1

    return {
        "total": len(corpus),
        "passed": passed,
        "failed": failed,
        "mismatches": mismatches,
    }
