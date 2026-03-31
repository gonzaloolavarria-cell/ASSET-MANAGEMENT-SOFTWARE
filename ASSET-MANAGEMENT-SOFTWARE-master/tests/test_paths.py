"""Tests for agents/_shared/paths.py — path resolution, validation, and security."""

import json
import os
from pathlib import Path

import pytest
import yaml

from agents._shared.paths import (
    INPUT_SUBDIRS,
    PROJECT_SUBDIRS,
    _validate_slug,
    get_branding_config,
    get_checkpoint_dir,
    get_client_context_dir,
    get_client_memory_dir,
    get_client_root,
    get_client_templates_dir,
    get_equipment_list_dir,
    get_existing_maintenance_dir,
    get_failure_history_dir,
    get_gates_file,
    get_input_dir,
    get_intent_specs_dir,
    get_interviews_dir,
    get_meetings_dir,
    get_memory_dir,
    get_output_dir,
    get_project_root,
    get_proposal_dir,
    get_scope_dir,
    get_session_file,
    get_shutdown_calendar_dir,
    get_spare_parts_dir,
    get_standards_dir,
    get_state_dir,
    get_system_root,
    get_template_path,
    get_templates_dir,
    get_vendor_docs_dir,
    get_workforce_dir,
    load_project_config,
    scaffold_project,
    validate_client_root_exists,
    validate_input_structure,
    validate_project_structure,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_ams(tmp_path):
    """Create a temporary AMS-like structure for testing."""
    system_root = tmp_path / "ASSET-MANAGEMENT-SOFTWARE"
    client_root = tmp_path / "ASSET-MANAGEMENT-SOFTWARE-CLIENT"
    system_root.mkdir()
    client_root.mkdir()
    # Create agents/_shared/ so paths.py env override is needed
    (system_root / "agents" / "_shared").mkdir(parents=True)
    return system_root, client_root


@pytest.fixture
def env_roots(tmp_ams, monkeypatch):
    """Set environment variables pointing to temp dirs."""
    system_root, client_root = tmp_ams
    monkeypatch.setenv("AMS_SYSTEM_ROOT", str(system_root))
    monkeypatch.setenv("AMS_CLIENT_ROOT", str(client_root))
    return system_root, client_root


@pytest.fixture
def project_dirs(env_roots):
    """Create a full project directory structure."""
    _, client_root = env_roots
    project_root = client_root / "clients" / "ocp" / "projects" / "jfc-strategy"
    for subdir in PROJECT_SUBDIRS:
        (project_root / subdir).mkdir(parents=True)
    input_dir = project_root / "0-input"
    for subdir in INPUT_SUBDIRS:
        (input_dir / subdir).mkdir(parents=True)
    # Client context
    (client_root / "clients" / "ocp" / "context" / "templates").mkdir(parents=True)
    (client_root / "clients" / "ocp" / "context" / "memory").mkdir(parents=True)
    return project_root


# ---------------------------------------------------------------------------
# Root resolution tests
# ---------------------------------------------------------------------------


class TestRootResolution:
    def test_system_root_from_env(self, env_roots):
        system_root, _ = env_roots
        assert get_system_root() == system_root.resolve()

    def test_client_root_from_env(self, env_roots):
        _, client_root = env_roots
        assert get_client_root() == client_root.resolve()

    def test_system_root_without_env(self, monkeypatch):
        monkeypatch.delenv("AMS_SYSTEM_ROOT", raising=False)
        monkeypatch.delenv("AMS_CLIENT_ROOT", raising=False)
        root = get_system_root()
        # Should resolve to 3 levels up from paths.py
        assert root.is_dir()

    def test_client_root_defaults_to_sibling(self, tmp_ams, monkeypatch):
        system_root, client_root = tmp_ams
        monkeypatch.setenv("AMS_SYSTEM_ROOT", str(system_root))
        monkeypatch.delenv("AMS_CLIENT_ROOT", raising=False)
        result = get_client_root()
        assert result == system_root.parent / "ASSET-MANAGEMENT-SOFTWARE-CLIENT"


# ---------------------------------------------------------------------------
# Slug validation tests
# ---------------------------------------------------------------------------


class TestSlugValidation:
    def test_valid_slugs(self):
        for slug in ["ocp", "my-client", "client-123", "a"]:
            _validate_slug(slug)  # Should not raise

    def test_empty_slug(self):
        with pytest.raises(ValueError, match="must not be empty"):
            _validate_slug("")

    def test_path_traversal_dotdot(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_slug("../../../etc")

    def test_path_traversal_slash(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_slug("ocp/evil")

    def test_path_traversal_backslash(self):
        with pytest.raises(ValueError, match="path traversal"):
            _validate_slug("ocp\\evil")

    def test_invalid_uppercase(self):
        with pytest.raises(ValueError, match="must match pattern"):
            _validate_slug("OCP")

    def test_invalid_special_chars(self):
        with pytest.raises(ValueError):
            _validate_slug("ocp; rm -rf /")

    def test_invalid_starts_with_hyphen(self):
        with pytest.raises(ValueError, match="must match pattern"):
            _validate_slug("-ocp")

    def test_invalid_spaces(self):
        with pytest.raises(ValueError, match="must match pattern"):
            _validate_slug("my client")


# ---------------------------------------------------------------------------
# Project path tests
# ---------------------------------------------------------------------------


class TestProjectPaths:
    def test_project_root(self, env_roots):
        _, client_root = env_roots
        result = get_project_root("ocp", "jfc-strategy")
        expected = client_root.resolve() / "clients" / "ocp" / "projects" / "jfc-strategy"
        assert result == expected

    def test_client_context_dir(self, env_roots):
        _, client_root = env_roots
        result = get_client_context_dir("ocp")
        assert result == client_root.resolve() / "clients" / "ocp" / "context"

    def test_input_dir(self, env_roots):
        result = get_input_dir("ocp", "jfc-strategy")
        assert result.name == "0-input"

    def test_output_dir(self, env_roots):
        result = get_output_dir("ocp", "jfc-strategy")
        assert result.name == "1-output"

    def test_state_dir(self, env_roots):
        result = get_state_dir("ocp", "jfc-strategy")
        assert result.name == "2-state"

    def test_memory_dir(self, env_roots):
        result = get_memory_dir("ocp", "jfc-strategy")
        assert result.name == "3-memory"

    def test_intent_specs_dir(self, env_roots):
        result = get_intent_specs_dir("ocp", "jfc-strategy")
        assert result.name == "4-intent-specs"

    def test_templates_dir(self, env_roots):
        result = get_templates_dir("ocp", "jfc-strategy")
        assert result.name == "5-templates"


# ---------------------------------------------------------------------------
# Input subdirectory tests
# ---------------------------------------------------------------------------


class TestInputSubdirs:
    def test_scope_dir(self, env_roots):
        assert get_scope_dir("ocp", "p").name == "00-scope"

    def test_equipment_list_dir(self, env_roots):
        assert get_equipment_list_dir("ocp", "p").name == "01-equipment-list"

    def test_failure_history_dir(self, env_roots):
        assert get_failure_history_dir("ocp", "p").name == "02-failure-history"

    def test_existing_maintenance_dir(self, env_roots):
        assert get_existing_maintenance_dir("ocp", "p").name == "03-existing-maintenance"

    def test_spare_parts_dir(self, env_roots):
        assert get_spare_parts_dir("ocp", "p").name == "04-spare-parts"

    def test_shutdown_calendar_dir(self, env_roots):
        assert get_shutdown_calendar_dir("ocp", "p").name == "05-shutdown-calendar"

    def test_workforce_dir(self, env_roots):
        assert get_workforce_dir("ocp", "p").name == "06-workforce"

    def test_standards_dir(self, env_roots):
        assert get_standards_dir("ocp", "p").name == "07-standards"

    def test_interviews_dir(self, env_roots):
        assert get_interviews_dir("ocp", "p").name == "08-interviews"

    def test_vendor_docs_dir(self, env_roots):
        assert get_vendor_docs_dir("ocp", "p").name == "09-vendor-docs"

    def test_proposal_dir(self, env_roots):
        assert get_proposal_dir("ocp", "p").name == "10-proposal"


# ---------------------------------------------------------------------------
# State file tests
# ---------------------------------------------------------------------------


class TestStateFiles:
    def test_agent_state_file(self, env_roots):
        from agents._shared.paths import get_agent_state_file
        result = get_agent_state_file("ocp", "p", "reliability")
        assert result.name == "reliability-state.md"
        assert result.parent.name == "2-state"

    def test_session_file(self, env_roots):
        result = get_session_file("ocp", "p")
        assert result.name == "session-state.json"

    def test_gates_file(self, env_roots):
        result = get_gates_file("ocp", "p")
        assert result.name == "gates.json"

    def test_checkpoint_dir(self, env_roots):
        result = get_checkpoint_dir("ocp", "p")
        assert result.name == "checkpoints"
        assert result.parent.name == "2-state"


# ---------------------------------------------------------------------------
# Client-level directory tests
# ---------------------------------------------------------------------------


class TestClientDirs:
    def test_client_templates_dir(self, env_roots):
        result = get_client_templates_dir("ocp")
        assert result.name == "templates"
        assert result.parent.name == "context"

    def test_client_memory_dir(self, env_roots):
        result = get_client_memory_dir("ocp")
        assert result.name == "memory"
        assert result.parent.name == "context"

    def test_meetings_dir(self, env_roots):
        result = get_meetings_dir("ocp", "p")
        assert result.name == "meetings"
        assert result.parent.name == "3-memory"


# ---------------------------------------------------------------------------
# Configuration loader tests
# ---------------------------------------------------------------------------


class TestProjectConfig:
    def test_load_valid_config(self, project_dirs):
        config = {
            "project": {"id": "ocp-jfc-001", "name": "Test"},
            "client": {"slug": "ocp", "language": "fr"},
        }
        config_path = project_dirs / "project.yaml"
        config_path.write_text(yaml.dump(config), encoding="utf-8")

        result = load_project_config("ocp", "jfc-strategy")
        assert result is not None
        assert result["project"]["id"] == "ocp-jfc-001"

    def test_load_missing_config(self, env_roots):
        result = load_project_config("ocp", "nonexistent")
        assert result is None

    def test_load_invalid_yaml(self, project_dirs):
        config_path = project_dirs / "project.yaml"
        config_path.write_text("not: [valid: yaml: {", encoding="utf-8")

        result = load_project_config("ocp", "jfc-strategy")
        # yaml.safe_load may parse this or return None — either is acceptable
        # The function should not raise

    def test_load_non_dict_yaml(self, project_dirs):
        config_path = project_dirs / "project.yaml"
        config_path.write_text("- just\n- a\n- list\n", encoding="utf-8")

        result = load_project_config("ocp", "jfc-strategy")
        assert result is None


# ---------------------------------------------------------------------------
# Branding cascade tests
# ---------------------------------------------------------------------------


class TestBrandingCascade:
    def test_project_level_branding(self, project_dirs):
        branding = {"primary_color": "#FF0000", "logo": "project-logo.png"}
        branding_path = project_dirs / "5-templates" / "branding.yaml"
        branding_path.write_text(yaml.dump(branding), encoding="utf-8")

        result = get_branding_config("ocp", "jfc-strategy")
        assert result is not None
        assert result["primary_color"] == "#FF0000"

    def test_client_level_fallback(self, project_dirs, env_roots):
        _, client_root = env_roots
        client_branding = client_root / "clients" / "ocp" / "context" / "templates" / "branding.yaml"
        branding = {"primary_color": "#00FF00", "logo": "client-logo.png"}
        client_branding.write_text(yaml.dump(branding), encoding="utf-8")

        result = get_branding_config("ocp", "jfc-strategy")
        assert result is not None
        assert result["primary_color"] == "#00FF00"

    def test_system_level_fallback(self, project_dirs, env_roots):
        system_root, _ = env_roots
        system_branding = system_root / "templates" / "branding.yaml"
        system_branding.parent.mkdir(parents=True, exist_ok=True)
        branding = {"primary_color": "#0000FF", "logo": "system-logo.png"}
        system_branding.write_text(yaml.dump(branding), encoding="utf-8")

        result = get_branding_config("ocp", "jfc-strategy")
        assert result is not None
        assert result["primary_color"] == "#0000FF"

    def test_project_overrides_client(self, project_dirs, env_roots):
        _, client_root = env_roots
        # Write client-level
        client_branding = client_root / "clients" / "ocp" / "context" / "templates" / "branding.yaml"
        client_branding.write_text(yaml.dump({"level": "client"}), encoding="utf-8")
        # Write project-level (should win)
        project_branding = project_dirs / "5-templates" / "branding.yaml"
        project_branding.write_text(yaml.dump({"level": "project"}), encoding="utf-8")

        result = get_branding_config("ocp", "jfc-strategy")
        assert result["level"] == "project"

    def test_no_branding_returns_none(self, project_dirs):
        result = get_branding_config("ocp", "jfc-strategy")
        assert result is None


# ---------------------------------------------------------------------------
# Template cascade tests (Phase 6)
# ---------------------------------------------------------------------------


class TestTemplateCascade:
    """Tests for get_template_path() 3-level cascade resolution."""

    def test_project_level_resolution(self, project_dirs, env_roots):
        """Template found at project level (level 1)."""
        template = project_dirs / "5-templates" / "01_equipment_hierarchy.xlsx"
        template.write_bytes(b"project-level")

        result = get_template_path("01_equipment_hierarchy.xlsx", "ocp", "jfc-strategy")
        assert result is not None
        assert result == template

    def test_client_level_fallback(self, project_dirs, env_roots):
        """Falls back to client level (level 2) when not at project level."""
        _, client_root = env_roots
        client_template = (
            client_root / "clients" / "ocp" / "context" / "templates" / "01_equipment_hierarchy.xlsx"
        )
        client_template.write_bytes(b"client-level")

        result = get_template_path("01_equipment_hierarchy.xlsx", "ocp", "jfc-strategy")
        assert result is not None
        assert result == client_template

    def test_system_level_fallback(self, project_dirs, env_roots):
        """Falls back to system level (level 3) when not at project or client level."""
        system_root, _ = env_roots
        system_template = system_root / "templates" / "01_equipment_hierarchy.xlsx"
        system_template.parent.mkdir(parents=True, exist_ok=True)
        system_template.write_bytes(b"system-level")

        result = get_template_path("01_equipment_hierarchy.xlsx", "ocp", "jfc-strategy")
        assert result is not None
        assert result == system_template

    def test_project_overrides_client(self, project_dirs, env_roots):
        """Project-level template takes precedence over client-level."""
        _, client_root = env_roots
        # Write client-level
        client_template = (
            client_root / "clients" / "ocp" / "context" / "templates" / "01_equipment_hierarchy.xlsx"
        )
        client_template.write_bytes(b"client-level")
        # Write project-level (should win)
        project_template = project_dirs / "5-templates" / "01_equipment_hierarchy.xlsx"
        project_template.write_bytes(b"project-level")

        result = get_template_path("01_equipment_hierarchy.xlsx", "ocp", "jfc-strategy")
        assert result == project_template

    def test_client_overrides_system(self, project_dirs, env_roots):
        """Client-level template takes precedence over system-level."""
        system_root, client_root = env_roots
        # Write system-level
        system_template = system_root / "templates" / "01_equipment_hierarchy.xlsx"
        system_template.parent.mkdir(parents=True, exist_ok=True)
        system_template.write_bytes(b"system-level")
        # Write client-level (should win)
        client_template = (
            client_root / "clients" / "ocp" / "context" / "templates" / "01_equipment_hierarchy.xlsx"
        )
        client_template.write_bytes(b"client-level")

        result = get_template_path("01_equipment_hierarchy.xlsx", "ocp", "jfc-strategy")
        assert result == client_template

    def test_not_found_returns_none(self, project_dirs, env_roots):
        """Returns None when template not found at any level."""
        result = get_template_path("nonexistent.xlsx", "ocp", "jfc-strategy")
        assert result is None

    def test_empty_name_raises(self, env_roots):
        with pytest.raises(ValueError, match="must not be empty"):
            get_template_path("", "ocp", "jfc-strategy")

    def test_path_traversal_dotdot(self, env_roots):
        with pytest.raises(ValueError, match="path traversal"):
            get_template_path("../../../etc/passwd", "ocp", "jfc-strategy")

    def test_path_traversal_slash(self, env_roots):
        with pytest.raises(ValueError, match="path traversal"):
            get_template_path("subdir/template.xlsx", "ocp", "jfc-strategy")

    def test_path_traversal_backslash(self, env_roots):
        with pytest.raises(ValueError, match="path traversal"):
            get_template_path("subdir\\template.xlsx", "ocp", "jfc-strategy")

    def test_all_14_templates_resolvable(self, project_dirs, env_roots):
        """All 14 numbered templates resolve when placed at system level."""
        system_root, _ = env_roots
        templates_dir = system_root / "templates"
        templates_dir.mkdir(parents=True, exist_ok=True)

        template_names = [
            f"{i:02d}_{name}.xlsx"
            for i, name in enumerate(
                [
                    "equipment_hierarchy", "criticality_assessment", "failure_modes",
                    "maintenance_tasks", "work_packages", "work_order_history",
                    "spare_parts_inventory", "shutdown_calendar", "workforce",
                    "field_capture", "rca_events", "planning_kpi_input",
                    "de_kpi_input", "maintenance_strategy",
                ],
                start=1,
            )
        ]
        for name in template_names:
            (templates_dir / name).write_bytes(b"test")

        for name in template_names:
            result = get_template_path(name, "ocp", "jfc-strategy")
            assert result is not None, f"Template {name} not resolved"


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestValidation:
    def test_valid_project_structure(self, project_dirs):
        missing = validate_project_structure("ocp", "jfc-strategy")
        assert missing == []

    def test_missing_directories(self, env_roots):
        _, client_root = env_roots
        project_root = client_root / "clients" / "ocp" / "projects" / "jfc-strategy"
        project_root.mkdir(parents=True)
        (project_root / "0-input").mkdir()
        # Missing 5 other dirs
        missing = validate_project_structure("ocp", "jfc-strategy")
        assert len(missing) == 5
        assert "1-output" in missing

    def test_valid_input_structure(self, project_dirs):
        missing = validate_input_structure("ocp", "jfc-strategy")
        assert missing == []

    def test_missing_input_subdirs(self, env_roots):
        _, client_root = env_roots
        input_dir = client_root / "clients" / "ocp" / "projects" / "jfc-strategy" / "0-input"
        input_dir.mkdir(parents=True)
        (input_dir / "00-scope").mkdir()
        missing = validate_input_structure("ocp", "jfc-strategy")
        assert len(missing) == 10  # 11 total - 1 created

    def test_client_root_exists(self, env_roots):
        assert validate_client_root_exists() is True

    def test_client_root_not_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("AMS_CLIENT_ROOT", str(tmp_path / "nonexistent"))
        assert validate_client_root_exists() is False


# ---------------------------------------------------------------------------
# Scaffold tests
# ---------------------------------------------------------------------------


class TestScaffold:
    def test_scaffold_creates_all_dirs(self, env_roots):
        root = scaffold_project("test-client", "test-project")
        assert root.is_dir()
        assert validate_project_structure("test-client", "test-project") == []
        assert validate_input_structure("test-client", "test-project") == []

    def test_scaffold_creates_client_context(self, env_roots):
        scaffold_project("test-client", "test-project")
        assert get_client_templates_dir("test-client").is_dir()
        assert get_client_memory_dir("test-client").is_dir()

    def test_scaffold_idempotent(self, env_roots):
        scaffold_project("test-client", "test-project")
        scaffold_project("test-client", "test-project")  # Should not raise
        assert validate_project_structure("test-client", "test-project") == []


# ---------------------------------------------------------------------------
# Security tests
# ---------------------------------------------------------------------------


class TestSecurity:
    def test_path_traversal_client_slug(self):
        with pytest.raises(ValueError):
            get_project_root("../../../etc", "passwd")

    def test_path_traversal_project_slug(self):
        with pytest.raises(ValueError):
            get_project_root("ocp", "../../../etc/passwd")

    def test_command_injection_slug(self):
        with pytest.raises(ValueError):
            get_project_root("ocp; rm -rf /", "test")

    def test_uppercase_rejected(self):
        with pytest.raises(ValueError):
            get_project_root("OCP", "test")

    def test_spaces_rejected(self):
        with pytest.raises(ValueError):
            get_project_root("my client", "my project")

    def test_dot_rejected(self):
        with pytest.raises(ValueError):
            get_project_root("ocp.evil", "test")


# ---------------------------------------------------------------------------
# SessionState integration tests
# ---------------------------------------------------------------------------


class TestSessionStateIntegration:
    def test_session_state_with_client_context(self):
        from agents.orchestration.session_state import SessionState
        session = SessionState(
            session_id="test-123",
            client_slug="ocp",
            project_slug="jfc-strategy",
        )
        assert session.client_slug == "ocp"
        assert session.project_slug == "jfc-strategy"

    def test_session_state_serialization(self):
        from agents.orchestration.session_state import SessionState
        session = SessionState(
            session_id="test-123",
            client_slug="ocp",
            project_slug="jfc-strategy",
            equipment_tag="SAG-MILL-001",
            plant_code="OCP-JFC",
        )
        json_str = session.to_json()
        restored = SessionState.from_json(json_str)
        assert restored.client_slug == "ocp"
        assert restored.project_slug == "jfc-strategy"
        assert restored.equipment_tag == "SAG-MILL-001"

    def test_session_state_backward_compat(self):
        from agents.orchestration.session_state import SessionState
        # Old-style without client_slug/project_slug
        session = SessionState(session_id="test-456")
        assert session.client_slug == ""
        assert session.project_slug == ""

    def test_to_file_and_from_file(self, env_roots):
        from agents.orchestration.session_state import SessionState
        session = SessionState(
            session_id="test-789",
            client_slug="ocp",
            project_slug="jfc-strategy",
            equipment_tag="SAG-MILL-001",
        )
        # Create state dir
        state_dir = get_state_dir("ocp", "jfc-strategy")
        state_dir.mkdir(parents=True, exist_ok=True)

        path = session.to_file()
        assert path is not None
        assert path.exists()

        restored = SessionState.from_file(path)
        assert restored.session_id == "test-789"
        assert restored.client_slug == "ocp"
        assert restored.equipment_tag == "SAG-MILL-001"

    def test_to_file_without_client_returns_none(self):
        from agents.orchestration.session_state import SessionState
        session = SessionState(session_id="test-no-client")
        result = session.to_file()
        assert result is None

    def test_to_file_with_explicit_path(self, tmp_path):
        from agents.orchestration.session_state import SessionState
        session = SessionState(session_id="test-explicit")
        path = tmp_path / "state.json"
        result = session.to_file(path)
        assert result == path
        assert path.exists()


# ---------------------------------------------------------------------------
# Live OCP structure test (only runs if Drive is mounted)
# ---------------------------------------------------------------------------


CLIENT_ROOT = Path("g:/Unidades compartidas/VSC Team/VSC CHILE/03. PRODUCT/ASSET-MANAGEMENT-SOFTWARE-CLIENT")


@pytest.mark.skipif(
    not CLIENT_ROOT.is_dir(),
    reason="Google Drive not mounted or ASSET-MANAGEMENT-SOFTWARE-CLIENT not found",
)
class TestLiveOCPStructure:
    def test_ocp_project_structure_exists(self):
        project_root = CLIENT_ROOT / "clients" / "ocp" / "projects" / "jfc-maintenance-strategy"
        assert project_root.is_dir()
        for subdir in PROJECT_SUBDIRS:
            assert (project_root / subdir).is_dir(), f"Missing: {subdir}"

    def test_ocp_input_structure_exists(self):
        input_dir = CLIENT_ROOT / "clients" / "ocp" / "projects" / "jfc-maintenance-strategy" / "0-input"
        for subdir in INPUT_SUBDIRS:
            assert (input_dir / subdir).is_dir(), f"Missing input: {subdir}"

    def test_ocp_proposal_migrated(self):
        proposal_dir = CLIENT_ROOT / "clients" / "ocp" / "projects" / "jfc-maintenance-strategy" / "0-input" / "10-proposal"
        files = list(proposal_dir.glob("*.pdf"))
        assert len(files) >= 2, f"Expected at least 2 PDFs, found {len(files)}"

    def test_ocp_interviews_migrated(self):
        interviews_dir = CLIENT_ROOT / "clients" / "ocp" / "projects" / "jfc-maintenance-strategy" / "0-input" / "08-interviews"
        files = list(interviews_dir.iterdir())
        # README + at least some interview files
        assert len(files) >= 2

    def test_ocp_project_yaml_exists(self):
        project_yaml = CLIENT_ROOT / "clients" / "ocp" / "projects" / "jfc-maintenance-strategy" / "project.yaml"
        assert project_yaml.is_file()
        config = yaml.safe_load(project_yaml.read_text(encoding="utf-8"))
        assert config["client"]["slug"] == "ocp"
        assert config["scope"]["plant"]["code"] == "OCP-JFC"
