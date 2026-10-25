"""G16... item 6 — Canonical serializer differential (P16).

A second pure-Python reference implementation of the canonical JSON
serializer is compared against the production
:func:`canonical_bytes` on >= 10 000 random + fixed vectors.
Byte equality is asserted.
"""

from __future__ import annotations

import pytest
from aminopstwin.contracts.canonical import canonical_bytes
from aminopstwin.twin.canonical_diff import (
    differential_check,
    generate_corpus,
    reference_canonical_bytes,
)


class TestCanonicalDifferential:
    """Differential test: production vs reference canonical bytes."""

    def test_fixed_vectors_match(self) -> None:
        """Fixed edge-case vectors produce identical bytes."""
        corpus = generate_corpus(100)
        for vector in corpus[:25]:  # check first 25 (fixed)
            prod = canonical_bytes(vector)
            ref = reference_canonical_bytes(vector)
            assert prod == ref, (
                f"Bytes differ for {vector!r}: "
                f"prod={prod!r}, ref={ref!r}"
            )

    def test_10k_differential(self) -> None:
        """>= 10 000 vectors produce identical bytes (G16... item 6)."""
        result = differential_check(10_000)
        assert result["total"] >= 10_000
        assert result["failed"] == 0, (
            f"{result['failed']} of {result['total']} vectors diverged. "
            f"First mismatch: {result['mismatches'][:3]}"
        )
        assert result["passed"] == result["total"]

    def test_empty_dict(self) -> None:
        assert canonical_bytes({}) == reference_canonical_bytes({})

    def test_nested_dict(self) -> None:
        payload = {"a": {"b": {"c": [1, 2, 3]}}}
        assert canonical_bytes(payload) == reference_canonical_bytes(payload)

    def test_unicode(self) -> None:
        payload = {"key": "café", "value": "αβγ"}
        assert canonical_bytes(payload) == reference_canonical_bytes(payload)

    def test_sorted_keys(self) -> None:
        """Both implementations sort keys identically."""
        payload = {"z": 1, "a": 2, "m": 3, "b": 4}
        assert canonical_bytes(payload) == reference_canonical_bytes(payload)

    def test_float_rejected_by_both(self) -> None:
        """Both implementations reject floats."""
        with pytest.raises((TypeError, ValueError)):
            canonical_bytes({"x": 1.5})
        with pytest.raises((TypeError, ValueError)):
            reference_canonical_bytes({"x": 1.5})

    def test_corpus_size(self) -> None:
        """The corpus has at least 10 000 entries."""
        corpus = generate_corpus(10_000)
        assert len(corpus) >= 10_000
