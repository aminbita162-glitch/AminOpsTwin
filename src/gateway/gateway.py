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

from src.contracts.decision import Decision, DecisionRecord, Stage
from src.contracts.envelope import Envelope

__all__ = [
    "PolicyGateway",
    "PolicyMatrixEntry",
    "PolicyMatrix",
    "GatewayError",
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
    ) -> DecisionRecord:
        """Evaluate an envelope and return a DecisionRecord.

        This is a pure function: repeated calls with the same inputs
        produce identical DecisionRecords (G1.2).
        """
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
