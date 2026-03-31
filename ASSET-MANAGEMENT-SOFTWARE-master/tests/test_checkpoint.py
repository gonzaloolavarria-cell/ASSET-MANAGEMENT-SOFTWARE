"""Tests for session checkpointing — save, load, find, auto-checkpoint, and recovery.

Tests REC-003: crash recovery via session state snapshots.
All tests are offline (no API key needed).
"""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agents.orchestration.checkpoint import (
    save_checkpoint,
    load_checkpoint,
    find_latest_checkpoint,
    auto_checkpoint,
    recover_from_checkpoint,
    _purge_old_auto_checkpoints,
)
from agents.orchestration.session_state import SessionState
from agents.definitions.base import AgentConfig
from agents.orchestration.workflow import StrategyWorkflow
from agents.orchestration.milestones import ValidationSummary


@pytest.fixture
def tmp_checkpoint_dir(tmp_path):
    """Provide a temporary directory for checkpoints."""
    return tmp_path / "checkpoints"


@pytest.fixture
def sample_session():
    """Create a session with some entities for testing."""
    session = SessionState(session_id="test-session-001")
    session.equipment_tag = "SAG Mill 001"
    session.plant_code = "OCP-JFC"
    session.hierarchy_nodes.append({"node_id": "n1", "name": "Plant"})
    session.hierarchy_nodes.append({"node_id": "n2", "name": "Area"})
    session.criticality_assessments.append({"assessment_id": "c1"})
    session.failure_modes.append({"mode_id": "fm1"})
    return session


class TestSaveCheckpoint:
    """Tests for save_checkpoint()."""

    def test_creates_file(self, tmp_checkpoint_dir, sample_session):
        """Checkpoint file should be created on disk."""
        path = save_checkpoint(sample_session, 1, tmp_checkpoint_dir)
        assert path.exists()
        assert path.name == "test-session-001_m1.json"

    def test_creates_directory_if_missing(self, tmp_path, sample_session):
        """Non-existent checkpoint directory should be auto-created."""
        deep_dir = tmp_path / "a" / "b" / "c"
        assert not deep_dir.exists()
        save_checkpoint(sample_session, 1, deep_dir)
        assert deep_dir.exists()

    def test_file_contains_valid_json(self, tmp_checkpoint_dir, sample_session):
        """Checkpoint file should contain valid JSON."""
        path = save_checkpoint(sample_session, 2, tmp_checkpoint_dir)
        data = json.loads(path.read_text(encoding="utf-8"))
        assert data["session_id"] == "test-session-001"
        assert data["equipment_tag"] == "SAG Mill 001"


class TestLoadCheckpoint:
    """Tests for load_checkpoint()."""

    def test_roundtrip(self, tmp_checkpoint_dir, sample_session):
        """Save then load should produce identical session data."""
        save_checkpoint(sample_session, 1, tmp_checkpoint_dir)
        loaded = load_checkpoint("test-session-001", 1, tmp_checkpoint_dir)

        assert loaded is not None
        assert loaded.session_id == "test-session-001"
        assert loaded.equipment_tag == "SAG Mill 001"
        assert loaded.plant_code == "OCP-JFC"
        assert len(loaded.hierarchy_nodes) == 2
        assert len(loaded.criticality_assessments) == 1
        assert len(loaded.failure_modes) == 1

    def test_missing_returns_none(self, tmp_checkpoint_dir):
        """Non-existent checkpoint should return None."""
        result = load_checkpoint("nonexistent-session", 1, tmp_checkpoint_dir)
        assert result is None


class TestFindLatestCheckpoint:
    """Tests for find_latest_checkpoint()."""

    def test_returns_highest_milestone(self, tmp_checkpoint_dir, sample_session):
        """When M1 and M2 are saved, should return M2."""
        save_checkpoint(sample_session, 1, tmp_checkpoint_dir)
        save_checkpoint(sample_session, 2, tmp_checkpoint_dir)

        result = find_latest_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is not None
        milestone_num, session = result
        assert milestone_num == 2

    def test_returns_none_when_empty(self, tmp_checkpoint_dir):
        """No checkpoints → None."""
        result = find_latest_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is None


class TestWorkflowCheckpointIntegration:
    """Integration test: workflow saves checkpoints on approve."""

    @patch("agents.orchestration.workflow._run_validation")
    def test_workflow_saves_checkpoint_on_approve(self, mock_validation, tmp_checkpoint_dir):
        """Auto-approve workflow should create checkpoint files."""
        mock_validation.return_value = ValidationSummary()

        def auto_approve(milestone_num, summary):
            return ("approve", "OK")

        with patch.object(AgentConfig, "load_system_prompt", return_value="Test"):
            with patch.object(AgentConfig, "get_tools_schema", return_value=[]):
                mock_client = MagicMock()
                workflow = StrategyWorkflow(
                    human_approval_fn=auto_approve,
                    client=mock_client,
                    checkpoint_dir=str(tmp_checkpoint_dir),
                )
                workflow.orchestrator.run = MagicMock(return_value="Done.")

        workflow.run("SAG Mill 001", "OCP")

        # All 4 milestones approved → 4 milestone checkpoint files
        # (auto-checkpoints with _auto_ prefix may also exist)
        milestone_files = [f for f in tmp_checkpoint_dir.glob("*.json") if "_auto_" not in f.name]
        assert len(milestone_files) == 4

    @patch("agents.orchestration.workflow._run_validation")
    def test_checkpoint_preserves_all_entities(self, mock_validation, tmp_checkpoint_dir):
        """Entities added to session should be preserved in checkpoint."""
        mock_validation.return_value = ValidationSummary()

        def auto_approve(milestone_num, summary):
            return ("approve", "OK")

        with patch.object(AgentConfig, "load_system_prompt", return_value="Test"):
            with patch.object(AgentConfig, "get_tools_schema", return_value=[]):
                mock_client = MagicMock()
                workflow = StrategyWorkflow(
                    human_approval_fn=auto_approve,
                    client=mock_client,
                    checkpoint_dir=str(tmp_checkpoint_dir),
                )
                workflow.orchestrator.run = MagicMock(return_value="Done.")

        # Add entities before running
        workflow.session.hierarchy_nodes.append({"node_id": "n1"})
        workflow.session.failure_modes.append({"mode_id": "fm1"})

        workflow.run("SAG Mill 001", "OCP")

        # Load the last checkpoint and verify entities
        session_id = workflow.session.session_id
        loaded = load_checkpoint(session_id, 4, tmp_checkpoint_dir)
        assert loaded is not None
        assert len(loaded.hierarchy_nodes) == 1
        assert len(loaded.failure_modes) == 1


# ---------------------------------------------------------------------------
# Auto-checkpoint tests
# ---------------------------------------------------------------------------

class TestAutoCheckpoint:
    """Tests for auto_checkpoint() — timestamped saves after agent interactions."""

    def test_creates_timestamped_file(self, tmp_checkpoint_dir, sample_session):
        """auto_checkpoint should create a file with _auto_ timestamp pattern."""
        path = auto_checkpoint(sample_session, tmp_checkpoint_dir)
        assert path.exists()
        assert "_auto_" in path.name
        assert path.name.startswith("test-session-001_auto_")
        assert path.suffix == ".json"

    def test_file_contains_valid_session(self, tmp_checkpoint_dir, sample_session):
        """Auto-checkpoint file should deserialize to a valid SessionState."""
        path = auto_checkpoint(sample_session, tmp_checkpoint_dir)
        loaded = SessionState.from_json(path.read_text(encoding="utf-8"))
        assert loaded.session_id == "test-session-001"
        assert len(loaded.hierarchy_nodes) == 2
        assert len(loaded.failure_modes) == 1

    def test_multiple_auto_checkpoints_unique_names(self, tmp_checkpoint_dir, sample_session):
        """Multiple calls should produce distinct files (different timestamps)."""
        path1 = auto_checkpoint(sample_session, tmp_checkpoint_dir)
        path2 = auto_checkpoint(sample_session, tmp_checkpoint_dir)
        assert path1.name != path2.name
        assert path1.exists()
        assert path2.exists()

    def test_creates_directory_if_missing(self, tmp_path, sample_session):
        """Auto-checkpoint should create the directory if it doesn't exist."""
        deep_dir = tmp_path / "x" / "y" / "z"
        assert not deep_dir.exists()
        auto_checkpoint(sample_session, deep_dir)
        assert deep_dir.exists()


class TestPurgeAutoCheckpoints:
    """Tests for _purge_old_auto_checkpoints() — enforcing max checkpoint limit."""

    def test_no_purge_when_under_limit(self, tmp_checkpoint_dir, sample_session):
        """Files should not be purged when count is within limit."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        auto_checkpoint(sample_session, tmp_checkpoint_dir, max_checkpoints=5)
        auto_files = list(tmp_checkpoint_dir.glob("*_auto_*.json"))
        assert len(auto_files) == 1

    def test_purge_oldest_when_over_limit(self, tmp_checkpoint_dir, sample_session):
        """Oldest auto-checkpoints should be removed when count exceeds limit."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        max_cp = 3

        # Create 5 checkpoints (exceeding limit of 3)
        paths = []
        for i in range(5):
            # Write files with distinct timestamps manually
            path = tmp_checkpoint_dir / f"test-session-001_auto_20260305T10000{i}.json"
            path.write_text(sample_session.to_json(), encoding="utf-8")
            paths.append(path)

        removed = _purge_old_auto_checkpoints("test-session-001", tmp_checkpoint_dir, max_cp)
        assert removed == 2  # 5 - 3 = 2 removed

        remaining = sorted(tmp_checkpoint_dir.glob("*_auto_*.json"))
        assert len(remaining) == 3
        # The 2 oldest should be gone
        assert not paths[0].exists()
        assert not paths[1].exists()
        # The 3 newest should remain
        assert paths[2].exists()
        assert paths[3].exists()
        assert paths[4].exists()

    def test_purge_returns_zero_when_exact_limit(self, tmp_checkpoint_dir, sample_session):
        """No purge when count exactly equals limit."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        for i in range(3):
            path = tmp_checkpoint_dir / f"test-session-001_auto_20260305T10000{i}.json"
            path.write_text(sample_session.to_json(), encoding="utf-8")

        removed = _purge_old_auto_checkpoints("test-session-001", tmp_checkpoint_dir, 3)
        assert removed == 0

    def test_purge_does_not_touch_milestone_checkpoints(self, tmp_checkpoint_dir, sample_session):
        """Purge should only affect _auto_ files, not milestone checkpoint files."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Create a milestone checkpoint
        save_checkpoint(sample_session, 1, tmp_checkpoint_dir)

        # Create auto-checkpoints exceeding limit
        for i in range(4):
            path = tmp_checkpoint_dir / f"test-session-001_auto_20260305T10000{i}.json"
            path.write_text(sample_session.to_json(), encoding="utf-8")

        _purge_old_auto_checkpoints("test-session-001", tmp_checkpoint_dir, 2)

        # Milestone checkpoint should still exist
        milestone_path = tmp_checkpoint_dir / "test-session-001_m1.json"
        assert milestone_path.exists()

        # Only 2 auto-checkpoints should remain
        auto_files = list(tmp_checkpoint_dir.glob("*_auto_*.json"))
        assert len(auto_files) == 2


# ---------------------------------------------------------------------------
# Recovery tests
# ---------------------------------------------------------------------------

class TestRecoverFromCheckpoint:
    """Tests for recover_from_checkpoint() — milestone-first, then auto fallback."""

    def test_recovers_from_milestone_checkpoint(self, tmp_checkpoint_dir, sample_session):
        """Should prefer milestone checkpoint over auto-checkpoint."""
        save_checkpoint(sample_session, 2, tmp_checkpoint_dir)

        # Also create an auto-checkpoint
        auto_checkpoint(sample_session, tmp_checkpoint_dir)

        result = recover_from_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is not None
        label, session = result
        assert label == "m2"
        assert session.session_id == "test-session-001"

    def test_falls_back_to_auto_checkpoint(self, tmp_checkpoint_dir, sample_session):
        """When no milestone checkpoint exists, should recover from auto."""
        auto_checkpoint(sample_session, tmp_checkpoint_dir)

        result = recover_from_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is not None
        label, session = result
        assert label.startswith("auto_")
        assert session.session_id == "test-session-001"
        assert len(session.hierarchy_nodes) == 2

    def test_returns_none_when_no_checkpoints(self, tmp_checkpoint_dir):
        """Should return None when no checkpoints exist at all."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)
        result = recover_from_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is None

    def test_recovers_latest_auto_checkpoint(self, tmp_checkpoint_dir, sample_session):
        """When multiple auto-checkpoints exist, should recover from the latest."""
        tmp_checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Create two auto-checkpoints with different data
        early = tmp_checkpoint_dir / "test-session-001_auto_20260305T100000.json"
        early.write_text(sample_session.to_json(), encoding="utf-8")

        # Modify session and create a later checkpoint
        sample_session.hierarchy_nodes.append({"node_id": "n3", "name": "System"})
        late = tmp_checkpoint_dir / "test-session-001_auto_20260305T110000.json"
        late.write_text(sample_session.to_json(), encoding="utf-8")

        result = recover_from_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is not None
        label, session = result
        assert "110000" in label  # Latest timestamp
        assert len(session.hierarchy_nodes) == 3  # Modified data

    def test_recovers_highest_milestone(self, tmp_checkpoint_dir, sample_session):
        """When multiple milestone checkpoints exist, should recover from highest."""
        save_checkpoint(sample_session, 1, tmp_checkpoint_dir)
        save_checkpoint(sample_session, 3, tmp_checkpoint_dir)

        result = recover_from_checkpoint("test-session-001", tmp_checkpoint_dir)
        assert result is not None
        label, session = result
        assert label == "m3"


class TestWorkflowAutoCheckpointIntegration:
    """Integration: workflow calls auto_checkpoint after each agent interaction."""

    @patch("agents.orchestration.workflow._run_validation")
    def test_auto_checkpoints_created_during_workflow(self, mock_validation, tmp_checkpoint_dir):
        """Workflow should create auto-checkpoint files after each agent interaction."""
        mock_validation.return_value = ValidationSummary()

        def auto_approve(milestone_num, summary):
            return ("approve", "OK")

        with patch.object(AgentConfig, "load_system_prompt", return_value="Test"):
            with patch.object(AgentConfig, "get_tools_schema", return_value=[]):
                mock_client = MagicMock()
                workflow = StrategyWorkflow(
                    human_approval_fn=auto_approve,
                    client=mock_client,
                    checkpoint_dir=str(tmp_checkpoint_dir),
                )
                workflow.orchestrator.run = MagicMock(return_value="Done.")

        workflow.run("SAG Mill 001", "OCP")

        # 4 milestones × 1 interaction each = 4 auto-checkpoints
        auto_files = list(tmp_checkpoint_dir.glob("*_auto_*.json"))
        assert len(auto_files) >= 4

    @patch("agents.orchestration.workflow._run_validation")
    def test_auto_checkpoint_on_each_modify_iteration(self, mock_validation, tmp_checkpoint_dir):
        """Each modify iteration should also produce an auto-checkpoint."""
        mock_validation.return_value = ValidationSummary()

        call_count = 0

        def modify_then_approve(milestone_num, summary):
            nonlocal call_count
            call_count += 1
            if milestone_num == 1 and call_count <= 2:
                return ("modify", "Try again")
            return ("approve", "OK")

        with patch.object(AgentConfig, "load_system_prompt", return_value="Test"):
            with patch.object(AgentConfig, "get_tools_schema", return_value=[]):
                mock_client = MagicMock()
                workflow = StrategyWorkflow(
                    human_approval_fn=modify_then_approve,
                    client=mock_client,
                    checkpoint_dir=str(tmp_checkpoint_dir),
                )
                workflow.orchestrator.run = MagicMock(return_value="Done.")

        workflow.run("SAG Mill 001", "OCP")

        # M1: 3 iterations (2 modify + 1 approve) + M2-M4: 1 each = 6 auto-checkpoints
        auto_files = list(tmp_checkpoint_dir.glob("*_auto_*.json"))
        assert len(auto_files) >= 6
