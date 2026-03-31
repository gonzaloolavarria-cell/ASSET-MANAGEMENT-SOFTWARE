"""Role-based UI configuration for OCP Maintenance AI.

Defines user roles, page mappings, KPIs, and quick actions per role.
Single source of truth consumed by app.py, dashboard pages, and role_banner.

GAP-W05: Workshop functional definition 2026-03-10.
Decision: Soft filtering with personalized landing page (no hard page blocking).
"""

from enum import Enum


class UserRole(str, Enum):
    """UI roles for the AMS platform.

    Consolidated from workshop roles:
    - Programador → merged into PLANNER
    - Operario/Inspector → merged into TECHNICIAN
    """

    MANAGER = "MANAGER"
    RELIABILITY_ENGINEER = "RELIABILITY_ENGINEER"
    PLANNER = "PLANNER"
    SUPERVISOR = "SUPERVISOR"
    TECHNICIAN = "TECHNICIAN"
    CONSULTANT = "CONSULTANT"
    RETIRED_EXPERT = "RETIRED_EXPERT"


DEFAULT_ROLE = UserRole.CONSULTANT

# --- Display names (i18n keys) ---

ROLE_DISPLAY_NAMES: dict[UserRole, str] = {
    UserRole.MANAGER: "role.manager",
    UserRole.RELIABILITY_ENGINEER: "role.reliability_engineer",
    UserRole.PLANNER: "role.planner",
    UserRole.SUPERVISOR: "role.supervisor",
    UserRole.TECHNICIAN: "role.technician",
    UserRole.CONSULTANT: "role.consultant",
    UserRole.RETIRED_EXPERT: "role.retired_expert",
}

ROLE_DESCRIPTIONS: dict[UserRole, str] = {
    UserRole.MANAGER: "role.desc_manager",
    UserRole.RELIABILITY_ENGINEER: "role.desc_reliability_engineer",
    UserRole.PLANNER: "role.desc_planner",
    UserRole.SUPERVISOR: "role.desc_supervisor",
    UserRole.TECHNICIAN: "role.desc_technician",
    UserRole.CONSULTANT: "role.desc_consultant",
    UserRole.RETIRED_EXPERT: "role.desc_retired_expert",
}

ROLE_ICONS: dict[UserRole, str] = {
    UserRole.MANAGER: "📊",
    UserRole.RELIABILITY_ENGINEER: "🔧",
    UserRole.PLANNER: "📋",
    UserRole.SUPERVISOR: "👷",
    UserRole.TECHNICIAN: "🔩",
    UserRole.CONSULTANT: "💼",
    UserRole.RETIRED_EXPERT: "🧑‍🔬",
}

# --- Page registry (all 27 pages) ---

PAGE_REGISTRY: list[dict] = [
    {"number": 1, "id": "hierarchy", "file": "1_hierarchy.py", "i18n_key": "hierarchy.title", "milestone": "M1"},
    {"number": 2, "id": "criticality", "file": "2_criticality.py", "i18n_key": "criticality.title", "milestone": "M1"},
    {"number": 3, "id": "fmea", "file": "3_fmea.py", "i18n_key": "fmea.title", "milestone": "M2"},
    {"number": 4, "id": "strategy", "file": "4_strategy.py", "i18n_key": "strategy.title", "milestone": "M2"},
    {"number": 5, "id": "analytics", "file": "5_analytics.py", "i18n_key": "analytics.title", "milestone": "Cross"},
    {"number": 6, "id": "sap_review", "file": "6_sap_review.py", "i18n_key": "sap.title", "milestone": "M4"},
    {"number": 7, "id": "overview", "file": "7_overview.py", "i18n_key": "overview.title", "milestone": "Cross"},
    {"number": 8, "id": "field_capture", "file": "8_field_capture.py", "i18n_key": "capture.title", "milestone": "M0"},
    {"number": 9, "id": "work_requests", "file": "9_work_requests.py", "i18n_key": "work_requests.title", "milestone": "M0"},
    {"number": 10, "id": "planner", "file": "10_planner.py", "i18n_key": "planner.title", "milestone": "M3"},
    {"number": 11, "id": "backlog", "file": "11_backlog.py", "i18n_key": "backlog.title", "milestone": "M3"},
    {"number": 12, "id": "scheduling", "file": "12_scheduling.py", "i18n_key": "scheduling.title", "milestone": "M3"},
    {"number": 13, "id": "reliability", "file": "13_reliability.py", "i18n_key": "reliability.title", "milestone": "M2"},
    {"number": 14, "id": "executive_dashboard", "file": "14_executive_dashboard.py", "i18n_key": "dashboard.title", "milestone": "Cross"},
    {"number": 15, "id": "reports_data", "file": "15_reports_data.py", "i18n_key": "reports.title", "milestone": "Cross"},
    {"number": 16, "id": "fmeca", "file": "16_fmeca.py", "i18n_key": "fmeca.title", "milestone": "M2"},
    {"number": 17, "id": "defect_elimination", "file": "17_defect_elimination.py", "i18n_key": "defect_elim.title", "milestone": "Cross"},
    {"number": 18, "id": "wizard", "file": "18_wizard.py", "i18n_key": "wizard.title", "milestone": "Setup"},
    {"number": 19, "id": "progress", "file": "19_progress.py", "i18n_key": "progress.title", "milestone": "Tracking"},
    {"number": 20, "id": "equipment_chat", "file": "20_equipment_chat.py", "i18n_key": "equipment_chat.title", "milestone": "Cross"},
    {"number": 21, "id": "deliverables", "file": "21_deliverables.py", "i18n_key": "deliverables.title", "milestone": "Tracking"},
    {"number": 22, "id": "execution_checklists", "file": "22_execution_checklists.py", "i18n_key": "execution_checklists.title", "milestone": "M3"},
    {"number": 23, "id": "troubleshooting", "file": "23_troubleshooting.py", "i18n_key": "troubleshooting.title", "milestone": "Cross"},
    {"number": 24, "id": "financial", "file": "24_financial.py", "i18n_key": "financial.title", "milestone": "Cross"},
    {"number": 25, "id": "expert_portal", "file": "25_expert_portal.py", "i18n_key": "expert_portal.title", "milestone": "Cross"},
    {"number": 26, "id": "expert_knowledge", "file": "26_expert_knowledge.py", "i18n_key": "expert_knowledge.title", "milestone": "Cross"},
    {"number": 27, "id": "workflow", "file": "27_workflow.py", "i18n_key": "workflow.title", "milestone": "Cross"},
]

# --- Role → Page mapping (primary = core tools, secondary = also useful) ---

ROLE_PAGE_MAP: dict[UserRole, dict[str, list[int]]] = {
    UserRole.MANAGER: {
        "primary": [7, 14, 5, 15, 21, 24],
        "secondary": [1, 2, 19, 26, 27],
    },
    UserRole.RELIABILITY_ENGINEER: {
        "primary": [2, 3, 4, 13, 16, 17, 23, 26],
        "secondary": [1, 5, 14, 15, 27],
    },
    UserRole.PLANNER: {
        "primary": [10, 11, 12, 6, 15],
        "secondary": [1, 5, 9, 14, 21, 22, 24],
    },
    UserRole.SUPERVISOR: {
        "primary": [11, 12, 8, 9, 22],
        "secondary": [7, 10, 15, 23],
    },
    UserRole.TECHNICIAN: {
        "primary": [8, 9, 22, 23],
        "secondary": [1, 7],
    },
    UserRole.CONSULTANT: {
        "primary": [18, 19, 21, 1, 2, 3, 4, 6, 26, 27],
        "secondary": [5, 7, 10, 13, 14, 15, 16, 17, 24],
    },
    UserRole.RETIRED_EXPERT: {
        "primary": [25],
        "secondary": [20],
    },
}

# --- Role → KPIs ---

ROLE_KPIS: dict[UserRole, list[dict]] = {
    UserRole.MANAGER: [
        {"key": "availability", "i18n_key": "kpi.availability", "target": 92, "unit": "%"},
        {"key": "budget_variance", "i18n_key": "kpi.budget_variance", "target": 0, "unit": "%"},
        {"key": "safety_incidents", "i18n_key": "kpi.safety_incidents", "target": 0, "unit": "count"},
        {"key": "production_compliance", "i18n_key": "kpi.production_compliance", "target": 95, "unit": "%"},
        {"key": "mtbf", "i18n_key": "kpi.mtbf", "target": None, "unit": "hours"},
    ],
    UserRole.RELIABILITY_ENGINEER: [
        {"key": "mtbf", "i18n_key": "kpi.mtbf", "target": None, "unit": "hours"},
        {"key": "mttr", "i18n_key": "kpi.mttr", "target": None, "unit": "hours"},
        {"key": "failure_rate", "i18n_key": "kpi.failure_rate", "target": None, "unit": "per_year"},
        {"key": "pm_compliance", "i18n_key": "kpi.pm_compliance", "target": 90, "unit": "%"},
        {"key": "bad_actor_count", "i18n_key": "kpi.bad_actor_count", "target": 0, "unit": "count"},
    ],
    UserRole.PLANNER: [
        {"key": "backlog_weeks", "i18n_key": "kpi.backlog_weeks", "target": 4, "unit": "weeks"},
        {"key": "schedule_adherence", "i18n_key": "kpi.schedule_adherence", "target": 90, "unit": "%"},
        {"key": "wo_completion", "i18n_key": "kpi.wo_completion", "target": 85, "unit": "%"},
        {"key": "cost_per_wo", "i18n_key": "kpi.cost_per_wo", "target": None, "unit": "USD"},
        {"key": "reactive_pct", "i18n_key": "kpi.reactive_pct", "target": 20, "unit": "%"},
    ],
    UserRole.SUPERVISOR: [
        {"key": "daily_completion", "i18n_key": "kpi.daily_completion", "target": 90, "unit": "%"},
        {"key": "resource_utilization", "i18n_key": "kpi.resource_utilization", "target": 85, "unit": "%"},
        {"key": "reactive_pct", "i18n_key": "kpi.reactive_pct", "target": 20, "unit": "%"},
        {"key": "rework_rate", "i18n_key": "kpi.rework_rate", "target": 5, "unit": "%"},
    ],
    UserRole.TECHNICIAN: [
        {"key": "tasks_completed", "i18n_key": "kpi.tasks_completed", "target": None, "unit": "count"},
        {"key": "quality_score", "i18n_key": "kpi.quality_score", "target": 85, "unit": "%"},
        {"key": "safety_incidents", "i18n_key": "kpi.safety_incidents", "target": 0, "unit": "count"},
    ],
    UserRole.CONSULTANT: [
        {"key": "wo_completion", "i18n_key": "kpi.wo_completion", "target": 85, "unit": "%"},
        {"key": "pm_compliance", "i18n_key": "kpi.pm_compliance", "target": 90, "unit": "%"},
        {"key": "backlog_weeks", "i18n_key": "kpi.backlog_weeks", "target": 4, "unit": "weeks"},
        {"key": "availability", "i18n_key": "kpi.availability", "target": 92, "unit": "%"},
    ],
    UserRole.RETIRED_EXPERT: [
        {"key": "consultations_completed", "i18n_key": "kpi.consultations_completed", "target": None, "unit": "count"},
        {"key": "avg_response_time", "i18n_key": "kpi.avg_response_time", "target": None, "unit": "minutes"},
        {"key": "contributions_promoted", "i18n_key": "kpi.contributions_promoted", "target": None, "unit": "count"},
    ],
}

# --- Role → Quick Actions ---

ROLE_QUICK_ACTIONS: dict[UserRole, list[dict]] = {
    UserRole.MANAGER: [
        {"label_key": "role.action.view_kpis", "page": 14},
        {"label_key": "role.action.view_reports", "page": 15},
        {"label_key": "role.action.plant_overview", "page": 7},
    ],
    UserRole.RELIABILITY_ENGINEER: [
        {"label_key": "role.action.run_fmeca", "page": 16},
        {"label_key": "role.action.view_strategy", "page": 4},
        {"label_key": "role.action.run_rca", "page": 17},
    ],
    UserRole.PLANNER: [
        {"label_key": "role.action.manage_backlog", "page": 11},
        {"label_key": "role.action.view_schedule", "page": 12},
        {"label_key": "role.action.export_sap", "page": 6},
    ],
    UserRole.SUPERVISOR: [
        {"label_key": "role.action.daily_program", "page": 12},
        {"label_key": "role.action.assign_work", "page": 11},
        {"label_key": "role.action.capture_work", "page": 8},
    ],
    UserRole.TECHNICIAN: [
        {"label_key": "role.action.capture_work", "page": 8},
        {"label_key": "role.action.view_instructions", "page": 9},
    ],
    UserRole.CONSULTANT: [
        {"label_key": "role.action.start_wizard", "page": 18},
        {"label_key": "role.action.view_progress", "page": 19},
        {"label_key": "role.action.track_deliverables", "page": 21},
        {"label_key": "role.action.view_kpis", "page": 14},
    ],
    UserRole.RETIRED_EXPERT: [
        {"label_key": "role.action.open_portal", "page": 25},
    ],
}

# --- Lookup index for fast page queries ---

_PAGE_BY_NUMBER: dict[int, dict] = {p["number"]: p for p in PAGE_REGISTRY}
_VALID_PAGE_NUMBERS: set[int] = {p["number"] for p in PAGE_REGISTRY}


def get_page_info(page_number: int) -> dict | None:
    """Get page metadata by page number."""
    return _PAGE_BY_NUMBER.get(page_number)


def get_role_pages(role: UserRole) -> dict[str, list[int]]:
    """Get primary and secondary page numbers for a role."""
    return ROLE_PAGE_MAP.get(role, {"primary": [], "secondary": []})


def get_role_kpis(role: UserRole) -> list[dict]:
    """Get KPI definitions for a role."""
    return ROLE_KPIS.get(role, [])


def get_role_quick_actions(role: UserRole) -> list[dict]:
    """Get quick action buttons for a role."""
    return ROLE_QUICK_ACTIONS.get(role, [])


def is_primary_page(role: UserRole, page_number: int) -> bool:
    """Check if a page is primary for the given role."""
    pages = ROLE_PAGE_MAP.get(role, {})
    return page_number in pages.get("primary", [])


def is_relevant_page(role: UserRole, page_number: int) -> bool:
    """Check if a page is either primary or secondary for the given role."""
    pages = ROLE_PAGE_MAP.get(role, {})
    return page_number in pages.get("primary", []) or page_number in pages.get("secondary", [])
