"""Tests for P26 deliverable 6: Authority precedence (ADR-007).

G26.6: a lower-level ALLOW never flips a higher-level DENY;
      an equal-level conflict yields DENY.
"""

from __future__ import annotations

from aminopstwin.contracts.authority import AuthorityLevel
from aminopstwin.contracts.decision import Decision
from aminopstwin.gateway.gateway import AuthorityDecision, combine_authority


class TestAuthorityPrecedence:
    """Tests for deny-overrides combining (ADR-007)."""

    def test_higher_level_deny_overrides_lower_level_allow(self) -> None:
        """G26.6: a lower-level ALLOW never flips a higher-level DENY."""
        decisions = [
            AuthorityDecision(AuthorityLevel.LAW, Decision.DENY, "law-deny"),
            AuthorityDecision(AuthorityLevel.AGENT, Decision.ALLOW, "agent-allow"),
        ]
        result, rule_id = combine_authority(decisions)
        assert result == Decision.DENY
        assert rule_id == "law-deny"

    def test_equal_level_conflict_yields_deny(self) -> None:
        """G26.6: an equal-level conflict yields DENY."""
        decisions = [
            AuthorityDecision(AuthorityLevel.OWNER, Decision.ALLOW, "owner-allow"),
            AuthorityDecision(AuthorityLevel.OWNER, Decision.DENY, "owner-deny"),
        ]
        result, rule_id = combine_authority(decisions)
        assert result == Decision.DENY
        assert rule_id == "owner-deny"

    def test_all_allow_yields_allow(self) -> None:
        decisions = [
            AuthorityDecision(AuthorityLevel.LAW, Decision.ALLOW, "law-allow"),
            AuthorityDecision(AuthorityLevel.AGENT, Decision.ALLOW, "agent-allow"),
        ]
        result, rule_id = combine_authority(decisions)
        assert result == Decision.ALLOW
        assert rule_id == "law-allow"

    def test_no_decisions_yields_deny(self) -> None:
        result, rule_id = combine_authority([])
        assert result == Decision.DENY
        assert rule_id == "deny-no-decisions"

    def test_lower_level_deny_does_not_override_higher_level_allow(self) -> None:
        decisions = [
            AuthorityDecision(AuthorityLevel.LAW, Decision.ALLOW, "law-allow"),
            AuthorityDecision(AuthorityLevel.AGENT, Decision.DENY, "agent-deny"),
        ]
        result, rule_id = combine_authority(decisions)
        assert result == Decision.ALLOW
        assert rule_id == "law-allow"

    def test_six_levels_exist(self) -> None:
        assert AuthorityLevel.LAW < AuthorityLevel.PLATFORM
        assert AuthorityLevel.PLATFORM < AuthorityLevel.OWNER
        assert AuthorityLevel.OWNER < AuthorityLevel.TENANT
        assert AuthorityLevel.TENANT < AuthorityLevel.ROLE
        assert AuthorityLevel.ROLE < AuthorityLevel.AGENT
