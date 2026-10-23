"""Agent A1 — ingest and normalize (§3.3, G2.1).

schema_id='ops.fixtures.synthetic@1', envelope_type='synthetic_fixture',
capability='ingest'.
"""

from src.agents.base import BaseAgent

__all__ = ["AgentA1"]


class AgentA1(BaseAgent):
    """A1: ingest and normalize synthetic fixtures."""

    agent_id = "A1"
    schema_id = "ops.fixtures.synthetic@1"
    envelope_type = "synthetic_fixture"
    capability = "ingest"
