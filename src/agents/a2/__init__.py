"""Agent A2 — simulate (§3.3, G2.1).

schema_id='ops.sim.scenario@1', envelope_type='scenario',
capability='simulate'.
"""

from src.agents.base import BaseAgent

__all__ = ["AgentA2"]


class AgentA2(BaseAgent):
    """A2: simulate operational scenarios."""

    agent_id = "A2"
    schema_id = "ops.sim.scenario@1"
    envelope_type = "scenario"
    capability = "simulate"
