"""RCA & Defect Elimination router — root cause analysis, planning KPIs, DE KPIs."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.services import rca_service

router = APIRouter(prefix="/rca", tags=["rca"])


# ── RCA Analyses ──────────────────────────────────────────────────────

@router.post("/analyses")
def create_rca(data: dict, db: Session = Depends(get_db)):
    return rca_service.create_rca(
        db,
        event_description=data.get("event_description", ""),
        plant_id=data.get("plant_id", "BRY"),
        equipment_id=data.get("equipment_id"),
        max_consequence=data.get("max_consequence", 3),
        frequency=data.get("frequency", 3),
        team_members=data.get("team_members"),
    )


@router.get("/analyses")
def list_rcas(
    plant_id: str | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
):
    return rca_service.list_rcas(db, plant_id, status)


@router.get("/analyses/summary")
def get_rca_summary(
    plant_id: str | None = None,
    db: Session = Depends(get_db),
):
    return rca_service.get_rca_summary(db, plant_id)


@router.get("/analyses/{analysis_id}")
def get_rca(analysis_id: str, db: Session = Depends(get_db)):
    result = rca_service.get_rca(db, analysis_id)
    if not result:
        raise HTTPException(status_code=404, detail="RCA analysis not found")
    return result


@router.post("/analyses/{analysis_id}/5w2h")
def run_5w2h(analysis_id: str, data: dict, db: Session = Depends(get_db)):
    result = rca_service.run_5w2h(db, analysis_id, data)
    if not result:
        raise HTTPException(status_code=404, detail="RCA analysis not found")
    return result


@router.put("/analyses/{analysis_id}/advance")
def advance_status(analysis_id: str, data: dict, db: Session = Depends(get_db)):
    target = data.get("status", "")
    result = rca_service.advance_rca_status(db, analysis_id, target)
    if not result:
        raise HTTPException(status_code=404, detail="RCA analysis not found")
    return result


# ── Planning KPIs ─────────────────────────────────────────────────────

@router.post("/planning-kpis/calculate")
def calculate_planning_kpis(data: dict, db: Session = Depends(get_db)):
    return rca_service.calculate_planning_kpis(db, data)


@router.get("/planning-kpis")
def list_planning_kpi_snapshots(
    plant_id: str | None = None,
    db: Session = Depends(get_db),
):
    return rca_service.list_planning_kpi_snapshots(db, plant_id)


# ── DE KPIs ───────────────────────────────────────────────────────────

@router.post("/de-kpis/calculate")
def calculate_de_kpis(data: dict, db: Session = Depends(get_db)):
    return rca_service.calculate_de_kpis(db, data)


@router.get("/de-kpis")
def list_de_kpi_snapshots(
    plant_id: str | None = None,
    db: Session = Depends(get_db),
):
    return rca_service.list_de_kpi_snapshots(db, plant_id)
