"""Reporting service — reports, DE KPIs, notifications, import/export, cross-module analytics."""

from datetime import datetime

from sqlalchemy.orm import Session

from api.database.models import ReportModel, NotificationModel, ImportHistoryModel
from api.services.audit_service import log_action
from tools.engines.reporting_engine import ReportingEngine
from tools.engines.de_kpi_engine import DEKPIEngine
from tools.engines.notification_engine import NotificationEngine
from tools.engines.data_import_engine import DataImportEngine
from tools.engines.data_export_engine import DataExportEngine
from tools.engines.cross_module_engine import CrossModuleEngine
from tools.engines.file_parser_engine import FileParserEngine
from tools.models.schemas import DEKPIInput, ImportSource, ExportFormat, ImportHistoryEntry, ImportValidationError


# ── Reports ─────────────────────────────────────────────────────────

def generate_weekly_report(db: Session, plant_id: str, week: int, year: int, data: dict) -> dict:
    result = ReportingEngine.generate_weekly_report(
        plant_id, week, year,
        work_orders_completed=data.get("work_orders_completed"),
        work_orders_open=data.get("work_orders_open"),
        safety_incidents=data.get("safety_incidents", 0),
        schedule_compliance_pct=data.get("schedule_compliance_pct"),
        backlog_hours=data.get("backlog_hours", 0.0),
        key_events=data.get("key_events"),
    )
    report_dict = result.model_dump(mode="json")
    obj = ReportModel(
        report_id=result.metadata.report_id,
        report_type="WEEKLY_MAINTENANCE",
        plant_id=plant_id,
        period_start=result.metadata.period_start,
        period_end=result.metadata.period_end,
        content=report_dict,
    )
    db.add(obj)
    log_action(db, "report", obj.report_id, "GENERATE_WEEKLY")
    db.commit()
    return report_dict


def generate_monthly_report(db: Session, plant_id: str, month: int, year: int, data: dict) -> dict:
    result = ReportingEngine.generate_monthly_kpi_report(
        plant_id, month, year,
        planning_kpis=data.get("planning_kpis"),
        de_kpis=data.get("de_kpis"),
        reliability_kpis=data.get("reliability_kpis"),
        health_summary=data.get("health_summary"),
        previous_month_kpis=data.get("previous_month_kpis"),
    )
    report_dict = result.model_dump(mode="json")
    obj = ReportModel(
        report_id=result.metadata.report_id,
        report_type="MONTHLY_KPI",
        plant_id=plant_id,
        period_start=result.metadata.period_start,
        period_end=result.metadata.period_end,
        content=report_dict,
    )
    db.add(obj)
    log_action(db, "report", obj.report_id, "GENERATE_MONTHLY")
    db.commit()
    return report_dict


def generate_quarterly_report(db: Session, plant_id: str, quarter: int, year: int, data: dict) -> dict:
    result = ReportingEngine.generate_quarterly_review(
        plant_id, quarter, year,
        monthly_reports=data.get("monthly_reports"),
        management_review=data.get("management_review"),
        rbi_summary=data.get("rbi_summary"),
        bad_actors=data.get("bad_actors"),
        capas_summary=data.get("capas_summary"),
    )
    report_dict = result.model_dump(mode="json")
    obj = ReportModel(
        report_id=result.metadata.report_id,
        report_type="QUARTERLY_REVIEW",
        plant_id=plant_id,
        period_start=result.metadata.period_start,
        period_end=result.metadata.period_end,
        content=report_dict,
    )
    db.add(obj)
    log_action(db, "report", obj.report_id, "GENERATE_QUARTERLY")
    db.commit()
    return report_dict


def list_reports(db: Session, plant_id: str | None = None, report_type: str | None = None) -> list[dict]:
    q = db.query(ReportModel)
    if plant_id:
        q = q.filter_by(plant_id=plant_id)
    if report_type:
        q = q.filter_by(report_type=report_type)
    return [
        {
            "report_id": r.report_id, "report_type": r.report_type,
            "plant_id": r.plant_id,
            "period_start": r.period_start.isoformat() if r.period_start else None,
            "period_end": r.period_end.isoformat() if r.period_end else None,
            "generated_at": r.generated_at.isoformat() if r.generated_at else None,
        }
        for r in q.order_by(ReportModel.generated_at.desc()).all()
    ]


def get_report(db: Session, report_id: str) -> dict | None:
    obj = db.query(ReportModel).filter_by(report_id=report_id).first()
    if not obj:
        return None
    return obj.content or {}


# ── DE KPIs ─────────────────────────────────────────────────────────

def calculate_de_kpis(db: Session, data: dict) -> dict:
    inp = DEKPIInput(**data)
    result = DEKPIEngine.calculate(inp)
    return result.model_dump(mode="json")


def assess_de_program_health(db: Session, data: dict) -> dict:
    inp = DEKPIInput(**data)
    de_kpis = DEKPIEngine.calculate(inp)
    health = DEKPIEngine.assess_program_health(inp.plant_id, de_kpis)
    return health.model_dump(mode="json")


# ── Notifications ───────────────────────────────────────────────────

def generate_notifications(db: Session, plant_id: str, data: dict) -> dict:
    result = NotificationEngine.generate_all_notifications(
        plant_id,
        rbi_assessments=data.get("rbi_assessments"),
        planning_kpis=data.get("planning_kpis"),
        de_kpis=data.get("de_kpis"),
        reliability_kpis=data.get("reliability_kpis"),
        health_scores=data.get("health_scores"),
        backlog_items=data.get("backlog_items"),
        capas=data.get("capas"),
        mocs=data.get("mocs"),
    )
    for alert in result.notifications:
        obj = NotificationModel(
            notification_id=alert.notification_id,
            notification_type=alert.notification_type.value,
            level=alert.level.value,
            plant_id=alert.plant_id or plant_id,
            equipment_id=alert.equipment_id,
            title=alert.title,
            message=alert.message,
        )
        db.add(obj)
    if result.notifications:
        db.commit()
    return result.model_dump(mode="json")


def list_notifications(
    db: Session, plant_id: str | None = None,
    level: str | None = None, acknowledged: bool | None = None,
) -> list[dict]:
    q = db.query(NotificationModel)
    if plant_id:
        q = q.filter_by(plant_id=plant_id)
    if level:
        q = q.filter_by(level=level)
    if acknowledged is not None:
        q = q.filter_by(acknowledged=acknowledged)
    return [
        {
            "notification_id": n.notification_id, "notification_type": n.notification_type,
            "level": n.level, "title": n.title, "message": n.message,
            "equipment_id": n.equipment_id, "plant_id": n.plant_id,
            "acknowledged": n.acknowledged,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in q.order_by(NotificationModel.created_at.desc()).all()
    ]


def acknowledge_notification(db: Session, notification_id: str) -> dict | None:
    obj = db.query(NotificationModel).filter_by(notification_id=notification_id).first()
    if not obj:
        return None
    obj.acknowledged = True
    obj.acknowledged_at = datetime.now()
    db.commit()
    return {"notification_id": notification_id, "acknowledged": True}


# ── Import ──────────────────────────────────────────────────────────

def validate_import(db: Session, source: str, rows: list[dict]) -> dict:
    src = ImportSource(source)
    result = DataImportEngine.validate_data(rows, src)
    return result.model_dump(mode="json")


MAX_IMPORT_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
ALLOWED_EXTENSIONS = {".csv", ".xlsx"}

# Template number → ImportSource mapping
_TEMPLATE_NUM_TO_SOURCE: dict[int, str] = {
    1: "EQUIPMENT_HIERARCHY", 2: "CRITICALITY_ASSESSMENT",
    3: "FAILURE_MODES", 4: "MAINTENANCE_TASKS",
    5: "MAINTENANCE_PLAN", 6: "WORK_ORDER_HISTORY",
    7: "SPARE_PARTS_INVENTORY", 8: "SHUTDOWN_CALENDAR",
    9: "WORKFORCE", 10: "FIELD_CAPTURE",
    11: "RCA_EVENTS", 12: "PLANNING_KPI",
    13: "DE_KPI", 14: "MAINTENANCE_STRATEGY",
}


def upload_and_validate(
    db: Session,
    content: bytes,
    filename: str,
    source: str,
    sheet_name: str | None = None,
    column_mapping: dict[str, str] | None = None,
    plant_id: str = "",
) -> dict:
    """Parse an uploaded file and validate its contents."""
    import os

    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise ValueError(f"Unsupported file extension: {ext}")
    if len(content) > MAX_IMPORT_FILE_SIZE:
        raise ValueError(
            f"File too large: {len(content)} bytes (max {MAX_IMPORT_FILE_SIZE})"
        )

    src = ImportSource(source)
    result = DataImportEngine.parse_and_validate(
        content, filename, src, sheet_name, column_mapping,
    )
    log_action(db, "import", filename, f"UPLOAD_VALIDATE_{source}")
    history = record_import_history(db, plant_id, src, filename, result, file_size_kb=len(content) // 1024)
    db.commit()
    # Merge validation result with history metadata so callers get import_id + status
    data = result.model_dump(mode="json")
    data["import_id"] = history.import_id
    data["status"] = history.status
    return data


# ── Import History ───────────────────────────────────────────────────

def _import_status(total: int, errors: int) -> str:
    if errors == 0:
        return "success"
    if errors >= total:
        return "failed"
    return "partial"


def record_import_history(
    db: Session,
    plant_id: str,
    source: ImportSource,
    filename: str,
    import_result,
    file_size_kb: int | None = None,
    imported_by: str | None = None,
) -> ImportHistoryEntry:
    """Persist an import operation to the history table."""
    import uuid as _uuid
    import json as _json

    import_id = str(_uuid.uuid4())
    imported_at = datetime.now()
    status = _import_status(import_result.total_rows, import_result.error_rows)
    errors_data = [e.model_dump() for e in import_result.errors]

    obj = ImportHistoryModel(
        import_id=import_id,
        plant_id=plant_id,
        source=source.value,
        filename=filename,
        file_size_kb=file_size_kb,
        total_rows=import_result.total_rows,
        valid_rows=import_result.valid_rows,
        error_rows=import_result.error_rows,
        status=status,
        errors_json=_json.dumps(errors_data) if errors_data else None,
        imported_by=imported_by,
        imported_at=imported_at,
    )
    db.add(obj)
    # Caller is responsible for db.commit()
    return ImportHistoryEntry(
        import_id=import_id,
        plant_id=plant_id,
        source=source,
        filename=filename,
        file_size_kb=file_size_kb,
        total_rows=import_result.total_rows,
        valid_rows=import_result.valid_rows,
        error_rows=import_result.error_rows,
        status=status,
        errors=[ImportValidationError(**e) for e in errors_data],
        imported_by=imported_by,
        imported_at=imported_at,
    )


def list_import_history(
    db: Session,
    plant_id: str | None = None,
    source: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """List import history entries, newest first."""
    import json as _json

    q = db.query(ImportHistoryModel)
    if plant_id:
        q = q.filter_by(plant_id=plant_id)
    if source:
        q = q.filter_by(source=source)
    rows = q.order_by(ImportHistoryModel.imported_at.desc()).offset(offset).limit(limit).all()
    result = []
    for r in rows:
        result.append({
            "import_id": r.import_id,
            "plant_id": r.plant_id,
            "source": r.source,
            "filename": r.filename,
            "file_size_kb": r.file_size_kb,
            "total_rows": r.total_rows,
            "valid_rows": r.valid_rows,
            "error_rows": r.error_rows,
            "status": r.status,
            "errors": _json.loads(r.errors_json) if r.errors_json else [],
            "imported_by": r.imported_by,
            "imported_at": r.imported_at.isoformat() if r.imported_at else None,
        })
    return result


def get_import_history_entry(db: Session, import_id: str) -> dict | None:
    """Get a single import history entry by ID."""
    import json as _json

    obj = db.query(ImportHistoryModel).filter_by(import_id=import_id).first()
    if not obj:
        return None
    return {
        "import_id": obj.import_id,
        "plant_id": obj.plant_id,
        "source": obj.source,
        "filename": obj.filename,
        "file_size_kb": obj.file_size_kb,
        "total_rows": obj.total_rows,
        "valid_rows": obj.valid_rows,
        "error_rows": obj.error_rows,
        "status": obj.status,
        "errors": _json.loads(obj.errors_json) if obj.errors_json else [],
        "imported_by": obj.imported_by,
        "imported_at": obj.imported_at.isoformat() if obj.imported_at else None,
    }


def detect_source_from_filename(filename: str) -> str | None:
    """Detect import source from template-style filename prefix (e.g. '01_...' → EQUIPMENT_HIERARCHY)."""
    import re

    match = re.match(r"^(\d{1,2})[_\-]", filename)
    if match:
        num = int(match.group(1))
        return _TEMPLATE_NUM_TO_SOURCE.get(num)
    return None


# ── Export ──────────────────────────────────────────────────────────

def export_data(db: Session, export_type: str, data: dict) -> dict:
    if export_type == "equipment":
        result = DataExportEngine.prepare_equipment_export(
            data.get("hierarchy_data", []),
            include_criticality=data.get("include_criticality", True),
            include_health=data.get("include_health", True),
        )
    elif export_type == "kpis":
        result = DataExportEngine.prepare_kpi_export(
            planning_kpis=data.get("planning_kpis"),
            de_kpis=data.get("de_kpis"),
            reliability_kpis=data.get("reliability_kpis"),
        )
    elif export_type == "schedule":
        result = DataExportEngine.prepare_schedule_export(
            data.get("program", {}),
            gantt_rows=data.get("gantt_rows"),
        )
    else:
        result = DataExportEngine.prepare_report_export(
            data.get("report", {}),
            format=ExportFormat(data.get("format", "EXCEL")),
        )
    return result.model_dump(mode="json")


# ── Cross-Module ────────────────────────────────────────────────────

def run_cross_module_analysis(db: Session, plant_id: str, data: dict) -> dict:
    correlations = []

    if data.get("equipment_criticality") and data.get("failure_records"):
        correlations.append(CrossModuleEngine.correlate_criticality_failures(
            data["equipment_criticality"], data["failure_records"],
        ))
    if data.get("cost_records") and data.get("reliability_kpis"):
        correlations.append(CrossModuleEngine.correlate_cost_reliability(
            data["cost_records"], data["reliability_kpis"],
        ))
    if data.get("health_scores") and data.get("backlog_items"):
        correlations.append(CrossModuleEngine.correlate_health_backlog(
            data["health_scores"], data["backlog_items"],
        ))

    overlap = None
    if any(data.get(k) for k in ["jackknife_result", "pareto_result", "rbi_result"]):
        overlap = CrossModuleEngine.find_bad_actor_overlap(
            jackknife_result=data.get("jackknife_result"),
            pareto_result=data.get("pareto_result"),
            rbi_result=data.get("rbi_result"),
        )

    summary = CrossModuleEngine.generate_cross_module_summary(plant_id, correlations, overlap)
    return summary.model_dump(mode="json")
