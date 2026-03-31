"""Data Import Engine — Phase 6 + GAP-W12.

Parses and validates pre-parsed row data (list[dict]) for 14 import types:
- Equipment hierarchy, criticality, failure modes, tasks, work packages
- Work order history, spare parts, shutdown calendar, workforce
- Field capture, RCA events, planning KPIs, DE KPIs, maintenance strategy

Also provides file-based import via FileParserEngine integration.

Validates data structure, maps columns, and returns validated results.
Deterministic — no LLM required.
"""

from __future__ import annotations

from datetime import date as _date

from tools.models.schemas import (
    VALID_FM_COMBINATIONS,
    Cause,
    ImportMapping,
    ImportResult,
    ImportSource,
    ImportSummary,
    ImportValidationError,
    Mechanism,
)

# ── Required columns per import source ────────────────────────────

_REQUIRED_COLUMNS: dict[ImportSource, list[str]] = {
    # Original 3 types
    ImportSource.EQUIPMENT_HIERARCHY: [
        "equipment_id", "description", "equipment_type",
    ],
    ImportSource.FAILURE_HISTORY: [
        "equipment_id", "failure_date", "failure_mode",
    ],
    ImportSource.MAINTENANCE_PLAN: [
        "equipment_id", "task_description", "frequency",
    ],
    # Extended types (GAP-W12)
    ImportSource.CRITICALITY_ASSESSMENT: [
        "equipment_tag", "method",
    ],
    ImportSource.FAILURE_MODES: [
        "equipment_tag", "function_description", "mechanism", "cause",
    ],
    ImportSource.MAINTENANCE_TASKS: [
        "task_id", "task_name", "task_type", "constraint",
    ],
    ImportSource.WORK_ORDER_HISTORY: [
        "wo_id", "order_type", "equipment_tag", "status",
    ],
    ImportSource.SPARE_PARTS_INVENTORY: [
        "material_code", "description", "ved_class", "quantity_on_hand",
    ],
    ImportSource.SHUTDOWN_CALENDAR: [
        "plant_id", "shutdown_name", "shutdown_type", "planned_start",
    ],
    ImportSource.WORKFORCE: [
        "worker_id", "name", "specialty", "shift",
    ],
    ImportSource.FIELD_CAPTURE: [
        "technician_id", "capture_type", "raw_text", "timestamp",
    ],
    ImportSource.RCA_EVENTS: [
        "event_description", "plant_id", "level",
    ],
    ImportSource.PLANNING_KPI: [
        "plant_id", "period_start", "period_end", "wo_planned", "wo_completed",
    ],
    ImportSource.DE_KPI: [
        "plant_id", "period_start", "period_end", "events_reported", "events_required",
    ],
    ImportSource.MAINTENANCE_STRATEGY: [
        "strategy_id", "equipment_tag", "mechanism", "cause", "tactics_type",
    ],
    # Gap Analysis Fase 3 (GAP-AMS)
    ImportSource.ACTIVE_BACKLOG: [
        "backlog_id", "equipment_tag", "priority", "status", "estimated_duration_hours",
    ],
    ImportSource.SAP_NOTIFICATIONS: [
        "qmnum", "qmart", "equipment_tag", "reported_date", "system_status",
    ],
    ImportSource.MEASUREMENT_DOCUMENTS: [
        "measurement_point_id", "equipment_tag", "reading_date", "measured_value",
    ],
    # Gap Analysis Fase 4 (GAP-AMS)
    ImportSource.TIME_CONFIRMATIONS: [
        "confirmation_id", "aufnr", "worker_id", "actual_work_hours",
    ],
    ImportSource.MATERIAL_MOVEMENTS: [
        "material_code", "movement_type", "quantity", "movement_date",
    ],
    ImportSource.EQUIPMENT_BOM: [
        "equipment_tag", "material_code", "quantity",
    ],
    ImportSource.COST_HISTORY: [
        "aufnr", "value_category", "amount_usd",
    ],
    ImportSource.RELIABILITY_DATA: [
        "equipment_tag", "failure_date", "time_to_failure_days",
    ],
}

# ── Known column aliases for auto-mapping ─────────────────────────

_COLUMN_ALIASES: dict[str, list[str]] = {
    # Original aliases
    "equipment_id": ["equipment_id", "equip_id", "eq_id", "asset_id", "tag", "functional_location"],
    "description": ["description", "desc", "name", "equipment_name", "asset_name"],
    "equipment_type": ["equipment_type", "type", "equip_type", "asset_type", "category"],
    "failure_date": ["failure_date", "date", "event_date", "occurrence_date"],
    "failure_mode": ["failure_mode", "mode", "fm", "failure_type"],
    "task_description": ["task_description", "task", "activity"],
    "frequency": ["frequency", "interval", "cycle", "periodicity"],
    "parent_id": ["parent_id", "parent", "superior", "parent_equipment"],
    "criticality": ["criticality", "crit", "risk_class", "criticality_class"],
    "downtime_hours": ["downtime_hours", "downtime", "duration_hours", "repair_hours"],
    "cost": ["cost", "repair_cost", "total_cost", "amount"],
    # Extended aliases (GAP-W12)
    "equipment_tag": ["equipment_tag", "tag", "equip_tag", "asset_tag", "functional_location", "sap_func_loc"],
    "method": ["method", "crit_method", "assessment_method"],
    "function_description": ["function_description", "function", "function_desc"],
    "mechanism": ["mechanism", "failure_mechanism", "how_it_fails"],
    "cause": ["cause", "root_cause", "failure_cause"],
    "task_id": ["task_id", "task_code", "activity_id"],
    "task_name": ["task_name", "task_description", "activity_name"],
    "task_type": ["task_type", "activity_type"],
    "constraint": ["constraint", "task_constraint", "execution_constraint"],
    "wo_id": ["wo_id", "work_order", "wo_number", "order_number"],
    "order_type": ["order_type", "wo_type"],
    "status": ["status", "wo_status", "order_status"],
    "material_code": ["material_code", "mat_code", "sap_material", "part_code", "part_number"],
    "ved_class": ["ved_class", "ved", "ved_classification"],
    "quantity_on_hand": ["quantity_on_hand", "qty_on_hand", "stock", "quantity"],
    "shutdown_name": ["shutdown_name", "event_name", "shutdown"],
    "shutdown_type": ["shutdown_type", "event_type"],
    "planned_start": ["planned_start", "start_date", "plan_start"],
    "worker_id": ["worker_id", "tech_id", "employee_id", "technician_id"],
    "name": ["name", "worker_name", "full_name", "employee_name"],
    "specialty": ["specialty", "trade", "skill", "labour_specialty"],
    "shift": ["shift", "shift_type", "work_shift"],
    "plant_id": ["plant_id", "plant", "plant_code", "site_id"],
    "technician_id": ["technician_id", "tech_id", "worker_id"],
    "capture_type": ["capture_type", "input_type", "type"],
    "raw_text": ["raw_text", "text", "input_text", "description"],
    "timestamp": ["timestamp", "date", "datetime", "captured_at"],
    "event_description": ["event_description", "event", "rca_event"],
    "level": ["level", "rca_level", "severity_level"],
    "period_start": ["period_start", "start_date", "from_date"],
    "period_end": ["period_end", "end_date", "to_date"],
    "wo_planned": ["wo_planned", "planned_wo", "work_orders_planned"],
    "wo_completed": ["wo_completed", "completed_wo", "work_orders_completed"],
    "events_reported": ["events_reported", "reported", "de_events"],
    "events_required": ["events_required", "required", "de_target"],
    "strategy_id": ["strategy_id", "strat_id", "strategy_code"],
    "tactics_type": ["tactics_type", "strategy_type", "maintenance_type", "tactic"],
}

# ── Valid enum values for type-specific validation ────────────────

_VALID_TASK_TYPES = {"INSPECT", "CHECK", "TEST", "LUBRICATE", "CLEAN", "REPLACE", "REPAIR", "CALIBRATE"}
_VALID_CONSTRAINTS = {"ONLINE", "OFFLINE", "TEST_MODE"}
_VALID_ORDER_TYPES = {"PM01", "PM02", "PM03"}
_VALID_WO_STATUSES = {"CREATED", "RELEASED", "IN_PROGRESS", "COMPLETED", "CLOSED", "CANCELLED"}
_VALID_VED_CLASSES = {"VITAL", "ESSENTIAL", "DESIRABLE"}
_VALID_SHUTDOWN_TYPES = {"MINOR_8H", "MAJOR_20H_PLUS"}
_VALID_SPECIALTIES = {"FITTER", "ELECTRICIAN", "INSTRUMENTIST", "OPERATOR", "CONMON_SPECIALIST", "LUBRICATOR"}
_VALID_SHIFTS = {"MORNING", "AFTERNOON", "NIGHT"}
_VALID_CAPTURE_TYPES = {"VOICE", "TEXT", "IMAGE", "VOICE+IMAGE"}
_VALID_RCA_LEVELS = {"1", "2", "3"}
_VALID_CRIT_METHODS = {"FULL_MATRIX", "SIMPLIFIED"}
_VALID_STRATEGY_TYPES = {"CONDITION_BASED", "FIXED_TIME", "RUN_TO_FAILURE", "FAULT_FINDING", "REDESIGN", "OEM"}


class DataImportEngine:
    """Parses and validates imported data files."""

    # ── Generic entry point (GAP-W12) ─────────────────────────────

    @staticmethod
    def validate_data(
        rows: list[dict],
        source: ImportSource,
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Generic validation for any import type.

        This is the recommended entry point for all import types.
        """
        return DataImportEngine._validate(rows, source, column_mapping)

    @staticmethod
    def parse_and_validate(
        file_content: bytes,
        filename: str,
        source: ImportSource,
        sheet_name: str | None = None,
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Parse a file and validate in one step.

        1. Parse file → rows
        2. Auto-detect column mapping if not provided
        3. Validate rows against source requirements
        """
        from tools.engines.file_parser_engine import FileParserEngine

        parse_result = FileParserEngine.parse_file(file_content, filename, sheet_name)
        if not parse_result.success:
            return ImportResult(
                source=source,
                total_rows=0,
                valid_rows=0,
                error_rows=0,
                errors=[
                    ImportValidationError(
                        row=0, column="", message=err.message,
                    )
                    for err in parse_result.errors
                ],
            )

        if not parse_result.rows:
            return ImportResult(source=source, total_rows=0, valid_rows=0, error_rows=0)

        # Auto-detect column mapping if not provided
        if column_mapping is None and parse_result.headers:
            detected = DataImportEngine.detect_column_mapping(parse_result.headers, source)
            if detected.confidence > 0:
                column_mapping = detected.mapping

        return DataImportEngine._validate(parse_result.rows, source, column_mapping)

    # ── Legacy entry points (backward compatible) ─────────────────

    @staticmethod
    def validate_hierarchy_data(
        rows: list[dict],
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Validate equipment hierarchy data."""
        return DataImportEngine._validate(
            rows, ImportSource.EQUIPMENT_HIERARCHY, column_mapping,
        )

    @staticmethod
    def validate_failure_history(
        rows: list[dict],
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Validate failure history records."""
        return DataImportEngine._validate(
            rows, ImportSource.FAILURE_HISTORY, column_mapping,
        )

    @staticmethod
    def validate_maintenance_plan(
        rows: list[dict],
        column_mapping: dict[str, str] | None = None,
    ) -> ImportResult:
        """Validate maintenance plan data."""
        return DataImportEngine._validate(
            rows, ImportSource.MAINTENANCE_PLAN, column_mapping,
        )

    # ── Column mapping ────────────────────────────────────────────

    @staticmethod
    def detect_column_mapping(
        headers: list[str],
        target_type: ImportSource,
    ) -> ImportMapping:
        """Auto-detect column mapping from source headers to target schema."""
        required = _REQUIRED_COLUMNS.get(target_type, [])
        mapping: dict[str, str] = {}
        headers_lower = [h.lower().strip() for h in headers]

        for target_col in required:
            aliases = _COLUMN_ALIASES.get(target_col, [target_col])
            for alias in aliases:
                alias_lower = alias.lower()
                if alias_lower in headers_lower:
                    idx = headers_lower.index(alias_lower)
                    mapping[headers[idx]] = target_col
                    break

        mapped_targets = set(mapping.values())
        confidence = len(mapped_targets) / max(len(required), 1)

        return ImportMapping(
            source_columns=headers,
            target_columns=required,
            mapping=mapping,
            confidence=round(confidence, 2),
        )

    # ── Summary ───────────────────────────────────────────────────

    @staticmethod
    def summarize_import(result: ImportResult) -> ImportSummary:
        """Generate summary statistics from an import result."""
        error_summary: dict[str, int] = {}
        for err in result.errors:
            key = err.column if err.column else "general"
            error_summary[key] = error_summary.get(key, 0) + 1

        valid_pct = round(
            result.valid_rows / max(result.total_rows, 1) * 100, 1,
        )

        return ImportSummary(
            source=result.source,
            total_rows=result.total_rows,
            valid_pct=valid_pct,
            error_summary=error_summary,
        )

    # ── Core validation ───────────────────────────────────────────

    @staticmethod
    def _validate(
        rows: list[dict],
        source: ImportSource,
        column_mapping: dict[str, str] | None,
    ) -> ImportResult:
        """Core validation logic for all import types."""
        if not rows:
            return ImportResult(source=source, total_rows=0, valid_rows=0, error_rows=0)

        required = _REQUIRED_COLUMNS.get(source, [])

        # Apply column mapping if provided
        mapped_rows: list[dict] = []
        if column_mapping:
            for row in rows:
                mapped = {}
                for src_col, tgt_col in column_mapping.items():
                    if src_col in row:
                        mapped[tgt_col] = row[src_col]
                # Keep unmapped columns
                for k, v in row.items():
                    if k not in column_mapping:
                        mapped[k] = v
                mapped_rows.append(mapped)
        else:
            mapped_rows = rows

        errors: list[ImportValidationError] = []
        valid_data: list[dict] = []
        error_row_indices: set[int] = set()

        for i, row in enumerate(mapped_rows):
            row_errors = False
            for col in required:
                val = row.get(col)
                if val is None or (isinstance(val, str) and not val.strip()):
                    errors.append(ImportValidationError(
                        row=i + 1,
                        column=col,
                        message=f"Required column '{col}' is missing or empty",
                    ))
                    row_errors = True

            # Type-specific validations (only if required fields passed)
            if not row_errors:
                type_errors = _validate_type_specific(row, source, i + 1)
                if type_errors:
                    errors.extend(type_errors)
                    row_errors = True

            if row_errors:
                error_row_indices.add(i)
            else:
                valid_data.append(row)

        return ImportResult(
            source=source,
            total_rows=len(rows),
            valid_rows=len(valid_data),
            error_rows=len(error_row_indices),
            errors=errors,
            validated_data=valid_data,
        )


# ── Type-specific validation helpers ──────────────────────────────


def _validate_type_specific(
    row: dict, source: ImportSource, row_num: int,
) -> list[ImportValidationError]:
    """Run type-specific validations on a single row."""
    errors: list[ImportValidationError] = []

    if source == ImportSource.FAILURE_HISTORY:
        errors.extend(_validate_iso_date(row, "failure_date", row_num))

    elif source == ImportSource.WORK_ORDER_HISTORY:
        errors.extend(_validate_enum_field(row, "order_type", _VALID_ORDER_TYPES, row_num))
        errors.extend(_validate_enum_field(row, "status", _VALID_WO_STATUSES, row_num))
        for date_col in ("created_date", "planned_start", "planned_end", "actual_start", "actual_end"):
            if row.get(date_col):
                errors.extend(_validate_iso_date(row, date_col, row_num))

    elif source == ImportSource.CRITICALITY_ASSESSMENT:
        errors.extend(_validate_enum_field(row, "method", _VALID_CRIT_METHODS, row_num))
        # Validate consequence scores are 1-5 integers (optional columns)
        for cat in ("safety", "health", "environment", "production", "operating_cost",
                     "capital_cost", "schedule", "revenue", "communications", "compliance", "reputation"):
            val = row.get(cat)
            if val is not None:
                errors.extend(_validate_score_1_5(val, cat, row_num))

    elif source == ImportSource.FAILURE_MODES:
        errors.extend(_validate_72_combo(row, row_num))

    elif source == ImportSource.MAINTENANCE_TASKS:
        errors.extend(_validate_enum_field(row, "task_type", _VALID_TASK_TYPES, row_num))
        errors.extend(_validate_enum_field(row, "constraint", _VALID_CONSTRAINTS, row_num))

    elif source == ImportSource.SPARE_PARTS_INVENTORY:
        errors.extend(_validate_enum_field(row, "ved_class", _VALID_VED_CLASSES, row_num))
        qty = row.get("quantity_on_hand")
        if qty is not None:
            try:
                if float(qty) < 0:
                    errors.append(ImportValidationError(
                        row=row_num, column="quantity_on_hand",
                        message=f"Quantity must be >= 0, got {qty}",
                    ))
            except (ValueError, TypeError):
                errors.append(ImportValidationError(
                    row=row_num, column="quantity_on_hand",
                    message=f"Invalid numeric value: '{qty}'",
                ))

    elif source == ImportSource.SHUTDOWN_CALENDAR:
        errors.extend(_validate_enum_field(row, "shutdown_type", _VALID_SHUTDOWN_TYPES, row_num))
        errors.extend(_validate_iso_date(row, "planned_start", row_num))
        if row.get("planned_end"):
            errors.extend(_validate_iso_date(row, "planned_end", row_num))
            # Validate start < end
            start_str = str(row.get("planned_start", ""))[:10]
            end_str = str(row.get("planned_end", ""))[:10]
            try:
                start_d = _date.fromisoformat(start_str)
                end_d = _date.fromisoformat(end_str)
                if start_d > end_d:
                    errors.append(ImportValidationError(
                        row=row_num, column="planned_end",
                        message=f"planned_start ({start_str}) is after planned_end ({end_str})",
                    ))
            except (ValueError, TypeError):
                pass  # Date parse errors already caught above

    elif source == ImportSource.WORKFORCE:
        errors.extend(_validate_enum_field(row, "specialty", _VALID_SPECIALTIES, row_num))
        errors.extend(_validate_enum_field(row, "shift", _VALID_SHIFTS, row_num))

    elif source == ImportSource.FIELD_CAPTURE:
        errors.extend(_validate_enum_field(row, "capture_type", _VALID_CAPTURE_TYPES, row_num))

    elif source == ImportSource.RCA_EVENTS:
        errors.extend(_validate_enum_field(row, "level", _VALID_RCA_LEVELS, row_num))

    elif source == ImportSource.PLANNING_KPI:
        errors.extend(_validate_iso_date(row, "period_start", row_num))
        errors.extend(_validate_iso_date(row, "period_end", row_num))

    elif source == ImportSource.DE_KPI:
        errors.extend(_validate_iso_date(row, "period_start", row_num))
        errors.extend(_validate_iso_date(row, "period_end", row_num))

    elif source == ImportSource.MAINTENANCE_STRATEGY:
        errors.extend(_validate_72_combo(row, row_num))
        errors.extend(_validate_enum_field(row, "tactics_type", _VALID_STRATEGY_TYPES, row_num))

    return errors


def _validate_iso_date(
    row: dict, col: str, row_num: int,
) -> list[ImportValidationError]:
    """Validate a date field is ISO format (YYYY-MM-DD)."""
    val = row.get(col, "")
    if not val:
        return []
    val_str = str(val)
    try:
        _date.fromisoformat(val_str[:10])
        return []
    except (ValueError, TypeError):
        return [ImportValidationError(
            row=row_num, column=col,
            message=f"Invalid date format: '{val_str}' (expected YYYY-MM-DD)",
        )]


def _validate_enum_field(
    row: dict, col: str, valid_values: set[str], row_num: int,
) -> list[ImportValidationError]:
    """Validate a field against a set of allowed enum values."""
    val = row.get(col)
    if val is None:
        return []
    val_str = str(val).strip().upper()
    if val_str not in valid_values:
        return [ImportValidationError(
            row=row_num, column=col,
            message=f"Invalid value '{val}'. Allowed: {', '.join(sorted(valid_values))}",
        )]
    return []


def _validate_72_combo(
    row: dict, row_num: int,
) -> list[ImportValidationError]:
    """Validate mechanism+cause against the 72-combo table."""
    mech_val = str(row.get("mechanism", "")).strip().upper()
    cause_val = str(row.get("cause", "")).strip().upper()

    if not mech_val or not cause_val:
        return []

    # Validate mechanism is valid
    try:
        mech = Mechanism(mech_val)
    except ValueError:
        return [ImportValidationError(
            row=row_num, column="mechanism",
            message=f"Invalid mechanism: '{mech_val}'",
        )]

    # Validate cause is valid
    try:
        cause = Cause(cause_val)
    except ValueError:
        return [ImportValidationError(
            row=row_num, column="cause",
            message=f"Invalid cause: '{cause_val}'",
        )]

    # Validate combination
    if (mech, cause) not in VALID_FM_COMBINATIONS:
        return [ImportValidationError(
            row=row_num, column="mechanism",
            message=f"Invalid mechanism+cause combination: {mech_val} + {cause_val}. Must be one of 72 valid combos.",
        )]

    return []


def _validate_score_1_5(
    val: object, col: str, row_num: int,
) -> list[ImportValidationError]:
    """Validate a criticality consequence score is an integer 1-5."""
    try:
        score = int(val)  # type: ignore[arg-type]
        if score < 1 or score > 5:
            return [ImportValidationError(
                row=row_num, column=col,
                message=f"Score must be 1-5, got {score}",
            )]
        return []
    except (ValueError, TypeError):
        return [ImportValidationError(
            row=row_num, column=col,
            message=f"Invalid score value: '{val}' (expected integer 1-5)",
        )]
