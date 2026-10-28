"""Agent base — shared AgentTrace model and base agent (§3.3, G2.1).

AgentTrace is a Pydantic v2 frozen, strict model that records the
execution of a single agent process. Each agent produces an independent
trace with a unique correlation_id (G2.1).
"""

from __future__ import annotations

import datetime as _dt
import hashlib
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from aminopstwin.contracts.canonical import canonical_hash
from aminopstwin.contracts.clock import Clock, IdFactory
from aminopstwin.contracts.decision import Decision, DecisionRecord
from aminopstwin.contracts.envelope import Envelope
from aminopstwin.contracts.request_context import RequestContext
from aminopstwin.executor import ExecutorState, ExecutorStateMachine
from aminopstwin.gateway.gateway import PolicyGateway

__all__ = ["AgentTrace", "BaseAgent"]


class AgentTrace(BaseModel):
    """Trace of a single agent process execution (§3.3, G2.1).

    model_config: frozen, strict, extra="forbid".
    """

    model_config = ConfigDict(
        extra="forbid",
        frozen=True,
        strict=True,
    )

    agent_id: str
    correlation_id: uuid.UUID
    capability: str
    started_at: _dt.datetime
    completed_at: _dt.datetime
    tokens_used: int = Field(ge=0)
    evidence_keys: list[str] = Field(default_factory=list)
    state_hash: str

    @field_validator("started_at")
    @classmethod
    def _validate_started_at(cls, v: _dt.datetime) -> _dt.datetime:
        if v.tzinfo is None:
            raise ValueError("started_at must be timezone-aware (UTC)")
        return v

    @field_validator("completed_at")
    @classmethod
    def _validate_completed_at(cls, v: _dt.datetime) -> _dt.datetime:
        if v.tzinfo is None:
            raise ValueError("completed_at must be timezone-aware (UTC)")
        return v


class BaseAgent:
    """Base class for all agents (A1–A5).

    Subclasses define agent_id, schema_id, envelope_type, and
    capability. The process() method creates an Envelope, evaluates
    it through the Gateway, and if allowed, transitions the executor.
    """

    agent_id: str = ""
    schema_id: str = ""
    envelope_type: str = ""
    capability: str = ""

    def _make_envelope(
        self,
        correlation_id: uuid.UUID,
        payload: dict[str, Any],
        clock: Clock,
        id_factory: IdFactory,
        tenant_id: str,
        policy_epoch: int = 0,
        causation_id: uuid.UUID | None = None,
    ) -> Envelope:
        """Create a valid Envelope for this agent's schema."""
        return Envelope(
            envelope_version="1.0",
            schema_id=self.schema_id,
            envelope_type=self.envelope_type,
            correlation_id=correlation_id,
            causation_id=causation_id,
            tenant_id=tenant_id,
            policy_epoch=policy_epoch,
            idempotency_key=id_factory.new_id().hex[:32].ljust(
                16, "0"
            ),
            payload=payload,
            payload_hash=canonical_hash(payload),
            created_at=clock.now(),
        )

    def process(
        self,
        correlation_id: uuid.UUID,
        payload: dict[str, Any],
        clock: Clock,
        id_factory: IdFactory,
        gateway: PolicyGateway,
        executor: ExecutorStateMachine,
        policy_epoch: int = 0,
        context: RequestContext | None = None,
    ) -> AgentTrace:
        """Process a single request and return an AgentTrace.

        1. Create an Envelope with the agent's schema_id.
        2. Evaluate it through the Gateway.
        3. If allowed, transition the executor state machine.
        4. Return the trace with correlation_id.

        If *context* is provided, the tenant_id and causation_id are
        taken from it (P26, ADR-008). Otherwise, the caller must
        supply a tenant_id explicitly (no hard-coded default).
        """
        started_at = clock.now()

        if context is None:
            raise ValueError(
                "context (RequestContext) is required; "
                "tenant_id must come from an explicit RequestContext"
            )
        tenant_id = context.tenant_id
        causation_id: uuid.UUID | None = context.causation_id
        policy_epoch = context.policy_epoch

        envelope = self._make_envelope(
            correlation_id=correlation_id,
            payload=payload,
            clock=clock,
            id_factory=id_factory,
            policy_epoch=policy_epoch,
            tenant_id=tenant_id,
            causation_id=causation_id,
        )

        decision: DecisionRecord = gateway.evaluate(
            envelope,
            principal=self.agent_id,
            decided_at=clock.now(),
            capability=self.capability,
        )

        tokens_used = 0
        evidence_keys: list[str] = []

        if decision.decision == Decision.ALLOW:
            # Transition through the executor state machine
            if executor.state == ExecutorState.PENDING:
                executor.transition(ExecutorState.RUNNING)
            executor.transition(ExecutorState.CHECKPOINTED)
            executor.transition(ExecutorState.COMMIT_INTENT)
            executor.transition(ExecutorState.COMMITTED)
            executor.transition(ExecutorState.COMPLETED)
            tokens_used = len(payload) + 1
            evidence_keys = [envelope.payload_hash]

        completed_at = clock.now()

        # State hash: hash of the executor's state history
        state_str = "|".join(s.value for s in executor.history)
        state_hash = hashlib.sha256(
            state_str.encode("utf-8")
        ).hexdigest()

        return AgentTrace(
            agent_id=self.agent_id,
            correlation_id=correlation_id,
            capability=self.capability,
            started_at=started_at,
            completed_at=completed_at,
            tokens_used=tokens_used,
            evidence_keys=evidence_keys,
            state_hash=state_hash,
        )
