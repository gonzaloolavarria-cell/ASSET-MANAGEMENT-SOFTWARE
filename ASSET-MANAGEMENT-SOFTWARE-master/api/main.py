"""FastAPI application — OCP Maintenance AI MVP."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.config import settings
from api.database.connection import create_all_tables
from api.routers import (
    hierarchy, criticality, fmea, tasks, work_packages, sap, analytics, admin,
    capture, work_requests, planner, backlog, scheduling,
    reliability, rca,
    reporting, dashboard,
    sync,
    troubleshooting,
    execution_checklists,
    deliverables,
    assignments,
    expert_knowledge,
    financial,
    workflow,
    media,
    imports,
)


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version="1.0.0",
        description="OCP Maintenance AI MVP — 4-module maintenance strategy platform",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include all routers under /api/v1
    prefix = settings.API_V1_PREFIX
    app.include_router(hierarchy.router, prefix=prefix)
    app.include_router(criticality.router, prefix=prefix)
    app.include_router(fmea.router, prefix=prefix)
    app.include_router(tasks.router, prefix=prefix)
    app.include_router(work_packages.router, prefix=prefix)
    app.include_router(sap.router, prefix=prefix)
    app.include_router(analytics.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    # Phase 3 — Modules 1-3
    app.include_router(capture.router, prefix=prefix)
    app.include_router(work_requests.router, prefix=prefix)
    app.include_router(planner.router, prefix=prefix)
    app.include_router(backlog.router, prefix=prefix)
    # Phase 4B — Scheduling
    app.include_router(scheduling.router, prefix=prefix)
    # Phase 5 — Advanced Reliability
    app.include_router(reliability.router, prefix=prefix)
    # Phase 6 — Reporting & Dashboards
    app.include_router(reporting.router, prefix=prefix)
    app.include_router(dashboard.router, prefix=prefix)
    # Phase 8 — RCA & Defect Elimination
    app.include_router(rca.router, prefix=prefix)
    # GAP-W03 — Offline Sync
    app.include_router(sync.router, prefix=prefix)
    # GAP-W02 — Troubleshooting / Diagnostic Assistant
    app.include_router(troubleshooting.router, prefix=prefix)
    # GAP-W06 — Execution Checklists
    app.include_router(execution_checklists.router, prefix=prefix)
    # GAP-W10 — Deliverable Tracking
    app.include_router(deliverables.router, prefix=prefix)
    # GAP-W09 — Competency-Based Work Assignment
    app.include_router(assignments.router, prefix=prefix)
    # GAP-W13 — Expert Knowledge Capture
    app.include_router(expert_knowledge.router, prefix=prefix)
    # GAP-W04 — Financial / ROI Tracking
    app.include_router(financial.router, prefix=prefix)
    # G-17 — Agent Workflow via API
    app.include_router(workflow.router, prefix=prefix)
    # G-08 — Voice + Image Media Processing
    app.include_router(media.router, prefix=prefix)
    # G-18 / Phase B — Data Import Pipeline
    app.include_router(imports.router, prefix=prefix)

    # GAP-W03 — Serve Field PWA at /field/ (only when dist/ has been built)
    field_dist = Path("field_app/dist")
    if field_dist.is_dir():
        app.mount("/field", StaticFiles(directory=str(field_dist), html=True), name="field-app")

    @app.on_event("startup")
    def startup():
        create_all_tables()
        for warning in settings.validate():
            import logging
            logging.getLogger("api.startup").warning(warning)

    @app.get("/")
    def root():
        return {
            "project": settings.PROJECT_NAME,
            "version": "1.0.0",
            "docs": "/docs",
            "modules": [
                "hierarchy", "criticality", "fmea", "tasks", "work-packages",
                "sap", "analytics", "admin",
                "capture", "work-requests", "planner", "backlog", "scheduling",
                "reliability", "reporting", "dashboard", "rca", "sync",
                "troubleshooting", "execution-checklists", "deliverables", "assignments",
                "financial",
            ],
        }

    @app.get("/health")
    def health():
        return {"status": "ok"}

    return app


app = create_app()
