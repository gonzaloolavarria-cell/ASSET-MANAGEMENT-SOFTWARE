"""Analytics router — KPIs, health scores, Weibull, variance."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from api.database.connection import get_db
from api.services import analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/health-score")
def calculate_health_score(data: dict, db: Session = Depends(get_db)):
    return analytics_service.calculate_health_score(
        db,
        node_id=data["node_id"],
        plant_id=data["plant_id"],
        equipment_tag=data["equipment_tag"],
        risk_class=data["risk_class"],
        pending_backlog_hours=data.get("pending_backlog_hours", 0.0),
        capacity_hours_per_week=data.get("capacity_hours_per_week", 40.0),
        total_failure_modes=data.get("total_failure_modes", 0),
        fm_with_strategy=data.get("fm_with_strategy", 0),
        active_alerts=data.get("active_alerts", 0),
        critical_alerts=data.get("critical_alerts", 0),
        planned_wo=data.get("planned_wo", 0),
        executed_on_time=data.get("executed_on_time", 0),
    )


@router.post("/kpis")
def calculate_kpis(data: dict, db: Session = Depends(get_db)):
    return analytics_service.calculate_kpis(
        db,
        plant_id=data["plant_id"],
        failure_dates=data.get("failure_dates"),
        total_period_hours=data.get("total_period_hours"),
        total_downtime_hours=data.get("total_downtime_hours"),
    )


@router.post("/weibull-fit")
def fit_weibull(data: dict):
    return analytics_service.fit_weibull(data["failure_intervals"])


@router.post("/weibull-predict")
def predict_failure(data: dict, db: Session = Depends(get_db)):
    return analytics_service.predict_failure(
        db,
        equipment_id=data["equipment_id"],
        equipment_tag=data["equipment_tag"],
        failure_intervals=data["failure_intervals"],
        current_age_days=data["current_age_days"],
        confidence_level=data.get("confidence_level", 0.9),
    )


@router.post("/variance-detect")
def detect_variance(data: dict):
    return analytics_service.detect_variance(data["snapshots"])


@router.get("/variance-alerts")
def get_variance_alerts(db: Session = Depends(get_db)):
    alerts = analytics_service.get_variance_alerts(db)
    return [
        {"alert_id": a.alert_id, "plant_id": a.plant_id, "metric_name": a.metric_name,
         "z_score": a.z_score, "variance_level": a.variance_level}
        for a in alerts
    ]
