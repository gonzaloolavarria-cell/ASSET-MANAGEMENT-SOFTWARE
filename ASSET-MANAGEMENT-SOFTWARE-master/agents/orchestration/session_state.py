"""Session state for a strategy development session.

Accumulates entities across milestones so each milestone builds on the
previous one's approved output.

Uses a generic entity store (dict[str, list[dict]]) internally, with
backward-compatible property accessors for each entity type.
Enforces Single Writer, Multiple Reader (SWMR) ownership.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Entity ownership (SWMR)
# ---------------------------------------------------------------------------

class EntityOwner(str, Enum):
    """Which agent owns writing rights for each AMS entity type."""

    ORCHESTRATOR = "orchestrator"
    RELIABILITY = "reliability"
    PLANNING = "planning"
    SPARE_PARTS = "spare_parts"


ENTITY_OWNERSHIP: dict[str, EntityOwner] = {
    "hierarchy_nodes": EntityOwner.RELIABILITY,
    "criticality_assessments": EntityOwner.RELIABILITY,
    "functions": EntityOwner.RELIABILITY,
    "functional_failures": EntityOwner.RELIABILITY,
    "failure_modes": EntityOwner.RELIABILITY,
    "maintenance_tasks": EntityOwner.PLANNING,
    "work_packages": EntityOwner.PLANNING,
    "work_instructions": EntityOwner.PLANNING,
    "material_assignments": EntityOwner.SPARE_PARTS,
    "quality_scores": EntityOwner.ORCHESTRATOR,
    "execution_checklists": EntityOwner.PLANNING,
    "budget_items": EntityOwner.PLANNING,
    "roi_calculations": EntityOwner.ORCHESTRATOR,
    "financial_impacts": EntityOwner.ORCHESTRATOR,
    # GAP-W09: Competency-based work assignment
    "workforce_assignments": EntityOwner.PLANNING,
    "technician_profiles": EntityOwner.PLANNING,
    # GAP-W10: Deliverable tracking
    "deliverables": EntityOwner.ORCHESTRATOR,
    "time_logs": EntityOwner.ORCHESTRATOR,
    # GAP-W13: Expert knowledge capture
    "expert_consultations": EntityOwner.ORCHESTRATOR,
    "expert_contributions": EntityOwner.RELIABILITY,
}


# ---------------------------------------------------------------------------
# SessionState
# ---------------------------------------------------------------------------

@dataclass
class SessionState:
    """Accumulator for all entities produced during a strategy session.

    Each milestone appends to these lists. The Orchestrator reads them
    to provide context to specialist agents and to run validation.
    """

    session_id: str = ""
    equipment_tag: str = ""
    plant_code: str = ""
    started_at: str = field(default_factory=lambda: datetime.now().isoformat())

    # Client project context (optional — backward-compatible)
    client_slug: str = ""
    project_slug: str = ""

    # Generic entity store
    entities: dict[str, list[dict]] = field(default_factory=dict)

    # Milestone 4 special output (not a list entity)
    sap_upload_package: dict | None = None

    # Execution plan path (set by wizard, read by workflow)
    execution_plan_path: str = ""

    # Audit trail
    agent_interactions: list[dict] = field(default_factory=list)

    # --- Backward-compatible property accessors ---

    @property
    def hierarchy_nodes(self) -> list[dict]:
        return self.entities.setdefault("hierarchy_nodes", [])

    @property
    def criticality_assessments(self) -> list[dict]:
        return self.entities.setdefault("criticality_assessments", [])

    @property
    def functions(self) -> list[dict]:
        return self.entities.setdefault("functions", [])

    @property
    def functional_failures(self) -> list[dict]:
        return self.entities.setdefault("functional_failures", [])

    @property
    def failure_modes(self) -> list[dict]:
        return self.entities.setdefault("failure_modes", [])

    @property
    def maintenance_tasks(self) -> list[dict]:
        return self.entities.setdefault("maintenance_tasks", [])

    @property
    def work_packages(self) -> list[dict]:
        return self.entities.setdefault("work_packages", [])

    @property
    def work_instructions(self) -> list[dict]:
        return self.entities.setdefault("work_instructions", [])

    @property
    def material_assignments(self) -> list[dict]:
        return self.entities.setdefault("material_assignments", [])

    @property
    def quality_scores(self) -> list[dict]:
        return self.entities.setdefault("quality_scores", [])

    @property
    def execution_checklists(self) -> list[dict]:
        return self.entities.setdefault("execution_checklists", [])

    @property
    def budget_items(self) -> list[dict]:
        return self.entities.setdefault("budget_items", [])

    @property
    def roi_calculations(self) -> list[dict]:
        return self.entities.setdefault("roi_calculations", [])

    @property
    def financial_impacts(self) -> list[dict]:
        return self.entities.setdefault("financial_impacts", [])

    @property
    def workforce_assignments(self) -> list[dict]:
        return self.entities.setdefault("workforce_assignments", [])

    @property
    def technician_profiles(self) -> list[dict]:
        return self.entities.setdefault("technician_profiles", [])

    @property
    def deliverables(self) -> list[dict]:
        return self.entities.setdefault("deliverables", [])

    @property
    def time_logs(self) -> list[dict]:
        return self.entities.setdefault("time_logs", [])

    # GAP-W13: Expert knowledge capture
    @property
    def expert_consultations(self) -> list[dict]:
        return self.entities.setdefault("expert_consultations", [])

    @property
    def expert_contributions(self) -> list[dict]:
        return self.entities.setdefault("expert_contributions", [])

    # --- Entity write with ownership enforcement ---

    def write_entities(
        self,
        entity_type: str,
        data: list[dict] | dict,
        writer_agent: str,
    ) -> None:
        """Write entities with SWMR ownership check.

        Args:
            entity_type: Type key (e.g. "hierarchy_nodes").
            data: Single entity dict or list of entity dicts.
            writer_agent: The agent performing the write.

        Raises:
            PermissionError: If the agent doesn't own this entity type.
            ValueError: If entity_type is not registered.
        """
        if entity_type not in ENTITY_OWNERSHIP:
            raise ValueError(
                f"Unknown entity type: '{entity_type}'. "
                f"Registered: {sorted(ENTITY_OWNERSHIP.keys())}"
            )

        expected_owner = ENTITY_OWNERSHIP[entity_type]
        if expected_owner.value != writer_agent:
            raise PermissionError(
                f"Agent '{writer_agent}' cannot write '{entity_type}'. "
                f"Owner is '{expected_owner.value}'."
            )

        if entity_type not in self.entities:
            self.entities[entity_type] = []

        if isinstance(data, dict):
            self.entities[entity_type].append(data)
        else:
            self.entities[entity_type].extend(data)

    def read_entities(self, entity_type: str) -> list[dict]:
        """Read all entities of a type. Any agent can read."""
        return self.entities.get(entity_type, [])

    # --- Existing API (backward-compatible) ---

    def record_interaction(self, agent_type: str, milestone: int, instruction: str, response_summary: str) -> None:
        """Record an agent interaction for audit trail."""
        self.agent_interactions.append({
            "timestamp": datetime.now().isoformat(),
            "agent_type": agent_type,
            "milestone": milestone,
            "instruction": instruction[:200],
            "response_summary": response_summary[:500],
        })

    def get_entity_counts(self) -> dict[str, int | bool]:
        """Return counts of all accumulated entities."""
        counts: dict[str, int | bool] = {}
        for key in ENTITY_OWNERSHIP:
            counts[key] = len(self.entities.get(key, []))
        counts["sap_upload_generated"] = self.sap_upload_package is not None
        return counts

    def to_json(self) -> str:
        """Serialize session state to JSON."""
        data = {
            "session_id": self.session_id,
            "equipment_tag": self.equipment_tag,
            "plant_code": self.plant_code,
            "started_at": self.started_at,
            "client_slug": self.client_slug,
            "project_slug": self.project_slug,
            "execution_plan_path": self.execution_plan_path,
            "entities": self.entities,
            "sap_upload_package": self.sap_upload_package,
            "agent_interactions": self.agent_interactions,
        }
        return json.dumps(data, indent=2, default=str)

    @classmethod
    def from_json(cls, json_str: str) -> SessionState:
        """Deserialize session state from JSON.

        Handles both new-style (entities dict) and legacy (flat lists) format.
        """
        data = json.loads(json_str)

        # Handle legacy format: flat list fields → entities dict
        if "entities" not in data:
            entities: dict[str, list[dict]] = {}
            for key in ENTITY_OWNERSHIP:
                if key in data and isinstance(data[key], list):
                    entities[key] = data.pop(key)
            data["entities"] = entities

        return cls(
            session_id=data.get("session_id", ""),
            equipment_tag=data.get("equipment_tag", ""),
            plant_code=data.get("plant_code", ""),
            started_at=data.get("started_at", ""),
            client_slug=data.get("client_slug", ""),
            project_slug=data.get("project_slug", ""),
            execution_plan_path=data.get("execution_plan_path", ""),
            entities=data.get("entities", {}),
            sap_upload_package=data.get("sap_upload_package"),
            agent_interactions=data.get("agent_interactions", []),
        )

    def to_file(self, path: Any = None) -> Any:
        """Save session state to a JSON file."""
        from pathlib import Path as _Path

        if path is None and self.client_slug and self.project_slug:
            from agents._shared.paths import get_session_file
            path = get_session_file(self.client_slug, self.project_slug)

        if path is None:
            return None

        path = _Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path

    @classmethod
    def from_file(cls, path: Any) -> SessionState:
        """Load session state from a JSON file."""
        from pathlib import Path as _Path

        path = _Path(path)
        return cls.from_json(path.read_text(encoding="utf-8"))

    def get_validation_input(self) -> dict[str, Any]:
        """Build the input dict for run_full_validation."""
        result: dict[str, Any] = {}
        if self.hierarchy_nodes:
            result["nodes"] = self.hierarchy_nodes
        if self.functions:
            result["functions"] = self.functions
        if self.functional_failures:
            result["functional_failures"] = self.functional_failures
        if self.criticality_assessments:
            result["criticality_assessments"] = self.criticality_assessments
        if self.failure_modes:
            result["failure_modes"] = self.failure_modes
        if self.maintenance_tasks:
            result["tasks"] = self.maintenance_tasks
        if self.work_packages:
            result["work_packages"] = self.work_packages
        return result
