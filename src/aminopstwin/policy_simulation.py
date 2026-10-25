"""Policy Simulation Mode (P20, deliverable 2).

Evaluate a candidate policy against historical or synthetic envelopes
**without committing effects**.  The simulator produces a report with
the decisions that *would* have been made; it does not alter live
executor state, evidence registry state, or any persisted record.

Key design constraints (§3.2, §3.8):

* The :class:`PolicySimulator` wraps a :class:`PolicyGateway` but never
  calls the executor, never writes to the evidence registry, and never
  mutates the gateway's policy matrix.  It evaluates envelopes in a
  read-only fashion and collects the resulting
  :class:`~aminopstwin.contracts.decision.DecisionRecord` objects.
* The simulation report is deterministic: the same envelopes + policy
  + clock produce the same report hash.

The module is imported by the stage-close script and by the P20 test
suite.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import json
from dataclasses import dataclass, field
from typing import Any

from aminopstwin.contracts.decision import Decision
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.gateway.gateway import PolicyGateway, PolicyMatrix

__all__ = [
    "SimulationResult",
    "PolicySimulator",
    "simulate_policy",
    "SimulationReport",
]


@dataclass(frozen=True)
class SimulationResult:
    """A single envelope's simulated evaluation result."""

    envelope_id: str
    decision: Decision
    reason_code: str | None
    principal: str
    capability: str


@dataclass
class SimulationReport:
    """Report of a completed policy simulation.

    The report contains:

    * the list of per-envelope results;
    * summary counts (allowed, denied);
    * a deterministic hash over the results.
    """

    results: list[SimulationResult] = field(default_factory=list)
    allowed_count: int = 0
    denied_count: int = 0
    total: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "allowed_count": self.allowed_count,
            "denied_count": self.denied_count,
            "results": [
                {
                    "envelope_id": r.envelope_id,
                    "decision": r.decision.value,
                    "reason_code": r.reason_code,
                    "principal": r.principal,
                    "capability": r.capability,
                }
                for r in self.results
            ],
        }

    @property
    def hash(self) -> str:
        """Deterministic SHA-256 hex over the canonical report bytes."""
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


class PolicySimulator:
    """Evaluate a candidate policy without committing effects (P20).

    The simulator wraps a :class:`PolicyGateway` and evaluates a list
    of envelopes against it.  It does **not** call the executor, does
    **not** write to the evidence registry, and does **not** mutate
    the gateway's internal state.  The wrapped gateway's
    ``evaluate`` method is a pure function (G1.2), so the simulation
    is side-effect-free.
    """

    def __init__(self, gateway: PolicyGateway) -> None:
        self._gateway = gateway

    def simulate(
        self,
        envelopes: list[tuple[Envelope, str, str, _dt.datetime]],
    ) -> SimulationReport:
        """Evaluate envelopes and return a read-only report.

        Each tuple is ``(envelope, principal, capability, decided_at)``.
        """
        results: list[SimulationResult] = []
        allowed = 0
        denied = 0
        for envelope, principal, capability, decided_at in envelopes:
            record = self._gateway.evaluate(
                envelope=envelope,
                principal=principal,
                decided_at=decided_at,
                capability=capability,
            )
            results.append(
                SimulationResult(
                    envelope_id=str(envelope.correlation_id),
                    decision=record.decision,
                    reason_code=record.reason_code,
                    principal=principal,
                    capability=capability,
                )
            )
            if record.decision == Decision.ALLOW:
                allowed += 1
            else:
                denied += 1
        return SimulationReport(
            results=results,
            allowed_count=allowed,
            denied_count=denied,
            total=len(results),
        )

    @property
    def gateway(self) -> PolicyGateway:
        """The wrapped gateway (read-only view)."""
        return self._gateway


def simulate_policy(
    gateway: PolicyGateway,
    envelopes: list[tuple[Envelope, str, str, _dt.datetime]],
) -> SimulationReport:
    """Convenience: simulate a policy against envelopes (P20)."""
    simulator = PolicySimulator(gateway)
    return simulator.simulate(envelopes)


def build_candidate_gateway(
    matrix: PolicyMatrix,
    current_epoch: int,
    schema_registry: set[str] | None = None,
    envelope_type_registry: dict[str, str] | None = None,
) -> PolicyGateway:
    """Build a candidate :class:`PolicyGateway` for simulation.

    This does not affect any live gateway; the returned gateway is a
    fresh instance that can be evaluated without side effects.
    """
    return PolicyGateway(
        policy_matrix=matrix,
        current_epoch=current_epoch,
        schema_registry=schema_registry,
        envelope_type_registry=envelope_type_registry,
    )
