"""HTTP client for FastAPI backend — used by Streamlit pages."""

import httpx

BASE_URL = "http://localhost:8000/api/v1"
_client = httpx.Client(base_url=BASE_URL, timeout=30.0)


def _get(path: str, params: dict | None = None) -> dict | list:
    r = _client.get(path, params=params)
    r.raise_for_status()
    return r.json()


def _post(path: str, data: dict | None = None) -> dict | list:
    r = _client.post(path, json=data or {})
    r.raise_for_status()
    return r.json()


def _put(path: str, data: dict | None = None) -> dict | list:
    r = _client.put(path, json=data or {})
    r.raise_for_status()
    return r.json()


def _delete(path: str) -> dict | list:
    r = _client.delete(path)
    r.raise_for_status()
    return r.json()


# ── Hierarchy ──────────────────────────────────────────────────────────

def list_plants():
    return _get("/hierarchy/plants")

def list_nodes(plant_id=None, node_type=None, parent_node_id=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if node_type: params["node_type"] = node_type
    if parent_node_id: params["parent_node_id"] = parent_node_id
    return _get("/hierarchy/nodes", params=params)

def get_node(node_id):
    return _get(f"/hierarchy/nodes/{node_id}")

def get_subtree(node_id):
    return _get(f"/hierarchy/nodes/{node_id}/tree")

def get_node_stats(plant_id=None):
    return _get("/hierarchy/stats", params={"plant_id": plant_id} if plant_id else None)

def build_from_vendor(data):
    return _post("/hierarchy/build-from-vendor", data)

# ── Criticality ────────────────────────────────────────────────────────

def assess_criticality(data):
    return _post("/criticality/assess", data)

def get_criticality(node_id):
    return _get(f"/criticality/{node_id}")

def approve_criticality(assessment_id):
    return _put(f"/criticality/{assessment_id}/approve")

# ── FMEA ───────────────────────────────────────────────────────────────

def list_functions(node_id=None):
    return _get("/fmea/functions", params={"node_id": node_id} if node_id else None)

def create_function(data):
    return _post("/fmea/functions", data)

def list_functional_failures(function_id=None):
    return _get("/fmea/functional-failures", params={"function_id": function_id} if function_id else None)

def create_functional_failure(data):
    return _post("/fmea/functional-failures", data)

def create_failure_mode(data):
    return _post("/fmea/failure-modes", data)

def get_failure_mode(fm_id):
    return _get(f"/fmea/failure-modes/{fm_id}")

def list_failure_modes(functional_failure_id=None):
    return _get("/fmea/failure-modes", params={"functional_failure_id": functional_failure_id} if functional_failure_id else None)

def validate_fm_combination(mechanism, cause):
    return _post("/fmea/validate-combination", {"mechanism": mechanism, "cause": cause})

def get_fm_combinations(mechanism=None):
    return _get("/fmea/fm-combinations", params={"mechanism": mechanism} if mechanism else None)

def rcm_decide(data):
    return _post("/fmea/rcm-decide", data)

# ── Tasks ──────────────────────────────────────────────────────────────

def create_task(data):
    return _post("/tasks/", data)

def get_task(task_id):
    return _get(f"/tasks/{task_id}")

def list_tasks(failure_mode_id=None, status=None):
    params = {}
    if failure_mode_id: params["failure_mode_id"] = failure_mode_id
    if status: params["status"] = status
    return _get("/tasks/", params=params)

def link_task_to_fm(task_id, fm_id):
    return _post(f"/tasks/link-fm/{task_id}/{fm_id}")

def validate_task_name(name, task_type=""):
    return _post("/tasks/validate-name", {"name": name, "task_type": task_type})

def validate_wp_name(name):
    return _post("/tasks/validate-wp-name", {"name": name})

# ── Work Packages ──────────────────────────────────────────────────────

def create_work_package(data):
    return _post("/work-packages/", data)

def get_work_package(wp_id):
    return _get(f"/work-packages/{wp_id}")

def list_work_packages(node_id=None, status=None):
    params = {}
    if node_id: params["node_id"] = node_id
    if status: params["status"] = status
    return _get("/work-packages/", params=params)

def approve_work_package(wp_id):
    return _put(f"/work-packages/{wp_id}/approve")

def group_tasks(items):
    return _post("/work-packages/group", {"items": items})

def generate_work_instruction(wp_id, data):
    return _post(f"/work-packages/{wp_id}/work-instruction", data)

# ── SAP ────────────────────────────────────────────────────────────────

def list_sap_uploads(plant_code=None):
    return _get("/sap/uploads", params={"plant_code": plant_code} if plant_code else None)

def approve_sap_upload(package_id):
    return _put(f"/sap/uploads/{package_id}/approve")

def get_sap_mock(transaction):
    return _get(f"/sap/mock/{transaction}")

# ── Analytics ──────────────────────────────────────────────────────────

def calculate_health_score(data):
    return _post("/analytics/health-score", data)

def calculate_kpis(data):
    return _post("/analytics/kpis", data)

def fit_weibull(failure_intervals):
    return _post("/analytics/weibull-fit", {"failure_intervals": failure_intervals})

def predict_failure(data):
    return _post("/analytics/weibull-predict", data)

# ── Admin ──────────────────────────────────────────────────────────────

def seed_database():
    return _post("/admin/seed-database")

def get_stats():
    return _get("/admin/stats")

def get_audit_log(entity_type=None, limit=50):
    params = {"limit": limit}
    if entity_type: params["entity_type"] = entity_type
    return _get("/admin/audit-log", params=params)

def get_agent_status():
    return _get("/admin/agent-status")


# ── Capture (M1) ─────────────────────────────────────────────────────

def submit_capture(data):
    return _post("/capture/", data)

def list_captures():
    return _get("/capture/")

def get_capture(capture_id):
    return _get(f"/capture/{capture_id}")

# ── Media — G-08 Voice + Image ───────────────────────────────────────

def transcribe_audio(audio_bytes: bytes, filename: str = "capture.webm", language: str = "en") -> dict:
    """Transcribe audio bytes via POST /media/transcribe (Whisper API)."""
    import io
    mime_map = {
        ".webm": "audio/webm",
        ".wav": "audio/wav",
        ".mp3": "audio/mpeg",
        ".m4a": "audio/mp4",
        ".ogg": "audio/ogg",
        ".flac": "audio/flac",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".webm"
    mime_type = mime_map.get(ext, "audio/webm")
    r = _client.post(
        "/media/transcribe",
        files={"file": (filename, io.BytesIO(audio_bytes), mime_type)},
        data={"language": language},
    )
    r.raise_for_status()
    return r.json()

def analyze_image(image_bytes: bytes, filename: str = "capture.jpg", context: str = "") -> dict:
    """Analyze an equipment image via POST /media/analyze-image (Claude Vision)."""
    import io
    mime_map = {
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".png": "image/png",
        ".webp": "image/webp",
    }
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ".jpg"
    mime_type = mime_map.get(ext, "image/jpeg")
    r = _client.post(
        "/media/analyze-image",
        files={"file": (filename, io.BytesIO(image_bytes), mime_type)},
        data={"context": context},
    )
    r.raise_for_status()
    return r.json()

def find_nearby_equipment(lat: float, lon: float, radius_m: float = 100.0) -> list:
    """Return equipment near (lat, lon) via GET /capture/nearby (G-08 D-5)."""
    return _get("/capture/nearby", params={"lat": lat, "lon": lon, "radius_m": radius_m})

# ── Work Requests (M1-M2) ────────────────────────────────────────────

def list_work_requests(status=None):
    return _get("/work-requests/", params={"status": status} if status else None)

def get_work_request(request_id):
    return _get(f"/work-requests/{request_id}")

def validate_work_request(request_id, action, modifications=None):
    return _put(f"/work-requests/{request_id}/validate", {"action": action, "modifications": modifications})

def classify_work_request(request_id):
    return _post(f"/work-requests/{request_id}/classify")

# ── Planner (M2) ─────────────────────────────────────────────────────

def generate_recommendation(work_request_id):
    return _post(f"/planner/{work_request_id}/recommend")

def get_recommendation(recommendation_id):
    return _get(f"/planner/recommendations/{recommendation_id}")

def apply_planner_action(recommendation_id, action, modifications=None):
    return _put(f"/planner/recommendations/{recommendation_id}/action", {"action": action, "modifications": modifications})

# ── Backlog (M3) ─────────────────────────────────────────────────────

def list_backlog(status=None, priority=None, equipment_tag=None):
    params = {}
    if status: params["status"] = status
    if priority: params["priority"] = priority
    if equipment_tag: params["equipment_tag"] = equipment_tag
    return _get("/backlog/", params=params)

def add_to_backlog(work_request_id):
    return _post(f"/backlog/add/{work_request_id}")

def optimize_backlog(plant_id, period_days=30):
    return _post("/backlog/optimize", {"plant_id": plant_id, "period_days": period_days})

def get_optimization(optimization_id):
    return _get(f"/backlog/optimizations/{optimization_id}")

def approve_schedule(optimization_id):
    return _put(f"/backlog/optimizations/{optimization_id}/approve")

def get_schedule():
    return _get("/backlog/schedule")

# ── Scheduling (Phase 4B) ──────────────────────────────────────────

def create_program(plant_id, week_number, year):
    return _post("/scheduling/programs", {"plant_id": plant_id, "week_number": week_number, "year": year})

def list_programs(plant_id=None, status=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if status: params["status"] = status
    return _get("/scheduling/programs", params=params)

def get_program(program_id):
    return _get(f"/scheduling/programs/{program_id}")

def finalize_program(program_id):
    return _put(f"/scheduling/programs/{program_id}/finalize")

def get_gantt(program_id):
    return _get(f"/scheduling/programs/{program_id}/gantt")


# ── Reliability (Phase 5) ─────────────────────────────────────────

def analyze_spare_parts(plant_id, parts):
    return _post("/reliability/spare-parts/analyze", {"plant_id": plant_id, "parts": parts})

def create_shutdown(plant_id, name, planned_start, planned_end, work_orders):
    return _post("/reliability/shutdowns", {"plant_id": plant_id, "name": name, "planned_start": planned_start, "planned_end": planned_end, "work_orders": work_orders})

def get_shutdown(shutdown_id):
    return _get(f"/reliability/shutdowns/{shutdown_id}")

def create_moc(plant_id, title, description, category, requester_id, affected_equipment=None, risk_level="LOW"):
    return _post("/reliability/moc", {"plant_id": plant_id, "title": title, "description": description, "category": category, "requester_id": requester_id, "affected_equipment": affected_equipment or [], "risk_level": risk_level})

def list_mocs(plant_id=None, status=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if status: params["status"] = status
    return _get("/reliability/moc", params=params)

def advance_moc(moc_id, action, **kwargs):
    return _put(f"/reliability/moc/{moc_id}/advance", data={"action": action, **kwargs})

def calculate_ocr(data):
    return _post("/reliability/ocr/analyze", data)

def analyze_jackknife(plant_id, equipment_data):
    return _post("/reliability/jackknife/analyze", {"plant_id": plant_id, "equipment_data": equipment_data})

def analyze_pareto(plant_id, metric_type, records):
    return _post("/reliability/pareto/analyze", {"plant_id": plant_id, "metric_type": metric_type, "records": records})

def assess_rbi(plant_id, equipment_list):
    return _post("/reliability/rbi/assess", {"plant_id": plant_id, "equipment_list": equipment_list})


# ── Reporting (Phase 6) ─────────────────────────────────────────

def generate_weekly_report(plant_id, week, year, data=None):
    return _post("/reporting/reports/weekly", {"plant_id": plant_id, "week": week, "year": year, **(data or {})})

def generate_monthly_report(plant_id, month, year, data=None):
    return _post("/reporting/reports/monthly", {"plant_id": plant_id, "month": month, "year": year, **(data or {})})

def generate_quarterly_report(plant_id, quarter, year, data=None):
    return _post("/reporting/reports/quarterly", {"plant_id": plant_id, "quarter": quarter, "year": year, **(data or {})})

def list_reports(plant_id=None, report_type=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if report_type: params["report_type"] = report_type
    return _get("/reporting/reports", params=params)

def get_report(report_id):
    return _get(f"/reporting/reports/{report_id}")

def calculate_de_kpis_standalone(data):
    return _post("/reporting/de-kpis/calculate", data)

def generate_notifications(plant_id, data=None):
    return _post("/reporting/notifications/generate", {"plant_id": plant_id, **(data or {})})

def list_notifications(plant_id=None, level=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if level: params["level"] = level
    return _get("/reporting/notifications", params=params)

def acknowledge_notification(notification_id):
    return _put(f"/reporting/notifications/{notification_id}/ack")

def validate_import(source, rows):
    return _post("/reporting/import/validate", {"source": source, "rows": rows})

def upload_and_validate_import(file_bytes, filename, source, sheet_name=None):
    """Upload a file for parsing and validation."""
    params = {"source": source}
    if sheet_name:
        params["sheet_name"] = sheet_name
    r = _client.post(
        "/reporting/import/upload",
        files={"file": (filename, file_bytes)},
        params=params,
    )
    r.raise_for_status()
    return r.json()

def download_template(number):
    """Download a blank import template by number (1-14)."""
    r = _client.get(f"/reporting/import/template/{number}")
    r.raise_for_status()
    return r.content

def get_import_history(plant_id=None, source=None, limit=50, offset=0):
    """List past import operations, newest first."""
    params = {"limit": limit, "offset": offset}
    if plant_id:
        params["plant_id"] = plant_id
    if source:
        params["source"] = source
    return _get("/reporting/import/history", params=params)

def get_import_history_entry(import_id):
    """Get a single import history entry by ID."""
    return _get(f"/reporting/import/history/{import_id}")

def export_data(export_type, data):
    return _post("/reporting/export", {"export_type": export_type, **data})

def run_cross_module_analysis(plant_id, data=None):
    return _post("/reporting/cross-module/analyze", {"plant_id": plant_id, **(data or {})})

# ── Dashboard (Phase 6) ─────────────────────────────────────────

def get_executive_dashboard(plant_id):
    return _get(f"/dashboard/executive/{plant_id}")

def get_kpi_summary(plant_id):
    return _get(f"/dashboard/kpi-summary/{plant_id}")

def get_dashboard_alerts(plant_id):
    return _get(f"/dashboard/alerts/{plant_id}")

# ── FMECA (Phase 7) ──────────────────────────────────────────────

def create_fmeca_worksheet(data):
    return _post("/fmea/fmeca/worksheets", data)

def get_fmeca_worksheet(worksheet_id):
    return _get(f"/fmea/fmeca/worksheets/{worksheet_id}")

def calculate_rpn(severity, occurrence, detection):
    return _post("/fmea/fmeca/rpn", {"severity": severity, "occurrence": occurrence, "detection": detection})

def run_fmeca_decisions(worksheet_id):
    return _put(f"/fmea/fmeca/worksheets/{worksheet_id}/run-decisions")

def get_fmeca_summary(worksheet_id):
    return _get(f"/fmea/fmeca/worksheets/{worksheet_id}/summary")


# ── RCA & Defect Elimination (Phase 8) ────────────────────────────

def create_rca(data):
    return _post("/rca/analyses", data)

def list_rcas(plant_id=None, status=None):
    params = {}
    if plant_id: params["plant_id"] = plant_id
    if status: params["status"] = status
    return _get("/rca/analyses", params=params)

def get_rca(analysis_id):
    return _get(f"/rca/analyses/{analysis_id}")

def get_rca_summary(plant_id=None):
    return _get("/rca/analyses/summary", params={"plant_id": plant_id} if plant_id else None)

def run_5w2h(analysis_id, data):
    return _post(f"/rca/analyses/{analysis_id}/5w2h", data)

def advance_rca(analysis_id, status):
    return _put(f"/rca/analyses/{analysis_id}/advance", {"status": status})

def calculate_planning_kpis(data):
    return _post("/rca/planning-kpis/calculate", data)

def list_planning_kpi_snapshots(plant_id=None):
    return _get("/rca/planning-kpis", params={"plant_id": plant_id} if plant_id else None)

def calculate_de_kpis_full(data):
    return _post("/rca/de-kpis/calculate", data)

def list_de_kpi_snapshots(plant_id=None):
    return _get("/rca/de-kpis", params={"plant_id": plant_id} if plant_id else None)


# ── Feedback (Phase 9) ─────────────────────────────────────────────

def submit_feedback(data):
    return _post("/admin/feedback", data)

def list_feedback(page=None, limit=50):
    params = {"limit": limit}
    if page:
        params["page"] = page
    return _get("/admin/feedback", params=params)


# ── Execution Checklists (GAP-W06) ──────────────────────────────────

def generate_execution_checklist(work_package, tasks, equipment_name="", equipment_tag=""):
    return _post("/execution-checklists/", {
        "work_package": work_package, "tasks": tasks,
        "equipment_name": equipment_name, "equipment_tag": equipment_tag,
    })

def list_execution_checklists(work_package_id=None, status=None, assigned_to=None):
    params = {}
    if work_package_id: params["work_package_id"] = work_package_id
    if status: params["status"] = status
    if assigned_to: params["assigned_to"] = assigned_to
    return _get("/execution-checklists/", params=params)

def get_execution_checklist(checklist_id):
    return _get(f"/execution-checklists/{checklist_id}")

def complete_checklist_step(checklist_id, step_id, observation=None, completed_by=""):
    return _post(f"/execution-checklists/{checklist_id}/steps/{step_id}/complete", {
        "observation": observation, "completed_by": completed_by,
    })

def skip_checklist_step(checklist_id, step_id, reason="", authorized_by=""):
    return _post(f"/execution-checklists/{checklist_id}/steps/{step_id}/skip", {
        "reason": reason, "authorized_by": authorized_by,
    })

def get_checklist_next_steps(checklist_id):
    return _get(f"/execution-checklists/{checklist_id}/next-steps")

def close_execution_checklist(checklist_id, supervisor, supervisor_notes=""):
    return _post(f"/execution-checklists/{checklist_id}/close", {
        "supervisor": supervisor, "supervisor_notes": supervisor_notes,
    })


# ── Deliverable Tracking (GAP-W10) ──────────────────────────────────

def list_deliverables(client_slug=None, project_slug=None, milestone=None, status=None):
    params = {}
    if client_slug: params["client_slug"] = client_slug
    if project_slug: params["project_slug"] = project_slug
    if milestone is not None: params["milestone"] = milestone
    if status: params["status"] = status
    return _get("/deliverables/", params=params)

def get_deliverable(deliverable_id):
    return _get(f"/deliverables/{deliverable_id}")

def create_deliverable(data):
    return _post("/deliverables/", data)

def update_deliverable(deliverable_id, data):
    return _put(f"/deliverables/{deliverable_id}", data)

def transition_deliverable(deliverable_id, status, feedback=""):
    return _put(f"/deliverables/{deliverable_id}/transition", {"status": status, "feedback": feedback})

def log_time(deliverable_id, data):
    return _post(f"/deliverables/{deliverable_id}/time-log", data)

def list_time_logs(deliverable_id):
    return _get(f"/deliverables/{deliverable_id}/time-logs")

def get_deliverable_summary(client_slug, project_slug):
    return _get(f"/deliverables/summary/{client_slug}/{project_slug}")

def seed_deliverables(plan, client_slug, project_slug):
    return _post("/deliverables/seed-from-plan", {"plan": plan, "client_slug": client_slug, "project_slug": project_slug})


# ── Troubleshooting (GAP-W02) ────────────────────────────────────────

def create_troubleshooting_session(equipment_type_id, equipment_tag="", plant_id="", technician_id=""):
    return _post("/troubleshooting/sessions", {
        "equipment_type_id": equipment_type_id,
        "equipment_tag": equipment_tag,
        "plant_id": plant_id,
        "technician_id": technician_id,
    })

def add_troubleshooting_symptom(session_id, description, category="", severity="MEDIUM"):
    return _post(f"/troubleshooting/sessions/{session_id}/symptoms", {
        "description": description, "category": category, "severity": severity,
    })

def record_troubleshooting_test(session_id, test_id, result, measured_value=""):
    return _post(f"/troubleshooting/sessions/{session_id}/tests", {
        "test_id": test_id, "result": result, "measured_value": measured_value,
    })

def finalize_troubleshooting(session_id, selected_fm_code):
    return _put(f"/troubleshooting/sessions/{session_id}/finalize", {
        "selected_fm_code": selected_fm_code,
    })

def troubleshooting_feedback(session_id, actual_cause, notes=""):
    return _put(f"/troubleshooting/sessions/{session_id}/feedback", {
        "actual_cause": actual_cause, "notes": notes,
    })


# ---------------------------------------------------------------------------
# G-17 — Agent Workflow API (multi-agent M1→M4 pipeline)
# ---------------------------------------------------------------------------

def run_workflow(equipment: str, plant_code: str = "OCP"):
    """Start a new agent workflow session. Returns {session_id, status, message}."""
    return _post("/workflow/run", {"equipment": equipment, "plant_code": plant_code})


def get_workflow_session(session_id: str):
    """Poll status of a running workflow session."""
    return _get(f"/workflow/{session_id}")


def list_workflow_sessions():
    """List all workflow sessions (active and completed)."""
    return _get("/workflow/sessions")


def approve_workflow_gate(session_id: str, action: str, feedback: str = ""):
    """Submit gate approval decision: action in {approve, modify, reject}."""
    return _post(f"/workflow/{session_id}/approve", {"action": action, "feedback": feedback})

def get_equipment_symptoms(equipment_type_id):
    return _get(f"/troubleshooting/equipment/{equipment_type_id}/symptoms")

def get_troubleshooting_tree(equipment_type_id, category=""):
    params = {"category": category} if category else None
    return _get(f"/troubleshooting/equipment/{equipment_type_id}/tree", params=params)


# ── Financial (GAP-W04) ────────────────────────────────────────────────

def calculate_roi(data):
    return _post("/financial/roi", data)

def compare_roi_scenarios(scenarios):
    return _post("/financial/roi/compare", {"scenarios": scenarios})

def track_budget(plant_id, items):
    return _post("/financial/budget/track", {"plant_id": plant_id, "items": items})

def get_budget_alerts(plant_id, items, threshold_pct=10.0):
    return _post("/financial/budget/alerts", {"plant_id": plant_id, "items": items, "threshold_pct": threshold_pct})

def get_financial_summary(plant_id):
    return _get(f"/financial/summary/{plant_id}")

def calculate_financial_impact(data):
    return _post("/financial/impact", data)

def calculate_man_hours_saved(data):
    return _post("/financial/man-hours", data)

def forecast_budget(items, months_ahead=3):
    return _post("/financial/budget/forecast", {"items": items, "months_ahead": months_ahead})


# ── Expert Knowledge (GAP-W13) ──────────────────────────────────────

def create_consultation(data):
    return _post("/expert-knowledge/consultations", data)

def get_consultation(consultation_id):
    return _get(f"/expert-knowledge/consultations/{consultation_id}")

def list_consultations(expert_id=None, status=None, plant_id=None):
    params = {}
    if expert_id: params["expert_id"] = expert_id
    if status: params["status"] = status
    if plant_id: params["plant_id"] = plant_id
    return _get("/expert-knowledge/consultations", params=params)

def mark_consultation_viewed(consultation_id):
    return _put(f"/expert-knowledge/consultations/{consultation_id}/view")

def submit_expert_response(consultation_id, data):
    return _put(f"/expert-knowledge/consultations/{consultation_id}/respond", data)

def close_consultation(consultation_id, data=None):
    return _put(f"/expert-knowledge/consultations/{consultation_id}/close", data)

def get_portal_consultation(token):
    return _get(f"/expert-knowledge/portal/{token}")

def create_contribution(consultation_id):
    return _post("/expert-knowledge/contributions", {"consultation_id": consultation_id})

def list_contributions(status=None, equipment_type_id=None):
    params = {}
    if status: params["status"] = status
    if equipment_type_id: params["equipment_type_id"] = equipment_type_id
    return _get("/expert-knowledge/contributions", params=params)

def validate_contribution(contribution_id, data):
    return _put(f"/expert-knowledge/contributions/{contribution_id}/validate", data)

def promote_contribution(contribution_id, data):
    return _put(f"/expert-knowledge/contributions/{contribution_id}/promote", data)

def list_experts(retired_only=False):
    params = {"retired_only": retired_only} if retired_only else {}
    return _get("/expert-knowledge/experts", params=params)

def register_expert(data):
    return _post("/expert-knowledge/experts", data)

def get_expert_compensation(expert_id, period=None):
    params = {"period": period} if period else {}
    return _get(f"/expert-knowledge/experts/{expert_id}/compensation", params=params)

def get_expert_notifications(recipient_id):
    return _get(f"/expert-knowledge/notifications/{recipient_id}")

def mark_expert_notification_read(notification_id):
    return _put(f"/expert-knowledge/notifications/{notification_id}/read")


# ── Data Import (G-18 / Phase B) ─────────────────────────────────────

def import_file(plant_id: str, source: str, file_bytes: bytes, filename: str, sheet_name: str | None = None) -> dict:
    """Upload a file: parse → validate → persist history. Returns merged result + import_id."""
    params = {"source": source, "plant_id": plant_id}
    if sheet_name:
        params["sheet_name"] = sheet_name
    r = _client.post(
        "/reporting/import/upload",
        files={"file": (filename, file_bytes)},
        params=params,
    )
    r.raise_for_status()
    return r.json()
