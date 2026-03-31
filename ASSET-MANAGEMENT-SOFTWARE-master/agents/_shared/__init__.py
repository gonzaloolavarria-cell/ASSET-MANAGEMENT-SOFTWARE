# agents/_shared/__init__.py
"""Infraestructura compartida para todos los agentes."""

from agents._shared.base import AgentConfig, Agent, AgentTurn, SkillContent
from agents._shared.loader import load_agent, load_skills_for_agent
from agents._shared.memory import (
    MemoryContent,
    MILESTONE_TO_STAGES,
    load_memory_for_milestone,
    load_memory_for_stage,
    format_memory_block,
)

__all__ = [
    "AgentConfig", "Agent", "AgentTurn", "SkillContent",
    "load_agent", "load_skills_for_agent",
    "MemoryContent", "MILESTONE_TO_STAGES",
    "load_memory_for_milestone", "load_memory_for_stage", "format_memory_block",
]
