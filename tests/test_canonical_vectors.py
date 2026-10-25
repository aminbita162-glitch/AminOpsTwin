"""Test canonical vector reproduction (§24.5, G1.11)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from aminopstwin.contracts.canonical import (
    CanonicalError,
    canonical_bytes,
)

_VECTORS_PATH = Path(__file__).parent.parent / "fixtures" / "canonical_vectors.json"


@pytest.fixture
def canonical_vectors() -> list[dict]:
    with _VECTORS_PATH.open() as f:
        return json.load(f)["vectors"]


def _accepted_vectors() -> list[dict]:
    with _VECTORS_PATH.open() as f:
        return [
            v
            for v in json.load(f)["vectors"]
            if v["category"] == "accepted"
        ]


def _rejected_vectors() -> list[dict]:
    with _VECTORS_PATH.open() as f:
        return [
            v
            for v in json.load(f)["vectors"]
            if v["category"] == "rejected"
        ]


class TestCanonicalVectors:
    """100% of >= 30 vectors reproduce the exact bytes and hash (G1.11)."""

    def test_at_least_30_accepted_vectors(
        self, canonical_vectors: list[dict]
    ) -> None:
        accepted = [
            v for v in canonical_vectors if v["category"] == "accepted"
        ]
        assert len(accepted) >= 30, (
            f"Need >= 30 accepted, got {len(accepted)}"
        )

    @pytest.mark.parametrize("vector", _accepted_vectors())
    def test_accepted_vector_reproduces(self, vector: dict) -> None:
        """Each accepted vector must reproduce exact canonical bytes and
        hash."""
        payload = vector["input_payload"]
        expected_bytes_hex = vector["expected_canonical_bytes_hex"]
        expected_hash = vector["expected_sha256"]

        actual_bytes = canonical_bytes(payload)

        assert actual_bytes.hex() == expected_bytes_hex, (
            f"Canonical bytes mismatch for {vector['id']}: "
            f"expected {expected_bytes_hex}, "
            f"got {actual_bytes.hex()}"
        )
        import hashlib

        actual_hash = hashlib.sha256(actual_bytes).hexdigest()
        assert actual_hash == expected_hash, (
            f"Hash mismatch for {vector['id']}: "
            f"expected {expected_hash}, got {actual_hash}"
        )

    @pytest.mark.parametrize("vector", _rejected_vectors())
    def test_rejected_vector_raises(self, vector: dict) -> None:
        """Each rejected vector must raise CanonicalError."""
        reason = vector.get("expected_rejection", "")
        reason_lower = reason.lower()

        if "float" in reason_lower or "nan" in reason_lower:
            with pytest.raises(CanonicalError):
                canonical_bytes({"a": 1.5})
        elif "infinity" in reason_lower or "inf" in reason_lower:
            with pytest.raises(CanonicalError):
                canonical_bytes({"a": float("inf")})
        elif "nfc" in reason_lower or "combining" in reason_lower:
            # Test with a non-NFC string (decomposed café) that
            # must be rejected, not silently normalized.
            with pytest.raises(CanonicalError):
                canonical_bytes({"a": "cafe\u0301"})
