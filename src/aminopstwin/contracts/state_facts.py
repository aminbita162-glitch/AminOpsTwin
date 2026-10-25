"""StateFacts — immutable snapshot of runtime state for the Gateway (P12, §112).

The Executor builds a :class:`StateFacts` snapshot capturing the
runtime-bound facts that the pure Gateway function needs:
  - idempotency record (whether this idempotency_key has been seen)
  - budget balance (remaining tokens for the current workflow)
  - tenant link (the tenant_id of the calling workflow)
  - policy epoch and policy hash

The Gateway receives this snapshot and includes ``hash(StateFacts)`` in
the :class:`~aminopstwin.contracts.decision.DecisionRecord` so that
every decision is traceable to the exact runtime state it was made
against.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from aminopstwin.contracts.canonical import canonical_hash

__all__ = [
    "StateFacts",
    "state_facts_hash",
]


@dataclass(frozen=True)
class StateFacts:
    """Immutable snapshot of runtime facts for the Gateway (§112).

    All fields are runtime-bound (not message-derived).  The Gateway
    receives this snapshot and includes its hash in the
    :class:`DecisionRecord`.
    """

    idempotency_seen: bool
    budget_remaining: int
    budget_limit: int
    tenant_id: str
    policy_epoch: int
    policy_hash: str

    def to_canonical_dict(self) -> dict[str, Any]:
        """Serialise to a canonical JSON-serialisable dict for hashing."""
        return {
            "idempotency_seen": self.idempotency_seen,
            "budget_remaining": self.budget_remaining,
            "budget_limit": self.budget_limit,
            "tenant_id": self.tenant_id,
            "policy_epoch": self.policy_epoch,
            "policy_hash": self.policy_hash,
        }


def state_facts_hash(facts: StateFacts) -> str:
    """Return the canonical hash of a :class:`StateFacts` snapshot."""
    return canonical_hash(facts.to_canonical_dict())
