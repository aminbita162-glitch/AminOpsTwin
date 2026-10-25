"""Agent A5 — orchestration (§3.3, G2.1).

schema_id='ops.sim.scenario@1', envelope_type='scenario',
capability='orchestrate'.
"""

from aminopstwin.agents.base import BaseAgent

__all__ = ["AgentA5"]


class AgentA5(BaseAgent):
    """A5: orchestrate multi-agent simulation workflows."""

    agent_id = "A5"
    schema_id = "ops.sim.scenario@1"
    envelope_type = "scenario"
    capability = "orchestrate"
