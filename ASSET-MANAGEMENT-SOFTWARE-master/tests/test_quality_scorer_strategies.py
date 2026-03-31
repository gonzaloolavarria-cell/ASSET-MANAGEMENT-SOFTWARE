"""Tests for individual Quality Scoring Strategies — Phase 9.

One test class per scorer strategy.
Each tests perfect score, accuracy penalties, completeness penalties, traceability penalties.
"""

import pytest

from tools.engines.scoring_strategies.hierarchy_scorer import HierarchyScorer
from tools.engines.scoring_strategies.criticality_scorer import CriticalityScorer
from tools.engines.scoring_strategies.fmeca_scorer import FMECAScorer
from tools.engines.scoring_strategies.task_scorer import TaskScorer
from tools.engines.scoring_strategies.work_package_scorer import WorkPackageScorer
from tools.engines.scoring_strategies.sap_scorer import SAPScorer
from tools.models.schemas import QualityDimension


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

DEFAULT_WEIGHTS = {
    "technical_accuracy": 0.30,
    "completeness": 0.25,
    "consistency": 0.15,
    "format": 0.10,
    "actionability": 0.10,
    "traceability": 0.10,
}


def _perfect_hierarchy():
    return {
        "hierarchy_nodes": [
            {"node_id": "N1", "name": "Plant A", "name_fr": "Usine A", "node_type": "PLANT", "level": 1, "parent_node_id": None},
            {"node_id": "N2", "name": "Area 1", "name_fr": "Zone 1", "node_type": "AREA", "level": 2, "parent_node_id": "N1"},
            {"node_id": "N3", "name": "System 1", "name_fr": "Système 1", "node_type": "SYSTEM", "level": 3, "parent_node_id": "N2"},
            {"node_id": "N4", "name": "Equip 1", "name_fr": "Équip 1", "node_type": "EQUIPMENT", "level": 4, "parent_node_id": "N3", "metadata": {"manufacturer": "ABB", "model": "M100"}},
            {"node_id": "N5", "name": "Motor", "name_fr": "Moteur", "node_type": "MAINTAINABLE_ITEM", "level": 5, "parent_node_id": "N4", "component_lib_ref": "CL-001"},
        ],
    }


def _perfect_criticality():
    h = _perfect_hierarchy()
    h["criticality_assessments"] = [
        {
            "assessment_id": "CA1", "node_id": "N4", "assessed_at": "2026-01-01",
            "assessed_by": "Analyst", "method": "FULL_MATRIX", "probability": 3,
            "overall_score": 35.0, "risk_class": "III_HIGH",
            "criteria_scores": [{"category": "SAFETY", "consequence_level": 3}],
        },
        {
            "assessment_id": "CA2", "node_id": "N3", "assessed_at": "2026-01-01",
            "assessed_by": "Analyst", "method": "FULL_MATRIX", "probability": 2,
            "overall_score": 20.0, "risk_class": "II_MEDIUM",
            "criteria_scores": [{"category": "SAFETY", "consequence_level": 2}],
        },
    ]
    return h


def _perfect_fmeca():
    e = _perfect_criticality()
    e["functions"] = [{"function_id": "F1", "node_id": "N5", "function_type": "PRIMARY", "description": "Drive belt"}]
    e["functional_failures"] = [{"failure_id": "FF1", "function_id": "F1", "failure_type": "TOTAL", "description": "Cannot drive"}]
    e["failure_modes"] = [
        {
            "failure_mode_id": "FM1", "functional_failure_id": "FF1",
            "what": "Motor winding burns out",
            "mechanism": "OVERHEATS/MELTS", "cause": "OVERLOAD",
            "failure_pattern": "E_RANDOM", "failure_consequence": "EVIDENT_OPERATIONAL",
            "is_hidden": False, "strategy_type": "CONDITION_BASED",
        },
    ]
    return e


def _perfect_tasks():
    e = _perfect_fmeca()
    e["maintenance_tasks"] = [
        {
            "task_id": "T1", "name": "Check motor temperature weekly",
            "task_type": "CHECK", "failure_mode_id": "FM1",
            "frequency_value": 7, "frequency_unit": "DAYS", "constraint": "ONLINE",
            "access_time_hours": 0, "acceptable_limits": "< 80°C",
            "conditional_comments": "If > 80°C, schedule inspection",
            "labour_resources": [{"specialty": "ELECTRICIAN", "quantity": 1, "hours_per_person": 0.5}],
        },
    ]
    return e


def _perfect_work_packages():
    e = _perfect_tasks()
    e["work_packages"] = [
        {
            "work_package_id": "WP1", "name": "WEEKLY CONVEYOR ONLINE",
            "node_id": "N4", "frequency_value": 7, "frequency_unit": "DAYS",
            "constraint": "ONLINE", "work_package_type": "STANDALONE",
            "allocated_tasks": [{"task_id": "T1", "order": 1, "operation_number": 10}],
        },
    ]
    return e


def _perfect_sap():
    e = _perfect_work_packages()
    e["sap_upload_package"] = {
        "package_id": "SAP1", "plant_code": "OCP", "generated_at": "2026-01-20",
        "status": "GENERATED",
        "maintenance_plan": {"plan_id": "MP1", "description": "Belt Conveyor PM", "cycle_value": 7, "cycle_unit": "DAYS"},
        "maintenance_items": [{"item_id": "MI1", "func_loc": "N4", "task_list_ref": "TL1", "priority": 3}],
        "task_lists": [{"task_list_id": "TL1", "operations": [{"operation_number": 10, "work_centre": "ELEC", "short_text": "Check motor temp"}]}],
    }
    return e


# ---------------------------------------------------------------------------
# TestHierarchyScorer
# ---------------------------------------------------------------------------

class TestHierarchyScorer:
    scorer = HierarchyScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_hierarchy(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 80.0, f"{d.dimension} scored only {d.score}"

    def test_accuracy_penalty_invalid_level(self):
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N1", "name": "X", "name_fr": "X", "node_type": "PLANT", "level": 99},
            ],
        }
        dim = self.scorer.score_technical_accuracy(entities, {})
        assert dim.score < 100.0

    def test_completeness_penalty_missing_name_fr(self):
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N1", "name": "Plant", "node_type": "PLANT", "level": 1},
                {"node_id": "N2", "name": "Area", "node_type": "AREA", "level": 2, "parent_node_id": "N1"},
            ],
        }
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0

    def test_traceability_penalty_orphan_node(self):
        entities = {
            "hierarchy_nodes": [
                {"node_id": "N1", "name": "Plant", "node_type": "PLANT", "level": 1},
                {"node_id": "N2", "name": "Area", "node_type": "AREA", "level": 2, "parent_node_id": "NONEXISTENT"},
            ],
        }
        dim = self.scorer.score_traceability(entities, {})
        assert dim.score < 100.0


# ---------------------------------------------------------------------------
# TestCriticalityScorer
# ---------------------------------------------------------------------------

class TestCriticalityScorer:
    scorer = CriticalityScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_criticality(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 50.0, f"{d.dimension} scored only {d.score}"

    def test_accuracy_penalty_invalid_probability(self):
        entities = {
            "hierarchy_nodes": [],
            "criticality_assessments": [
                {"assessment_id": "CA1", "node_id": "N1", "probability": 99, "risk_class": "INVALID", "method": "INVALID"},
            ],
        }
        dim = self.scorer.score_technical_accuracy(entities, {})
        assert dim.score < 50.0

    def test_completeness_penalty_missing_assessed_by(self):
        entities = {
            "hierarchy_nodes": [],
            "criticality_assessments": [
                {"assessment_id": "CA1", "node_id": "N1", "probability": 3, "risk_class": "III_HIGH", "method": "FULL_MATRIX"},
            ],
        }
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0

    def test_traceability_penalty_bad_node_ref(self):
        entities = {
            "hierarchy_nodes": [{"node_id": "N1", "name": "Plant", "node_type": "PLANT", "level": 1}],
            "criticality_assessments": [
                {"assessment_id": "CA1", "node_id": "NONEXISTENT", "probability": 3, "risk_class": "III_HIGH"},
            ],
        }
        dim = self.scorer.score_traceability(entities, {})
        assert dim.score < 100.0


# ---------------------------------------------------------------------------
# TestFMECAScorer
# ---------------------------------------------------------------------------

class TestFMECAScorer:
    scorer = FMECAScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_fmeca(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 50.0, f"{d.dimension} scored only {d.score}"

    def test_accuracy_penalty_invalid_combo(self):
        entities = {
            "failure_modes": [
                {
                    "failure_mode_id": "FM1", "functional_failure_id": "FF1",
                    "what": "Something", "mechanism": "INVALID_MECH", "cause": "INVALID_CAUSE",
                    "strategy_type": "INVALID_STRAT", "failure_consequence": "INVALID",
                },
            ],
            "functions": [],
            "functional_failures": [],
            "hierarchy_nodes": [],
        }
        dim = self.scorer.score_technical_accuracy(entities, {})
        assert dim.score == 0.0

    def test_completeness_penalty_missing_what(self):
        entities = {
            "failure_modes": [
                {"failure_mode_id": "FM1", "functional_failure_id": "FF1", "mechanism": "WEARS", "cause": "USE"},
            ],
            "functions": [],
            "functional_failures": [],
            "hierarchy_nodes": [],
        }
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0

    def test_traceability_penalty_bad_ff_ref(self):
        entities = {
            "failure_modes": [
                {"failure_mode_id": "FM1", "functional_failure_id": "NONEXISTENT", "what": "X", "mechanism": "WEARS", "cause": "USE"},
            ],
            "functional_failures": [],
            "functions": [],
        }
        dim = self.scorer.score_traceability(entities, {})
        assert dim.score < 100.0


# ---------------------------------------------------------------------------
# TestTaskScorer
# ---------------------------------------------------------------------------

class TestTaskScorer:
    scorer = TaskScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_tasks(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 50.0, f"{d.dimension} scored only {d.score}"

    def test_accuracy_penalty_cb_without_limits(self):
        entities = {
            "maintenance_tasks": [
                {
                    "task_id": "T1", "name": "Check something",
                    "strategy_type": "CONDITION_BASED",
                    "frequency_value": 7, "frequency_unit": "DAYS",
                },
            ],
            "failure_modes": [],
        }
        dim = self.scorer.score_technical_accuracy(entities, {})
        assert dim.score < 100.0

    def test_completeness_penalty_no_labour(self):
        entities = {
            "maintenance_tasks": [
                {"task_id": "T1", "name": "Task", "frequency_value": 7, "frequency_unit": "DAYS", "constraint": "ONLINE"},
            ],
        }
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0

    def test_traceability_penalty_bad_fm_ref(self):
        entities = {
            "maintenance_tasks": [
                {"task_id": "T1", "name": "Task", "failure_mode_id": "NONEXISTENT"},
            ],
            "failure_modes": [],
        }
        dim = self.scorer.score_traceability(entities, {})
        assert dim.score < 100.0


# ---------------------------------------------------------------------------
# TestWorkPackageScorer
# ---------------------------------------------------------------------------

class TestWorkPackageScorer:
    scorer = WorkPackageScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_work_packages(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 50.0, f"{d.dimension} scored only {d.score}"

    def test_format_penalty_lowercase_name(self):
        entities = {
            "work_packages": [
                {"work_package_id": "WP1", "name": "lowercase name", "node_id": "N1", "frequency_value": 7, "constraint": "ONLINE", "allocated_tasks": []},
            ],
            "maintenance_tasks": [],
            "hierarchy_nodes": [{"node_id": "N1", "name": "Plant", "node_type": "PLANT", "level": 1}],
        }
        dim = self.scorer.score_format(entities, {})
        assert dim.score < 100.0

    def test_completeness_penalty_unallocated_task(self):
        entities = {
            "work_packages": [
                {"work_package_id": "WP1", "name": "WP ONE", "node_id": "N1", "frequency_value": 7, "frequency_unit": "DAYS", "constraint": "ONLINE", "allocated_tasks": []},
            ],
            "maintenance_tasks": [
                {"task_id": "T1", "name": "Orphan task"},
            ],
            "hierarchy_nodes": [],
        }
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0

    def test_traceability_penalty_bad_node_ref(self):
        entities = {
            "work_packages": [
                {"work_package_id": "WP1", "name": "WP ONE", "node_id": "NONEXISTENT", "allocated_tasks": []},
            ],
            "maintenance_tasks": [],
            "hierarchy_nodes": [],
        }
        dim = self.scorer.score_traceability(entities, {})
        assert dim.score < 100.0


# ---------------------------------------------------------------------------
# TestSAPScorer
# ---------------------------------------------------------------------------

class TestSAPScorer:
    scorer = SAPScorer()

    def test_perfect_score(self):
        dims = self.scorer.score_all(_perfect_sap(), {}, DEFAULT_WEIGHTS)
        for d in dims:
            assert d.score >= 50.0, f"{d.dimension} scored only {d.score}"

    def test_accuracy_penalty_no_package(self):
        dim = self.scorer.score_technical_accuracy({}, {})
        assert dim.score == 0.0

    def test_format_penalty_long_short_text(self):
        entities = {
            "sap_upload_package": {
                "package_id": "SAP1", "plant_code": "OCP", "generated_at": "2026-01-20",
                "status": "GENERATED",
                "maintenance_plan": {"plan_id": "MP1", "description": "A" * 50},  # > 40 chars
                "maintenance_items": [],
                "task_lists": [{"task_list_id": "TL1", "operations": [
                    {"operation_number": 10, "work_centre": "ELEC", "short_text": "A" * 80},  # > 72 chars
                ]}],
            },
        }
        dim = self.scorer.score_format(entities, {})
        assert dim.score < 100.0

    def test_completeness_penalty_missing_fields(self):
        entities = {"sap_upload_package": {"status": "GENERATED"}}
        dim = self.scorer.score_completeness(entities, {})
        assert dim.score < 100.0
