"""Planning Specialist Agent definition.

Expert in work packaging, SAP PM integration, work instructions, and
CAPA management. Uses the sonnet model for balanced speed/quality.
Participates in Milestones 3 and 4.
"""

from agents.definitions.base import Agent, AgentConfig

PLANNING_CONFIG = AgentConfig(
    name="Planning Specialist",
    agent_type="planning",
    model="claude-sonnet-4-6",
    agent_dir="agents/planning",
    max_turns=30,
    temperature=0.0,
)


def create_planning_agent(client=None) -> Agent:
    """Create a Planning Specialist agent instance."""
    return Agent(PLANNING_CONFIG, client=client)
