"""Backward-compatible re-exports from the unified agents._shared.base module.

All Agent infrastructure is now in agents/_shared/base.py.
This module exists to preserve existing imports:
    from agents.definitions.base import Agent, AgentConfig
"""

from agents._shared.base import (  # noqa: F401
    Agent,
    AgentConfig,
    AgentTurn,
    SkillContent,
    PROMPTS_DIR,
    _format_skills_block as format_skills_block,
)
from agents.tool_wrappers.registry import call_tool  # noqa: F401 — used as mock target by tests

__all__ = [
    "Agent", "AgentConfig", "AgentTurn", "SkillContent",
    "PROMPTS_DIR", "format_skills_block", "call_tool",
]
