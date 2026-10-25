"""F08: LLM returns malformed output → rejected at OUTPUT stage (G2.9).

Scenario: The LLM returns malformed output (invalid JSON). The output
is rejected at the OUTPUT validation stage. A deterministic fallback
response is returned with fallback_reason=OUTPUT_VALIDATION_FAILED.
"""

from __future__ import annotations

import uuid

from aminopstwin.tokens.fallback import FallbackReason

from tests.fault.infrastructure import LLMMalformedSimulator


class TestF08MalformedOutput:
    """F08: LLM returns malformed output → rejected at OUTPUT stage."""

    def test_malformed_output_rejected(self) -> None:
        sim = LLMMalformedSimulator()
        output = sim.call()
        assert not LLMMalformedSimulator.validate_output(output)

    def test_output_validation_failed_fallback(self) -> None:
        sim = LLMMalformedSimulator()
        output = sim.call()
        assert not LLMMalformedSimulator.validate_output(output)

        fallback = sim.handle_malformed(uuid.uuid4(), 0)
        assert fallback.fallback_reason == (
            FallbackReason.OUTPUT_VALIDATION_FAILED
        )
        assert fallback.path == "deterministic"
        assert fallback.tokens_used == 0

    def test_valid_output_accepted(self) -> None:
        """Valid output passes validation (negative test)."""
        import json
        valid = json.dumps({"result": "ok", "value": 42})
        assert LLMMalformedSimulator.validate_output(valid)

    def test_malformed_output_single_call(self) -> None:
        """The malformed output is detected on a single call."""
        sim = LLMMalformedSimulator()
        output = sim.call()
        assert sim.call_count == 1
        assert not LLMMalformedSimulator.validate_output(output)

    def test_fallback_deterministic(self) -> None:
        """The fallback response is deterministic."""
        sim = LLMMalformedSimulator()
        f1 = sim.handle_malformed(uuid.uuid4(), 0)
        f2 = sim.handle_malformed(uuid.uuid4(), 0)
        assert f1.fallback_reason == f2.fallback_reason
        assert f1.message_template_id == f2.message_template_id

    def test_no_partial_state(self) -> None:
        """Malformed output produces no partial state — tokens_used=0."""
        sim = LLMMalformedSimulator()
        fallback = sim.handle_malformed(uuid.uuid4(), 0)
        assert fallback.tokens_used == 0
        assert fallback.honesty_statement is not None
