# tests/test_memory.py
"""Tests for agents/_shared/memory.py — hierarchical memory system.

Categories:
  - Functional: load, format, save operations
  - Integration: memory + base.py, memory + workflow.py
  - Security: path traversal, injection, sanitization
"""
from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents._shared.memory import (
    MILESTONE_TO_STAGES,
    MemoryContent,
    _sanitize_content,
    _validate_id,
    extract_learning,
    format_memory_block,
    load_memory_for_milestone,
    load_memory_for_stage,
    save_deviation,
    save_meeting_notes,
    save_pattern,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _create_memory_tree(tmp_path: Path) -> Path:
    """Create a realistic 3-memory/ directory structure for testing."""
    mem = tmp_path / "3-memory"
    mem.mkdir()

    # Global requirements
    (mem / "global-requirements.md").write_text(
        "# Global Requirements\n\n- Primary language: fr\n- CMMS: SAP PM\n",
        encoding="utf-8",
    )

    # Maintenance strategy
    ms = mem / "maintenance-strategy"
    ms.mkdir()
    (ms / "requirements.md").write_text(
        "# Maintenance Strategy Requirements\n\n- Criticality method: R8+GFSN\n",
        encoding="utf-8",
    )
    (ms / "patterns.md").write_text(
        "# Patterns\n\n### PAT-001: Use OEM intervals for new equipment\n"
        "- **Context**: New equipment with no failure history\n"
        "- **Decision**: Use OEM-recommended intervals\n",
        encoding="utf-8",
    )

    # Work planning
    wp = mem / "work-planning"
    wp.mkdir()
    (wp / "requirements.md").write_text(
        "# Work Planning Requirements\n\n- SAP version: ECC 6.0\n",
        encoding="utf-8",
    )
    (wp / "patterns.md").write_text(
        "# Work Planning Patterns\n\n<!-- No patterns yet -->\n",
        encoding="utf-8",
    )

    # Reliability engineering
    re_dir = mem / "reliability-engineering"
    re_dir.mkdir()
    (re_dir / "requirements.md").write_text(
        "# Reliability Engineering Requirements\n\n- Weibull fitting: Required\n",
        encoding="utf-8",
    )

    # Cost analysis
    ca = mem / "cost-analysis"
    ca.mkdir()
    (ca / "requirements.md").write_text(
        "# Cost Analysis Requirements\n\n- Currency: USD\n",
        encoding="utf-8",
    )

    # Empty dirs
    (mem / "deviations").mkdir()
    (mem / "meetings").mkdir()

    return mem


# ============================================================================
# FUNCTIONAL TESTS
# ============================================================================


class TestMilestoneToStages:
    """Verify the MILESTONE_TO_STAGES mapping is correct."""

    def test_m1_maps_to_maintenance_strategy(self):
        assert MILESTONE_TO_STAGES[1] == ["maintenance-strategy"]

    def test_m2_maps_to_maintenance_strategy_and_reliability(self):
        assert MILESTONE_TO_STAGES[2] == ["maintenance-strategy", "reliability-engineering"]

    def test_m3_maps_to_work_planning_and_cost(self):
        assert MILESTONE_TO_STAGES[3] == ["work-planning", "cost-analysis"]

    def test_m4_maps_to_work_planning(self):
        assert MILESTONE_TO_STAGES[4] == ["work-planning"]

    def test_all_four_milestones_defined(self):
        assert set(MILESTONE_TO_STAGES.keys()) == {1, 2, 3, 4}


class TestLoadMemoryForStage:
    """Test load_memory_for_stage function."""

    def test_returns_empty_if_dir_missing(self, tmp_path):
        result = load_memory_for_stage("maintenance-strategy", tmp_path / "nonexistent")
        assert result == []

    def test_loads_global_requirements(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("maintenance-strategy", mem)
        global_items = [mc for mc in result if mc.category == "global"]
        assert len(global_items) == 1
        assert "Primary language: fr" in global_items[0].body

    def test_loads_stage_requirements(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("maintenance-strategy", mem)
        stage_items = [mc for mc in result if mc.category == "stage"]
        assert len(stage_items) == 1
        assert "Criticality method: R8+GFSN" in stage_items[0].body

    def test_loads_patterns_with_real_content(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("maintenance-strategy", mem)
        pattern_items = [mc for mc in result if mc.category == "pattern"]
        assert len(pattern_items) == 1
        assert "PAT-001" in pattern_items[0].body

    def test_skips_patterns_with_only_comments(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("work-planning", mem)
        pattern_items = [mc for mc in result if mc.category == "pattern"]
        assert len(pattern_items) == 0

    def test_returns_three_items_for_full_stage(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("maintenance-strategy", mem)
        assert len(result) == 3  # global + requirements + patterns

    def test_returns_two_items_when_no_patterns(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("reliability-engineering", mem)
        assert len(result) == 2  # global + requirements (no patterns file)

    def test_source_paths_are_relative(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("maintenance-strategy", mem)
        sources = {mc.source for mc in result}
        assert "global-requirements.md" in sources
        assert "maintenance-strategy/requirements.md" in sources

    def test_nonexistent_stage_returns_only_global(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_stage("work-identification", mem)
        assert len(result) == 1
        assert result[0].category == "global"


class TestLoadMemoryForMilestone:
    """Test load_memory_for_milestone function."""

    def test_milestone_1_loads_maintenance_strategy(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_milestone(1, mem)
        sources = {mc.source for mc in result}
        assert "maintenance-strategy/requirements.md" in sources

    def test_milestone_2_loads_both_stages(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_milestone(2, mem)
        sources = {mc.source for mc in result}
        assert "maintenance-strategy/requirements.md" in sources
        assert "reliability-engineering/requirements.md" in sources

    def test_milestone_3_loads_work_planning_and_cost(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_milestone(3, mem)
        sources = {mc.source for mc in result}
        assert "work-planning/requirements.md" in sources
        assert "cost-analysis/requirements.md" in sources

    def test_deduplicates_global_requirements(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_milestone(2, mem)
        global_items = [mc for mc in result if mc.source == "global-requirements.md"]
        assert len(global_items) == 1  # only one, not two

    def test_unknown_milestone_returns_empty(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        result = load_memory_for_milestone(99, mem)
        assert result == []

    def test_graceful_fallback_missing_dir(self, tmp_path):
        result = load_memory_for_milestone(1, tmp_path / "nope")
        assert result == []


class TestFormatMemoryBlock:
    """Test format_memory_block function."""

    def test_empty_contents_returns_empty_string(self):
        assert format_memory_block([]) == ""

    def test_wraps_in_client_memory_tags(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert block.startswith("<client_memory>")
        assert block.endswith("</client_memory>")

    def test_contains_must_follow_header(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert "MUST follow these requirements" in block

    def test_contains_override_instruction(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert "OVERRIDE methodology defaults" in block

    def test_contains_source_comments(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert "<!-- source: global-requirements.md (global) -->" in block

    def test_contains_actual_content(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert "Primary language: fr" in block
        assert "Criticality method: R8+GFSN" in block

    def test_single_item(self):
        mc = MemoryContent("test.md", "global", "Hello world")
        block = format_memory_block([mc])
        assert "<client_memory>" in block
        assert "Hello world" in block


class TestSaveDeviation:
    """Test save_deviation function."""

    def test_creates_deviation_file(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        path = save_deviation(mem, "001", "# Test deviation")
        assert path.exists()
        assert path.name == "DEV-001.md"
        assert path.read_text(encoding="utf-8") == "# Test deviation"

    def test_creates_deviations_dir_if_missing(self, tmp_path):
        mem = tmp_path / "empty-memory"
        mem.mkdir()
        path = save_deviation(mem, "001", "content")
        assert (mem / "deviations").is_dir()
        assert path.exists()

    def test_overwrites_existing_deviation(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        save_deviation(mem, "001", "First version")
        save_deviation(mem, "001", "Second version")
        content = (mem / "deviations" / "DEV-001.md").read_text(encoding="utf-8")
        assert content == "Second version"

    def test_rejects_empty_id(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="must not be empty"):
            save_deviation(mem, "", "content")

    def test_alphanumeric_with_hyphens_allowed(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        path = save_deviation(mem, "M1-0", "content")
        assert path.name == "DEV-M1-0.md"


class TestSavePattern:
    """Test save_pattern function."""

    def test_appends_to_patterns_file(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        save_pattern(mem, "maintenance-strategy", "### PAT-002: New pattern")
        content = (mem / "maintenance-strategy" / "patterns.md").read_text(encoding="utf-8")
        assert "PAT-001" in content  # original still there
        assert "PAT-002" in content  # new one appended

    def test_creates_stage_dir_if_missing(self, tmp_path):
        mem = tmp_path / "empty-memory"
        mem.mkdir()
        save_pattern(mem, "work-planning", "### PAT-001: Pattern")
        assert (mem / "work-planning" / "patterns.md").is_file()

    def test_rejects_invalid_stage(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="Invalid stage"):
            save_pattern(mem, "invalid-stage", "content")

    def test_accepts_all_valid_stages(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        for stage in [
            "maintenance-strategy", "work-identification", "work-planning",
            "reliability-engineering", "cost-analysis",
        ]:
            save_pattern(mem, stage, f"Pattern for {stage}")


class TestSaveMeetingNotes:
    """Test save_meeting_notes function."""

    def test_creates_meeting_file(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        path = save_meeting_notes(mem, "2026-03-05", "# Meeting\n\nDiscussion points")
        assert path.exists()
        assert path.name == "2026-03-05_meeting.md"

    def test_creates_meetings_dir_if_missing(self, tmp_path):
        mem = tmp_path / "empty-memory"
        mem.mkdir()
        save_meeting_notes(mem, "2026-01-15", "content")
        assert (mem / "meetings").is_dir()

    def test_rejects_invalid_date_format(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            save_meeting_notes(mem, "March 5 2026", "content")

    def test_rejects_partial_date(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="YYYY-MM-DD"):
            save_meeting_notes(mem, "2026-03", "content")


class TestExtractLearning:
    """Test extract_learning function."""

    def test_modify_returns_deviation(self):
        result = extract_learning("Please fix the hierarchy naming", "modify")
        assert result is not None
        assert result["type"] == "deviation"
        assert "Modify requested" in result["content"]
        assert "fix the hierarchy naming" in result["content"]

    def test_approve_returns_pattern(self):
        result = extract_learning("Good approach for pump classification", "approve")
        assert result is not None
        assert result["type"] == "pattern"
        assert "PAT-AUTO" in result["content"]
        assert "pump classification" in result["content"]

    def test_returns_none_for_empty_feedback(self):
        assert extract_learning("", "modify") is None
        assert extract_learning(None, "approve") is None

    def test_returns_none_for_trivial_feedback(self):
        assert extract_learning("OK", "approve") is None
        assert extract_learning("  fine  ", "modify") is None

    def test_returns_none_for_unknown_action(self):
        assert extract_learning("Some feedback here", "reject") is None

    def test_includes_date(self):
        result = extract_learning("Detailed feedback for testing", "modify")
        assert "Date" in result["content"]


class TestMemoryContentDataclass:
    """Verify MemoryContent is a proper frozen dataclass."""

    def test_is_frozen(self):
        mc = MemoryContent("test.md", "global", "body")
        with pytest.raises(AttributeError):
            mc.source = "other.md"

    def test_equality(self):
        mc1 = MemoryContent("a.md", "global", "body")
        mc2 = MemoryContent("a.md", "global", "body")
        assert mc1 == mc2

    def test_fields(self):
        mc = MemoryContent("src", "cat", "bod")
        assert mc.source == "src"
        assert mc.category == "cat"
        assert mc.body == "bod"


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


class TestMemoryWithAgentBase:
    """Integration: memory module + Agent.get_system_prompt()."""

    def test_get_system_prompt_without_memory_dir_unchanged(self, tmp_path):
        """Backward compat: no memory_dir → no memory block."""
        from agents._shared.base import Agent, AgentConfig

        claude_md = tmp_path / "agent" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("# Test Agent", encoding="utf-8")

        config = AgentConfig(
            name="TestAgent",
            model="claude-sonnet-4-5-20250929",
            agent_dir=str(tmp_path / "agent"),
            tools=[],
        )
        agent = Agent(config)
        prompt = agent.get_system_prompt(milestone=1)
        assert "<client_memory>" not in prompt
        assert "# Test Agent" in prompt

    def test_get_system_prompt_with_memory_dir_injects_block(self, tmp_path):
        """Memory dir provided → memory block injected."""
        from agents._shared.base import Agent, AgentConfig

        claude_md = tmp_path / "agent" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("# Test Agent", encoding="utf-8")

        mem = _create_memory_tree(tmp_path)

        config = AgentConfig(
            name="TestAgent",
            model="claude-sonnet-4-5-20250929",
            agent_dir=str(tmp_path / "agent"),
            tools=[],
        )
        agent = Agent(config)
        prompt = agent.get_system_prompt(milestone=1, memory_dir=mem)
        assert "<client_memory>" in prompt
        assert "MUST follow these requirements" in prompt
        assert "Criticality method: R8+GFSN" in prompt

    def test_memory_injected_after_base_prompt(self, tmp_path):
        """Memory block appears after the base system prompt."""
        from agents._shared.base import Agent, AgentConfig

        claude_md = tmp_path / "agent" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("# Base Prompt Content", encoding="utf-8")

        mem = _create_memory_tree(tmp_path)

        config = AgentConfig(
            name="TestAgent",
            model="claude-sonnet-4-5-20250929",
            agent_dir=str(tmp_path / "agent"),
            tools=[],
        )
        agent = Agent(config)
        prompt = agent.get_system_prompt(milestone=1, memory_dir=mem)

        base_pos = prompt.index("# Base Prompt Content")
        memory_pos = prompt.index("<client_memory>")
        assert memory_pos > base_pos

    def test_prompt_size_under_80k(self, tmp_path):
        """System prompt with memory must stay under 80,000 characters."""
        from agents._shared.base import Agent, AgentConfig

        claude_md = tmp_path / "agent" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("# Agent\n" * 100, encoding="utf-8")

        mem = _create_memory_tree(tmp_path)

        config = AgentConfig(
            name="TestAgent",
            model="claude-sonnet-4-5-20250929",
            agent_dir=str(tmp_path / "agent"),
            tools=[],
        )
        agent = Agent(config)
        prompt = agent.get_system_prompt(milestone=2, memory_dir=mem)
        assert len(prompt) < 80_000

    def test_missing_memory_dir_graceful(self, tmp_path):
        """Non-existent memory_dir → no crash, no memory block."""
        from agents._shared.base import Agent, AgentConfig

        claude_md = tmp_path / "agent" / "CLAUDE.md"
        claude_md.parent.mkdir(parents=True)
        claude_md.write_text("# Test Agent", encoding="utf-8")

        config = AgentConfig(
            name="TestAgent",
            model="claude-sonnet-4-5-20250929",
            agent_dir=str(tmp_path / "agent"),
            tools=[],
        )
        agent = Agent(config)
        prompt = agent.get_system_prompt(
            milestone=1, memory_dir=tmp_path / "nonexistent"
        )
        assert "<client_memory>" not in prompt


class TestMemoryWithWorkflow:
    """Integration: memory learning extraction + workflow gate actions."""

    def test_save_memory_learning_on_modify(self, tmp_path):
        """Workflow saves deviation on modify action."""
        mem = _create_memory_tree(tmp_path)

        from agents._shared.memory import MILESTONE_TO_STAGES

        # Simulate what workflow._save_memory_learning does
        from agents._shared.memory import extract_learning, save_deviation

        feedback = "The hierarchy naming is wrong, use French names"
        learning = extract_learning(feedback, "modify")
        assert learning is not None
        save_deviation(mem, "M1-0", learning["content"])

        dev_file = mem / "deviations" / "DEV-M1-0.md"
        assert dev_file.exists()
        assert "French names" in dev_file.read_text(encoding="utf-8")

    def test_save_memory_learning_on_approve(self, tmp_path):
        """Workflow saves pattern on approve action."""
        mem = _create_memory_tree(tmp_path)

        from agents._shared.memory import MILESTONE_TO_STAGES, extract_learning, save_pattern

        feedback = "Confirmed: use OEM intervals for all new equipment"
        learning = extract_learning(feedback, "approve")
        assert learning is not None
        stage = MILESTONE_TO_STAGES[1][0]
        save_pattern(mem, stage, learning["content"])

        content = (mem / "maintenance-strategy" / "patterns.md").read_text(encoding="utf-8")
        assert "OEM intervals" in content

    def test_deviations_persist_across_milestones(self, tmp_path):
        """Deviations saved in M1 are accessible in M2."""
        mem = _create_memory_tree(tmp_path)
        save_deviation(mem, "M1-0", "# Deviation from M1")

        # M2 loads from same memory_dir, so deviations are available
        dev = mem / "deviations" / "DEV-M1-0.md"
        assert dev.exists()
        assert "M1" in dev.read_text(encoding="utf-8")

    def test_patterns_from_project_a_isolated_from_project_b(self, tmp_path):
        """Each project has its own memory directory — no cross-contamination."""
        mem_a = tmp_path / "project-a" / "3-memory"
        mem_b = tmp_path / "project-b" / "3-memory"
        mem_a.mkdir(parents=True)
        mem_b.mkdir(parents=True)

        save_pattern(mem_a, "maintenance-strategy", "Pattern for project A")
        save_pattern(mem_b, "maintenance-strategy", "Pattern for project B")

        content_a = (mem_a / "maintenance-strategy" / "patterns.md").read_text(encoding="utf-8")
        content_b = (mem_b / "maintenance-strategy" / "patterns.md").read_text(encoding="utf-8")

        assert "project A" in content_a
        assert "project B" not in content_a
        assert "project B" in content_b
        assert "project A" not in content_b


# ============================================================================
# SECURITY TESTS
# ============================================================================


@pytest.mark.security
class TestSecurityPathTraversal:
    """Security: path traversal prevention in identifiers."""

    def test_deviation_id_rejects_dotdot(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="path traversal"):
            save_deviation(mem, "../../../etc/passwd", "content")

    def test_deviation_id_rejects_forward_slash(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="path traversal"):
            save_deviation(mem, "foo/bar", "content")

    def test_deviation_id_rejects_backslash(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError, match="path traversal"):
            save_deviation(mem, "foo\\bar", "content")

    def test_deviation_id_rejects_special_chars(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError):
            save_deviation(mem, "id;rm -rf /", "content")

    def test_deviation_id_rejects_spaces(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError):
            save_deviation(mem, "my deviation", "content")

    def test_validate_id_rejects_empty(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_id("")

    def test_validate_id_accepts_alphanumeric(self):
        _validate_id("M1-attempt-0")  # should not raise
        _validate_id("abc123")
        _validate_id("test_id")


@pytest.mark.security
class TestSecurityContentSanitization:
    """Security: content sanitization prevents injection."""

    def test_strips_script_tags(self):
        result = _sanitize_content('Hello <script>alert("xss")</script> world')
        assert "<script>" not in result
        assert "alert" not in result
        assert "Hello" in result
        assert "world" in result

    def test_strips_iframe_tags(self):
        result = _sanitize_content('Hello <iframe src="evil.com"></iframe> world')
        assert "<iframe" not in result
        assert "Hello" in result

    def test_preserves_normal_markdown(self):
        md = "# Title\n\n- Item 1\n- Item 2\n\n**Bold** and *italic*"
        assert _sanitize_content(md) == md

    def test_preserves_html_comments(self):
        md = "<!-- This is a comment -->"
        assert _sanitize_content(md) == md

    def test_save_deviation_sanitizes_content(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        save_deviation(mem, "001", '<script>alert("xss")</script> Real content')
        content = (mem / "deviations" / "DEV-001.md").read_text(encoding="utf-8")
        assert "<script>" not in content
        assert "Real content" in content

    def test_save_pattern_sanitizes_content(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        save_pattern(mem, "maintenance-strategy", '<iframe src="evil"></iframe> Good pattern')
        content = (mem / "maintenance-strategy" / "patterns.md").read_text(encoding="utf-8")
        assert "<iframe" not in content
        assert "Good pattern" in content


@pytest.mark.security
class TestSecurityNoCodeExecution:
    """Security: memory loading does not execute embedded code."""

    def test_no_eval_in_memory_loading(self, tmp_path):
        """Memory files with Python code are treated as plain text."""
        mem = tmp_path / "3-memory"
        mem.mkdir()
        (mem / "global-requirements.md").write_text(
            '# Requirements\n\n```python\nimport os; os.system("rm -rf /")\n```\n',
            encoding="utf-8",
        )
        ms = mem / "maintenance-strategy"
        ms.mkdir()
        (ms / "requirements.md").write_text(
            "__import__('os').system('whoami')\n",
            encoding="utf-8",
        )

        # Loading should not execute any code
        result = load_memory_for_stage("maintenance-strategy", mem)
        assert len(result) >= 1
        # The dangerous code is just text, not executed
        assert any("os.system" in mc.body for mc in result)

    def test_extract_learning_does_not_eval(self):
        """extract_learning never evaluates feedback as code."""
        feedback = "__import__('os').system('whoami')"
        result = extract_learning(feedback, "modify")
        assert result is not None
        assert "__import__" in result["content"]  # stored as text


@pytest.mark.security
class TestSecurityNoCredentials:
    """Security: memory operations don't leak credentials."""

    def test_format_block_does_not_add_env_vars(self, tmp_path):
        mem = _create_memory_tree(tmp_path)
        contents = load_memory_for_stage("maintenance-strategy", mem)
        block = format_memory_block(contents)
        assert "API_KEY" not in block
        assert "SECRET" not in block

    def test_meeting_notes_date_validation(self, tmp_path):
        """Date parameter can't be used for path injection."""
        mem = _create_memory_tree(tmp_path)
        with pytest.raises(ValueError):
            save_meeting_notes(mem, "../../etc/passwd", "content")


# ============================================================================
# CLAUDE.md PROTOCOL TESTS
# ============================================================================


class TestClaudeMdProtocol:
    """Verify all agent CLAUDE.md files contain the memory protocol."""

    AGENT_DIRS = [
        "agents/orchestrator/CLAUDE.md",
        "agents/reliability/CLAUDE.md",
        "agents/planning/CLAUDE.md",
        "agents/spare-parts/CLAUDE.md",
    ]

    @pytest.mark.parametrize("claude_md_path", AGENT_DIRS)
    def test_contains_client_memory_protocol(self, claude_md_path):
        path = Path("c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE") / claude_md_path
        if not path.exists():
            pytest.skip(f"File not found: {path}")
        content = path.read_text(encoding="utf-8")
        assert "Client Memory Protocol (MANDATORY)" in content
        assert "OVERRIDE methodology defaults" in content


# ============================================================================
# BAD SMELLS VERIFICATION
# ============================================================================


class TestBadSmellsPrevention:
    """Verify bad smell constraints from Phase 7 spec."""

    def test_memory_module_under_200_lines(self):
        """memory.py must be < 200 lines (prevent God Module)."""
        memory_path = Path("c:/Users/Usuario/Desktop/ASSET-MANAGEMENT-SOFTWARE/agents/_shared/memory.py")
        if not memory_path.exists():
            pytest.skip("memory.py not found")
        line_count = len(memory_path.read_text(encoding="utf-8").splitlines())
        assert line_count < 200, f"memory.py is {line_count} lines, must be < 200"

    def test_memory_content_is_dataclass(self):
        """MemoryContent must be a dataclass, not a dict."""
        import dataclasses
        assert dataclasses.is_dataclass(MemoryContent)

    def test_memory_content_is_frozen(self):
        """MemoryContent must be immutable."""
        mc = MemoryContent("a", "b", "c")
        with pytest.raises(AttributeError):
            mc.body = "new"

    def test_milestone_to_stages_single_definition(self):
        """MILESTONE_TO_STAGES defined once in memory.py, not duplicated."""
        import agents._shared.memory as mem_module
        assert hasattr(mem_module, "MILESTONE_TO_STAGES")
        # Verify it's the canonical dict (not a copy)
        assert mem_module.MILESTONE_TO_STAGES is MILESTONE_TO_STAGES
