"""Database seeding — populates SQLite with synthetic phosphate data.

Uses SyntheticDataGenerator (existing) to create realistic OCP data,
then inserts into the database via SQLAlchemy models.
Also generates SAP mock JSON files.
"""

import uuid
from datetime import date, datetime

from sqlalchemy.orm import Session

from api.database.connection import create_all_tables, SessionLocal
from api.database.models import (
    PlantModel, HierarchyNodeModel, WorkOrderModel,
    FailureModeModel, FunctionModel, FunctionalFailureModel,
    AuditLogModel,
    WorkforceModel, InventoryItemModel, ShutdownCalendarModel,
    WorkRequestModel, FieldCaptureModel, BacklogItemModel,
    ExpertCardModel, ExpertConsultationModel, ExpertContributionModel,
)
from tools.generators.synthetic_data import SyntheticDataGenerator
from sap_mock.generate_mock_data import generate_all as generate_sap_mock


def seed_all(db: Session) -> dict:
    """Seed the database with synthetic data. Returns statistics."""
    gen = SyntheticDataGenerator(seed=42)

    # 1. Generate hierarchy
    nodes = gen.generate_plant_hierarchy("OCP-JFC1", "Jorf Fertilizer Complex 1")

    # 2. Create plant
    plant = db.query(PlantModel).filter(PlantModel.plant_id == "OCP-JFC1").first()
    if not plant:
        plant = PlantModel(plant_id="OCP-JFC1", name="Jorf Fertilizer Complex 1", name_fr="Complexe d'engrais de Jorf 1", location="El Jadida, Morocco")
        db.add(plant)
        db.flush()

    # 3. Insert hierarchy nodes
    node_count = 0
    for n in nodes:
        existing = db.query(HierarchyNodeModel).filter(HierarchyNodeModel.node_id == n["node_id"]).first()
        if existing:
            continue
        obj = HierarchyNodeModel(
            node_id=n["node_id"],
            node_type=n["node_type"],
            name=n["name"],
            name_fr=n.get("name_fr", ""),
            code=n.get("code", ""),
            parent_node_id=n.get("parent_node_id"),
            level=n["level"],
            plant_id="OCP-JFC1",
            tag=n.get("tag"),
            criticality=n.get("criticality"),
            status="ACTIVE",
            metadata_json={
                "manufacturer": n.get("manufacturer"),
                "power_kw": n.get("power_kw"),
                "weight_kg": n.get("weight_kg"),
            } if n.get("manufacturer") else None,
        )
        db.add(obj)
        node_count += 1

    db.flush()

    # 4. Generate failure modes and insert
    failure_modes = gen.generate_failure_modes(nodes)
    fm_count = 0

    # Step A: create functions (depends on hierarchy_nodes)
    func_map = {}  # fm_id -> func_id
    for fm in failure_modes:
        func_id = str(uuid.uuid4())
        func = FunctionModel(
            function_id=func_id,
            node_id=fm["node_id"],
            function_type="PRIMARY",
            description=f"Primary function of {fm['mi_name']}",
            description_fr=f"Fonction principale de {fm['mi_name']}",
            status="DRAFT",
        )
        db.add(func)
        func_map[fm["failure_mode_id"]] = func_id

    db.flush()

    # Step B: create functional failures (depends on functions)
    fm_ff_map = {}  # fm_id -> ff_id
    for fm in failure_modes:
        ff_id = str(uuid.uuid4())
        ff = FunctionalFailureModel(
            failure_id=ff_id,
            function_id=func_map[fm["failure_mode_id"]],
            failure_type="TOTAL",
            description=f"Failure of {fm['mi_name']}",
            description_fr=f"Défaillance de {fm['mi_name']}",
        )
        db.add(ff)
        fm_ff_map[fm["failure_mode_id"]] = ff_id

    db.flush()

    # Step C: create failure modes (depends on functional failures)
    for fm in failure_modes:
        fm_obj = FailureModeModel(
            failure_mode_id=fm["failure_mode_id"],
            functional_failure_id=fm_ff_map[fm["failure_mode_id"]],
            what=fm["what"],
            mechanism=fm["mechanism"],
            cause=fm["cause"],
            failure_pattern=fm.get("failure_pattern"),
            failure_consequence=fm.get("failure_consequence", "EVIDENT_OPERATIONAL"),
            is_hidden=fm.get("is_hidden", False),
            strategy_type=fm.get("strategy_type", "CONDITION_BASED"),
            failure_effect={"evidence": f"{fm['what']} shows signs of {fm['mechanism'].lower()}"},
        )
        db.add(fm_obj)
        fm_count += 1

    db.flush()

    # 5. Generate work order history
    work_orders = gen.generate_work_order_history(nodes, months=24)
    wo_count = 0
    for wo in work_orders:
        existing = db.query(WorkOrderModel).filter(WorkOrderModel.work_order_id == wo["work_order_id"]).first()
        if existing:
            continue
        obj = WorkOrderModel(
            work_order_id=wo["work_order_id"],
            order_type=wo["order_type"],
            equipment_id=wo["equipment_id"],
            equipment_tag=wo.get("equipment_tag", ""),
            priority=wo["priority"],
            status=wo["status"],
            created_date=date.fromisoformat(wo["created_date"]),
            actual_duration_hours=wo.get("actual_duration_hours"),
            description=wo.get("description", ""),
        )
        db.add(obj)
        wo_count += 1

    # 6. Audit log entry
    db.add(AuditLogModel(
        entity_type="system", entity_id="seed",
        action="SEED", payload={"nodes": node_count, "failure_modes": fm_count, "work_orders": wo_count},
        user="system", timestamp=datetime.now(),
    ))

    db.flush()

    # 6b. G-08 D-5: Assign mock GPS coordinates to EQUIPMENT nodes (OCP-JFC area: ~32.3°N, -6.8°W)
    _seed_gps_coordinates(db)
    db.flush()

    # 7. Seed M1-3 data: workforce, inventory, shutdowns, work requests, backlog
    m13_stats = _seed_m13_data(db, nodes)

    db.commit()

    # 8. Generate SAP mock JSON files
    sap_stats = generate_sap_mock()

    stats = gen.get_statistics(nodes)
    return {
        "status": "seeded",
        "hierarchy_nodes": node_count,
        "failure_modes": fm_count,
        "work_orders": wo_count,
        "total_hierarchy_nodes": stats["total_nodes"],
        "node_types": stats["by_type"],
        "sap_mock_files": sap_stats,
        **m13_stats,
    }


def _seed_m13_data(db: Session, nodes: list[dict]) -> dict:
    """Seed M1-3 data: workforce, inventory, shutdowns, work requests, backlog."""
    from datetime import timedelta
    import random
    random.seed(42)

    # ── Workforce (25 workers with GAP-W09 competency data) ──
    specialties = ["MECHANICAL", "ELECTRICAL", "INSTRUMENTATION", "WELDING", "GENERAL"]
    shifts = ["MORNING", "AFTERNOON", "NIGHT"]
    equipment_types = ["SAG_MILL", "CONVEYOR", "CRUSHER", "PUMP", "MOTOR"]

    # Competency distribution per 5-worker group: 1A, 2B, 2C
    level_pattern = ["A", "B", "B", "C", "C"]
    experience_ranges = {"A": (10, 20), "B": (5, 10), "C": (1, 5)}
    cert_map = {
        "A": ["SAFETY_ADV", "CONFINED_SPACE", "HOT_WORK"],
        "B": ["SAFETY_ADV", "CONFINED_SPACE"],
        "C": ["SAFETY_BASIC"],
    }
    expertise_count = {"A": 4, "B": 2, "C": 1}

    wf_count = 0
    for i in range(25):
        spec = specialties[i % len(specialties)]
        shift = shifts[i % len(shifts)]
        level = level_pattern[i % len(level_pattern)]
        yrs_lo, yrs_hi = experience_ranges[level]
        yrs = random.randint(yrs_lo, yrs_hi)

        # Equipment expertise: A knows more types than C
        n_equip = expertise_count[level]
        equip_exp = random.sample(equipment_types, min(n_equip, len(equipment_types)))

        # Build competency matrix
        competencies = []
        for eq in equip_exp:
            # Primary specialty at assigned level
            competencies.append({
                "specialty": spec,
                "equipment_type": eq,
                "level": level,
                "certified": level == "A",
            })

        db.add(WorkforceModel(
            worker_id=f"WKR-{i+1:03d}",
            name=f"Technician {spec.title()} {i+1}",
            specialty=spec,
            shift=shift,
            plant_id="OCP-JFC1",
            available=i % 5 != 0,  # 80% available
            certifications=cert_map[level] + [spec],
            competency_level=level,
            years_experience=yrs,
            equipment_expertise=equip_exp,
            safety_training_current=True,
            competencies=competencies,
        ))
        wf_count += 1

    # ── Inventory (50 items) ──
    inv_count = 0
    component_types = ["Bearing", "Seal", "Impeller", "Filter", "Belt", "Motor", "Coupling", "Liner", "Gearbox", "Valve"]
    for i in range(50):
        comp = component_types[i % len(component_types)]
        qty = random.randint(0, 20)
        reserved = min(random.randint(0, 3), qty)
        db.add(InventoryItemModel(
            material_code=f"MAT-{comp[:3].upper()}-{i+1:03d}",
            warehouse_id="WH-JFC1",
            description=f"{comp} replacement part #{i+1}",
            quantity_on_hand=qty,
            quantity_reserved=reserved,
            quantity_available=qty - reserved,
            min_stock=2,
            reorder_point=5,
            last_movement_date=date.today() - timedelta(days=random.randint(1, 60)),
        ))
        inv_count += 1

    # ── Shutdown Calendar (6 windows) ──
    sd_count = 0
    for i in range(6):
        start = date.today() + timedelta(days=30 * (i + 1))
        is_major = i % 3 == 0
        duration_days = 3 if is_major else 1
        db.add(ShutdownCalendarModel(
            shutdown_id=f"SD-JFC1-{i+1:02d}",
            plant_id="OCP-JFC1",
            start_date=start,
            end_date=start + timedelta(days=duration_days),
            shutdown_type="MAJOR_20H_PLUS" if is_major else "MINOR_8H",
            areas=["BRY-SAG", "BRY-CYC"] if is_major else ["BRY-SAG"],
            description=f"{'Major' if is_major else 'Minor'} shutdown #{i+1}",
        ))
        sd_count += 1

    db.flush()

    # ── Work Requests (20) ──
    equipment_nodes = [n for n in nodes if n["node_type"] == "EQUIPMENT"]
    statuses = ["DRAFT", "PENDING_VALIDATION", "VALIDATED", "DRAFT", "PENDING_VALIDATION"]
    wr_count = 0
    wr_ids = []
    for i in range(min(20, max(len(equipment_nodes) * 2, 5))):
        eq = equipment_nodes[i % len(equipment_nodes)] if equipment_nodes else {"node_id": "EQ-DEFAULT", "tag": "DEFAULT-TAG"}
        st = statuses[i % len(statuses)]
        wr_id = f"WR-SEED-{i+1:03d}"
        wr_ids.append((wr_id, st, eq))

        # Create capture
        cap_id = f"CAP-SEED-{i+1:03d}"
        db.add(FieldCaptureModel(
            capture_id=cap_id,
            technician_id=f"TECH-{(i % 10) + 1:03d}",
            capture_type="TEXT",
            language="en",
            raw_text=f"Equipment {eq.get('tag', 'UNKNOWN')} showing signs of wear on bearing",
            created_at=datetime.now() - timedelta(days=random.randint(1, 30)),
        ))

        db.add(WorkRequestModel(
            request_id=wr_id,
            source_capture_id=cap_id,
            status=st,
            equipment_id=eq.get("node_id", "UNKNOWN"),
            equipment_tag=eq.get("tag", eq.get("code", "UNKNOWN")),
            equipment_confidence=0.85,
            resolution_method="EXACT_MATCH",
            problem_description={
                "original_text": f"Bearing wear detected on {eq.get('tag', 'UNKNOWN')}",
                "structured_description": f"Affected component: Bearing. Failure mechanism: WEARS.",
                "structured_description_fr": f"Composant affecté: Roulement. Mécanisme: USURE.",
            },
            ai_classification={
                "work_order_type": "PM03_CORRECTIVE" if i % 3 == 0 else "PM02_PREVENTIVE",
                "priority_suggested": ["3_NORMAL", "2_URGENT", "4_PLANNED"][i % 3],
                "priority_justification": "AI classification based on equipment criticality",
                "estimated_duration_hours": [4.0, 8.0, 2.0][i % 3],
                "required_specialties": ["MECHANICAL"],
                "safety_flags": ["SAFETY"] if i % 7 == 0 else [],
            },
            spare_parts=[],
            created_at=datetime.now() - timedelta(days=random.randint(1, 30)),
        ))
        wr_count += 1

    db.flush()

    # ── Backlog Items (from validated work requests) ──
    bl_count = 0
    for wr_id, st, eq in wr_ids:
        if st == "VALIDATED":
            db.add(BacklogItemModel(
                backlog_id=f"BL-{wr_id}",
                work_request_id=wr_id,
                equipment_id=eq.get("node_id", "UNKNOWN"),
                equipment_tag=eq.get("tag", eq.get("code", "UNKNOWN")),
                priority="3_NORMAL",
                wo_type="PM02",
                status="AWAITING_APPROVAL",
                estimated_hours=4.0,
                specialties=["MECHANICAL"],
                materials_ready=random.choice([True, True, False]),
                shutdown_required=random.choice([True, False, False]),
                age_days=random.randint(1, 45),
                created_at=datetime.now() - timedelta(days=random.randint(1, 30)),
            ))
            bl_count += 1

    # ── Expert Knowledge (GAP-W13) ──────────────────────────────────
    expert_count = _seed_expert_knowledge(db)

    return {
        "workforce": wf_count,
        "inventory_items": inv_count,
        "shutdown_windows": sd_count,
        "work_requests": wr_count,
        "backlog_items": bl_count,
        "experts": expert_count,
    }


def _seed_expert_knowledge(db: Session) -> int:
    """Seed 3 retired experts + 2 consultations + 1 contribution for GAP-W13 demo."""
    from datetime import date as _date

    experts = [
        {
            "expert_id": "EXP-001",
            "user_id": "retired.hassan@ocp.ma",
            "name": "Hassan Benali",
            "role": "RETIRED_EXPERT",
            "plant_id": "OCP-JFC1",
            "domains": ["rotating-equipment", "vibration-analysis"],
            "equipment_expertise": ["PUMP", "COMPRESSOR", "TURBINE"],
            "certifications": ["ISO-18436-2", "API-686"],
            "years_experience": 32,
            "resolution_count": 12,
            "last_active": datetime(2025, 6, 15),
            "contact_method": "retired.hassan@ocp.ma",
            "languages": ["fr", "ar"],
            "is_retired": True,
            "retired_at": _date(2025, 1, 1),
            "hourly_rate_usd": 85.0,
            "availability_hours": "Mon-Fri 9-12",
            "preferred_contact": "EMAIL",
        },
        {
            "expert_id": "EXP-002",
            "user_id": "retired.fatima@ocp.ma",
            "name": "Fatima Zahraoui",
            "role": "RETIRED_EXPERT",
            "plant_id": "OCP-JFC1",
            "domains": ["static-equipment", "pressure-vessels", "heat-exchangers"],
            "equipment_expertise": ["HEAT_EXCHANGER", "VESSEL", "PIPING"],
            "certifications": ["API-580", "ASME-VIII"],
            "years_experience": 28,
            "resolution_count": 8,
            "last_active": datetime(2025, 9, 20),
            "contact_method": "retired.fatima@ocp.ma",
            "languages": ["fr", "en"],
            "is_retired": True,
            "retired_at": _date(2025, 6, 1),
            "hourly_rate_usd": 75.0,
            "availability_hours": "Tue-Thu 10-14",
            "preferred_contact": "IN_APP",
        },
        {
            "expert_id": "EXP-003",
            "user_id": "retired.youssef@ocp.ma",
            "name": "Youssef Kadiri",
            "role": "RETIRED_EXPERT",
            "plant_id": "OCP-JFC1",
            "domains": ["electrical", "instrumentation", "control-systems"],
            "equipment_expertise": ["MOTOR", "TRANSFORMER", "PLC"],
            "certifications": ["IEC-62061", "ISA-84"],
            "years_experience": 25,
            "resolution_count": 5,
            "last_active": datetime(2025, 11, 1),
            "contact_method": "retired.youssef@ocp.ma",
            "languages": ["fr", "en", "ar"],
            "is_retired": True,
            "retired_at": _date(2025, 10, 1),
            "hourly_rate_usd": 70.0,
            "availability_hours": "Mon-Wed 14-17",
            "preferred_contact": "IN_APP",
        },
    ]

    count = 0
    for e in experts:
        existing = db.query(ExpertCardModel).filter_by(expert_id=e["expert_id"]).first()
        if existing:
            continue
        db.add(ExpertCardModel(**e))
        count += 1

    db.flush()

    # ── 2 Consultations ──
    import json as _json
    consultations = [
        dict(
            consultation_id="CONS-SEED-001",
            session_id="SESS-DEMO-001",
            expert_id="EXP-001",
            plant_id="OCP-JFC1",
            equipment_type_id="PUMP",
            equipment_tag="P-1001A",
            ai_suggestion="FM-07 (Erosion-Wear) at 0.38 confidence",
            language="fr",
            status="RESPONDED",
            expert_guidance=(
                "Après analyse: problème d'alignement couplage + érosion impulseur. "
                "Codes FM: FM-15 (Fatigue-Misalignment), FM-07 (Erosion-Wear). "
                "Étapes: 1) Mesure alignement laser. 2) Inspection impulseur. "
                "Action corrective: Re-alignement + remplacement impulseur dans 72h."
            ),
            expert_fm_codes=_json.dumps(["FM-15", "FM-07"]),
            expert_confidence=0.92,
            token="tok_demo_001_do_not_use",
            token_expires_at=datetime(2026, 12, 31),
            requested_at=datetime(2026, 3, 1),
            responded_at=datetime(2026, 3, 2),
        ),
        dict(
            consultation_id="CONS-SEED-002",
            session_id="SESS-DEMO-002",
            expert_id="EXP-002",
            plant_id="OCP-JFC1",
            equipment_type_id="HEAT_EXCHANGER",
            equipment_tag="HE-2201",
            ai_suggestion="FM-03 (Fouling-Scaling) at 0.45 confidence",
            language="fr",
            status="REQUESTED",
            token="tok_demo_002_do_not_use",
            token_expires_at=datetime(2026, 12, 31),
            requested_at=datetime(2026, 3, 10),
        ),
    ]

    for c in consultations:
        existing = db.query(ExpertConsultationModel).filter_by(
            consultation_id=c["consultation_id"]
        ).first()
        if existing:
            continue
        db.add(ExpertConsultationModel(**c))

    db.flush()

    # ── 1 Contribution (from responded consultation) ──
    contrib_existing = db.query(ExpertContributionModel).filter_by(
        contribution_id="CONTRIB-SEED-001"
    ).first()
    if not contrib_existing:
        db.add(ExpertContributionModel(
            contribution_id="CONTRIB-SEED-001",
            consultation_id="CONS-SEED-001",
            expert_id="EXP-001",
            equipment_type_id="PUMP",
            fm_codes=_json.dumps(["FM-15", "FM-07"]),
            symptom_descriptions=_json.dumps(["Vibration haute fréquence", "Bruit de cavitation"]),
            diagnostic_steps=_json.dumps([
                "Mesure alignement laser (tolérance <0.05mm)",
                "Inspection visuelle de l'impulseur",
                "Test hydraulique à débit nominal",
            ]),
            corrective_actions=_json.dumps([
                "Re-alignement couplage flexible",
                "Remplacement impulseur érodé",
            ]),
            tips="Toujours vérifier l'alignement avant remplacement de pièces",
            status="PROMOTED",
            validated_by="RELIABILITY-ENGINEER",
            promoted_targets=_json.dumps(["symptom-catalog", "manual", "memory"]),
            created_at=datetime(2026, 3, 2),
            validated_at=datetime(2026, 3, 3),
        ))

    db.flush()
    return count


def _seed_gps_coordinates(db: Session) -> None:
    """Assign mock GPS coordinates to EQUIPMENT nodes — G-08 D-5.

    OCP Jorf Fertilizer Complex 1 is located near El Jadida, Morocco
    (approx. 33.26°N, -8.51°W). We spread equipment nodes across a 500m
    radius for realistic proximity-matching demo data. Coordinates use
    a deterministic offset pattern so tests remain reproducible.

    Only updates nodes that do NOT already have GPS data (idempotent).
    """
    import math as _math
    from api.database.models import HierarchyNodeModel

    # Centre of OCP-JFC1 plant: El Jadida area
    BASE_LAT = 33.2600
    BASE_LON = -8.5100

    # 1 degree ≈ 111 km → 500 m ≈ 0.0045°
    SPREAD_DEG = 0.0045  # ~500 m spread

    equipment_nodes = (
        db.query(HierarchyNodeModel)
        .filter(
            HierarchyNodeModel.node_type == "EQUIPMENT",
            HierarchyNodeModel.gps_lat.is_(None),
        )
        .order_by(HierarchyNodeModel.node_id)
        .all()
    )

    for idx, node in enumerate(equipment_nodes):
        # Distribute evenly around the base using an Archimedean-spiral pattern
        angle = idx * 2.399963  # golden angle in radians
        radius_frac = _math.sqrt(idx + 1) / _math.sqrt(max(len(equipment_nodes), 1))
        offset_lat = SPREAD_DEG * radius_frac * _math.cos(angle)
        offset_lon = SPREAD_DEG * radius_frac * _math.sin(angle) / _math.cos(_math.radians(BASE_LAT))

        node.gps_lat = round(BASE_LAT + offset_lat, 7)
        node.gps_lon = round(BASE_LON + offset_lon, 7)


def main():
    """CLI entry point: python -m api.seed"""
    create_all_tables()
    db = SessionLocal()
    try:
        result = seed_all(db)
        print(f"Database seeded successfully:")
        for k, v in result.items():
            print(f"  {k}: {v}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
