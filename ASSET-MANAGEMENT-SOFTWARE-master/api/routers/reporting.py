"""Reporting router — reports, DE KPIs, notifications, import/export, cross-module analytics."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.services import reporting_service

router = APIRouter(prefix="/reporting", tags=["reporting"])

# Template directory for download endpoint
_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "templates"

# Template number → filename
_TEMPLATE_FILES: dict[int, str] = {
    1: "01_equipment_hierarchy.xlsx",
    2: "02_criticality_assessment.xlsx",
    3: "03_failure_modes.xlsx",
    4: "04_maintenance_tasks.xlsx",
    5: "05_work_packages.xlsx",
    6: "06_work_order_history.xlsx",
    7: "07_spare_parts_inventory.xlsx",
    8: "08_shutdown_calendar.xlsx",
    9: "09_workforce.xlsx",
    10: "10_field_capture.xlsx",
    11: "11_rca_events.xlsx",
    12: "12_planning_kpi_input.xlsx",
    13: "13_de_kpi_input.xlsx",
    14: "14_maintenance_strategy.xlsx",
}


# ── Reports ─────────────────────────────────────────────────────────

@router.post("/reports/weekly")
def generate_weekly_report(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    week = data.get("week", data.get("week_number", 1))
    year = data.get("year", 2025)
    return reporting_service.generate_weekly_report(db, plant_id, week, year, data)


@router.post("/reports/monthly")
def generate_monthly_report(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    month = data.get("month", 1)
    year = data.get("year", 2025)
    return reporting_service.generate_monthly_report(db, plant_id, month, year, data)


@router.post("/reports/quarterly")
def generate_quarterly_report(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    quarter = data.get("quarter", 1)
    year = data.get("year", 2025)
    return reporting_service.generate_quarterly_report(db, plant_id, quarter, year, data)


@router.get("/reports")
def list_reports(
    plant_id: str | None = None,
    report_type: str | None = None,
    db: Session = Depends(get_db),
):
    return reporting_service.list_reports(db, plant_id, report_type)


@router.get("/reports/{report_id}")
def get_report(report_id: str, db: Session = Depends(get_db)):
    result = reporting_service.get_report(db, report_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Report not found")
    return result


# ── DE KPIs ─────────────────────────────────────────────────────────

@router.post("/de-kpis/calculate")
def calculate_de_kpis(data: dict, db: Session = Depends(get_db)):
    return reporting_service.calculate_de_kpis(db, data)


@router.post("/de-kpis/program-health")
def assess_de_program_health(data: dict, db: Session = Depends(get_db)):
    return reporting_service.assess_de_program_health(db, data)


# ── Notifications ───────────────────────────────────────────────────

@router.post("/notifications/generate")
def generate_notifications(data: dict, db: Session = Depends(get_db)):
    plant_id = data.pop("plant_id", "BRY")
    return reporting_service.generate_notifications(db, plant_id, data)


@router.get("/notifications")
def list_notifications(
    plant_id: str | None = None,
    level: str | None = None,
    db: Session = Depends(get_db),
):
    return reporting_service.list_notifications(db, plant_id, level)


@router.put("/notifications/{notification_id}/ack")
def acknowledge_notification(notification_id: str, db: Session = Depends(get_db)):
    result = reporting_service.acknowledge_notification(db, notification_id)
    if not result:
        raise HTTPException(status_code=404, detail="Notification not found")
    return result


# ── Import ──────────────────────────────────────────────────────────

@router.post("/import/validate")
def validate_import(data: dict, db: Session = Depends(get_db)):
    source = data.get("source", "EQUIPMENT_HIERARCHY")
    rows = data.get("rows", [])
    return reporting_service.validate_import(db, source, rows)


@router.post("/import/upload")
async def upload_and_validate(
    file: UploadFile = File(...),
    source: str = Query("EQUIPMENT_HIERARCHY"),
    sheet_name: str | None = Query(None),
    plant_id: str = Query(default=""),
    db: Session = Depends(get_db),
):
    content = await file.read()
    try:
        return reporting_service.upload_and_validate(
            db, content, file.filename or "upload.xlsx", source, sheet_name,
            plant_id=plant_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/import/batch")
async def batch_import(
    files: list[UploadFile] = File(...),
    db: Session = Depends(get_db),
):
    results = []
    for f in files:
        content = await f.read()
        filename = f.filename or "unknown.xlsx"
        source = reporting_service.detect_source_from_filename(filename)
        if not source:
            results.append({
                "filename": filename,
                "error": f"Cannot detect import type from filename '{filename}'. "
                         "Use template-style prefix (e.g. 01_equipment_hierarchy.xlsx).",
            })
            continue
        try:
            result = reporting_service.upload_and_validate(
                db, content, filename, source,
            )
            results.append({"filename": filename, "source": source, **result})
        except ValueError as e:
            results.append({"filename": filename, "source": source, "error": str(e)})
    return {"results": results, "total_files": len(files)}


@router.get("/import/history")
def list_import_history(
    plant_id: str | None = None,
    source: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    return reporting_service.list_import_history(db, plant_id, source, limit, offset)


@router.get("/import/history/{import_id}")
def get_import_history_entry(import_id: str, db: Session = Depends(get_db)):
    result = reporting_service.get_import_history_entry(db, import_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Import history entry not found")
    return result


@router.get("/import/template/{number}")
def download_template(number: int):
    if number not in _TEMPLATE_FILES:
        raise HTTPException(
            status_code=404,
            detail=f"Template {number} not found. Valid: 1-14.",
        )
    tpl_path = _TEMPLATE_DIR / _TEMPLATE_FILES[number]
    if not tpl_path.is_file():
        raise HTTPException(status_code=404, detail="Template file missing on server")
    return FileResponse(
        path=str(tpl_path),
        filename=_TEMPLATE_FILES[number],
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


# ── Export ──────────────────────────────────────────────────────────

@router.post("/export")
def export_data(data: dict, db: Session = Depends(get_db)):
    export_type = data.pop("export_type", "report")
    return reporting_service.export_data(db, export_type, data)


# ── Cross-Module ────────────────────────────────────────────────────

@router.post("/cross-module/analyze")
def run_cross_module_analysis(data: dict, db: Session = Depends(get_db)):
    plant_id = data.pop("plant_id", "BRY")
    return reporting_service.run_cross_module_analysis(db, plant_id, data)
