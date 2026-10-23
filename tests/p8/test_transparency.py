"""G5.5 — Transparency contract fields in all responses (P8, §4.5).

G5.5: 100% of responses contain the unified transparency contract
fields from §4.5.  Every response type — deterministic, template,
cache, LLM, and fallback — must include correlation_id, path,
cache_hit, policy_decision, policy_epoch, fallback_reason,
reservation_status, tokens_used, tokens_budget_remaining.
"""

from __future__ import annotations

import uuid

from src.enterprise.transparency import (
    TRANSPARENCY_REQUIRED_FIELDS,
    build_transparency_response,
)
from src.tokens.fallback import FallbackReason, ReservationStatus


class TestTransparencyContract:
    """G5.5: 100% of responses contain unified transparency fields."""

    def test_required_fields_complete(self) -> None:
        """All required fields from §4.5 are defined."""
        expected = {
            "correlation_id",
            "path",
            "cache_hit",
            "policy_decision",
            "policy_epoch",
            "fallback_reason",
            "reservation_status",
            "tokens_used",
            "tokens_budget_remaining",
        }
        assert set(TRANSPARENCY_REQUIRED_FIELDS) == expected

    def test_build_deterministic_response(self) -> None:
        """Deterministic path response has all fields."""
        resp = build_transparency_response(
            path="deterministic",
            cache_hit=False,
            policy_decision="ALLOW",
            policy_epoch=0,
            tokens_used=0,
            tokens_budget_remaining=100,
        )
        assert resp.path == "deterministic"
        assert resp.cache_hit is False
        assert resp.policy_decision == "ALLOW"
        assert resp.tokens_used == 0
        assert resp.tokens_budget_remaining == 100

    def test_build_cache_response(self) -> None:
        """Cache path response has all fields."""
        corr = str(uuid.uuid4())
        resp = build_transparency_response(
            correlation_id=corr,
            path="cache",
            cache_hit=True,
            policy_decision="ALLOW",
            policy_epoch=1,
            tokens_used=0,
            tokens_budget_remaining=50,
        )
        assert resp.path == "cache"
        assert resp.cache_hit is True
        assert resp.correlation_id == corr

    def test_build_llm_response(self) -> None:
        """LLM path response has all fields."""
        resp = build_transparency_response(
            path="llm",
            cache_hit=False,
            policy_decision="ALLOW",
            policy_epoch=0,
            tokens_used=500,
            tokens_budget_remaining=500,
        )
        assert resp.path == "llm"
        assert resp.tokens_used == 500

    def test_build_fallback_response(self) -> None:
        """Fallback response has fallback_reason set."""
        resp = build_transparency_response(
            path="deterministic",
            cache_hit=False,
            policy_decision="DENY",
            policy_epoch=0,
            fallback_reason=FallbackReason.BUDGET_SESSION_EXHAUSTED,
            reservation_status=ReservationStatus.NOT_REQUIRED,
            tokens_used=0,
            tokens_budget_remaining=0,
        )
        assert resp.fallback_reason == "BUDGET_SESSION_EXHAUSTED"
        assert resp.policy_decision == "DENY"

    def test_verify_passes_on_complete_response(self) -> None:
        """verify() returns True when all fields are present."""
        resp = build_transparency_response()
        assert resp.verify() is True

    def test_to_dict_has_all_fields(self) -> None:
        """to_dict() includes all required fields."""
        resp = build_transparency_response()
        d = resp.to_dict()
        for field_name in TRANSPARENCY_REQUIRED_FIELDS:
            assert field_name in d, (
                f"Missing field in dict: {field_name}"
            )

    def test_to_dict_extra_fields(self) -> None:
        """Extra fields are passed through to dict."""
        resp = build_transparency_response(
            extra_metric_1=42,
            extra_metric_2="test",
        )
        d = resp.to_dict()
        assert d["extra_metric_1"] == 42
        assert d["extra_metric_2"] == "test"

    def test_100_percent_fields_present(self) -> None:
        """G5.5: 100% of responses have all required fields.

        Iterate over every response path type and verify that
        each has 100% of the required fields.
        """
        paths = ["deterministic", "template", "cache", "llm"]
        for path in paths:
            resp = build_transparency_response(path=path)
            d = resp.to_dict()
            missing = [
                f for f in TRANSPARENCY_REQUIRED_FIELDS if f not in d
            ]
            assert not missing, (
                f"Path '{path}' missing fields: {missing}"
            )

    def test_uuid_correlation_id_accepted(self) -> None:
        """UUID correlation_id is converted to string."""
        corr = uuid.uuid4()
        resp = build_transparency_response(correlation_id=corr)
        assert resp.correlation_id == str(corr)

    def test_auto_correlation_id_generated(self) -> None:
        """Auto-generated correlation_id is a valid UUID string."""
        resp = build_transparency_response()
        uuid.UUID(resp.correlation_id)  # raises if invalid
