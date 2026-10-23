"""F04: Duplicate delivery of same envelope → single effect (G2.9).

Scenario: The same envelope is delivered twice. The first delivery
executes the effect and stores the result. The second delivery returns
the stored result without re-executing.
"""

from __future__ import annotations

from src.contracts.canonical import canonical_hash

from tests.fault.infrastructure import IdempotentDelivery


class TestF04DuplicateDelivery:
    """F04: Duplicate delivery → single effect; second returns stored result."""

    def test_single_effect_on_duplicate(self) -> None:
        delivery = IdempotentDelivery()
        key = "idem-key-001-abcdef0123456789"
        payload = {"action": "test", "value": 42}
        payload_hash = canonical_hash(payload)

        call_count = 0

        def effect_fn() -> dict:
            nonlocal call_count
            call_count += 1
            return {"result": "ok", "value": 42}

        # First delivery
        result1 = delivery.deliver(key, payload_hash, effect_fn)
        assert result1 == {"result": "ok", "value": 42}
        assert call_count == 1
        assert delivery.effect_count == 1

        # Second delivery (duplicate) — returns stored result
        result2 = delivery.deliver(key, payload_hash, effect_fn)
        assert result2 == result1
        assert call_count == 1  # effect_fn was NOT called again
        assert delivery.effect_count == 1  # still 1

    def test_different_keys_different_effects(self) -> None:
        delivery = IdempotentDelivery()
        key1 = "idem-key-001-abcdef0123456789"
        key2 = "idem-key-002-abcdef0123456789"
        payload = {"action": "test"}
        payload_hash = canonical_hash(payload)

        def make_effect(value: int):
            def effect_fn() -> dict:
                return {"result": value}
            return effect_fn

        r1 = delivery.deliver(key1, payload_hash, make_effect(1))
        r2 = delivery.deliver(key2, payload_hash, make_effect(2))
        assert r1 == {"result": 1}
        assert r2 == {"result": 2}
        assert delivery.effect_count == 2

    def test_is_delivered_check(self) -> None:
        delivery = IdempotentDelivery()
        key = "idem-key-003-abcdef0123456789"
        payload = {"action": "test"}
        payload_hash = canonical_hash(payload)

        assert not delivery.is_delivered(key)
        delivery.deliver(key, payload_hash, lambda: "ok")
        assert delivery.is_delivered(key)
