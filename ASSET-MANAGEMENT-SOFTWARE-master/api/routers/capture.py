"""Capture router — field capture submission and retrieval."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.services import capture_service

router = APIRouter(prefix="/capture", tags=["capture"])


@router.post("/")
def submit_capture(data: dict, db: Session = Depends(get_db)):
    result = capture_service.process_capture(db, data)
    return result


@router.get("/")
def list_captures(db: Session = Depends(get_db)):
    captures = capture_service.list_captures(db)
    return [
        {
            "capture_id": c.capture_id,
            "technician_id": c.technician_id,
            "capture_type": c.capture_type,
            "language": c.language,
            "equipment_tag_manual": c.equipment_tag_manual,
            "created_at": c.created_at.isoformat() if c.created_at else None,
        }
        for c in captures
    ]


@router.get("/nearby")
def get_nearby_equipment(
    lat: float = Query(..., description="Technician latitude (WGS-84)"),
    lon: float = Query(..., description="Technician longitude (WGS-84)"),
    radius_m: float = Query(100.0, description="Search radius in metres"),
    db: Session = Depends(get_db),
):
    """Return equipment nodes within *radius_m* metres of the given GPS position.

    Results are sorted by distance (closest first) and include a confidence
    tier: HIGH (<= 20 m) or MEDIUM (<= 100 m).
    """
    matches = capture_service.find_nearby_equipment(db, lat, lon, radius_m)
    return matches


@router.get("/{capture_id}")
def get_capture(capture_id: str, db: Session = Depends(get_db)):
    c = capture_service.get_capture(db, capture_id)
    if not c:
        raise HTTPException(status_code=404, detail="Capture not found")
    return {
        "capture_id": c.capture_id,
        "technician_id": c.technician_id,
        "capture_type": c.capture_type,
        "language": c.language,
        "raw_text": c.raw_text,
        "raw_voice_text": c.raw_voice_text,
        "equipment_tag_manual": c.equipment_tag_manual,
        "location_hint": c.location_hint,
        "created_at": c.created_at.isoformat() if c.created_at else None,
    }
