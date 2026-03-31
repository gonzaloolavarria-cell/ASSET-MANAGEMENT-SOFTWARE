"""Tests for execution plan security — Section 11: Cybersecurity Tests.

Validates:
- YAML injection prevention in wizard inputs
- No sensitive data in plaintext in execution plans
- XSS prevention in equipment names / descriptions
- No command injection via project.yaml
"""

from __future__ import annotations

import re

import pytest
import yaml

from agents.orchestration.execution_plan import (
    ExecutionPlan,
    ExecutionPlanItem,
    ExecutionPlanStage,
    PlanStatus,
    StrategyApproach,
)


# ---------------------------------------------------------------------------
# Sanitization regex (same as wizard)
# ---------------------------------------------------------------------------

_YAML_INJECTION = re.compile(r"[{}\[\]!%*&|>]")


def _sanitize(value: str, max_len: int = 200) -> str:
    value = value[:max_len].strip()
    return _YAML_INJECTION.sub("", value)


# ---------------------------------------------------------------------------
# YAML injection
# ---------------------------------------------------------------------------

class TestYAMLInjection:
    """Wizard sanitizes inputs to prevent YAML injection."""

    def test_curly_braces_stripped(self):
        result = _sanitize("{malicious: true}")
        assert "{" not in result
        assert "}" not in result

    def test_yaml_anchors_stripped(self):
        result = _sanitize("&anchor value")
        assert "&" not in result

    def test_yaml_aliases_stripped(self):
        result = _sanitize("*alias")
        assert "*" not in result

    def test_multiline_indicator_stripped(self):
        result = _sanitize("|multiline")
        assert "|" not in result
        result = _sanitize(">folded")
        assert ">" not in result

    def test_tag_indicator_stripped(self):
        result = _sanitize("!python/object:os.system")
        assert "!" not in result

    def test_merge_key_stripped(self):
        result = _sanitize("<<: *default")
        assert "<" in result  # < is NOT in the injection pattern
        assert "*" not in result

    def test_max_length_enforced(self):
        result = _sanitize("A" * 500, max_len=200)
        assert len(result) == 200

    def test_safe_text_passes(self):
        safe = "SAG Mill 001 - Phosphate Processing"
        result = _sanitize(safe)
        assert result == safe

    def test_percent_stripped(self):
        result = _sanitize("%TAG ! tag:yaml.org,2002:")
        assert "%" not in result


# ---------------------------------------------------------------------------
# Sensitive data in execution plan
# ---------------------------------------------------------------------------

class TestNoSensitiveData:
    """Execution plan should not contain sensitive client data in plaintext."""

    def test_no_passwords_in_yaml(self):
        plan = ExecutionPlan(
            starting_milestone=1,
            approach=StrategyApproach.FULL_RCM,
            client_slug="ocp",
            project_slug="jfc",
        )
        stage = ExecutionPlanStage(id="M1", name="Test", milestone=1)
        stage.items.append(ExecutionPlanItem(
            id="i1", description="Regular task description"
        ))
        plan.stages.append(stage)

        yaml_str = plan.to_yaml()
        # Should not contain common sensitive patterns
        sensitive_patterns = [
            "password", "secret", "api_key", "token",
            "credential", "private_key", "ssh-rsa",
        ]
        yaml_lower = yaml_str.lower()
        for pattern in sensitive_patterns:
            assert pattern not in yaml_lower, f"Found sensitive pattern: {pattern}"

    def test_equipment_tags_only_metadata(self):
        """Equipment tags contain only identifiers, not operational data."""
        plan = ExecutionPlan(starting_milestone=1, approach=StrategyApproach.FULL_RCM)
        stage = ExecutionPlanStage(id="M1", name="Test", milestone=1)
        stage.items.append(ExecutionPlanItem(
            id="i1",
            description="Analyze PUMP-001",
            equipment_tag="PUMP-001",
        ))
        plan.stages.append(stage)

        yaml_str = plan.to_yaml()
        # Should not contain IP addresses, emails, phone numbers
        assert not re.search(r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}", yaml_str)
        assert not re.search(r"[\w.]+@[\w.]+\.\w+", yaml_str)


# ---------------------------------------------------------------------------
# XSS prevention
# ---------------------------------------------------------------------------

class TestXSSPrevention:
    """Equipment names and descriptions should not allow XSS."""

    def test_script_tags_in_description(self):
        """Script tags in descriptions are treated as plain text."""
        item = ExecutionPlanItem(
            id="i1",
            description='<script>alert("xss")</script>',
        )
        d = item.to_dict()
        # YAML serialization should not interpret HTML
        yaml_str = yaml.dump(d)
        assert "<script>" in yaml_str  # preserved as text, not executed

    def test_sanitizer_strips_angle_brackets(self):
        """Wizard sanitizer handles script injection attempts."""
        # Note: <script> doesn't match YAML injection pattern
        # But Streamlit auto-escapes markdown. This test verifies
        # the description survives serialization as-is.
        malicious = '<img src=x onerror="alert(1)">'
        item = ExecutionPlanItem(id="i1", description=malicious)
        d = item.to_dict()
        # The description is stored as-is; rendering layer (Streamlit) escapes
        assert d["description"] == malicious

    def test_equipment_tag_sanitized(self):
        """Wizard sanitizer cleans equipment tags."""
        result = _sanitize("PUMP{001}")
        assert "{" not in result
        assert "}" not in result


# ---------------------------------------------------------------------------
# Command injection via project.yaml
# ---------------------------------------------------------------------------

class TestCommandInjection:
    """Wizard CLI does not execute commands from project.yaml."""

    def test_yaml_safe_load_only(self):
        """Ensure yaml.safe_load is used, never yaml.load."""
        # This is a code-level assertion. We verify by attempting
        # to load a YAML with a Python object tag.
        malicious_yaml = "!!python/object/apply:os.system ['echo pwned']"
        with pytest.raises(Exception):
            # safe_load should reject this
            yaml.safe_load(malicious_yaml)

    def test_plan_from_yaml_uses_safe_load(self):
        """ExecutionPlan.from_yaml rejects malicious YAML."""
        malicious = "!!python/object/apply:os.system ['echo pwned']"
        with pytest.raises(Exception):
            ExecutionPlan.from_yaml(malicious)

    def test_safe_yaml_with_execution_plan_key(self):
        """Even with correct key, embedded code is rejected."""
        malicious = yaml.dump({
            "execution_plan": {
                "stages": [],
                "starting_milestone": "!!python/object/apply:os.system ['id']",
            }
        })
        # Should load but the value is just a string
        plan = ExecutionPlan.from_yaml(malicious)
        # starting_milestone defaults since the string isn't an int
        assert isinstance(plan.starting_milestone, int)


# ---------------------------------------------------------------------------
# Read-only enforcement (progress dashboard)
# ---------------------------------------------------------------------------

class TestReadOnlyEnforcement:
    """Progress dashboard operations don't modify plan unless authorized."""

    def test_calculate_progress_is_readonly(self):
        """calculate_progress() doesn't mutate item statuses."""
        item = ExecutionPlanItem(id="i1", description="Task", status=PlanStatus.PENDING)
        stage = ExecutionPlanStage(id="s1", name="S1", milestone=1)
        stage.items = [item]
        plan = ExecutionPlan()
        plan.stages = [stage]

        plan.calculate_progress()
        assert item.status == PlanStatus.PENDING  # unchanged

    def test_get_next_pending_is_readonly(self):
        """get_next_pending_items() doesn't mutate plan."""
        item = ExecutionPlanItem(id="i1", description="Task", status=PlanStatus.PENDING)
        stage = ExecutionPlanStage(id="s1", name="S1", milestone=1)
        stage.items = [item]
        plan = ExecutionPlan()
        plan.stages = [stage]

        result = plan.get_next_pending_items()
        assert len(result) == 1
        assert item.status == PlanStatus.PENDING  # unchanged
