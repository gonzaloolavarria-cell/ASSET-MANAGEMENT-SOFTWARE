"""Extended tests for SessionState — serialization edge cases and mutation behavior.

Complements the 7 existing tests in test_milestones.py::TestSessionState.
All tests are offline (no API key needed).
"""

import json
import pytest

from agents.orchestration.session_state import (
    SessionState,
    ENTITY_OWNERSHIP,
    EntityOwner,
)


class TestSessionStateSerialization:
    """Edge cases for to_json()/from_json() round-trips."""

    def test_from_json_with_extra_fields_ignored(self):
        """Unknown keys in JSON should be silently ignored by from_json."""
        s = SessionState(session_id="s1")
        j = s.to_json()
        data = json.loads(j)
        data["unknown_field"] = "surprise"
        # from_json explicitly constructs from known fields — extra keys are dropped
        s2 = SessionState.from_json(json.dumps(data))
        assert s2.session_id == "s1"
        assert not hasattr(s2, "unknown_field")

    def test_roundtrip_sap_upload_dict(self):
        """sap_upload_package as a dict should survive JSON round-trip."""
        s = SessionState(session_id="s1")
        s.sap_upload_package = {
            "status": "GENERATED",
            "maintenance_items": [{"mi_id": "MI-001"}],
            "task_lists": [{"tl_id": "TL-001"}],
        }
        s2 = SessionState.from_json(s.to_json())
        assert s2.sap_upload_package is not None
        assert s2.sap_upload_package["status"] == "GENERATED"
        assert len(s2.sap_upload_package["maintenance_items"]) == 1

    def test_roundtrip_sap_upload_none(self):
        """sap_upload_package=None should round-trip as None."""
        s = SessionState(session_id="s1")
        assert s.sap_upload_package is None
        s2 = SessionState.from_json(s.to_json())
        assert s2.sap_upload_package is None

    def test_to_json_serializes_datetime(self):
        """started_at is a datetime-format string; to_json uses default=str."""
        s = SessionState(session_id="s1")
        j = s.to_json()
        data = json.loads(j)
        assert isinstance(data["started_at"], str)
        assert len(data["started_at"]) > 10  # ISO format


class TestSessionStateMutability:
    """Tests documenting the mutable public list behavior."""

    def test_direct_list_mutation_reflected(self):
        """Appending to a public list should be reflected in get_entity_counts."""
        s = SessionState(session_id="s1")
        s.hierarchy_nodes.append({"id": "n1"})
        s.hierarchy_nodes.append({"id": "n2"})
        assert s.get_entity_counts()["hierarchy_nodes"] == 2

    def test_shared_reference_mutation(self):
        """Mutating an appended dict changes the state (shallow copy risk)."""
        s = SessionState(session_id="s1")
        node = {"id": "original"}
        s.hierarchy_nodes.append(node)
        # Mutate the original dict
        node["id"] = "mutated"
        # The change is reflected in the session state
        assert s.hierarchy_nodes[0]["id"] == "mutated"


class TestSessionStateValidationInput:
    """Tests for get_validation_input() key mapping behavior."""

    def test_validation_input_key_mapping(self):
        """hierarchy_nodes maps to 'nodes', maintenance_tasks maps to 'tasks'."""
        s = SessionState(session_id="s1")
        s.hierarchy_nodes.append({"id": "n1"})
        s.maintenance_tasks.append({"id": "t1"})
        vi = s.get_validation_input()
        assert "nodes" in vi
        assert "tasks" in vi
        # The original field names are NOT used as keys
        assert "hierarchy_nodes" not in vi
        assert "maintenance_tasks" not in vi

    def test_validation_input_excludes_sap(self):
        """sap_upload_package is never included in validation input."""
        s = SessionState(session_id="s1")
        s.sap_upload_package = {"status": "GENERATED"}
        vi = s.get_validation_input()
        assert "sap_upload_package" not in vi

    def test_validation_input_excludes_work_instructions(self):
        """work_instructions are not mapped to validation_input."""
        s = SessionState(session_id="s1")
        s.work_instructions.append({"id": "wi1"})
        vi = s.get_validation_input()
        assert "work_instructions" not in vi

    def test_multiple_interactions_preserved(self):
        """Multiple record_interaction calls should all be preserved."""
        s = SessionState(session_id="s1")
        s.record_interaction("reliability", 1, "Build hierarchy", "Done")
        s.record_interaction("reliability", 2, "Run FMECA", "Complete")
        s.record_interaction("planning", 3, "Create tasks", "Finished")
        assert len(s.agent_interactions) == 3
        assert s.agent_interactions[0]["agent_type"] == "reliability"
        assert s.agent_interactions[1]["milestone"] == 2
        assert s.agent_interactions[2]["agent_type"] == "planning"


# ---------------------------------------------------------------------------
# SWMR ownership enforcement tests
# ---------------------------------------------------------------------------

class TestSWMROwnership:
    """Tests for write_entities() / read_entities() with ownership enforcement."""

    def test_owner_can_write_own_entity(self):
        """Reliability agent should be able to write hierarchy_nodes."""
        s = SessionState(session_id="s1")
        s.write_entities("hierarchy_nodes", {"node_id": "n1"}, "reliability")
        assert len(s.hierarchy_nodes) == 1
        assert s.hierarchy_nodes[0]["node_id"] == "n1"

    def test_owner_can_write_list_of_entities(self):
        """write_entities with a list should extend the entity list."""
        s = SessionState(session_id="s1")
        nodes = [{"node_id": "n1"}, {"node_id": "n2"}, {"node_id": "n3"}]
        s.write_entities("hierarchy_nodes", nodes, "reliability")
        assert len(s.hierarchy_nodes) == 3

    def test_non_owner_cannot_write(self):
        """Planning agent writing to hierarchy_nodes should raise PermissionError."""
        s = SessionState(session_id="s1")
        with pytest.raises(PermissionError, match="planning.*cannot write.*hierarchy_nodes"):
            s.write_entities("hierarchy_nodes", {"node_id": "n1"}, "planning")

    def test_unknown_entity_type_raises_value_error(self):
        """Writing to an unregistered entity type should raise ValueError."""
        s = SessionState(session_id="s1")
        with pytest.raises(ValueError, match="Unknown entity type.*bogus_type"):
            s.write_entities("bogus_type", {"id": "1"}, "reliability")

    def test_planning_agent_owns_maintenance_tasks(self):
        """Planning agent should own maintenance_tasks."""
        s = SessionState(session_id="s1")
        s.write_entities("maintenance_tasks", {"task_id": "t1"}, "planning")
        assert len(s.maintenance_tasks) == 1

    def test_spare_parts_agent_owns_material_assignments(self):
        """Spare parts agent should own material_assignments."""
        s = SessionState(session_id="s1")
        s.write_entities("material_assignments", {"mat_id": "m1"}, "spare_parts")
        assert len(s.material_assignments) == 1

    def test_reliability_cannot_write_tasks(self):
        """Reliability agent cannot write maintenance_tasks (owned by planning)."""
        s = SessionState(session_id="s1")
        with pytest.raises(PermissionError, match="reliability.*cannot write.*maintenance_tasks"):
            s.write_entities("maintenance_tasks", {"task_id": "t1"}, "reliability")

    def test_any_agent_can_read_any_entity(self):
        """read_entities should work for any agent (SWMR = multiple readers)."""
        s = SessionState(session_id="s1")
        s.write_entities("hierarchy_nodes", {"node_id": "n1"}, "reliability")
        # Any "agent" can read (read_entities doesn't check ownership)
        nodes = s.read_entities("hierarchy_nodes")
        assert len(nodes) == 1
        assert nodes[0]["node_id"] == "n1"

    def test_read_empty_entity_returns_empty_list(self):
        """Reading an entity type with no data should return empty list."""
        s = SessionState(session_id="s1")
        result = s.read_entities("hierarchy_nodes")
        assert result == []

    def test_read_unregistered_entity_returns_empty_list(self):
        """Reading an unregistered entity type should return empty list."""
        s = SessionState(session_id="s1")
        result = s.read_entities("nonexistent_type")
        assert result == []

    def test_write_entities_accumulates(self):
        """Multiple write_entities calls should accumulate, not replace."""
        s = SessionState(session_id="s1")
        s.write_entities("failure_modes", {"fm_id": "fm1"}, "reliability")
        s.write_entities("failure_modes", {"fm_id": "fm2"}, "reliability")
        assert len(s.failure_modes) == 2

    def test_all_ownership_mappings_defined(self):
        """Every entity type in ENTITY_OWNERSHIP should have a valid owner."""
        expected_types = {
            "hierarchy_nodes", "criticality_assessments", "functions",
            "functional_failures", "failure_modes", "maintenance_tasks",
            "work_packages", "work_instructions", "material_assignments",
            "quality_scores", "execution_checklists",
            "budget_items", "roi_calculations", "financial_impacts",
            "workforce_assignments", "technician_profiles",
            "deliverables", "time_logs",
            "expert_contributions", "expert_consultations",
        }
        assert set(ENTITY_OWNERSHIP.keys()) == expected_types
        for entity_type, owner in ENTITY_OWNERSHIP.items():
            assert isinstance(owner, EntityOwner)

    def test_multi_agent_simulation(self):
        """Simulate a realistic multi-agent write flow without conflicts."""
        s = SessionState(session_id="s1")

        # Reliability agent writes M1 + M2 entities
        s.write_entities("hierarchy_nodes", [{"id": "n1"}, {"id": "n2"}], "reliability")
        s.write_entities("criticality_assessments", [{"id": "c1"}], "reliability")
        s.write_entities("functions", [{"id": "f1"}], "reliability")
        s.write_entities("functional_failures", [{"id": "ff1"}], "reliability")
        s.write_entities("failure_modes", [{"id": "fm1"}], "reliability")

        # Planning agent writes M3 entities
        s.write_entities("maintenance_tasks", [{"id": "t1"}, {"id": "t2"}], "planning")
        s.write_entities("work_packages", [{"id": "wp1"}], "planning")
        s.write_entities("work_instructions", [{"id": "wi1"}], "planning")

        # Spare parts agent writes M3 entities
        s.write_entities("material_assignments", [{"id": "ma1"}], "spare_parts")

        counts = s.get_entity_counts()
        assert counts["hierarchy_nodes"] == 2
        assert counts["criticality_assessments"] == 1
        assert counts["functions"] == 1
        assert counts["functional_failures"] == 1
        assert counts["failure_modes"] == 1
        assert counts["maintenance_tasks"] == 2
        assert counts["work_packages"] == 1
        assert counts["work_instructions"] == 1
        assert counts["material_assignments"] == 1


# ---------------------------------------------------------------------------
# Legacy format migration tests
# ---------------------------------------------------------------------------

class TestLegacyFormatMigration:
    """Tests for from_json() handling of legacy flat-list format."""

    def test_legacy_flat_lists_migrated_to_entities_dict(self):
        """Old format with flat list fields should be migrated to entities dict."""
        legacy_json = json.dumps({
            "session_id": "legacy-001",
            "equipment_tag": "Pump 001",
            "plant_code": "OCP",
            "started_at": "2026-01-01T00:00:00",
            "hierarchy_nodes": [{"node_id": "n1"}],
            "failure_modes": [{"fm_id": "fm1"}, {"fm_id": "fm2"}],
            "maintenance_tasks": [{"task_id": "t1"}],
            "agent_interactions": [],
        })

        s = SessionState.from_json(legacy_json)
        assert s.session_id == "legacy-001"
        assert len(s.hierarchy_nodes) == 1
        assert len(s.failure_modes) == 2
        assert len(s.maintenance_tasks) == 1
        # Verify they're inside the entities dict
        assert "hierarchy_nodes" in s.entities
        assert "failure_modes" in s.entities
        assert "maintenance_tasks" in s.entities

    def test_new_format_with_entities_dict_loaded_directly(self):
        """New format with entities dict should load without migration."""
        new_json = json.dumps({
            "session_id": "new-001",
            "equipment_tag": "Conveyor 001",
            "plant_code": "OCP",
            "started_at": "2026-03-01T00:00:00",
            "entities": {
                "hierarchy_nodes": [{"node_id": "n1"}],
                "failure_modes": [{"fm_id": "fm1"}],
            },
            "agent_interactions": [],
        })

        s = SessionState.from_json(new_json)
        assert len(s.hierarchy_nodes) == 1
        assert len(s.failure_modes) == 1

    def test_legacy_format_with_empty_lists(self):
        """Legacy format with empty lists should not create spurious entity keys."""
        legacy_json = json.dumps({
            "session_id": "legacy-002",
            "equipment_tag": "Motor 001",
            "plant_code": "OCP",
            "started_at": "2026-01-01T00:00:00",
            "hierarchy_nodes": [],
            "agent_interactions": [],
        })

        s = SessionState.from_json(legacy_json)
        # Empty list should still be migrated into entities
        assert s.entities.get("hierarchy_nodes") == []
