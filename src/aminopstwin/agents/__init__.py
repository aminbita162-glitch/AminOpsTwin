"""Five Agents (A1–A5) — bounded real work with independent traces (G2.1).

Each agent:
    - Creates an Envelope with its schema_id and envelope_type
    - Evaluates it through the Policy Gateway
    - If allowed, transitions the executor state machine
    - Returns an AgentTrace with a unique correlation_id

A1: ingest and normalize  (ops.fixtures.synthetic@1, synthetic_fixture, ingest)
A2: simulate               (ops.sim.scenario@1, scenario, simulate)
A3: evidence query          (ops.evidence.query@1, evidence_query, query)
A4: governance/assurance   (ops.assurance.weekly@1, assurance_weekly, schedule)
A5: orchestration          (ops.sim.scenario@1, scenario, orchestrate)
"""

from aminopstwin.agents.a1 import AgentA1
from aminopstwin.agents.a2 import AgentA2
from aminopstwin.agents.a3 import AgentA3
from aminopstwin.agents.a4 import AgentA4
from aminopstwin.agents.a5 import AgentA5
from aminopstwin.agents.base import AgentTrace

__all__ = [
    "AgentTrace",
    "AgentA1",
    "AgentA2",
    "AgentA3",
    "AgentA4",
    "AgentA5",
]
