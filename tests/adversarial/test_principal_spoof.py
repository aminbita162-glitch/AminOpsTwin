"""Principal-spoofing adversarial tests (T15, G1.12).

Tests that attempts to assert an identity through message content are
denied. The caller's principal is runtime-bound, never message-derived
(§3.5.1). A message carrying an "issuer" key anywhere in the payload
fails schema validation with GW-SCHEMA-001.
"""

from __future__ import annotations

import pytest
from src.contracts.canonical import canonical_hash
from src.contracts.clock import SeededClock, SeededIdFactory
from src.contracts.envelope import Envelope


def _make_env(payload: dict) -> Envelope:
    """Create a test envelope with the given payload."""
    clock = SeededClock()
    idf = SeededIdFactory(seed=42)
    return Envelope(
        envelope_version="1.0",
        schema_id="ops.sim.scenario@1",
        envelope_type="scenario",
        correlation_id=idf.new_id(),
        causation_id=None,
        tenant_id="tenant-default",
        policy_epoch=0,
        idempotency_key="test-idempotency-key-001",
        payload=payload,
        payload_hash=canonical_hash(payload),
        created_at=clock.now(),
    )


class TestPrincipalSpoofing:
    """G1.12: Principal-spoofing attempts are denied (100%)."""

    def test_issuer_top_level(self) -> None:
        """Direct 'issuer' key in payload rejected."""
        with pytest.raises(ValueError):
            _make_env({"issuer": "A1", "site": "a"})

    def test_issuer_nested(self) -> None:
        """Nested 'issuer' key rejected."""
        with pytest.raises(ValueError):
            _make_env({"nested": {"issuer": "A1"}})

    def test_issuer_in_list(self) -> None:
        """'issuer' key inside a list element rejected."""
        with pytest.raises(ValueError):
            _make_env({"items": [{"issuer": "A1"}]})

    def test_issuer_deeply_nested(self) -> None:
        """Deeply nested 'issuer' key rejected."""
        with pytest.raises(ValueError):
            _make_env(
                {"a": {"b": {"c": {"d": {"issuer": "admin"}}}}}
            )

    def test_issuer_empty_value(self) -> None:
        """'issuer' with empty value still rejected."""
        with pytest.raises(ValueError):
            _make_env({"issuer": ""})

    def test_issuer_null_value(self) -> None:
        """'issuer' with null value still rejected."""
        with pytest.raises(ValueError):
            _make_env({"issuer": None})

    def test_issuer_numeric_value(self) -> None:
        """'issuer' with numeric value still rejected."""
        with pytest.raises(ValueError):
            _make_env({"issuer": 42})

    def test_issuer_in_mixed_payload(self) -> None:
        """'issuer' among other valid keys still rejected."""
        with pytest.raises(ValueError):
            _make_env(
                {"site": "a", "issuer": "A2", "capacity": 10}
            )

    def test_issuer_case_variations(self) -> None:
        """'ISSUER' (uppercase) is NOT the forbidden key; only
        lowercase 'issuer' is forbidden per §3.5.1."""
        # Uppercase ISSUER is a different key — it should NOT be
        # rejected by the issuer check. But it IS a valid key name
        # since it doesn't match _FORBIDDEN_KEYS.
        env = _make_env({"ISSUER": "A1"})
        assert env.payload["ISSUER"] == "A1"

    def test_no_issuer_passes(self) -> None:
        """Payload without 'issuer' key passes construction."""
        env = _make_env({"site": "a", "capacity": 10})
        assert env.payload["site"] == "a"
