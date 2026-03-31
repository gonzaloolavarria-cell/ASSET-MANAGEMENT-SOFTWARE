# agents/_shared/base.py
"""Unified Agent base class for OCP Maintenance AI multi-agent system.

Merges the two previous architectures:
- API loop (previously in agents/definitions/base.py)
- Milestone-based YAML skill loading (previously only here)

AgentConfig supports two prompt-loading modes:
1. agent_dir-based: loads from {agent_dir}/CLAUDE.md + skills.yaml
2. system_prompt_file-based (legacy): loads from agents/definitions/prompts/

Usage:
    # New-style (agent_dir):
    config = AgentConfig(name="Orchestrator", model="...", agent_dir="agents/orchestrator", tools=[...])
    agent = Agent(config, client=Anthropic())

    # Legacy-style (system_prompt_file):
    config = AgentConfig(name="Reliability", agent_type="reliability", model="...",
                         system_prompt_file="reliability_prompt.md", use_skills=True)
    agent = Agent(config, client=Anthropic())
"""

from __future__ import annotations

import json
import pathlib
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

# Lazy imports for Anthropic (not required for config-only usage)
_anthropic = None
_httpx = None

def _get_anthropic():
    global _anthropic
    if _anthropic is None:
        import anthropic
        _anthropic = anthropic
    return _anthropic

def _get_httpx():
    global _httpx
    if _httpx is None:
        import httpx
        _httpx = httpx
    return _httpx


# Legacy prompts directory (for system_prompt_file-based configs)
PROMPTS_DIR = pathlib.Path(__file__).parent.parent / "definitions" / "prompts"


# ---------------------------------------------------------------------------
# Skill content container
# ---------------------------------------------------------------------------

@dataclass
class SkillContent:
    """Contenido cargado de un skill."""

    name: str
    path: str
    body: str = ""
    references: list[str] = field(default_factory=list)
    mandatory: bool = False
    milestone: int | str = 0


# ---------------------------------------------------------------------------
# AgentConfig (unified)
# ---------------------------------------------------------------------------

@dataclass
class AgentConfig:
    """Unified configuration for all agents.

    Supports two prompt-loading modes:
    - agent_dir: loads CLAUDE.md from the agent's own directory
    - system_prompt_file: loads from agents/definitions/prompts/ (legacy)
    """

    name: str
    model: str

    # --- New-style: agent directory-based ---
    agent_dir: str = ""
    tools: list[str] = field(default_factory=list)

    # --- Legacy: definitions-based ---
    agent_type: str = ""
    system_prompt_file: str = ""
    use_skills: bool = False
    include_shared_skills: bool = True

    # --- Shared ---
    max_turns: int = 30
    temperature: float = 0.0
    api_timeout_seconds: float = 300.0
    api_max_retries: int = 2

    # -- Derived paths (agent_dir mode) ---------------------------------

    @property
    def system_prompt_path(self) -> Path:
        return Path(self.agent_dir) / "CLAUDE.md"

    @property
    def skills_map_path(self) -> Path:
        return Path(self.agent_dir) / "skills.yaml"

    @property
    def references_dir(self) -> Path:
        return Path(self.agent_dir) / "references"

    # -- System prompt loading ------------------------------------------

    def load_system_prompt(self) -> str:
        """Load the system prompt, with optional skill injection.

        Uses agent_dir mode (CLAUDE.md) if agent_dir is set,
        otherwise falls back to system_prompt_file (legacy).
        """
        if self.agent_dir:
            base_prompt = self.system_prompt_path.read_text(encoding="utf-8")
        elif self.system_prompt_file:
            base_prompt = (PROMPTS_DIR / self.system_prompt_file).read_text(encoding="utf-8")
        else:
            return ""

        # Inject skills if configured (legacy mode)
        if self.use_skills and self.agent_type:
            return self._inject_legacy_skills(base_prompt)

        return base_prompt

    def _inject_legacy_skills(self, base_prompt: str) -> str:
        """Inject skills via the legacy loader (for definitions-based configs)."""
        try:
            from agents._shared.loader import load_skills_for_agent as _load
        except ImportError:
            return base_prompt

        agent_skills = _load(self.agent_type)

        if self.include_shared_skills:
            try:
                from core.skills.loader import load_shared_skills
                agent_skills.extend(load_shared_skills())
            except (ModuleNotFoundError, ImportError):
                pass

        if not agent_skills:
            return base_prompt

        skills_block = _format_skills_block(agent_skills)
        return (
            f"{base_prompt}\n\n"
            f"# SKILLS (Standard Operating Procedures)\n\n"
            f"The following skills contain detailed methodology you MUST follow "
            f"when performing each type of analysis. Follow the step-by-step "
            f"instructions exactly.\n\n"
            f"{skills_block}"
        )

    # -- Milestone-based skill loading (agent_dir mode) -----------------

    def load_skills_for_milestone(self, milestone: int) -> list[SkillContent]:
        """Carga los skills asignados a este agente para un milestone."""
        if not self.agent_dir or not self.skills_map_path.exists():
            return []

        skills_config = yaml.safe_load(
            self.skills_map_path.read_text(encoding="utf-8")
        )
        relevant: list[SkillContent] = []

        for skill in skills_config.get("skills", []):
            skill_milestone = skill.get("milestone")
            if skill_milestone == milestone or skill_milestone == "all":
                content = self._load_skill_at_level(skill)
                relevant.append(content)

        return relevant

    def _load_skill_at_level(self, skill: dict[str, Any]) -> SkillContent:
        """Carga un skill según su load_level configurado."""
        skill_path = Path(skill["path"])
        load_level = skill.get("load_level", 2)

        if load_level == 1:
            body = _extract_front_matter(skill_path)
            return SkillContent(
                name=skill["name"],
                path=skill["path"],
                body=body,
                mandatory=skill.get("mandatory", False),
                milestone=skill.get("milestone", 0),
            )

        if load_level == 2:
            body = skill_path.read_text(encoding="utf-8") if skill_path.exists() else ""
            refs: list[str] = []
            for ref_rel in skill.get("references_to_preload", []):
                full_ref = skill_path.parent / ref_rel
                if full_ref.exists():
                    refs.append(full_ref.read_text(encoding="utf-8"))
            return SkillContent(
                name=skill["name"],
                path=skill["path"],
                body=body,
                references=refs,
                mandatory=skill.get("mandatory", False),
                milestone=skill.get("milestone", 0),
            )

        # load_level == 3: Solo punteros
        body = _extract_front_matter(skill_path)
        return SkillContent(
            name=skill["name"],
            path=skill["path"],
            body=body,
            mandatory=skill.get("mandatory", False),
            milestone=skill.get("milestone", 0),
        )

    def load_agent_references(self) -> dict[str, str]:
        """Carga las references propias del agente."""
        refs: dict[str, str] = {}
        if self.agent_dir and self.references_dir.exists():
            for ref_file in self.references_dir.glob("*.md"):
                refs[ref_file.stem] = ref_file.read_text(encoding="utf-8")
        return refs

    # -- Tool schema (for API loop) -------------------------------------

    def get_tools_schema(self) -> list[dict]:
        """Return Anthropic-compatible tool definitions for this agent."""
        from agents.tool_wrappers.server import get_tools_for_agent
        agent_key = self.agent_type or self.name.lower().replace(" ", "_")
        raw = get_tools_for_agent(agent_key)
        return [
            {
                "name": t["name"],
                "description": t["description"],
                "input_schema": t["input_schema"],
            }
            for t in raw
        ]


# ---------------------------------------------------------------------------
# AgentTurn (interaction record)
# ---------------------------------------------------------------------------

@dataclass
class AgentTurn:
    """Record of a single turn in the agent loop."""

    role: str
    content: Any
    tool_calls: list[dict] = field(default_factory=list)
    tool_results: list[dict] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Agent (unified: config + API loop + skill loading)
# ---------------------------------------------------------------------------

class Agent:
    """Unified agent with agentic loop and milestone-based skill loading.

    Usage:
        # With API loop:
        agent = Agent(config, client=Anthropic())
        result = agent.run("Assess criticality for SAG Mill 001")

        # Config-only (no API loop):
        agent = Agent(config)
        prompt = agent.get_system_prompt(milestone=1)
    """

    def __init__(self, config: AgentConfig, client: Any | None = None) -> None:
        self.config = config
        self._system_prompt: str | None = None
        self.history: list[AgentTurn] = []

        # Initialize Anthropic client if provided or if API params are set
        if client is not None:
            self.client = client
            self.system_prompt = config.load_system_prompt()
            self.tools = config.get_tools_schema()
        else:
            self.client = None
            self.system_prompt = ""
            self.tools = []

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def model(self) -> str:
        return self.config.model

    def get_system_prompt(
        self,
        milestone: int | None = None,
        memory_dir: "Path | None" = None,
        context: dict | None = None,
    ) -> str:
        """Assemble system prompt with skills, client memory, and intent.

        Args:
            milestone: Current milestone number (1-4).
            memory_dir: Path to project's 3-memory/ directory.
                        If None, memory injection is skipped (backward-compat).
            context: Optional dict with 'intent_profile' and other context data.
        """
        if self._system_prompt is None:
            self._system_prompt = self.config.load_system_prompt()

        prompt = self._system_prompt

        if milestone is not None and self.config.agent_dir:
            skills = self.config.load_skills_for_milestone(milestone)
            if skills:
                skills_block = _format_skills_block(skills)
                prompt = f"{prompt}\n\n{skills_block}"

        # Inject client memory AFTER skills (memory overrides methodology)
        if milestone is not None and memory_dir is not None:
            from agents._shared.memory import load_memory_for_milestone, format_memory_block
            contents = load_memory_for_milestone(milestone, memory_dir)
            block = format_memory_block(contents)
            if block:
                prompt = f"{prompt}\n\n{block}"

        # Inject client intent AFTER memory (memory overrides intent)
        context = context or {}
        intent_profile = context.get("intent_profile")
        if intent_profile:
            intent_block = _format_intent_block(intent_profile)
            if intent_block:
                prompt = f"{prompt}\n\n{intent_block}"

        return prompt

    def run(self, user_message: str, context: list[dict] | None = None) -> str:
        """Execute the agent loop until a final text response is produced.

        Requires a client to be set (passed in __init__).

        Args:
            user_message: The task/instruction for this agent.
            context: Optional prior conversation messages to prepend.

        Returns:
            Final text response from the agent.
        """
        if self.client is None:
            raise RuntimeError(
                f"Agent '{self.config.name}' has no Anthropic client. "
                "Pass client=Anthropic() to Agent.__init__() to use the API loop."
            )

        anthropic_mod = _get_anthropic()
        from anthropic.types import TextBlock, ToolUseBlock
        # Import call_tool from the definitions module so tests can mock it
        # at agents.definitions.base.call_tool (backward-compat mock target)
        from agents.definitions.base import call_tool

        messages = list(context) if context else []
        messages.append({"role": "user", "content": user_message})

        text_parts: list[str] = []

        for _turn in range(self.config.max_turns):
            response = self._call_api(messages)

            text_parts = []
            tool_uses = []
            for block in response.content:
                if isinstance(block, TextBlock):
                    text_parts.append(block.text)
                elif isinstance(block, ToolUseBlock):
                    tool_uses.append(block)

            turn = AgentTurn(
                role="assistant",
                content=response.content,
                tool_calls=[{"id": t.id, "name": t.name, "input": t.input} for t in tool_uses],
            )

            if not tool_uses:
                self.history.append(turn)
                return "\n".join(text_parts)

            messages.append({"role": "assistant", "content": response.content})

            tool_results_content = []
            for tool_use in tool_uses:
                result_str = call_tool(tool_use.name, tool_use.input)
                tool_results_content.append({
                    "type": "tool_result",
                    "tool_use_id": tool_use.id,
                    "content": result_str,
                })
                turn.tool_results.append({
                    "tool_use_id": tool_use.id,
                    "tool_name": tool_use.name,
                    "result": result_str,
                })

            self.history.append(turn)
            messages.append({"role": "user", "content": tool_results_content})

        return "\n".join(text_parts) if text_parts else "[Agent reached max turns without final response]"

    def _call_api(self, messages: list[dict]) -> Any:
        """API call to Anthropic Messages with timeout retry."""
        anthropic_mod = _get_anthropic()
        httpx_mod = _get_httpx()

        if self.client is None:
            raise RuntimeError("No Anthropic client configured")

        kwargs: dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": 8192,
            "system": self.system_prompt or self.get_system_prompt(),
            "messages": messages,
            "temperature": self.config.temperature,
        }
        if self.tools:
            kwargs["tools"] = self.tools

        for attempt in range(self.config.api_max_retries + 1):
            try:
                return self.client.messages.create(**kwargs)
            except anthropic_mod.APITimeoutError:
                if attempt < self.config.api_max_retries:
                    time.sleep(2 ** attempt)
                    continue
                raise

    def reset(self) -> None:
        """Clear conversation history for a fresh run."""
        self.history.clear()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _format_intent_block(profile: dict) -> str:
    """Format intent profile as a context block for system prompt injection."""
    summary = profile.get("intent_summary")
    if not summary or not isinstance(summary, dict):
        return ""

    lines = [
        "<client_intent>",
        "# CLIENT INTENT — Trade-off priorities and constraints",
        "",
        f"**Client**: {summary.get('client', 'Unknown')}",
        f"**Project**: {summary.get('project', 'Unknown')}",
    ]

    priority = summary.get("trade_off_priority", [])
    if priority:
        lines.append(f"**Trade-off Priority**: {' > '.join(str(p) for p in priority)}")

    if summary.get("risk_appetite"):
        lines.append(f"**Risk Appetite**: {summary['risk_appetite']}")

    if summary.get("primary_kpi"):
        target = summary.get("primary_kpi_target", "")
        kpi_line = f"**Primary KPI**: {summary['primary_kpi']}"
        if target:
            kpi_line += f" (target: {target})"
        lines.append(kpi_line)

    hard_limits = summary.get("hard_limits", [])
    if hard_limits:
        lines.append("")
        lines.append("**Hard Limits** (non-negotiable):")
        for limit in hard_limits:
            lines.append(f"- {limit}")

    lines.append("")
    lines.append("When intent conflicts with methodology default:")
    lines.append("- Memory requirements OVERRIDE intent")
    lines.append("- Intent priorities OVERRIDE methodology defaults")
    lines.append("- Hard limits are NEVER overridable (escalate to human)")
    lines.append("</client_intent>")
    return "\n".join(lines)


def _format_skills_block(skills: list[SkillContent]) -> str:
    """Format loaded skills as a context block."""
    lines = ["<loaded_skills>"]
    for skill in skills:
        lines.append(f"\n## Skill: {skill.name}")
        lines.append(f"Path: {skill.path}")
        lines.append(f"Mandatory: {skill.mandatory}")
        if skill.body:
            lines.append(f"\n{skill.body}")
        for i, ref in enumerate(skill.references, 1):
            lines.append(f"\n### Reference {i}:\n{ref}")
    lines.append("\n</loaded_skills>")
    return "\n".join(lines)


def _extract_front_matter(path: Path) -> str:
    """Extrae el YAML front matter de un archivo Markdown."""
    if not path.exists():
        return ""

    text = path.read_text(encoding="utf-8")
    if not text.startswith("---"):
        return ""

    end = text.find("---", 3)
    if end == -1:
        return ""

    return text[: end + 3]
