"""Reliability router — spare parts, shutdowns, MoC, OCR, Jack-Knife, Pareto, LCC, RBI."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.services import reliability_service

router = APIRouter(prefix="/reliability", tags=["reliability"])


# ── Spare Parts ──────────────────────────────────────────────────────

@router.post("/spare-parts/analyze")
def analyze_spare_parts(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    parts = data.get("parts", [])
    return reliability_service.analyze_spare_parts(db, plant_id, parts)


# ── Shutdowns ────────────────────────────────────────────────────────

@router.post("/shutdowns")
def create_shutdown(data: dict, db: Session = Depends(get_db)):
    return reliability_service.create_shutdown(
        db,
        data.get("plant_id", "BRY"),
        data.get("name", ""),
        data.get("planned_start", ""),
        data.get("planned_end", ""),
        data.get("work_orders", []),
    )


@router.get("/shutdowns/{shutdown_id}")
def get_shutdown(shutdown_id: str, db: Session = Depends(get_db)):
    result = reliability_service.get_shutdown(db, shutdown_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.put("/shutdowns/{shutdown_id}/start")
def start_shutdown(shutdown_id: str, db: Session = Depends(get_db)):
    result = reliability_service.start_shutdown(db, shutdown_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.put("/shutdowns/{shutdown_id}/complete")
def complete_shutdown(shutdown_id: str, db: Session = Depends(get_db)):
    result = reliability_service.complete_shutdown(db, shutdown_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


# ── Shutdown Reporting & Scheduling (GAP-W14) ───────────────────────


@router.post("/shutdowns/{shutdown_id}/daily-report")
def shutdown_daily_report(shutdown_id: str, data: dict, db: Session = Depends(get_db)):
    result = reliability_service.generate_shutdown_daily_report(db, shutdown_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.post("/shutdowns/{shutdown_id}/shift-report")
def shutdown_shift_report(shutdown_id: str, data: dict, db: Session = Depends(get_db)):
    result = reliability_service.generate_shutdown_shift_report(db, shutdown_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.post("/shutdowns/{shutdown_id}/suggest-next-shift")
def shutdown_suggest_next_shift(shutdown_id: str, data: dict, db: Session = Depends(get_db)):
    result = reliability_service.suggest_shutdown_next_shift(db, shutdown_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.post("/shutdowns/{shutdown_id}/schedule")
def shutdown_schedule(shutdown_id: str, data: dict, db: Session = Depends(get_db)):
    result = reliability_service.generate_shutdown_schedule(db, shutdown_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


@router.post("/shutdowns/{shutdown_id}/final-summary")
def shutdown_final_summary(shutdown_id: str, db: Session = Depends(get_db)):
    result = reliability_service.generate_shutdown_final_summary(db, shutdown_id)
    if not result:
        raise HTTPException(status_code=404, detail="Shutdown not found")
    return result


# ── MoC ──────────────────────────────────────────────────────────────

@router.post("/moc")
def create_moc(data: dict, db: Session = Depends(get_db)):
    return reliability_service.create_moc(
        db,
        data.get("plant_id", "BRY"),
        data.get("title", ""),
        data.get("description", ""),
        data.get("category", "EQUIPMENT_MODIFICATION"),
        data.get("requester_id", ""),
        data.get("affected_equipment"),
        data.get("risk_level", "LOW"),
    )


@router.get("/moc")
def list_mocs(
    plant_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return reliability_service.list_mocs(db, plant_id, status)


@router.get("/moc/{moc_id}")
def get_moc(moc_id: str, db: Session = Depends(get_db)):
    result = reliability_service.get_moc(db, moc_id)
    if not result:
        raise HTTPException(status_code=404, detail="MoC not found")
    return result


@router.put("/moc/{moc_id}/advance")
def advance_moc(moc_id: str, data: dict, db: Session = Depends(get_db)):
    action = data.pop("action", "")
    result = reliability_service.advance_moc(db, moc_id, action, **data)
    if not result:
        raise HTTPException(status_code=404, detail="MoC not found")
    return result


# ── OCR ──────────────────────────────────────────────────────────────

@router.post("/ocr/analyze")
def calculate_ocr(data: dict, db: Session = Depends(get_db)):
    return reliability_service.calculate_ocr(db, data)


# ── Jack-Knife ───────────────────────────────────────────────────────

@router.post("/jackknife/analyze")
def analyze_jackknife(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    equipment_data = data.get("equipment_data", [])
    return reliability_service.analyze_jackknife(db, plant_id, equipment_data)


# ── Pareto ───────────────────────────────────────────────────────────

@router.post("/pareto/analyze")
def analyze_pareto(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    metric_type = data.get("metric_type", "failures")
    records = data.get("records", [])
    return reliability_service.analyze_pareto(db, plant_id, metric_type, records)


# ── LCC ──────────────────────────────────────────────────────────────

@router.post("/lcc/calculate")
def calculate_lcc(data: dict, db: Session = Depends(get_db)):
    return reliability_service.calculate_lcc(db, data)


# ── RBI ──────────────────────────────────────────────────────────────

@router.post("/rbi/assess")
def assess_rbi(data: dict, db: Session = Depends(get_db)):
    plant_id = data.get("plant_id", "BRY")
    equipment_list = data.get("equipment_list", [])
    return reliability_service.assess_rbi(db, plant_id, equipment_list)
