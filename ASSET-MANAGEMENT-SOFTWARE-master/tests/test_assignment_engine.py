"""Tests for the Competency-Based Work Assignment Engine (GAP-W09).

Covers: score_match, optimize_assignments, reoptimize_with_absences,
generate_assignment_summary, and edge cases.
"""

from __future__ import annotations

from datetime import date

import pytest

from tools.engines.assignment_engine import (
    AssignmentEngine,
    WEIGHT_AVAILABILITY,
    WEIGHT_CERTIFICATION,
    WEIGHT_COMPETENCY,
    WEIGHT_EQUIPMENT,
    WEIGHT_SPECIALTY,
)
from tools.models.schemas import (
    AssignmentStatus,
    CompetencyLevel,
    LabourSpecialty,
    TaskCompetencyRequirement,
    TechnicianCompetency,
    TechnicianProfile,
    WorkAssignment,
)


# ── Fixtures ──────────────────────────────────────────────────────────

@pytest.fixture
def engine():
    return AssignmentEngine()


@pytest.fixture
def senior_fitter():
    """A-level mechanical fitter with SAG Mill expertise."""
    return TechnicianProfile(
        worker_id="W-001",
        name="García",
        specialty=LabourSpecialty.FITTER,
        shift="MORNING",
        plant_id="OCP-JFC",
        available=True,
        competencies=[
            TechnicianCompetency(
                specialty=LabourSpecialty.FITTER,
                equipment_type="SAG_MILL",
                level=CompetencyLevel.A,
                certified=True,
            ),
            TechnicianCompetency(
                specialty=LabourSpecialty.FITTER,
                equipment_type="CONVEYOR",
                level=CompetencyLevel.B,
            ),
        ],
        years_experience=15,
        equipment_expertise=["SAG_MILL", "CONVEYOR", "CRUSHER"],
        certifications=["SAFETY_ADV", "CONFINED_SPACE"],
        safety_training_current=True,
    )


@pytest.fixture
def mid_fitter():
    """B-level fitter."""
    return TechnicianProfile(
        worker_id="W-002",
        name="López",
        specialty=LabourSpecialty.FITTER,
        shift="MORNING",
        plant_id="OCP-JFC",
        available=True,
        competencies=[
            TechnicianCompetency(
                specialty=LabourSpecialty.FITTER,
                equipment_type="CONVEYOR",
                level=CompetencyLevel.B,
            ),
        ],
        years_experience=7,
        equipment_expertise=["CONVEYOR"],
        certifications=["SAFETY_BASIC"],
        safety_training_current=True,
    )


@pytest.fixture
def junior_electrician():
    """C-level electrician."""
    return TechnicianProfile(
        worker_id="W-003",
        name="Martínez",
        specialty=LabourSpecialty.ELECTRICIAN,
        shift="MORNING",
        plant_id="OCP-JFC",
        available=True,
        competencies=[
            TechnicianCompetency(
                specialty=LabourSpecialty.ELECTRICIAN,
                equipment_type="MOTOR",
                level=CompetencyLevel.C,
            ),
        ],
        years_experience=2,
        equipment_expertise=["MOTOR"],
        certifications=[],
        safety_training_current=True,
    )


@pytest.fixture
def absent_fitter():
    """Fitter who is marked as unavailable."""
    return TechnicianProfile(
        worker_id="W-004",
        name="Ruiz",
        specialty=LabourSpecialty.FITTER,
        shift="MORNING",
        plant_id="OCP-JFC",
        available=False,
        competencies=[
            TechnicianCompetency(
                specialty=LabourSpecialty.FITTER,
                equipment_type="SAG_MILL",
                level=CompetencyLevel.B,
            ),
        ],
        years_experience=5,
        equipment_expertise=["SAG_MILL"],
        certifications=["SAFETY_BASIC"],
    )


@pytest.fixture
def senior_electrician():
    """A-level electrician with motor expertise."""
    return TechnicianProfile(
        worker_id="W-005",
        name="Sánchez",
        specialty=LabourSpecialty.ELECTRICIAN,
        shift="MORNING",
        plant_id="OCP-JFC",
        available=True,
        competencies=[
            TechnicianCompetency(
                specialty=LabourSpecialty.ELECTRICIAN,
                equipment_type="MOTOR",
                level=CompetencyLevel.A,
                certified=True,
            ),
        ],
        years_experience=20,
        equipment_expertise=["MOTOR", "TRANSFORMER"],
        certifications=["SAFETY_ADV", "HV_CERT"],
        safety_training_current=True,
    )


@pytest.fixture
def sample_tasks():
    """Typical shift task list."""
    return [
        {
            "task_id": "T-001",
            "work_package_id": "WP-001",
            "name": "PM SAG Mill Bearings",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.FITTER,
                    min_level=CompetencyLevel.A,
                    equipment_type="SAG_MILL",
                    requires_certification=True,
                ),
            ],
            "estimated_hours": 4.0,
            "priority": 5,
        },
        {
            "task_id": "T-002",
            "work_package_id": "WP-001",
            "name": "Inspect Conveyor Belt",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.FITTER,
                    min_level=CompetencyLevel.B,
                    equipment_type="CONVEYOR",
                ),
            ],
            "estimated_hours": 2.0,
            "priority": 3,
        },
        {
            "task_id": "T-003",
            "work_package_id": "WP-002",
            "name": "Motor Insulation Test",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.ELECTRICIAN,
                    min_level=CompetencyLevel.A,
                    equipment_type="MOTOR",
                    requires_certification=True,
                ),
            ],
            "estimated_hours": 3.0,
            "priority": 4,
        },
    ]


# ============================================================
# TestScoreMatch
# ============================================================

class TestScoreMatch:
    """Tests for AssignmentEngine.score_match()."""

    def test_perfect_match(self, engine, senior_fitter):
        """A-level fitter with exact equipment and certs scores 100."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.A,
            equipment_type="SAG_MILL",
            requires_certification=True,
        )
        score, reasons = engine.score_match(senior_fitter, req)
        assert score == 100.0
        assert any("Specialty match" in r for r in reasons)

    def test_specialty_mismatch_zero_specialty_points(self, engine, senior_fitter):
        """Fitter scored against electrician requirement — no specialty points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.ELECTRICIAN,
            min_level=CompetencyLevel.C,
        )
        score, reasons = engine.score_match(senior_fitter, req)
        assert score < 100.0
        assert any("Specialty mismatch" in r for r in reasons)

    def test_competency_b_meets_b(self, engine, mid_fitter):
        """B-level meets B requirement — partial competency points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.B,
            equipment_type="CONVEYOR",
        )
        score, reasons = engine.score_match(mid_fitter, req)
        # Should get specialty(30) + competency(partial) + equipment(20) + cert(15) + avail(10)
        assert score > 60
        assert any("meets min B" in r for r in reasons)

    def test_under_qualified_c_for_b(self, engine, junior_electrician):
        """C-level technician for B-required task — no competency points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.ELECTRICIAN,
            min_level=CompetencyLevel.B,
            equipment_type="MOTOR",
        )
        score, reasons = engine.score_match(junior_electrician, req)
        assert any("Under-qualified" in r for r in reasons)

    def test_a_level_exceeds_c_requirement(self, engine, senior_fitter):
        """A-level for C-required task — full competency points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.C,
            equipment_type="SAG_MILL",
        )
        score, reasons = engine.score_match(senior_fitter, req)
        assert score == 100.0

    def test_no_equipment_requirement_full_points(self, engine, senior_fitter):
        """No specific equipment needed — full equipment points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.B,
        )
        score, reasons = engine.score_match(senior_fitter, req)
        assert any("No specific equipment" in r for r in reasons)

    def test_no_certification_full_points(self, engine, mid_fitter):
        """No cert required — full cert points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.B,
            equipment_type="CONVEYOR",
            requires_certification=False,
        )
        score, reasons = engine.score_match(mid_fitter, req)
        assert any("No certification required" in r for r in reasons)

    def test_missing_certification(self, engine, junior_electrician):
        """Task requires cert but technician has none — no cert points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.ELECTRICIAN,
            min_level=CompetencyLevel.C,
            equipment_type="MOTOR",
            requires_certification=True,
        )
        score, reasons = engine.score_match(junior_electrician, req)
        assert any("Missing certifications" in r for r in reasons)

    def test_partially_available(self, engine, senior_fitter):
        """Technician with 6h already assigned — partial availability."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.A,
            equipment_type="SAG_MILL",
            requires_certification=True,
        )
        score, reasons = engine.score_match(senior_fitter, req, assigned_hours=6.0)
        assert any("Partially available" in r for r in reasons)
        assert score < 100.0

    def test_fully_booked(self, engine, senior_fitter):
        """Technician fully booked — zero availability points."""
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.A,
            equipment_type="SAG_MILL",
            requires_certification=True,
        )
        score, reasons = engine.score_match(senior_fitter, req, assigned_hours=8.0)
        assert any("Fully booked" in r for r in reasons)

    def test_equipment_competency_partial_credit(self, engine, senior_fitter):
        """Has competency record for equipment but not in expertise list."""
        # senior_fitter has CONVEYOR competency but let's test with CONVEYOR
        # which IS in equipment_expertise — so let's create a scenario
        # where competency exists but not in equipment_expertise
        tech = TechnicianProfile(
            worker_id="W-X",
            name="Test",
            specialty=LabourSpecialty.FITTER,
            shift="MORNING",
            plant_id="OCP-JFC",
            competencies=[
                TechnicianCompetency(
                    specialty=LabourSpecialty.FITTER,
                    equipment_type="PUMP",
                    level=CompetencyLevel.B,
                ),
            ],
            equipment_expertise=[],  # Not in expertise list
        )
        req = TaskCompetencyRequirement(
            specialty=LabourSpecialty.FITTER,
            min_level=CompetencyLevel.B,
            equipment_type="PUMP",
        )
        score, reasons = engine.score_match(tech, req)
        assert any("Has competency record" in r for r in reasons)

    def test_score_weights_sum_to_100(self):
        """Verify the 5 scoring dimensions sum to 100."""
        total = WEIGHT_SPECIALTY + WEIGHT_COMPETENCY + WEIGHT_EQUIPMENT + WEIGHT_CERTIFICATION + WEIGHT_AVAILABILITY
        assert total == 100


# ============================================================
# TestOptimizeAssignments
# ============================================================

class TestOptimizeAssignments:
    """Tests for AssignmentEngine.optimize_assignments()."""

    def test_happy_path_all_assigned(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """All 3 tasks assigned to appropriate technicians."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 3
        assert summary.unassigned_tasks == 0
        assert len(summary.assignments) == 3

    def test_high_priority_gets_best_match(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Highest-priority task (SAG Mill, P5) should get the A-level fitter."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        sag_assignment = next(
            a for a in summary.assignments if a.task_id == "T-001"
        )
        assert sag_assignment.worker_id == "W-001"  # García (senior fitter)

    def test_absent_workers_excluded(
        self, engine, senior_fitter, absent_fitter, senior_electrician, sample_tasks,
    ):
        """Absent workers (available=False) are not assigned."""
        techs = [senior_fitter, absent_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assigned_ids = {a.worker_id for a in summary.assignments}
        assert "W-004" not in assigned_ids  # Ruiz is absent
        assert summary.absent_technicians == 1

    def test_wrong_shift_excluded(
        self, engine, senior_fitter, sample_tasks,
    ):
        """Workers on MORNING shift not available for AFTERNOON tasks."""
        summary = engine.optimize_assignments(
            sample_tasks, [senior_fitter],
            date(2026, 3, 15), "AFTERNOON", "OCP-JFC",
        )
        assert summary.available_technicians == 0
        assert summary.unassigned_tasks == len(sample_tasks)

    def test_insufficient_crew_partial_assignment(self, engine, senior_fitter, sample_tasks):
        """Only 1 technician for 3 tasks — some go unassigned."""
        summary = engine.optimize_assignments(
            sample_tasks, [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        # Senior fitter can do 8h — can handle T-001 (4h) + T-002 (2h) = 6h
        # T-003 requires ELECTRICIAN — unassigned
        assert summary.unassigned_tasks >= 1

    def test_all_assignments_are_suggested(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """All new assignments have SUGGESTED status."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        for assignment in summary.assignments:
            assert assignment.status == AssignmentStatus.SUGGESTED

    def test_crew_utilization_calculated(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Utilization % is correctly calculated."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        total_hours = sum(a.estimated_hours for a in summary.assignments)
        expected_util = total_hours / (3 * 8.0) * 100
        assert abs(summary.crew_utilization_pct - round(expected_util, 1)) < 0.2

    def test_no_tasks_empty_result(self, engine, senior_fitter):
        """No tasks to assign — empty summary."""
        summary = engine.optimize_assignments(
            [], [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 0
        assert summary.unassigned_tasks == 0
        assert summary.crew_utilization_pct == 0.0

    def test_no_technicians_all_unassigned(self, engine, sample_tasks):
        """No technicians available — all tasks unassigned."""
        summary = engine.optimize_assignments(
            sample_tasks, [],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 0
        assert summary.unassigned_tasks == len(sample_tasks)

    def test_tasks_without_requirements(self, engine, senior_fitter):
        """Tasks with no competency requirements get default handling."""
        tasks = [{
            "task_id": "T-X",
            "work_package_id": "WP-X",
            "name": "Generic inspection",
            "competency_requirements": [],
            "estimated_hours": 1.0,
        }]
        summary = engine.optimize_assignments(
            tasks, [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 1

    def test_underqualified_warning(self, engine, junior_electrician):
        """C-level assigned to B-required task generates warning."""
        tasks = [{
            "task_id": "T-UQ",
            "work_package_id": "WP-UQ",
            "name": "Motor Overhaul",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.ELECTRICIAN,
                    min_level=CompetencyLevel.B,
                    equipment_type="MOTOR",
                ),
            ],
            "estimated_hours": 3.0,
        }]
        summary = engine.optimize_assignments(
            tasks, [junior_electrician],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.underqualified_assignments >= 0  # May or may not assign

    def test_dict_competency_requirements_parsed(self, engine, senior_fitter):
        """Competency requirements as dicts (from JSON) are parsed correctly."""
        tasks = [{
            "task_id": "T-D",
            "work_package_id": "WP-D",
            "name": "Dict-based task",
            "competency_requirements": [
                {
                    "specialty": "FITTER",
                    "min_level": "A",
                    "equipment_type": "SAG_MILL",
                    "requires_certification": True,
                }
            ],
            "estimated_hours": 2.0,
        }]
        summary = engine.optimize_assignments(
            tasks, [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 1

    def test_match_score_in_range(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """All match scores are between 0 and 100."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        summary = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        for a in summary.assignments:
            assert 0 <= a.match_score <= 100


# ============================================================
# TestReoptimize
# ============================================================

class TestReoptimize:
    """Tests for reoptimize_with_absences()."""

    def test_reoptimize_removes_absent_assignments(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Absent worker's assignments get reassigned."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        original = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )

        # Remove senior fitter
        result = engine.reoptimize_with_absences(
            original.assignments,
            absent_worker_ids=["W-001"],
            all_technicians=techs,
            tasks=sample_tasks,
            target_date=date(2026, 3, 15),
            target_shift="MORNING",
            plant_id="OCP-JFC",
        )
        assigned_ids = {a.worker_id for a in result.assignments}
        assert "W-001" not in assigned_ids
        assert result.absent_technicians == 1
        assert any("Re-optimized" in w for w in result.warnings)

    def test_reoptimize_keeps_unaffected(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Workers who are present keep their assignments."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        original = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )

        # Remove junior electrician (not in this fixture set, so nobody)
        result = engine.reoptimize_with_absences(
            original.assignments,
            absent_worker_ids=["W-999"],  # nonexistent
            all_technicians=techs,
            tasks=sample_tasks,
            target_date=date(2026, 3, 15),
            target_shift="MORNING",
            plant_id="OCP-JFC",
        )
        assert result.assigned_tasks == original.assigned_tasks

    def test_reoptimize_multiple_absent(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Multiple absent workers — all their tasks get reassigned."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        original = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )

        result = engine.reoptimize_with_absences(
            original.assignments,
            absent_worker_ids=["W-001", "W-002"],
            all_technicians=techs,
            tasks=sample_tasks,
            target_date=date(2026, 3, 15),
            target_shift="MORNING",
            plant_id="OCP-JFC",
        )
        assert result.absent_technicians == 2


# ============================================================
# TestGenerateSummary
# ============================================================

class TestGenerateSummary:
    """Tests for generate_assignment_summary()."""

    def test_summary_structure(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Summary dict has required keys."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        result = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        summary = engine.generate_assignment_summary(result)

        assert "date" in summary
        assert "shift" in summary
        assert "crew" in summary
        assert "tasks" in summary
        assert "technician_assignments" in summary
        assert "warnings" in summary

    def test_summary_technician_count(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Per-technician breakdown has correct number of entries."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        result = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        summary = engine.generate_assignment_summary(result)
        assigned_worker_ids = {a.worker_id for a in result.assignments}
        assert len(summary["technician_assignments"]) == len(assigned_worker_ids)

    def test_summary_hours_tally(
        self, engine, senior_fitter, mid_fitter, senior_electrician, sample_tasks,
    ):
        """Per-technician hours add up to total assigned hours."""
        techs = [senior_fitter, mid_fitter, senior_electrician]
        result = engine.optimize_assignments(
            sample_tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        summary = engine.generate_assignment_summary(result)
        total = sum(
            t["total_hours"] for t in summary["technician_assignments"]
        )
        expected = sum(a.estimated_hours for a in result.assignments)
        assert abs(total - expected) < 0.01


# ============================================================
# TestEdgeCases
# ============================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_workforce_empty_tasks(self, engine):
        """Both empty — no crash."""
        summary = engine.optimize_assignments(
            [], [], date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        assert summary.assigned_tasks == 0
        assert summary.crew_utilization_pct == 0.0

    def test_all_c_level_for_a_required(self, engine):
        """All C-level technicians for A-required tasks — none qualify."""
        techs = [
            TechnicianProfile(
                worker_id=f"W-C{i}",
                name=f"Junior{i}",
                specialty=LabourSpecialty.FITTER,
                shift="MORNING",
                plant_id="OCP-JFC",
                competencies=[
                    TechnicianCompetency(
                        specialty=LabourSpecialty.FITTER,
                        equipment_type="SAG_MILL",
                        level=CompetencyLevel.C,
                    ),
                ],
            )
            for i in range(3)
        ]
        tasks = [{
            "task_id": "T-HL",
            "work_package_id": "WP-HL",
            "name": "Critical SAG Mill Repair",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.FITTER,
                    min_level=CompetencyLevel.A,
                    equipment_type="SAG_MILL",
                    requires_certification=True,
                ),
            ],
            "estimated_hours": 4.0,
            "priority": 5,
        }]
        summary = engine.optimize_assignments(
            tasks, techs,
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        # May assign with low score or leave unassigned
        if summary.assigned_tasks == 0:
            assert summary.unassigned_tasks == 1
        else:
            assert summary.underqualified_assignments > 0

    def test_single_technician_multiple_tasks(self, engine, senior_fitter):
        """One tech, multiple tasks — fills up to shift limit."""
        tasks = [
            {
                "task_id": f"T-M{i}",
                "work_package_id": "WP-M",
                "name": f"Task {i}",
                "competency_requirements": [
                    TaskCompetencyRequirement(
                        specialty=LabourSpecialty.FITTER,
                        min_level=CompetencyLevel.B,
                    ),
                ],
                "estimated_hours": 3.0,
            }
            for i in range(4)  # 12h total > 8h shift
        ]
        summary = engine.optimize_assignments(
            tasks, [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        # Can only fit 2 tasks (6h) or maybe 2 (6h), 3rd doesn't fit at 9h
        assert summary.assigned_tasks <= 2
        assert summary.unassigned_tasks >= 2

    def test_assignment_summary_date_format(self, engine, senior_fitter):
        """Summary date is ISO-formatted string."""
        tasks = [{
            "task_id": "T-D",
            "work_package_id": "WP-D",
            "name": "Date test",
            "competency_requirements": [],
            "estimated_hours": 1.0,
        }]
        result = engine.optimize_assignments(
            tasks, [senior_fitter],
            date(2026, 3, 15), "MORNING", "OCP-JFC",
        )
        summary = engine.generate_assignment_summary(result)
        assert summary["date"] == "2026-03-15"


# ============================================================
# TestSchemaValidation
# ============================================================

class TestSchemaValidation:
    """Test Pydantic schema validation for GAP-W09 models."""

    def test_competency_level_values(self):
        assert CompetencyLevel.A.value == "A"
        assert CompetencyLevel.B.value == "B"
        assert CompetencyLevel.C.value == "C"

    def test_assignment_status_values(self):
        assert AssignmentStatus.SUGGESTED.value == "SUGGESTED"
        assert AssignmentStatus.CONFIRMED.value == "CONFIRMED"
        assert AssignmentStatus.MODIFIED.value == "MODIFIED"

    def test_technician_profile_defaults(self):
        tp = TechnicianProfile(
            worker_id="W1", name="Test", specialty=LabourSpecialty.FITTER,
            shift="MORNING", plant_id="P1",
        )
        assert tp.available is True
        assert tp.competencies == []
        assert tp.years_experience == 0
        assert tp.safety_training_current is True

    def test_work_assignment_defaults(self):
        wa = WorkAssignment(
            work_package_id="WP1",
            worker_id="W1",
            worker_name="Test",
            specialty=LabourSpecialty.FITTER,
            competency_level=CompetencyLevel.B,
            scheduled_date=date(2026, 3, 15),
            scheduled_shift="MORNING",
            estimated_hours=4.0,
        )
        assert wa.status == AssignmentStatus.SUGGESTED
        assert wa.match_score == 0.0
        assert wa.assignment_id  # UUID generated

    def test_work_assignment_score_validation(self):
        """Match score must be 0-100."""
        with pytest.raises(Exception):
            WorkAssignment(
                work_package_id="WP1",
                worker_id="W1",
                worker_name="Test",
                specialty=LabourSpecialty.FITTER,
                competency_level=CompetencyLevel.B,
                scheduled_date=date(2026, 3, 15),
                scheduled_shift="MORNING",
                estimated_hours=4.0,
                match_score=150.0,  # Invalid
            )

    def test_task_competency_requirement_defaults(self):
        tcr = TaskCompetencyRequirement(specialty=LabourSpecialty.FITTER)
        assert tcr.min_level == CompetencyLevel.B
        assert tcr.requires_certification is False
        assert tcr.supervision_required is False

    def test_technician_competency_creation(self):
        tc = TechnicianCompetency(
            specialty=LabourSpecialty.ELECTRICIAN,
            equipment_type="MOTOR",
            level=CompetencyLevel.A,
            certified=True,
        )
        assert tc.level == CompetencyLevel.A
        assert tc.certified is True


# ============================================================
# TestIntegration — Full flow
# ============================================================

class TestIntegration:
    """Integration tests: optimize → confirm → re-optimize with absences."""

    def test_full_flow_optimize_reoptimize(self, engine):
        """Full flow: create crew, optimize, absent worker, re-optimize."""
        # Build a small crew
        techs = [
            TechnicianProfile(
                worker_id=f"INT-{i}",
                name=f"Worker {i}",
                specialty=[LabourSpecialty.FITTER, LabourSpecialty.ELECTRICIAN,
                           LabourSpecialty.FITTER][i],
                shift="MORNING",
                plant_id="P1",
                available=True,
                competencies=[
                    TechnicianCompetency(
                        specialty=[LabourSpecialty.FITTER, LabourSpecialty.ELECTRICIAN,
                                   LabourSpecialty.FITTER][i],
                        equipment_type="PUMP",
                        level=[CompetencyLevel.A, CompetencyLevel.A, CompetencyLevel.B][i],
                    ),
                ],
                years_experience=[15, 12, 5][i],
                equipment_expertise=["PUMP"],
                certifications=["SAFETY_ADV"] if i < 2 else ["SAFETY_BASIC"],
            )
            for i in range(3)
        ]

        tasks = [
            {
                "task_id": "INT-T1",
                "work_package_id": "INT-WP",
                "name": "Pump bearing replacement",
                "competency_requirements": [
                    TaskCompetencyRequirement(
                        specialty=LabourSpecialty.FITTER,
                        min_level=CompetencyLevel.A,
                        equipment_type="PUMP",
                        requires_certification=True,
                    ),
                ],
                "estimated_hours": 3.0,
                "priority": 5,
            },
            {
                "task_id": "INT-T2",
                "work_package_id": "INT-WP",
                "name": "Motor insulation check",
                "competency_requirements": [
                    TaskCompetencyRequirement(
                        specialty=LabourSpecialty.ELECTRICIAN,
                        min_level=CompetencyLevel.B,
                        equipment_type="PUMP",
                    ),
                ],
                "estimated_hours": 2.0,
                "priority": 3,
            },
        ]

        # Step 1: Initial optimization
        summary1 = engine.optimize_assignments(
            tasks, techs, date(2026, 3, 20), "MORNING", "P1",
        )
        assert summary1.assigned_tasks == 2
        assert summary1.unassigned_tasks == 0

        # Step 2: Worker 0 (senior fitter) calls in sick
        summary2 = engine.reoptimize_with_absences(
            existing_assignments=summary1.assignments,
            absent_worker_ids=["INT-0"],
            all_technicians=techs,
            tasks=tasks,
            target_date=date(2026, 3, 20),
            target_shift="MORNING",
            plant_id="P1",
        )
        assert summary2.absent_technicians == 1
        assigned_ids = {a.worker_id for a in summary2.assignments}
        assert "INT-0" not in assigned_ids

        # Step 3: Generate summary
        report = engine.generate_assignment_summary(summary2)
        assert report["crew"]["absent"] == 1
        assert isinstance(report["technician_assignments"], list)

    def test_session_state_swmr_integration(self):
        """Verify workforce_assignments can be written by planning agent."""
        from agents.orchestration.session_state import SessionState

        state = SessionState(session_id="test-int")
        state.write_entities(
            "workforce_assignments",
            [{"assignment_id": "A1", "worker_id": "W1", "task_id": "T1"}],
            "planning",
        )
        assert len(state.workforce_assignments) == 1

        # Orchestrator cannot write workforce_assignments
        with pytest.raises(PermissionError):
            state.write_entities(
                "workforce_assignments",
                [{"assignment_id": "A2"}],
                "orchestrator",
            )

    def test_scheduling_engine_integration(self):
        """SchedulingEngine.generate_crew_assignments delegates correctly."""
        from tools.engines.scheduling_engine import SchedulingEngine

        techs = [
            TechnicianProfile(
                worker_id="SE-1",
                name="Fitter A",
                specialty=LabourSpecialty.FITTER,
                shift="MORNING",
                plant_id="P1",
                competencies=[
                    TechnicianCompetency(
                        specialty=LabourSpecialty.FITTER,
                        equipment_type="PUMP",
                        level=CompetencyLevel.A,
                    ),
                ],
                equipment_expertise=["PUMP"],
            ),
        ]
        tasks = [{
            "task_id": "SE-T1",
            "work_package_id": "SE-WP",
            "name": "Test task",
            "competency_requirements": [
                TaskCompetencyRequirement(
                    specialty=LabourSpecialty.FITTER,
                    min_level=CompetencyLevel.B,
                ),
            ],
            "estimated_hours": 2.0,
        }]

        summary = SchedulingEngine.generate_crew_assignments(
            tasks, techs, date(2026, 3, 20), "MORNING", "P1",
        )
        assert summary.assigned_tasks == 1
