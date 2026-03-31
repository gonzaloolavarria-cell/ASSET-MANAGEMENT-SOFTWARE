"""Tests for the intent profile loading system (Phase 11 — Intent Adoption)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
import yaml


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def tmp_client_root(tmp_path):
    """Create a temporary client root with project structure."""
    project_dir = tmp_path / "clients" / "test-client" / "projects" / "test-project"
    for subdir in ("0-input", "1-output", "2-state", "3-memory", "4-intent-specs", "5-templates"):
        (project_dir / subdir).mkdir(parents=True, exist_ok=True)
    return tmp_path


@pytest.fixture
def valid_intent_profile():
    """A valid minimal intent profile (IP-L1 only)."""
    return {
        "schema_version": "1.0",
        "intent_summary": {
            "client": "OCP Group",
            "project": "JFC Maintenance Strategy",
            "trade_off_priority": ["safety", "availability", "cost"],
            "risk_appetite": "moderate",
            "primary_kpi": "availability",
            "primary_kpi_target": 92,
            "hard_limits": ["No unplanned shutdowns on SAG mills"],
        },
        "domain_intent": {
            "reliability": {"focus": "critical_equipment_first"},
            "planning": {},
            "spare_parts": {},
        },
        "full_context": {},
        "trade_off_matrix": [],
        "veto_rules": [],
    }


@pytest.fixture
def profile_on_disk(tmp_client_root, valid_intent_profile):
    """Write a valid intent profile to the temp project's 4-intent-specs/."""
    intent_dir = tmp_client_root / "clients" / "test-client" / "projects" / "test-project" / "4-intent-specs"
    path = intent_dir / "intent-profile.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(valid_intent_profile, f)
    return path


# ── validate_intent_profile ──────────────────────────────────────

class TestValidateIntentProfile:
    def test_valid_profile(self, valid_intent_profile):
        from agents._shared.paths import validate_intent_profile
        is_valid, warnings = validate_intent_profile(valid_intent_profile)
        assert is_valid
        assert warnings == []

    def test_missing_intent_summary(self):
        from agents._shared.paths import validate_intent_profile
        is_valid, warnings = validate_intent_profile({"schema_version": "1.0"})
        assert not is_valid
        assert any("intent_summary" in w for w in warnings)

    def test_missing_required_fields(self):
        from agents._shared.paths import validate_intent_profile
        profile = {"intent_summary": {"client": "OCP"}}
        is_valid, warnings = validate_intent_profile(profile)
        assert not is_valid
        assert any("trade_off_priority" in w for w in warnings)

    def test_intent_summary_not_dict(self):
        from agents._shared.paths import validate_intent_profile
        is_valid, warnings = validate_intent_profile({"intent_summary": "string"})
        assert not is_valid

    def test_empty_profile(self):
        from agents._shared.paths import validate_intent_profile
        is_valid, warnings = validate_intent_profile({})
        assert not is_valid


# ── load_intent_profile ──────────────────────────────────────────

class TestLoadIntentProfile:
    def test_load_valid_profile(self, tmp_client_root, profile_on_disk):
        from agents._shared.paths import load_intent_profile
        os.environ["AMS_CLIENT_ROOT"] = str(tmp_client_root)
        try:
            result = load_intent_profile("test-client", "test-project")
            assert result is not None
            assert result["intent_summary"]["client"] == "OCP Group"
            assert result["intent_summary"]["trade_off_priority"] == ["safety", "availability", "cost"]
        finally:
            del os.environ["AMS_CLIENT_ROOT"]

    def test_load_missing_file(self, tmp_client_root):
        from agents._shared.paths import load_intent_profile
        os.environ["AMS_CLIENT_ROOT"] = str(tmp_client_root)
        try:
            result = load_intent_profile("test-client", "test-project")
            assert result is None
        finally:
            del os.environ["AMS_CLIENT_ROOT"]

    def test_load_invalid_yaml(self, tmp_client_root):
        from agents._shared.paths import load_intent_profile
        intent_dir = tmp_client_root / "clients" / "test-client" / "projects" / "test-project" / "4-intent-specs"
        (intent_dir / "intent-profile.yaml").write_text("not: valid: yaml: [", encoding="utf-8")
        os.environ["AMS_CLIENT_ROOT"] = str(tmp_client_root)
        try:
            result = load_intent_profile("test-client", "test-project")
            assert result is None
        finally:
            del os.environ["AMS_CLIENT_ROOT"]


# ── get_intent_domain ────────────────────────────────────────────

class TestGetIntentDomain:
    def test_existing_domain(self, valid_intent_profile):
        from agents._shared.paths import get_intent_domain
        domain = get_intent_domain(valid_intent_profile, "reliability")
        assert domain == {"focus": "critical_equipment_first"}

    def test_missing_domain(self, valid_intent_profile):
        from agents._shared.paths import get_intent_domain
        domain = get_intent_domain(valid_intent_profile, "nonexistent")
        assert domain is None

    def test_no_domain_intent_section(self):
        from agents._shared.paths import get_intent_domain
        profile = {"intent_summary": {"client": "X", "project": "Y", "trade_off_priority": []}}
        domain = get_intent_domain(profile, "reliability")
        assert domain is None


# ── _format_intent_block ─────────────────────────────────────────

class TestFormatIntentBlock:
    def test_format_complete_profile(self, valid_intent_profile):
        from agents._shared.base import _format_intent_block
        block = _format_intent_block(valid_intent_profile)
        assert "<client_intent>" in block
        assert "</client_intent>" in block
        assert "OCP Group" in block
        assert "safety > availability > cost" in block
        assert "No unplanned shutdowns on SAG mills" in block

    def test_format_empty_profile(self):
        from agents._shared.base import _format_intent_block
        block = _format_intent_block({})
        assert block == ""

    def test_format_minimal_profile(self):
        from agents._shared.base import _format_intent_block
        profile = {
            "intent_summary": {
                "client": "Acme",
                "project": "Test",
                "trade_off_priority": ["cost", "safety"],
            }
        }
        block = _format_intent_block(profile)
        assert "Acme" in block
        assert "cost > safety" in block


# ── Agent.get_system_prompt with intent ──────────────────────────

class TestAgentIntentInjection:
    def test_prompt_without_intent(self, tmp_path):
        from agents._shared.base import Agent, AgentConfig
        prompt_file = tmp_path / "CLAUDE.md"
        prompt_file.write_text("# Test Agent\nYou are a test agent.", encoding="utf-8")
        config = AgentConfig(name="Test", model="test", agent_dir=str(tmp_path))
        agent = Agent(config)
        prompt = agent.get_system_prompt()
        assert "Test Agent" in prompt
        assert "<client_intent>" not in prompt

    def test_prompt_with_intent(self, tmp_path, valid_intent_profile):
        from agents._shared.base import Agent, AgentConfig
        prompt_file = tmp_path / "CLAUDE.md"
        prompt_file.write_text("# Test Agent\nYou are a test agent.", encoding="utf-8")
        config = AgentConfig(name="Test", model="test", agent_dir=str(tmp_path))
        agent = Agent(config)
        prompt = agent.get_system_prompt(context={"intent_profile": valid_intent_profile})
        assert "<client_intent>" in prompt
        assert "OCP Group" in prompt
        assert "safety > availability > cost" in prompt

    def test_intent_after_memory_block(self, tmp_path, valid_intent_profile):
        """Intent should appear after memory in the prompt."""
        from agents._shared.base import Agent, AgentConfig
        prompt_file = tmp_path / "CLAUDE.md"
        prompt_file.write_text("# Test Agent", encoding="utf-8")
        config = AgentConfig(name="Test", model="test", agent_dir=str(tmp_path))
        agent = Agent(config)
        # With intent only (no memory dir), intent appears at end
        prompt = agent.get_system_prompt(context={"intent_profile": valid_intent_profile})
        assert prompt.index("<client_intent>") > prompt.index("# Test Agent")
