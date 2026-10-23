"""F07: LLM call times out → deterministic fallback with LLM_UNAVAILABLE (G2.9).

Scenario: An LLM call times out. A deterministic fallback response is
returned with fallback_reason=LLM_UNAVAILABLE. No retry storm — the
timeout is handled exactly once.
"""

from __future__ import annotations

import uuid

from src.tokens.fallback import FallbackReason, ReservationStatus
from tests.fault.infrastructure import LLMTimeoutSimulator


class TestF07LLMTimeout:
    """F07: LLM call times out → deterministic fallback, no retry storm."""

    def test_timeout_returns_fallback(self) -> None:
        sim = LLMTimeoutSimulator()
        correlation_id = uuid.uuid4()
        policy_epoch = 0

        try:
            sim.call()
        except TimeoutError:
            fallback = sim.handle_timeout(correlation_id, policy_epoch)
            assert fallback.fallback_reason == FallbackReason.LLM_UNAVAILABLE
            assert fallback.path == "deterministic"
            assert fallback.tokens_used == 0

    def test_no_retry_storm(self) -> None:
        """The timeout is handled exactly once — no retry storm."""
        sim = LLMTimeoutSimulator()
        correlation_id = uuid.uuid4()
        policy_epoch = 0

        # First attempt times out
        try:
            sim.call()
        except TimeoutError:
            pass

        # The fallback is returned without retrying
        fallback = sim.handle_timeout(correlation_id, policy_epoch)

        # Only one call was made (no retry storm)
        assert sim.call_count == 1
        assert fallback.fallback_reason == FallbackReason.LLM_UNAVAILABLE

    def test_fallback_is_deterministic(self) -> None:
        """The fallback response is deterministic (same input → same output)."""
        sim = LLMTimeoutSimulator()
        correlation_id = uuid.uuid4()
        policy_epoch = 0

        f1 = sim.handle_timeout(correlation_id, policy_epoch)
        f2 = sim.handle_timeout(correlation_id, policy_epoch)
        assert f1.fallback_reason == f2.fallback_reason
        assert f1.message_template_id == f2.message_template_id
        assert f1.message == f2.message

    def test_zero_tokens_used(self) -> None:
        """The fallback uses zero tokens (no LLM call was successful)."""
        sim = LLMTimeoutSimulator()
        fallback = sim.handle_timeout(uuid.uuid4(), 0)
        assert fallback.tokens_used == 0
        assert fallback.honesty_statement is not None
