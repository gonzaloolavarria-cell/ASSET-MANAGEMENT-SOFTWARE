"""Tests for Execution Checklist Engine and Models (GAP-W06).

Covers: enums, Pydantic models, checklist generation, gate logic,
step completion, closure summaries, skip logic, and MCP tool wrappers.
"""

import json
import pytest

from tools.models.schemas import (
    ChecklistClosureSummary,
    ChecklistStatus,
    ConditionCode,
    ExecutionChecklist,
    ExecutionStep,
    StepObservation,
    StepStatus,
    StepType,
    TaskType,
    TaskConstraint,
)
from tools.engines.execution_checklist_engine import ExecutionChecklistEngine


# ====================================================================
# Test fixtures
# ====================================================================

def _make_work_package(
    constraint="ONLINE",
    allocated_tasks=None,
    wp_id="WP-001",
    name="PUMP OVERHAUL",
    code="WP-PM-001",
):
    """Create a minimal work package dict."""
    return {
        "work_package_id": wp_id,
        "name": name,
        "code": code,
        "constraint": constraint,
        "allocated_tasks": allocated_tasks or [],
        "job_preparation": "Ensure area is clean",
        "post_shutdown": "Verify alignment",
    }


def _make_task(
    task_id="T-001",
    name="Inspect bearings",
    name_fr="Inspecter roulements",
    task_type="INSPECT",
    acceptable_limits=None,
    materials=None,
    labour=None,
):
    """Create a minimal maintenance task dict."""
    return {
        "task_id": task_id,
        "name": name,
        "name_fr": name_fr,
        "task_type": task_type,
        "acceptable_limits": acceptable_limits,
        "material_resources": materials or [],
        "labour_resources": labour or [],
        "access_time_hours": 0,
    }


def _make_allocated(task_id, op_number, order=1):
    return {"task_id": task_id, "operation_number": op_number, "order": order}


def _simple_online_wp():
    """3-task online WP for quick tests."""
    wp = _make_work_package(
        constraint="ONLINE",
        allocated_tasks=[
            _make_allocated("T-001", 10, 1),
            _make_allocated("T-002", 20, 2),
            _make_allocated("T-003", 30, 3),
        ],
    )
    tasks = [
        _make_task("T-001", "Inspect bearings", task_type="INSPECT"),
        _make_task("T-002", "Lubricate gearbox", task_type="LUBRICATE"),
        _make_task("T-003", "Check alignment", task_type="CHECK",
                   acceptable_limits="Alignment < 0.05mm"),
    ]
    return wp, tasks


def _offline_replace_wp():
    """Offline WP with a REPLACE task — triggers LOTO + quality gate."""
    wp = _make_work_package(
        constraint="OFFLINE",
        allocated_tasks=[
            _make_allocated("T-010", 10, 1),
            _make_allocated("T-011", 20, 2),
        ],
    )
    tasks = [
        _make_task("T-010", "Replace seal", task_type="REPLACE",
                   materials=[{"material_name": "Mechanical Seal"}]),
        _make_task("T-011", "Inspect shaft", task_type="INSPECT",
                   acceptable_limits="No scoring > 0.1mm"),
    ]
    return wp, tasks


# ====================================================================
# Enum tests
# ====================================================================

class TestEnums:
    def test_checklist_status_values(self):
        assert len(ChecklistStatus) == 5
        assert ChecklistStatus.DRAFT.value == "DRAFT"
        assert ChecklistStatus.CANCELLED.value == "CANCELLED"

    def test_step_status_values(self):
        assert len(StepStatus) == 6
        assert StepStatus.BLOCKED.value == "BLOCKED"
        assert StepStatus.FAILED.value == "FAILED"

    def test_condition_code_values(self):
        assert ConditionCode.NO_FAULT_FOUND == 1
        assert ConditionCode.FAULT_FOUND_AND_FIXED == 2
        assert ConditionCode.DEFECT_FOUND_NOT_FIXED == 3
        assert len(ConditionCode) == 3

    def test_step_type_values(self):
        assert len(StepType) == 6
        assert StepType.QUALITY_GATE.value == "QUALITY_GATE"
        assert StepType.HANDOVER.value == "HANDOVER"


# ====================================================================
# Model tests
# ====================================================================

class TestStepObservation:
    def test_defaults(self):
        obs = StepObservation()
        assert obs.observed_by == ""
        assert obs.condition_code == ConditionCode.NO_FAULT_FOUND
        assert obs.measured_value is None
        assert obs.photo_ref is None
        assert obs.defect_created is False

    def test_with_all_fields(self):
        obs = StepObservation(
            observed_by="TECH-01",
            condition_code=ConditionCode.DEFECT_FOUND_NOT_FIXED,
            measured_value="0.15mm",
            notes="Scoring visible on shaft",
            photo_ref="/photos/shaft_001.jpg",
            defect_created=True,
            defect_ref="WR-999",
        )
        assert obs.condition_code == ConditionCode.DEFECT_FOUND_NOT_FIXED
        assert obs.defect_ref == "WR-999"


class TestExecutionStep:
    def test_defaults(self):
        step = ExecutionStep()
        assert step.step_id  # UUID auto-generated
        assert step.step_type == StepType.TASK_OPERATION
        assert step.status == StepStatus.PENDING
        assert step.is_gate is False
        assert step.observation is None

    def test_gate_step(self):
        step = ExecutionStep(
            step_type=StepType.QUALITY_GATE,
            is_gate=True,
            gate_question="Ready to proceed?",
        )
        assert step.is_gate is True
        assert step.gate_question == "Ready to proceed?"

    def test_auto_uuid_generation(self):
        s1 = ExecutionStep()
        s2 = ExecutionStep()
        assert s1.step_id != s2.step_id

    def test_with_observation(self):
        obs = StepObservation(condition_code=ConditionCode.FAULT_FOUND_AND_FIXED)
        step = ExecutionStep(observation=obs)
        assert step.observation.condition_code == ConditionCode.FAULT_FOUND_AND_FIXED


class TestExecutionChecklist:
    def test_defaults(self):
        cl = ExecutionChecklist()
        assert cl.checklist_id  # UUID
        assert cl.status == ChecklistStatus.DRAFT
        assert cl.steps == []
        assert cl.ai_generated is True
        assert cl.closure_summary is None

    def test_status_lifecycle(self):
        for s in [ChecklistStatus.DRAFT, ChecklistStatus.IN_PROGRESS,
                   ChecklistStatus.COMPLETED, ChecklistStatus.CLOSED]:
            cl = ExecutionChecklist(status=s)
            assert cl.status == s


class TestChecklistClosureSummary:
    def test_defaults(self):
        cs = ChecklistClosureSummary()
        assert cs.total_steps == 0
        assert cs.completion_pct == 0.0
        assert cs.defects_raised == 0

    def test_with_values(self):
        cs = ChecklistClosureSummary(
            total_steps=10,
            completed_steps=8,
            skipped_steps=2,
            completion_pct=100.0,
            condition_distribution={"NO_FAULT_FOUND": 7, "FAULT_FOUND_AND_FIXED": 1},
            defects_raised=0,
        )
        assert cs.completed_steps + cs.skipped_steps == 10


# ====================================================================
# Generation tests
# ====================================================================

class TestChecklistGeneration:
    def test_generate_from_simple_wp(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks, "Pump 001", "PMP-001")

        assert cl.work_package_id == "WP-001"
        assert cl.equipment_tag == "PMP-001"
        assert cl.status == ChecklistStatus.DRAFT
        assert len(cl.steps) > 0
        # No LOTO for ONLINE
        assert cl.safety_section == []

    def test_generate_from_offline_wp(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks, "Pump 002", "PMP-002")

        # Should have safety section (LOTO)
        assert len(cl.safety_section) > 0
        # Should have SAFETY_CHECK steps
        safety_steps = [s for s in cl.steps if s.step_type == StepType.SAFETY_CHECK]
        assert len(safety_steps) == 8  # LOTO application has 8 items

    def test_step_numbering_hierarchical(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # All steps should have group.sub format
        for step in cl.steps:
            parts = step.step_number.split(".")
            assert len(parts) == 2, f"Step number '{step.step_number}' not hierarchical"
            assert parts[0].isdigit()
            assert parts[1].isdigit()

    def test_quality_gate_after_replace_task(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Find the REPLACE operation step
        replace_idx = None
        for i, s in enumerate(cl.steps):
            if s.source_task_id == "T-010" and s.step_type == StepType.TASK_OPERATION:
                replace_idx = i
                break

        assert replace_idx is not None
        # After REPLACE, there should be a QUALITY_GATE
        found_gate = False
        for s in cl.steps[replace_idx + 1:]:
            if s.source_task_id == "T-010" and s.step_type == StepType.QUALITY_GATE:
                found_gate = True
                break
            if s.source_task_id != "T-010":
                break
        assert found_gate, "Quality gate not found after REPLACE task"

    def test_commissioning_gate_at_end(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Should have a commissioning quality gate
        comm_gates = [
            s for s in cl.steps
            if s.step_type == StepType.QUALITY_GATE
            and "commissioning" in (s.gate_question or "").lower()
        ]
        assert len(comm_gates) == 1

    def test_handover_gate_final(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Last step should be HANDOVER gate
        assert cl.steps[-1].step_type == StepType.HANDOVER
        assert cl.steps[-1].is_gate is True

    def test_predecessor_wiring(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Safety gate should depend on all safety check steps
        safety_gate = None
        for s in cl.steps:
            if s.step_type == StepType.QUALITY_GATE and "safety" in (s.gate_question or "").lower():
                safety_gate = s
                break

        if safety_gate:
            safety_checks = [
                s.step_id for s in cl.steps if s.step_type == StepType.SAFETY_CHECK
            ]
            for sc_id in safety_checks:
                assert sc_id in safety_gate.predecessor_step_ids

    def test_empty_wp_no_operation_steps(self):
        wp = _make_work_package(allocated_tasks=[])
        cl = ExecutionChecklistEngine.generate_checklist(wp, [])
        # Should still have commissioning + handover gates if enabled
        # But no operation steps
        op_steps = [s for s in cl.steps if s.step_type == StepType.TASK_OPERATION]
        assert len(op_steps) == 0

    def test_materials_propagated_to_steps(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        replace_step = None
        for s in cl.steps:
            if s.source_task_id == "T-010" and s.step_type == StepType.TASK_OPERATION:
                replace_step = s
                break

        assert replace_step is not None
        assert "Mechanical Seal" in replace_step.materials

    def test_pre_post_notes_propagated(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)
        assert cl.pre_task_notes == "Ensure area is clean"
        assert cl.post_task_notes == "Verify alignment"

    def test_inspection_step_for_acceptable_limits(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # T-003 has acceptable_limits — should generate an INSPECTION step
        insp_steps = [
            s for s in cl.steps
            if s.step_type == StepType.INSPECTION and s.source_task_id == "T-003"
        ]
        assert len(insp_steps) == 1
        assert "0.05mm" in insp_steps[0].acceptable_limits

    def test_no_safety_gates_when_disabled(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(
            wp, tasks, include_safety_gates=False,
        )
        safety_gates = [
            s for s in cl.steps
            if s.step_type == StepType.QUALITY_GATE
            and "safety" in (s.gate_question or "").lower()
        ]
        assert len(safety_gates) == 0


# ====================================================================
# Gate logic tests
# ====================================================================

class TestGateLogic:
    def test_cannot_complete_step_with_pending_predecessor(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Find a step with predecessors
        step_with_preds = None
        for s in cl.steps:
            if s.predecessor_step_ids:
                step_with_preds = s
                break

        assert step_with_preds is not None
        can, reason = ExecutionChecklistEngine.validate_step_completion(
            cl, step_with_preds.step_id
        )
        assert can is False
        assert "not yet completed" in reason

    def test_can_complete_step_when_predecessors_done(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # First task step should have no (or only safety) predecessors
        # For ONLINE, first task step has no safety preds
        first_op = None
        for s in cl.steps:
            if s.step_type == StepType.TASK_OPERATION:
                first_op = s
                break

        assert first_op is not None
        can, reason = ExecutionChecklistEngine.validate_step_completion(
            cl, first_op.step_id
        )
        assert can is True

    def test_gate_step_cannot_be_skipped(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        gate = None
        for s in cl.steps:
            if s.is_gate:
                gate = s
                break

        assert gate is not None
        with pytest.raises(ValueError, match="Gate steps cannot be skipped"):
            ExecutionChecklistEngine.skip_step(cl, gate.step_id, "Testing")

    def test_non_gate_step_can_be_skipped(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        non_gate = None
        for s in cl.steps:
            if not s.is_gate and s.step_type == StepType.TASK_OPERATION:
                non_gate = s
                break

        assert non_gate is not None
        cl = ExecutionChecklistEngine.skip_step(
            cl, non_gate.step_id, "Not needed", "SUPERVISOR-01"
        )
        # Find the skipped step
        skipped = None
        for s in cl.steps:
            if s.step_id == non_gate.step_id:
                skipped = s
                break
        assert skipped.status == StepStatus.SKIPPED

    def test_completing_predecessor_unblocks_successor(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Complete all operation steps in order to reach gates
        for step in cl.steps:
            if step.step_type in (StepType.TASK_OPERATION, StepType.INSPECTION):
                can, _ = ExecutionChecklistEngine.validate_step_completion(cl, step.step_id)
                if can:
                    cl = ExecutionChecklistEngine.complete_step(
                        cl, step.step_id, {"condition_code": 1}, "TECH-01"
                    )

        # Now commissioning gate should be completable
        comm_gate = None
        for s in cl.steps:
            if s.step_type == StepType.QUALITY_GATE and "commissioning" in (s.gate_question or "").lower():
                comm_gate = s
                break

        if comm_gate:
            can, reason = ExecutionChecklistEngine.validate_step_completion(cl, comm_gate.step_id)
            assert can is True, f"Commissioning gate blocked: {reason}"

    def test_step_not_found(self):
        cl = ExecutionChecklist()
        can, reason = ExecutionChecklistEngine.validate_step_completion(cl, "nonexistent")
        assert can is False
        assert "not found" in reason

    def test_already_completed_step(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        cl = ExecutionChecklistEngine.complete_step(cl, first_op.step_id)

        can, reason = ExecutionChecklistEngine.validate_step_completion(cl, first_op.step_id)
        assert can is False
        assert "already completed" in reason


# ====================================================================
# Step completion tests
# ====================================================================

class TestStepCompletion:
    def test_complete_step_updates_status(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        cl = ExecutionChecklistEngine.complete_step(cl, first_op.step_id, completed_by="TECH-01")

        updated = next(s for s in cl.steps if s.step_id == first_op.step_id)
        assert updated.status == StepStatus.COMPLETED
        assert updated.completed_by == "TECH-01"

    def test_complete_step_records_observation(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        obs = {
            "condition_code": 2,
            "notes": "Bearing had wear, replaced",
            "observed_by": "TECH-01",
        }
        cl = ExecutionChecklistEngine.complete_step(cl, first_op.step_id, obs, "TECH-01")

        updated = next(s for s in cl.steps if s.step_id == first_op.step_id)
        assert updated.observation is not None
        assert updated.observation.condition_code == ConditionCode.FAULT_FOUND_AND_FIXED
        assert "wear" in updated.observation.notes

    def test_complete_step_sets_timestamps(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        cl = ExecutionChecklistEngine.complete_step(cl, first_op.step_id)

        updated = next(s for s in cl.steps if s.step_id == first_op.step_id)
        assert updated.completed_at is not None
        assert updated.started_at is not None

    def test_first_completion_sets_checklist_in_progress(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)
        assert cl.status == ChecklistStatus.DRAFT

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        cl = ExecutionChecklistEngine.complete_step(cl, first_op.step_id)
        assert cl.status == ChecklistStatus.IN_PROGRESS
        assert cl.started_at is not None

    def test_complete_all_steps_generates_closure(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Complete all steps in order
        for _ in range(len(cl.steps)):
            actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
            if not actionable:
                break
            for step in actionable:
                cl = ExecutionChecklistEngine.complete_step(
                    cl, step.step_id, {"condition_code": 1}, "TECH-01"
                )

        assert cl.status == ChecklistStatus.COMPLETED
        assert cl.closure_summary is not None
        assert cl.closure_summary.completion_pct == 100.0

    def test_gate_blocked_raises_error(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Find a gate with pending predecessors
        gate = None
        for s in cl.steps:
            if s.is_gate and s.predecessor_step_ids:
                gate = s
                break

        assert gate is not None
        with pytest.raises(ValueError, match="not yet completed"):
            ExecutionChecklistEngine.complete_step(cl, gate.step_id)


# ====================================================================
# Closure summary tests
# ====================================================================

class TestClosureSummary:
    def test_closure_summary_computation(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Complete all steps
        for _ in range(len(cl.steps)):
            actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
            if not actionable:
                break
            for step in actionable:
                cl = ExecutionChecklistEngine.complete_step(
                    cl, step.step_id, {"condition_code": 1}, "TECH-01"
                )

        summary = cl.closure_summary
        assert summary is not None
        assert summary.total_steps == len(cl.steps)
        assert summary.completed_steps + summary.skipped_steps == summary.total_steps

    def test_condition_code_distribution(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Complete some with different condition codes
        actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
        codes = [1, 2, 1]
        for i, step in enumerate(actionable):
            code = codes[i] if i < len(codes) else 1
            cl = ExecutionChecklistEngine.complete_step(
                cl, step.step_id, {"condition_code": code}, "TECH-01"
            )

        summary = ExecutionChecklistEngine.generate_closure_summary(cl)
        assert "NO_FAULT_FOUND" in summary.condition_distribution

    def test_defects_listed_in_closure(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        first_op = next(s for s in cl.steps if s.step_type == StepType.TASK_OPERATION)
        cl = ExecutionChecklistEngine.complete_step(
            cl, first_op.step_id,
            {
                "condition_code": 3,
                "defect_created": True,
                "defect_ref": "WR-100",
            },
            "TECH-01",
        )

        summary = ExecutionChecklistEngine.generate_closure_summary(cl)
        assert summary.defects_raised == 1
        assert "WR-100" in summary.defect_refs


# ====================================================================
# Close checklist tests
# ====================================================================

class TestChecklistClose:
    def _complete_all(self, cl):
        """Helper: complete all steps in order."""
        for _ in range(len(cl.steps)):
            actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
            if not actionable:
                break
            for step in actionable:
                cl = ExecutionChecklistEngine.complete_step(
                    cl, step.step_id, {"condition_code": 1}, "TECH-01"
                )
        return cl

    def test_close_requires_all_steps_done(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        with pytest.raises(ValueError, match="Cannot close checklist"):
            ExecutionChecklistEngine.close_checklist(cl, "SUPER-01")

    def test_close_sets_supervisor(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)
        cl = self._complete_all(cl)

        cl = ExecutionChecklistEngine.close_checklist(cl, "SUPER-01", "All good")
        assert cl.supervisor == "SUPER-01"
        assert cl.status == ChecklistStatus.CLOSED

    def test_close_sets_timestamp(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)
        cl = self._complete_all(cl)

        cl = ExecutionChecklistEngine.close_checklist(cl, "SUPER-01")
        assert cl.closed_at is not None

    def test_close_generates_signature(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)
        cl = self._complete_all(cl)

        cl = ExecutionChecklistEngine.close_checklist(cl, "SUPER-01", "Reviewed and approved")
        assert cl.supervisor_signature == "Reviewed and approved"


# ====================================================================
# Next actionable steps tests
# ====================================================================

class TestNextActionableSteps:
    def test_initial_actionable_steps_online(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
        # For ONLINE, first operation steps should be actionable immediately
        assert len(actionable) > 0
        for s in actionable:
            assert s.status == StepStatus.PENDING

    def test_initial_actionable_steps_offline(self):
        wp, tasks = _offline_replace_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
        # For OFFLINE, only safety check steps should be actionable first
        for s in actionable:
            assert s.step_type == StepType.SAFETY_CHECK

    def test_no_actionable_when_all_done(self):
        wp, tasks = _simple_online_wp()
        cl = ExecutionChecklistEngine.generate_checklist(wp, tasks)

        # Complete everything
        for _ in range(len(cl.steps)):
            actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
            if not actionable:
                break
            for step in actionable:
                cl = ExecutionChecklistEngine.complete_step(
                    cl, step.step_id, {"condition_code": 1}, "TECH-01"
                )

        actionable = ExecutionChecklistEngine.get_next_actionable_steps(cl)
        assert len(actionable) == 0


# ====================================================================
# MCP Tool tests
# ====================================================================

class TestMCPTools:
    def test_generate_execution_checklist_tool(self):
        from agents.tool_wrappers.execution_checklist_tools import generate_execution_checklist

        wp, tasks = _simple_online_wp()
        result = generate_execution_checklist(json.dumps({
            "work_package": wp,
            "tasks": tasks,
            "equipment_name": "Pump 001",
            "equipment_tag": "PMP-001",
        }))
        data = json.loads(result)
        assert data["work_package_id"] == "WP-001"
        assert len(data["steps"]) > 0

    def test_complete_checklist_step_tool(self):
        from agents.tool_wrappers.execution_checklist_tools import (
            generate_execution_checklist,
            complete_checklist_step,
        )

        wp, tasks = _simple_online_wp()
        cl_json = json.loads(generate_execution_checklist(json.dumps({
            "work_package": wp, "tasks": tasks,
        })))

        # Find first TASK_OPERATION
        first_op = None
        for s in cl_json["steps"]:
            if s["step_type"] == "TASK_OPERATION":
                first_op = s
                break

        result = complete_checklist_step(json.dumps({
            "checklist": cl_json,
            "step_id": first_op["step_id"],
            "observation": {"condition_code": 1},
            "completed_by": "TECH-01",
        }))
        data = json.loads(result)
        assert data["status"] == "IN_PROGRESS"

    def test_get_checklist_status_tool(self):
        from agents.tool_wrappers.execution_checklist_tools import (
            generate_execution_checklist,
            get_checklist_status,
        )

        wp, tasks = _simple_online_wp()
        cl_json = json.loads(generate_execution_checklist(json.dumps({
            "work_package": wp, "tasks": tasks,
        })))

        result = get_checklist_status(json.dumps({"checklist": cl_json}))
        data = json.loads(result)
        assert data["status"] == "DRAFT"
        assert data["total_steps"] > 0
        assert "next_actionable_steps" in data

    def test_skip_checklist_step_tool(self):
        from agents.tool_wrappers.execution_checklist_tools import (
            generate_execution_checklist,
            skip_checklist_step,
        )

        wp, tasks = _simple_online_wp()
        cl_json = json.loads(generate_execution_checklist(json.dumps({
            "work_package": wp, "tasks": tasks,
        })))

        # Find first non-gate TASK_OPERATION
        first_op = None
        for s in cl_json["steps"]:
            if s["step_type"] == "TASK_OPERATION" and not s["is_gate"]:
                first_op = s
                break

        result = skip_checklist_step(json.dumps({
            "checklist": cl_json,
            "step_id": first_op["step_id"],
            "reason": "Not applicable",
            "authorized_by": "SUPER-01",
        }))
        data = json.loads(result)
        # Find the skipped step
        skipped = next(s for s in data["steps"] if s["step_id"] == first_op["step_id"])
        assert skipped["status"] == "SKIPPED"

    def test_tool_registration_in_registry(self):
        from agents.tool_wrappers.registry import TOOL_REGISTRY

        tool_names = list(TOOL_REGISTRY.keys())
        assert "generate_execution_checklist" in tool_names
        assert "complete_checklist_step" in tool_names
        assert "skip_checklist_step" in tool_names
        assert "get_checklist_status" in tool_names
        assert "close_execution_checklist" in tool_names


# ====================================================================
# SessionState integration tests
# ====================================================================

class TestSessionStateIntegration:
    def test_entity_ownership_registered(self):
        from agents.orchestration.session_state import ENTITY_OWNERSHIP, EntityOwner
        assert "execution_checklists" in ENTITY_OWNERSHIP
        assert ENTITY_OWNERSHIP["execution_checklists"] == EntityOwner.PLANNING

    def test_property_accessor(self):
        from agents.orchestration.session_state import SessionState
        state = SessionState()
        assert state.execution_checklists == []
        # Verify it creates the key in entities
        assert "execution_checklists" in state.entities
