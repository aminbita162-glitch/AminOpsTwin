"""Agent A4 — governance/assurance (§3.3, G2.1).

schema_id='ops.assurance.weekly@1', envelope_type='assurance_weekly',
capability='schedule'.
"""

from src.agents.base import BaseAgent

__all__ = ["AgentA4"]


class AgentA4(BaseAgent):
    """A4: governance and weekly assurance scheduling."""

    agent_id = "A4"
    schema_id = "ops.assurance.weekly@1"
    envelope_type = "assurance_weekly"
    capability = "schedule"
