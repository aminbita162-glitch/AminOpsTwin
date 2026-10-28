"""Policy Gateway (S1) — pure function, deny-by-default (§3.2, §3.8, §3.9).

The Gateway evaluates every envelope against the current policy epoch and
policy matrix. It is a pure function: the same inputs always produce the same
output (G1.2). It never queries time, the network, or mutable storage
internally (§3.9).

Inputs:
    - envelope: the Envelope to evaluate
    - principal: the runtime-bound principal (A1..A5, S1, S2)
    - current_epoch: the current policy epoch
    - policy_matrix: the allow-list of (principal, envelope_type,
      capability) triples
    - decided_at: the trusted injected Clock input
    - schema_registry: set of known schema_ids
    - envelope_type_registry: mapping of schema_id -> envelope_type

Output:
    - DecisionRecord (ALLOW or DENY with exact reason code)

Evaluation order (§4.1 pre-filter):
    1. Schema validation (already done by Envelope construction)
    2. Policy Gateway:
       a. epoch check
       b. authorization (policy matrix)
       c. deny-by-default for unknown actions
"""

from __future__ import annotations

import datetime as _dt
from typing import Final

from aminopstwin.contracts.authority import AuthorityLevel
from aminopstwin.contracts.decision import Decision, DecisionRecord, Stage
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.contracts.state_facts import StateFacts, state_facts_hash

__all__ = [
    "PolicyGateway",
    "PolicyMatrixEntry",
    "PolicyMatrix",
    "GatewayError",
    "AuthorityDecision",
    "combine_authority",
]


class GatewayError(Exception):
    """Raised when the Gateway encounters an internal error (not a
    denial)."""


class PolicyMatrixEntry:
    """A single entry in the policy matrix (§3.8).

    (principal, envelope_type, capability) triple.
    """

    __slots__ = ("principal", "envelope_type", "capability")

    def __init__(
        self, principal: str, envelope_type: str, capability: str
    ) -> None:
        self.principal = principal
        self.envelope_type = envelope_type
        self.capability = capability

    def matches(
        self, principal: str, envelope_type: str, capability: str
    ) -> bool:
        return (
            self.principal == principal
            and self.envelope_type == envelope_type
            and self.capability == capability
        )

    def __repr__(self) -> str:
        return (
            f"PolicyMatrixEntry({self.principal!r}, "
            f"{self.envelope_type!r}, {self.capability!r})"
        )

    def __hash__(self) -> int:
        return hash((self.principal, self.envelope_type, self.capability))

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, PolicyMatrixEntry):
            return NotImplemented
        return (
            self.principal == other.principal
            and self.envelope_type == other.envelope_type
            and self.capability == other.capability
        )


class PolicyMatrix:
    """Deny-by-default allow-list of (principal, envelope_type, capability)
    triples (§3.8).

    A combination not listed => DENY GW-AUTH-001.
    """

    def __init__(
        self, entries: set[PolicyMatrixEntry] | None = None
    ) -> None:
        self._entries: set[PolicyMatrixEntry] = entries or set()

    def add(self, entry: PolicyMatrixEntry) -> None:
        self._entries.add(entry)

    def is_allowed(
        self, principal: str, envelope_type: str, capability: str
    ) -> bool:
        for e in self._entries:
            if e.matches(principal, envelope_type, capability):
                return True
        return False

    @property
    def entries(self) -> set[PolicyMatrixEntry]:
        return set(self._entries)

    def __len__(self) -> int:
        return len(self._entries)


class PolicyGateway:
    """Pure-function Policy Gateway (S1) — deny-by-default.

    The same inputs always produce the same DecisionRecord (G1.2 purity).
    """

    def __init__(
        self,
        policy_matrix: PolicyMatrix,
        current_epoch: int,
        schema_registry: set[str] | None = None,
        envelope_type_registry: dict[str, str] | None = None,
    ) -> None:
        self._policy_matrix = policy_matrix
        self._current_epoch = current_epoch
        self._schema_registry: set[str] = schema_registry or set()
        self._envelope_type_registry: dict[str, str] = (
            envelope_type_registry or {}
        )

    @property
    def current_epoch(self) -> int:
        return self._current_epoch

    def evaluate(
        self,
        envelope: Envelope,
        principal: str,
        decided_at: _dt.datetime,
        capability: str = "default",
        state_facts: StateFacts | None = None,
    ) -> DecisionRecord:
        """Evaluate an envelope and return a DecisionRecord.

        This is a pure function: repeated calls with the same inputs
        produce identical DecisionRecords (G1.2).

        If *state_facts* is provided, its canonical hash is included
        in the returned DecisionRecord (P12, §112).
        """
        sf_hash = (
            state_facts_hash(state_facts)
            if state_facts is not None
            else None
        )

        # --- Stage 1: Schema validation (already done by Envelope) ---
        # Check schema_id and envelope_type against the registries.
        if envelope.schema_id not in self._schema_registry:
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.SCHEMA,
                reason_code="GW-DEFAULT-001",
                secondary_codes=[],
                policy_epoch=self._current_epoch,
                rule_ids=["deny-unknown-schema"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=sf_hash,
            )

        expected_type = self._envelope_type_registry.get(
            envelope.schema_id
        )
        if (
            expected_type is not None
            and envelope.envelope_type != expected_type
        ):
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.SCHEMA,
                reason_code="GW-DEFAULT-001",
                secondary_codes=[],
                policy_epoch=self._current_epoch,
                rule_ids=["deny-type-mismatch"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=sf_hash,
            )

        # --- Stage 2: Epoch check (§3.7) ---
        if envelope.policy_epoch < self._current_epoch:
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.GATEWAY,
                reason_code="GW-EPOCH-001",
                secondary_codes=[],
                policy_epoch=self._current_epoch,
                rule_ids=["epoch-outdated"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=sf_hash,
            )

        if envelope.policy_epoch > self._current_epoch:
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.GATEWAY,
                reason_code="GW-EPOCH-002",
                secondary_codes=[],
                policy_epoch=self._current_epoch,
                rule_ids=["epoch-future"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=sf_hash,
            )

        # --- Stage 3: Authorization (policy matrix, §3.8) ---
        if not self._policy_matrix.is_allowed(
            principal, envelope.envelope_type, capability
        ):
            return DecisionRecord(
                decision=Decision.DENY,
                stage=Stage.GATEWAY,
                reason_code="GW-AUTH-001",
                secondary_codes=[],
                policy_epoch=self._current_epoch,
                rule_ids=["deny-not-in-matrix"],
                correlation_id=envelope.correlation_id,
                principal=principal,
                payload_hash=envelope.payload_hash,
                decided_at=decided_at,
                state_facts_hash=sf_hash,
            )

        # --- All checks passed: ALLOW ---
        return DecisionRecord(
            decision=Decision.ALLOW,
            stage=Stage.GATEWAY,
            reason_code=None,
            secondary_codes=[],
            policy_epoch=self._current_epoch,
            rule_ids=["allow"],
            correlation_id=envelope.correlation_id,
            principal=principal,
            payload_hash=envelope.payload_hash,
            decided_at=decided_at,
            state_facts_hash=sf_hash,
        )

    def evaluate_pure(
        self,
        envelope: Envelope,
        principal: str,
        decided_at: _dt.datetime,
        capability: str = "default",
    ) -> DecisionRecord:
        """Alias for evaluate — emphasizes purity."""
        return self.evaluate(
            envelope, principal, decided_at, capability
        )


# Known principals (§3.1, §3.2)
KNOWN_PRINCIPALS: Final[tuple[str, ...]] = (
    "A1",
    "A2",
    "A3",
    "A4",
    "A5",
    "S1",
    "S2",
)


# ---------------------------------------------------------------------------#
# Authority precedence (ADR-007)
# ---------------------------------------------------------------------------#


class AuthorityDecision:
    """A single authority-level decision (ADR-007).

    Combines a :class:`~aminopstwin.contracts.authority.AuthorityLevel`
    with a :class:`~aminopstwin.contracts.decision.Decision` and a
    rule id.
    """

    __slots__ = ("level", "decision", "rule_id")

    def __init__(
        self,
        level: AuthorityLevel,
        decision: Decision,
        rule_id: str,
    ) -> None:
        self.level = level
        self.decision = decision
        self.rule_id = rule_id

    def __repr__(self) -> str:
        return (
            f"AuthorityDecision(level={self.level!r}, "
            f"decision={self.decision!r}, rule_id={self.rule_id!r})"
        )


def combine_authority(
    decisions: list[AuthorityDecision],
) -> tuple[Decision, str]:
    """Combine multiple authority-level decisions using deny-overrides.

    The highest-precedence (lowest integer) level wins. If the highest
    level says DENY, the result is DENY. If the highest level says
    ALLOW but a same-level conflict says DENY, the result is DENY
    (deny-overrides). The winning rule id is returned with the result.

    Returns (Decision, rule_id).
    """
    if not decisions:
        return Decision.DENY, "deny-no-decisions"

    # Find the highest-precedence level (lowest integer).
    min_level = min(d.level for d in decisions)

    # Gather all decisions at that level.
    top_level = [
        d for d in decisions if d.level == min_level
    ]

    # Deny-overrides: if any at the top level says DENY, DENY wins.
    for d in top_level:
        if d.decision == Decision.DENY:
            return Decision.DENY, d.rule_id

    # All at the top level say ALLOW.
    return Decision.ALLOW, top_level[0].rule_id
