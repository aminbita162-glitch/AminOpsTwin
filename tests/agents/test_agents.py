"""Agent tests — five agents with independent traces (G2.1).

Tests:
    - 5/5 traces produced
    - Each trace has a unique correlation_id
    - Each trace has the correct agent_id and capability
"""

from __future__ import annotations

import datetime as _dt
import uuid

import pytest
from src.agents.a1 import AgentA1
from src.agents.a2 import AgentA2
from src.agents.a3 import AgentA3
from src.agents.a4 import AgentA4
from src.agents.a5 import AgentA5
from src.agents.base import AgentTrace
from src.contracts.clock import SeededClock, SeededIdFactory
from src.executor import ExecutorStateMachine
from src.gateway.gateway import PolicyGateway, PolicyMatrix, PolicyMatrixEntry


@pytest.fixture
def full_policy_matrix() -> PolicyMatrix:
    """Policy matrix with entries for all five agents."""
    entries = {
        PolicyMatrixEntry("A1", "synthetic_fixture", "ingest"),
        PolicyMatrixEntry("A2", "scenario", "simulate"),
        PolicyMatrixEntry("A3", "evidence_query", "query"),
        PolicyMatrixEntry("A4", "assurance_weekly", "schedule"),
        PolicyMatrixEntry("A5", "scenario", "orchestrate"),
    }
    return PolicyMatrix(entries)


@pytest.fixture
def full_schema_registry() -> set[str]:
    return {
        "ops.fixtures.synthetic@1",
        "ops.sim.scenario@1",
        "ops.evidence.query@1",
        "ops.assurance.weekly@1",
    }


@pytest.fixture
def full_envelope_type_registry() -> dict[str, str]:
    return {
        "ops.fixtures.synthetic@1": "synthetic_fixture",
        "ops.sim.scenario@1": "scenario",
        "ops.evidence.query@1": "evidence_query",
        "ops.assurance.weekly@1": "assurance_weekly",
    }


@pytest.fixture
def full_gateway(
    full_policy_matrix: PolicyMatrix,
    full_schema_registry: set[str],
    full_envelope_type_registry: dict[str, str],
) -> PolicyGateway:
    return PolicyGateway(
        policy_matrix=full_policy_matrix,
        current_epoch=0,
        schema_registry=full_schema_registry,
        envelope_type_registry=full_envelope_type_registry,
    )


class TestFiveAgents:
    """G2.1: Five agents each produce independent trace with correlation_id."""

    def test_five_traces_produced(
        self,
        full_gateway: PolicyGateway,
    ) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        id_factory = SeededIdFactory(seed=42)

        agents = [AgentA1(), AgentA2(), AgentA3(), AgentA4(), AgentA5()]
        payloads = [
            {"fixture": "synthetic-001", "count": 10},
            {"scenario": "baseline", "iterations": 100},
            {"query": "evidence-lookup", "span": "W01"},
            {"assurance": "weekly", "week": "2026-W01"},
            {"orchestration": "multi-agent", "agents": 5},
        ]

        traces: list[AgentTrace] = []
        for agent, payload in zip(agents, payloads, strict=True):
            executor = ExecutorStateMachine()
            corr_id = id_factory.new_id()
            trace = agent.process(
                correlation_id=corr_id,
                payload=payload,
                clock=clock,
                id_factory=id_factory,
                gateway=full_gateway,
                executor=executor,
            )
            traces.append(trace)

        assert len(traces) == 5

    def test_unique_correlation_ids(
        self,
        full_gateway: PolicyGateway,
    ) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        id_factory = SeededIdFactory(seed=42)

        agents = [AgentA1(), AgentA2(), AgentA3(), AgentA4(), AgentA5()]
        payloads = [
            {"fixture": "synthetic-001", "count": 10},
            {"scenario": "baseline", "iterations": 100},
            {"query": "evidence-lookup", "span": "W01"},
            {"assurance": "weekly", "week": "2026-W01"},
            {"orchestration": "multi-agent", "agents": 5},
        ]

        corr_ids: list[uuid.UUID] = []
        for agent, payload in zip(agents, payloads, strict=True):
            executor = ExecutorStateMachine()
            corr_id = id_factory.new_id()
            trace = agent.process(
                correlation_id=corr_id,
                payload=payload,
                clock=clock,
                id_factory=id_factory,
                gateway=full_gateway,
                executor=executor,
            )
            corr_ids.append(trace.correlation_id)

        assert len(set(corr_ids)) == 5

    def test_correct_agent_ids_and_capabilities(
        self,
        full_gateway: PolicyGateway,
    ) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        id_factory = SeededIdFactory(seed=42)

        agents = [AgentA1(), AgentA2(), AgentA3(), AgentA4(), AgentA5()]
        expected_ids = ["A1", "A2", "A3", "A4", "A5"]
        expected_caps = [
            "ingest",
            "simulate",
            "query",
            "schedule",
            "orchestrate",
        ]
        payload = {"data": "test"}

        for agent, eid, ecap in zip(
            agents, expected_ids, expected_caps, strict=True
        ):
            executor = ExecutorStateMachine()
            corr_id = id_factory.new_id()
            trace = agent.process(
                correlation_id=corr_id,
                payload=payload,
                clock=clock,
                id_factory=id_factory,
                gateway=full_gateway,
                executor=executor,
            )
            assert trace.agent_id == eid
            assert trace.capability == ecap

    def test_trace_is_frozen(self) -> None:
        from pydantic import ValidationError

        trace = AgentTrace(
            agent_id="A1",
            correlation_id=uuid.uuid4(),
            capability="ingest",
            started_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            completed_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
            tokens_used=10,
            evidence_keys=["abc123"],
            state_hash="def456",
        )
        with pytest.raises(ValidationError):
            trace.agent_id = "A2"  # type: ignore[misc]

    def test_tokens_used_non_negative(self) -> None:
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            AgentTrace(
                agent_id="A1",
                correlation_id=uuid.uuid4(),
                capability="ingest",
                started_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                completed_at=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC),
                tokens_used=-1,
                evidence_keys=[],
                state_hash="hash",
            )

    def test_agent_trace_has_state_hash(
        self,
        full_gateway: PolicyGateway,
    ) -> None:
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        id_factory = SeededIdFactory(seed=42)
        executor = ExecutorStateMachine()
        trace = AgentA1().process(
            correlation_id=id_factory.new_id(),
            payload={"x": 1},
            clock=clock,
            id_factory=id_factory,
            gateway=full_gateway,
            executor=executor,
        )
        assert len(trace.state_hash) == 64
        int(trace.state_hash, 16)  # valid hex

    def test_denied_agent_produces_zero_tokens(
        self,
        full_gateway: PolicyGateway,
    ) -> None:
        """An agent whose envelope is denied by the gateway produces
        zero tokens and empty evidence_keys."""
        clock = SeededClock(
            start=_dt.datetime(2026, 1, 1, tzinfo=_dt.UTC)
        )
        id_factory = SeededIdFactory(seed=42)
        executor = ExecutorStateMachine()

        # Use a gateway with epoch 1 but the envelope has epoch 0
        # so the epoch check fails and the envelope is denied.
        from src.gateway.gateway import PolicyGateway

        denied_gateway = PolicyGateway(
            policy_matrix=PolicyMatrix(set()),
            current_epoch=1,
            schema_registry=set(),
            envelope_type_registry={},
        )
        trace = AgentA1().process(
            correlation_id=id_factory.new_id(),
            payload={"x": 1},
            clock=clock,
            id_factory=id_factory,
            gateway=denied_gateway,
            executor=executor,
        )
        assert trace.tokens_used == 0
        assert trace.evidence_keys == []
