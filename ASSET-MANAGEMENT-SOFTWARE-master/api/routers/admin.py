"""Admin router — seed database, audit log, stats, agent status."""

from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from api.config import settings
from api.database.connection import get_db
from api.database.models import AuditLogModel, UserFeedbackModel
from api.services import hierarchy_service, agent_service

router = APIRouter(prefix="/admin", tags=["admin"])


def _require_admin_key(x_admin_key: str = Header(...)) -> str:
    """Dependency that requires a valid admin API key for destructive operations."""
    if not settings.ADMIN_API_KEY:
        raise HTTPException(status_code=503, detail="Admin API key not configured")
    if x_admin_key != settings.ADMIN_API_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin API key")
    return x_admin_key


@router.post("/seed-database")
def seed_database(db: Session = Depends(get_db), _key: str = Depends(_require_admin_key)):
    from api.seed import seed_all
    result = seed_all(db)
    return result


@router.get("/audit-log")
def get_audit_log(entity_type: str | None = None, limit: int = 100, db: Session = Depends(get_db)):
    q = db.query(AuditLogModel)
    if entity_type:
        q = q.filter(AuditLogModel.entity_type == entity_type)
    entries = q.order_by(AuditLogModel.timestamp.desc()).limit(limit).all()
    return [
        {"id": e.id, "entity_type": e.entity_type, "entity_id": e.entity_id,
         "action": e.action, "user": e.user,
         "timestamp": e.timestamp.isoformat() if e.timestamp else None}
        for e in entries
    ]


@router.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    node_counts = hierarchy_service.count_nodes_by_type(db)
    plants = hierarchy_service.list_plants(db)
    return {
        "plants": len(plants),
        "hierarchy_nodes": node_counts,
        "total_nodes": sum(node_counts.values()),
    }


@router.delete("/reset-database")
def reset_database(db: Session = Depends(get_db), _key: str = Depends(_require_admin_key)):
    # Delete all rows from all tables via session (works with test DB override)
    from api.database.models import (
        VarianceAlertModel, HealthScoreModel, KPIMetricsModel,
        FailurePredictionModel, CAPAItemModel, ExpertCardModel,
        SAPUploadPackageModel, WorkPackageModel, MaintenanceTaskModel,
        FailureModeModel, FunctionalFailureModel, FunctionModel,
        CriticalityAssessmentModel, WorkOrderModel, HierarchyNodeModel, PlantModel,
        FieldCaptureModel, WorkRequestModel, PlannerRecommendationModel,
        BacklogItemModel, OptimizedBacklogModel, WorkforceModel,
        ShutdownCalendarModel, InventoryItemModel,
        TimeLogModel, DeliverableModel,
    )
    for model in [
        AuditLogModel,
        TimeLogModel, DeliverableModel,  # GAP-W10 (TimeLog first — FK)
        OptimizedBacklogModel, PlannerRecommendationModel, BacklogItemModel,
        WorkRequestModel, FieldCaptureModel,
        InventoryItemModel, ShutdownCalendarModel, WorkforceModel,
        VarianceAlertModel, HealthScoreModel, KPIMetricsModel,
        FailurePredictionModel, CAPAItemModel, ExpertCardModel,
        SAPUploadPackageModel, WorkPackageModel, MaintenanceTaskModel,
        FailureModeModel, FunctionalFailureModel, FunctionModel,
        CriticalityAssessmentModel, WorkOrderModel, HierarchyNodeModel, PlantModel,
    ]:
        db.query(model).delete()
    db.commit()
    return {"status": "Database reset complete"}


@router.get("/agent-status")
def agent_status():
    return agent_service.get_status()


@router.post("/feedback")
def submit_feedback(data: dict, db: Session = Depends(get_db)):
    fb = UserFeedbackModel(
        page=data.get("page", "unknown"),
        rating=data.get("rating", 3),
        comment=data.get("comment", ""),
    )
    db.add(fb)
    db.commit()
    return {"feedback_id": fb.feedback_id, "status": "received"}


@router.get("/feedback")
def list_feedback(page: str | None = None, limit: int = 50, db: Session = Depends(get_db)):
    q = db.query(UserFeedbackModel)
    if page:
        q = q.filter(UserFeedbackModel.page == page)
    entries = q.order_by(UserFeedbackModel.created_at.desc()).limit(limit).all()
    return [
        {"feedback_id": f.feedback_id, "page": f.page, "rating": f.rating,
         "comment": f.comment, "created_at": f.created_at.isoformat() if f.created_at else None}
        for f in entries
    ]
