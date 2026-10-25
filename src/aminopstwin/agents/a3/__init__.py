"""Agent A3 — evidence query (§3.3, G2.1).

schema_id='ops.evidence.query@1', envelope_type='evidence_query',
capability='query'.
"""

from aminopstwin.agents.base import BaseAgent

__all__ = ["AgentA3"]


class AgentA3(BaseAgent):
    """A3: query the evidence registry."""

    agent_id = "A3"
    schema_id = "ops.evidence.query@1"
    envelope_type = "evidence_query"
    capability = "query"
