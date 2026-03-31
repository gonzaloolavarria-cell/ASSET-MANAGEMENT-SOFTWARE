"""Tests for TemplatePopulationEngine."""

import json
from pathlib import Path

import pytest

from tools.engines.template_population_engine import TemplatePopulationEngine

openpyxl = pytest.importorskip("openpyxl")


# ── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def sample_nodes():
    return [
        {
            "node_id": "PLT-001", "node_type": "PLANT", "name": "JFC Plant",
            "name_fr": "Usine JFC", "code": "JFC", "level": 1,
            "parent_node_id": None, "status": "ACTIVE",
        },
        {
            "node_id": "AREA-001", "node_type": "AREA", "name": "Grinding Area",
            "name_fr": "Zone Broyage", "code": "GRD", "level": 2,
            "parent_node_id": "PLT-001",
        },
        {
            "node_id": "SYS-001", "node_type": "SYSTEM", "name": "SAG Mill System",
            "name_fr": "Systeme Broyeur SAG", "code": "SAG-SYS", "level": 3,
            "parent_node_id": "AREA-001",
        },
        {
            "node_id": "EQP-001", "node_type": "EQUIPMENT", "name": "SAG Mill 001",
            "name_fr": "Broyeur SAG 001", "code": "SAG-001", "level": 4,
            "parent_node_id": "SYS-001", "tag": "SAG-001",
        },
        {
            "node_id": "MI-001", "node_type": "MAINTAINABLE_ITEM",
            "name": "Mill Shell & Liners", "name_fr": "Virole et Blindages",
            "code": "MI-SHL", "level": 6, "parent_node_id": "EQP-001",
        },
    ]


@pytest.fixture
def sample_assessments():
    return [
        {
            "assessment_id": "CA-001", "node_id": "MI-001",
            "risk_class": "A", "method": "FULL_MATRIX",
            "assessed_at": "2026-01-01T00:00:00", "assessed_by": "reliability_agent",
            "safety": 4, "production": 5, "environment": 3, "probability": 3,
        },
    ]


@pytest.fixture
def sample_functions():
    return [
        {
            "function_id": "F-001", "node_id": "MI-001",
            "function_type": "PRIMARY",
            "description": "Grind ore from 150mm to P80 2mm at 2000 tph",
            "description_fr": "Broyer le minerai de 150mm a P80 2mm a 2000 tph",
        },
    ]


@pytest.fixture
def sample_failures():
    return [
        {
            "failure_id": "FF-001", "function_id": "F-001",
            "failure_type": "TOTAL",
            "description": "Unable to grind ore",
            "description_fr": "Incapable de broyer le minerai",
        },
    ]


@pytest.fixture
def sample_failure_modes():
    return [
        {
            "fm_id": "FM-001", "function_id": "F-001",
            "failure_id": "FF-001", "node_id": "MI-001",
            "what_component": "Liner Plate",
            "mechanism": "BREAKS_FRACTURE_SEPARATES",
            "cause": "FATIGUE",
            "failure_pattern": "C_FATIGUE",
            "failure_consequence": "EVIDENT_OPERATIONAL",
            "rpn_severity": 8, "rpn_occurrence": 5, "rpn_detection": 3,
            "rcm_decision": {
                "strategy_type": "FIXED_TIME",
                "task_id": "T-001",
                "interval": 180,
            },
        },
    ]


@pytest.fixture
def sample_tasks():
    return [
        {
            "task_id": "T-001", "task_type": "REPLACE",
            "description": "Replace mill liner plates",
            "description_fr": "Remplacer les plaques de blindage",
            "constraint": "OFFLINE", "estimated_hours": 48.0,
            "frequency_days": 180, "material_required": True,
        },
        {
            "task_id": "T-002", "task_type": "INSPECT",
            "description": "Inspect liner wear thickness",
            "constraint": "ONLINE", "estimated_hours": 2.0,
            "frequency_days": 30,
        },
    ]


@pytest.fixture
def sample_work_packages():
    return [
        {
            "wp_id": "WP-001", "name": "SAG Mill Liner Replacement",
            "task_ids": ["T-001"], "equipment_tag": "SAG-001",
            "constraint": "OFFLINE", "estimated_hours": 48.0,
            "frequency_value": 180, "frequency_unit": "DAYS",
        },
    ]


@pytest.fixture
def sample_materials():
    return [
        {
            "task_id": "T-001", "material_number": "MAT-LNR-001",
            "description": "SAG Mill Liner Plate (Mn Steel)",
            "quantity": 24, "unit": "EA",
            "manufacturer": "ME Elecmetal",
        },
    ]


# ── T-01 Tests ────────────────────────────────────────────────────

class TestPopulate01Hierarchy:
    def test_creates_xlsx(self, tmp_path, sample_nodes):
        out = tmp_path / "01.xlsx"
        result = TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        assert result.exists()
        wb = openpyxl.load_workbook(result)
        # Sheet 1: Equipment Hierarchy (L4+ only) — standard 18-column structure
        ws = wb["Equipment Hierarchy"]
        assert ws.cell(1, 1).value == "plant_id"
        assert ws.cell(1, 7).value == "equipment_tag"
        assert ws.cell(1, 18).value == "installation_date"
        # 2 equipment rows: EQP-001 (L4) + MI-001 (L6)
        assert ws.max_row == 3
        # Sheet 2: Equipment BOM
        ws_bom = wb["Equipment BOM"]
        assert ws_bom.cell(1, 1).value == "equipment_tag"
        assert ws_bom.max_row == 3  # header + 2 BOM rows (L4+)

    def test_resolves_ancestors(self, tmp_path, sample_nodes):
        out = tmp_path / "01.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        # Row 2 is EQP-001 (L4), Row 3 is MI-001 (L6)
        # plant_id in col 1, area_code in col 3
        row3 = [ws.cell(3, c).value for c in range(1, 19)]
        assert row3[0] == "JFC"        # plant_id (col 1)
        assert row3[2] == "GRD"       # area_code (col 3) from ancestor

    def test_empty_nodes(self, tmp_path):
        out = tmp_path / "01.xlsx"
        result = TemplatePopulationEngine.populate_01_hierarchy([], out)
        wb = openpyxl.load_workbook(result)
        ws = wb["Equipment Hierarchy"]
        assert ws.max_row == 1  # header only

    def test_string_levels(self, tmp_path):
        """Nodes with string levels like 'L4_EQUIPMENT' are coerced correctly."""
        nodes = [
            {"node_id": "P1", "level": "L1_SITE", "name": "Plant", "parent_node_id": None},
            {"node_id": "E1", "level": "L4_EQUIPMENT", "name": "Pump", "parent_node_id": "P1",
             "tag": "PMP-001", "equipment_type": "PUMP"},
        ]
        out = tmp_path / "01_str.xlsx"
        result = TemplatePopulationEngine.populate_01_hierarchy(nodes, out)
        wb = openpyxl.load_workbook(result)
        ws = wb["Equipment Hierarchy"]
        assert ws.max_row == 2  # header + 1 equipment row
        assert ws.cell(2, 7).value == "PMP-001"  # equipment_tag (col 7)


# ── T-02 Tests ────────────────────────────────────────────────────

class TestPopulate02Criticality:
    def test_creates_xlsx(self, tmp_path, sample_assessments, sample_nodes):
        out = tmp_path / "02.xlsx"
        result = TemplatePopulationEngine.populate_02_criticality(
            sample_assessments, sample_nodes, out,
        )
        assert result.exists()
        wb = openpyxl.load_workbook(result)
        ws = wb["Criticality Assessment"]
        assert ws.cell(1, 1).value == "equipment_tag"
        assert ws.max_row == 2

    def test_consequence_scores_flat(self, tmp_path, sample_assessments, sample_nodes):
        """Flat keys (safety=4, production=5) are picked up correctly."""
        out = tmp_path / "02.xlsx"
        TemplatePopulationEngine.populate_02_criticality(
            sample_assessments, sample_nodes, out,
        )
        wb = openpyxl.load_workbook(out)
        ws = wb["Criticality Assessment"]
        # safety is col 3 (index 1-based)
        assert ws.cell(2, 3).value == 4

    def test_consequence_scores_nested(self, tmp_path, sample_nodes):
        """Nested criteria_scores list (agent format) is extracted correctly."""
        assessments = [{
            "assessment_id": "CA-N1", "node_id": "MI-001",
            "method": "FULL_MATRIX", "probability": 3,
            "criteria_scores": [
                {"category": "SAFETY", "consequence_level": 5},
                {"category": "HEALTH", "consequence_level": 2},
                {"category": "ENVIRONMENT", "consequence_level": 3},
                {"category": "PRODUCTION", "consequence_level": 4},
                {"category": "OPERATING_COST", "score": 3},
                {"category": "CAPITAL_COST", "score": 2},
                {"category": "SCHEDULE", "consequence_level": 4},
                {"category": "REVENUE", "consequence_level": 5},
                {"category": "COMMUNICATIONS", "consequence_level": 1},
                {"category": "COMPLIANCE", "consequence_level": 3},
                {"category": "REPUTATION", "consequence_level": 2},
            ],
        }]
        out = tmp_path / "02_nested.xlsx"
        TemplatePopulationEngine.populate_02_criticality(assessments, sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Criticality Assessment"]
        assert ws.cell(2, 3).value == 5   # safety
        assert ws.cell(2, 4).value == 2   # health
        assert ws.cell(2, 7).value == 3   # operating_cost (via "score" key)
        assert ws.cell(2, 14).value == 3  # probability


# ── T-03 Tests ────────────────────────────────────────────────────

class TestPopulate03FailureModes:
    def test_creates_xlsx(self, tmp_path, sample_failure_modes, sample_functions,
                          sample_failures, sample_nodes):
        out = tmp_path / "03.xlsx"
        result = TemplatePopulationEngine.populate_03_failure_modes(
            sample_failure_modes, sample_functions, sample_failures,
            sample_nodes, out,
        )
        assert result.exists()
        wb = openpyxl.load_workbook(result)
        ws = wb["Failure Modes"]
        assert ws.max_row == 2
        assert ws.cell(2, 6).value == "BREAKS_FRACTURE_SEPARATES"  # mechanism


# ── T-04 Tests ────────────────────────────────────────────────────

class TestPopulate04Tasks:
    def test_creates_4_sheets(self, tmp_path, sample_tasks, sample_materials):
        out = tmp_path / "04.xlsx"
        result = TemplatePopulationEngine.populate_04_tasks(
            sample_tasks, sample_materials, out,
        )
        wb = openpyxl.load_workbook(result)
        # 4 data sheets + Instructions
        assert "Tasks" in wb.sheetnames
        assert "Task_Labour" in wb.sheetnames
        assert "Task_Materials" in wb.sheetnames
        assert "Task_Tools" in wb.sheetnames

    def test_tasks_sheet_rows(self, tmp_path, sample_tasks, sample_materials):
        out = tmp_path / "04.xlsx"
        TemplatePopulationEngine.populate_04_tasks(sample_tasks, sample_materials, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Tasks"]
        assert ws.max_row == 1 + len(sample_tasks)
        assert ws.cell(2, 1).value == "T-001"
        assert ws.cell(2, 4).value == "REPLACE"

    def test_materials_sheet(self, tmp_path, sample_tasks, sample_materials):
        out = tmp_path / "04.xlsx"
        TemplatePopulationEngine.populate_04_tasks(sample_tasks, sample_materials, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Task_Materials"]
        assert ws.max_row == 2
        assert ws.cell(2, 3).value == "MAT-LNR-001"


# ── T-05 Tests ────────────────────────────────────────────────────

class TestPopulate05WorkPackages:
    def test_creates_xlsx(self, tmp_path, sample_work_packages, sample_nodes):
        out = tmp_path / "05.xlsx"
        result = TemplatePopulationEngine.populate_05_work_packages(
            sample_work_packages, sample_nodes, out,
        )
        assert result.exists()
        wb = openpyxl.load_workbook(result)
        ws = wb["Work Packages"]
        assert ws.cell(2, 1).value == "SAG Mill Liner Replacement"
        assert ws.cell(2, 9).value == "T-001"  # task_ids_csv


# ── T-07 Tests ────────────────────────────────────────────────────

class TestPopulate07SpareParts:
    def test_creates_xlsx(self, tmp_path, sample_materials):
        out = tmp_path / "07.xlsx"
        result = TemplatePopulationEngine.populate_07_spare_parts(sample_materials, out)
        wb = openpyxl.load_workbook(result)
        ws = wb["Spare Parts Inventory"]
        assert ws.cell(2, 1).value == "MAT-LNR-001"
        assert ws.cell(2, 2).value == "SAG Mill Liner Plate (Mn Steel)"

    def test_deduplicates(self, tmp_path, sample_materials):
        duped = sample_materials + sample_materials
        out = tmp_path / "07.xlsx"
        TemplatePopulationEngine.populate_07_spare_parts(duped, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Spare Parts Inventory"]
        assert ws.max_row == 2  # header + 1 deduped row


# ── T-14 Tests ────────────────────────────────────────────────────

class TestPopulate14Strategy:
    def test_creates_xlsx(self, tmp_path, sample_failure_modes, sample_tasks,
                          sample_functions, sample_nodes):
        out = tmp_path / "14.xlsx"
        result = TemplatePopulationEngine.populate_14_strategy(
            sample_failure_modes, sample_tasks, sample_functions,
            sample_nodes, out,
        )
        assert result.exists()
        wb = openpyxl.load_workbook(result)
        ws = wb["Strategies"]
        assert ws.cell(2, 6).value == "BREAKS_FRACTURE_SEPARATES"  # mechanism
        assert ws.cell(2, 9).value == "FIXED_TIME"  # tactics_type
        assert ws.cell(2, 10).value == "T-001"  # primary_task_id


# ── populate_all Tests ────────────────────────────────────────────

class TestPopulateAll:
    def test_generates_all_applicable(self, tmp_path, sample_nodes,
                                       sample_assessments, sample_functions,
                                       sample_failures, sample_failure_modes,
                                       sample_tasks, sample_work_packages,
                                       sample_materials):
        entities = {
            "hierarchy_nodes": sample_nodes,
            "criticality_assessments": sample_assessments,
            "functions": sample_functions,
            "functional_failures": sample_failures,
            "failure_modes": sample_failure_modes,
            "maintenance_tasks": sample_tasks,
            "work_packages": sample_work_packages,
            "material_assignments": sample_materials,
        }
        results = TemplatePopulationEngine.populate_all(
            session_entities=entities,
            output_dir=tmp_path / "deliverables",
        )
        assert len(results) == 7
        for name, path in results.items():
            assert path.exists(), f"{name} not found at {path}"

    def test_empty_entities_generates_nothing(self, tmp_path):
        results = TemplatePopulationEngine.populate_all(
            session_entities={},
            output_dir=tmp_path / "empty",
        )
        assert len(results) == 0

    def test_partial_entities(self, tmp_path, sample_nodes, sample_assessments):
        entities = {
            "hierarchy_nodes": sample_nodes,
            "criticality_assessments": sample_assessments,
        }
        results = TemplatePopulationEngine.populate_all(
            session_entities=entities,
            output_dir=tmp_path / "partial",
        )
        assert "01_equipment_hierarchy.xlsx" in results
        assert "02_criticality_assessment.xlsx" in results
        assert "04_maintenance_tasks.xlsx" not in results


# ── Styling Tests ─────────────────────────────────────────────────

class TestStyling:
    def test_header_green_fill(self, tmp_path, sample_nodes):
        out = tmp_path / "styled.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        fill = ws.cell(1, 1).fill
        assert fill.start_color.rgb == "001B5E20" or fill.start_color.rgb == "1B5E20"

    def test_frozen_panes(self, tmp_path, sample_nodes):
        out = tmp_path / "frozen.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        assert ws.freeze_panes == "A2"

    def test_data_cell_styling(self, tmp_path, sample_nodes):
        """Data cells have Calibri 10 font, thin borders, wrap alignment."""
        out = tmp_path / "data_styled.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        cell = ws.cell(2, 1)  # First data cell
        assert cell.font.name == "Calibri"
        assert cell.font.size == 10
        assert cell.border.left.style == "thin"
        assert cell.border.right.style == "thin"
        assert cell.alignment.wrap_text is True


# ── metadata_json fallback tests ─────────────────────────────────

class TestMetadataJsonFallback:
    """Nodes using metadata_json (from build_from_vendor) should populate columns."""

    def test_metadata_json_fallback(self, tmp_path):
        """manufacturer/model/power_kw from metadata_json are written to xlsx."""
        nodes = [
            {"node_id": "P1", "level": 1, "name": "Plant", "parent_node_id": None},
            {
                "node_id": "E1", "level": 4, "name": "SAG Mill",
                "parent_node_id": "P1", "tag": "SAG-001", "node_type": "EQUIPMENT",
                "metadata_json": {
                    "manufacturer": "Metso",
                    "model": "SAG-36x20",
                    "power_kw": 8000,
                    "serial_number": "SN-12345",
                    "weight_kg": 250000,
                },
            },
        ]
        out = tmp_path / "01_meta.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        # Row 2 is the L4 equipment node (standard 18-col layout)
        assert ws.cell(2, 10).value == "Metso"       # manufacturer (col 10)
        assert ws.cell(2, 11).value == "SAG-36x20"   # model (col 11)
        assert ws.cell(2, 13).value == 8000           # power_kw (col 13)
        assert ws.cell(2, 12).value == "SN-12345"    # serial_number (col 12)
        assert ws.cell(2, 14).value == 250000         # weight_kg (col 14)

    def test_equipment_type_from_metadata(self, tmp_path):
        """equipment_type stored inside metadata_json appears in output."""
        nodes = [
            {"node_id": "P1", "level": 1, "name": "Plant", "parent_node_id": None},
            {
                "node_id": "E1", "level": 4, "name": "SAG Mill",
                "parent_node_id": "P1", "tag": "SAG-001", "node_type": "EQUIPMENT",
                "metadata_json": {
                    "equipment_type": "SAG_MILL",
                    "manufacturer": "Metso",
                },
            },
        ]
        out = tmp_path / "01_eqtype.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        # equipment_type is col 9 — should be "SAG_MILL" not "EQUIPMENT"
        assert ws.cell(2, 9).value == "SAG_MILL"

    def test_bom_manufacturer_from_metadata_json(self, tmp_path):
        """BOM sheet also uses metadata_json fallback for manufacturer."""
        nodes = [
            {"node_id": "P1", "level": 1, "name": "Plant", "parent_node_id": None},
            {
                "node_id": "E1", "level": 4, "name": "SAG Mill",
                "parent_node_id": "P1", "tag": "SAG-001", "node_type": "EQUIPMENT",
                "metadata_json": {"manufacturer": "FLSmidth"},
            },
        ]
        out = tmp_path / "01_bom_meta.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(nodes, out)
        wb = openpyxl.load_workbook(out)
        ws_bom = wb["Equipment BOM"]
        # manufacturer is col 10 in BOM
        assert ws_bom.cell(2, 10).value == "FLSmidth"


# ── Data Validation Tests ────────────────────────────────────────

class TestDataValidations:
    """Verify dropdown data validations exist on enum columns."""

    def _get_validated_cols(self, ws) -> set[str]:
        """Return set of column letters that have data validations."""
        cols = set()
        for dv in ws.data_validations.dataValidation:
            for cell_range in dv.sqref.ranges:
                cols.add(cell_range.bounds[0])  # min_col
        return cols

    def test_t01_validations(self, tmp_path, sample_nodes):
        out = tmp_path / "01_val.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Equipment Hierarchy"]
        validated = self._get_validated_cols(ws)
        assert 15 in validated  # criticality
        assert 16 in validated  # status

    def test_t02_validations(self, tmp_path, sample_assessments, sample_nodes):
        out = tmp_path / "02_val.xlsx"
        TemplatePopulationEngine.populate_02_criticality(
            sample_assessments, sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Criticality Assessment"]
        validated = self._get_validated_cols(ws)
        assert 2 in validated   # method
        assert 3 in validated   # safety (1-5)
        assert 13 in validated  # reputation (1-5)

    def test_t03_validations(self, tmp_path, sample_failure_modes, sample_functions,
                             sample_failures, sample_nodes):
        out = tmp_path / "03_val.xlsx"
        TemplatePopulationEngine.populate_03_failure_modes(
            sample_failure_modes, sample_functions, sample_failures,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Failure Modes"]
        validated = self._get_validated_cols(ws)
        assert 3 in validated  # function_type
        assert 6 in validated  # mechanism
        assert 7 in validated  # cause
        assert 8 in validated  # failure_pattern
        assert 9 in validated  # failure_consequence

    def test_t04_validations(self, tmp_path, sample_tasks, sample_materials):
        out = tmp_path / "04_val.xlsx"
        TemplatePopulationEngine.populate_04_tasks(sample_tasks, sample_materials, out)
        wb = openpyxl.load_workbook(out)
        ws_tasks = wb["Tasks"]
        validated = self._get_validated_cols(ws_tasks)
        assert 4 in validated  # task_type
        assert 5 in validated  # constraint

        ws_labour = wb["Task_Labour"]
        labour_validated = self._get_validated_cols(ws_labour)
        assert 4 in labour_validated  # specialty

        ws_mat = wb["Task_Materials"]
        mat_validated = self._get_validated_cols(ws_mat)
        assert 8 in mat_validated  # unit_of_measure

    def test_t05_validations(self, tmp_path, sample_work_packages, sample_nodes):
        out = tmp_path / "05_val.xlsx"
        TemplatePopulationEngine.populate_05_work_packages(
            sample_work_packages, sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Work Packages"]
        validated = self._get_validated_cols(ws)
        assert 5 in validated  # frequency_unit
        assert 6 in validated  # constraint
        assert 7 in validated  # wp_type

    def test_t07_validations(self, tmp_path, sample_materials):
        out = tmp_path / "07_val.xlsx"
        TemplatePopulationEngine.populate_07_spare_parts(sample_materials, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Spare Parts Inventory"]
        validated = self._get_validated_cols(ws)
        assert 5 in validated   # ved_class
        assert 6 in validated   # fsn_class
        assert 7 in validated   # abc_class
        assert 14 in validated  # unit_of_measure

    def test_t14_validations(self, tmp_path, sample_failure_modes, sample_tasks,
                             sample_functions, sample_nodes):
        out = tmp_path / "14_val.xlsx"
        TemplatePopulationEngine.populate_14_strategy(
            sample_failure_modes, sample_tasks, sample_functions,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        ws = wb["Strategies"]
        validated = self._get_validated_cols(ws)
        assert 6 in validated   # mechanism
        assert 7 in validated   # cause
        assert 8 in validated   # status
        assert 9 in validated   # tactics_type
        assert 29 in validated  # justification_category


# ── Instructions Sheet Tests ─────────────────────────────────────

class TestInstructionsSheets:
    """Verify all templates have an Instructions sheet."""

    def test_t01_has_instructions(self, tmp_path, sample_nodes):
        out = tmp_path / "01_instr.xlsx"
        TemplatePopulationEngine.populate_01_hierarchy(sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames
        ws = wb["Instructions"]
        assert ws.cell(1, 1).value == "Field Name"
        assert ws.cell(1, 5).value == "Description"

    def test_t02_has_instructions(self, tmp_path, sample_assessments, sample_nodes):
        out = tmp_path / "02_instr.xlsx"
        TemplatePopulationEngine.populate_02_criticality(
            sample_assessments, sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames

    def test_t03_has_instructions(self, tmp_path, sample_failure_modes, sample_functions,
                                  sample_failures, sample_nodes):
        out = tmp_path / "03_instr.xlsx"
        TemplatePopulationEngine.populate_03_failure_modes(
            sample_failure_modes, sample_functions, sample_failures,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames

    def test_t04_has_instructions(self, tmp_path, sample_tasks, sample_materials):
        out = tmp_path / "04_instr.xlsx"
        TemplatePopulationEngine.populate_04_tasks(sample_tasks, sample_materials, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames

    def test_t05_has_instructions(self, tmp_path, sample_work_packages, sample_nodes):
        out = tmp_path / "05_instr.xlsx"
        TemplatePopulationEngine.populate_05_work_packages(
            sample_work_packages, sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames

    def test_t07_has_instructions(self, tmp_path, sample_materials):
        out = tmp_path / "07_instr.xlsx"
        TemplatePopulationEngine.populate_07_spare_parts(sample_materials, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames

    def test_t14_has_instructions(self, tmp_path, sample_failure_modes, sample_tasks,
                                  sample_functions, sample_nodes):
        out = tmp_path / "14_instr.xlsx"
        TemplatePopulationEngine.populate_14_strategy(
            sample_failure_modes, sample_tasks, sample_functions,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Instructions" in wb.sheetnames


# ── Reference Sheet Tests ────────────────────────────────────────

class TestReferenceSheets:
    """Verify T-03 and T-14 have FM Combos sheet, T-14 has Strategy Rules."""

    def test_t03_has_fm_combos(self, tmp_path, sample_failure_modes, sample_functions,
                               sample_failures, sample_nodes):
        out = tmp_path / "03_ref.xlsx"
        TemplatePopulationEngine.populate_03_failure_modes(
            sample_failure_modes, sample_functions, sample_failures,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Valid FM Combinations" in wb.sheetnames
        ws = wb["Valid FM Combinations"]
        assert ws.cell(1, 1).value == "Mechanism"
        assert ws.cell(1, 2).value == "Cause"
        assert ws.max_row > 50  # 72 combos + header

    def test_t14_has_fm_combos(self, tmp_path, sample_failure_modes, sample_tasks,
                               sample_functions, sample_nodes):
        out = tmp_path / "14_ref.xlsx"
        TemplatePopulationEngine.populate_14_strategy(
            sample_failure_modes, sample_tasks, sample_functions,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Valid FM Combinations" in wb.sheetnames

    def test_t14_has_strategy_rules(self, tmp_path, sample_failure_modes, sample_tasks,
                                    sample_functions, sample_nodes):
        out = tmp_path / "14_ref.xlsx"
        TemplatePopulationEngine.populate_14_strategy(
            sample_failure_modes, sample_tasks, sample_functions,
            sample_nodes, out)
        wb = openpyxl.load_workbook(out)
        assert "Strategy Type Rules" in wb.sheetnames
        ws = wb["Strategy Type Rules"]
        assert ws.cell(1, 1).value == "Tactics Type"
        assert ws.cell(2, 1).value == "CONDITION_BASED"
