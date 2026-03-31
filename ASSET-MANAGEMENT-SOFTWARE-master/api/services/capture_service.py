"""Capture service — processes field captures into structured work requests.

G-08 pipeline:
  1. FieldCaptureProcessor (deterministic: FM keywords, priority, spare parts)
  2. Apply pre-computed ImageAnalysis if passed in data (analyzed via POST /media/analyze-image)
  3. LLMCaptureEnhancer (Claude Haiku) — if equipment confidence < 0.7 or no FM detected
"""

import json
import logging
from datetime import datetime
from sqlalchemy.orm import Session

from api.database.models import FieldCaptureModel, WorkRequestModel
from api.services.audit_service import log_action
from tools.processors.field_capture_processor import FieldCaptureProcessor
from tools.models.schemas import FieldCaptureInput, CaptureType, Language, ImageAnalysis

logger = logging.getLogger(__name__)


def process_capture(db: Session, data: dict) -> dict:
    """Process a field capture: persist raw capture, run processor, persist work request.

    data keys:
      technician_id, technician_name, capture_type, language,
      raw_voice_text, raw_text_input, equipment_tag_manual, location_hint,
      image_analysis_json (optional): pre-computed ImageAnalysis as JSON string or dict (G-08)
      gps_lat, gps_lon (optional): GPS coordinates from device (G-08)
    """
    # G-08: When only pre-computed image_analysis_json is provided (no raw bytes),
    # derive a placeholder text so FieldCaptureInput validation passes.
    raw_voice = data.get("raw_voice_text")
    raw_text = data.get("raw_text_input")
    image_analysis_raw_str = data.get("image_analysis_json")

    if not raw_text and not raw_voice and image_analysis_raw_str:
        try:
            ia_preview = json.loads(image_analysis_raw_str) if isinstance(image_analysis_raw_str, str) else image_analysis_raw_str
            component = ia_preview.get("component_identified") or "component"
            anomalies = ", ".join(ia_preview.get("anomalies_detected") or ["anomaly detected"])
            raw_text = f"[Image analysis] {component}: {anomalies}"
        except Exception:
            raw_text = "[Image analysis submitted]"

    requested_type_str = data.get("capture_type", "TEXT")
    # IMAGE/VOICE+IMAGE captures send pre-analysed JSON (no actual image bytes in images=[]).
    # Downgrade to TEXT/VOICE so FieldCaptureInput validator passes.
    if requested_type_str in ("IMAGE", "VOICE+IMAGE"):
        effective_type = CaptureType.VOICE if raw_voice else CaptureType.TEXT
    else:
        effective_type = CaptureType(requested_type_str)

    capture_input = FieldCaptureInput(
        timestamp=datetime.now(),
        technician_id=data.get("technician_id", "UNKNOWN"),
        technician_name=data.get("technician_name", "Unknown"),
        capture_type=effective_type,
        language_detected=Language(data.get("language", "en")),
        raw_voice_text=raw_voice,
        raw_text_input=raw_text,
        images=[],
        equipment_tag_manual=data.get("equipment_tag_manual"),
        location_hint=data.get("location_hint"),
    )

    # G-08: Parse pre-computed image analysis if provided
    pre_image_analysis: ImageAnalysis | None = None
    image_analysis_raw = image_analysis_raw_str
    if image_analysis_raw:
        try:
            if isinstance(image_analysis_raw, str):
                image_analysis_raw = json.loads(image_analysis_raw)
            pre_image_analysis = ImageAnalysis.model_validate(image_analysis_raw)
        except Exception as exc:
            logger.warning("Could not parse image_analysis_json: %s", exc)

    # G-08: GPS coordinates
    gps_lat = data.get("gps_lat")
    gps_lon = data.get("gps_lon")

    # Persist raw capture — store the original requested type, not the effective type
    capture_model = FieldCaptureModel(
        capture_id=capture_input.capture_id,
        technician_id=capture_input.technician_id,
        capture_type=requested_type_str,
        language=capture_input.language_detected.value,
        raw_text=capture_input.raw_text_input,
        raw_voice_text=capture_input.raw_voice_text,
        images=None,
        equipment_tag_manual=capture_input.equipment_tag_manual,
        location_hint=capture_input.location_hint,
        created_at=datetime.now(),
        # G-08 fields (nullable — backward compat)
        gps_lat=gps_lat,
        gps_lon=gps_lon,
        image_analysis_result=(
            json.dumps(pre_image_analysis.model_dump(mode="json"))
            if pre_image_analysis else None
        ),
    )
    db.add(capture_model)
    log_action(db, "field_capture", capture_model.capture_id, "CREATE")

    # Build equipment registry from hierarchy nodes
    from api.database.models import HierarchyNodeModel
    nodes = db.query(HierarchyNodeModel).filter(
        HierarchyNodeModel.node_type == "EQUIPMENT"
    ).all()
    equipment_registry = [
        {
            "equipment_id": n.node_id,
            "tag": n.tag or n.code,
            "description": n.name,
            "description_fr": n.name_fr or "",
            "aliases": [],
        }
        for n in nodes
    ]

    # Step 1: Deterministic processing
    processor = FieldCaptureProcessor(equipment_registry)
    wr = processor.process(capture_input)

    # Step 2: Apply pre-computed image analysis
    if pre_image_analysis:
        wr = wr.model_copy(update={"image_analysis": pre_image_analysis})

    # Step 3: LLM enhancement for low-confidence results (G-08 D-3)
    try:
        from tools.processors.llm_capture_enhancer import get_llm_enhancer
        enhancer = get_llm_enhancer()
        if enhancer.needs_enhancement(wr):
            wr = enhancer.enhance(capture_input, wr, pre_image_analysis)
            logger.info(
                "LLM enhancement applied: capture=%s, new_confidence=%.2f",
                capture_input.capture_id,
                wr.equipment_identification.confidence_score,
            )
    except Exception as exc:
        logger.warning("LLM enhancement unavailable (continuing with deterministic result): %s", exc)

    # Persist work request
    wr_model = WorkRequestModel(
        request_id=wr.request_id,
        source_capture_id=capture_input.capture_id,
        status=wr.status.value,
        equipment_id=wr.equipment_identification.equipment_id,
        equipment_tag=wr.equipment_identification.equipment_tag,
        equipment_confidence=wr.equipment_identification.confidence_score,
        resolution_method=wr.equipment_identification.resolution_method.value,
        problem_description=wr.problem_description.model_dump(mode="json"),
        ai_classification=wr.ai_classification.model_dump(mode="json"),
        spare_parts=[sp.model_dump(mode="json") for sp in wr.spare_parts_suggested],
        image_analysis=wr.image_analysis.model_dump(mode="json") if wr.image_analysis else None,
        validation=wr.validation.model_dump(mode="json"),
        created_at=datetime.now(),
    )
    db.add(wr_model)
    log_action(db, "work_request", wr_model.request_id, "CREATE")
    db.commit()

    return {
        "capture_id": capture_input.capture_id,
        "work_request_id": wr.request_id,
        "status": wr.status.value,
        "equipment_tag": wr.equipment_identification.equipment_tag,
        "equipment_confidence": wr.equipment_identification.confidence_score,
        "resolution_method": wr.equipment_identification.resolution_method.value,
        "failure_mode_detected": wr.problem_description.failure_mode_detected,
        "failure_mode_code": wr.problem_description.failure_mode_code,
        "priority_suggested": wr.ai_classification.priority_suggested.value,
        "spare_parts_count": len(wr.spare_parts_suggested),
        "image_analysis": wr.image_analysis.model_dump(mode="json") if wr.image_analysis else None,
    }


def get_capture(db: Session, capture_id: str) -> FieldCaptureModel | None:
    return db.query(FieldCaptureModel).filter(
        FieldCaptureModel.capture_id == capture_id
    ).first()


def list_captures(db: Session) -> list[FieldCaptureModel]:
    return db.query(FieldCaptureModel).order_by(FieldCaptureModel.created_at.desc()).all()


def find_nearby_equipment(
    db: Session,
    lat: float,
    lon: float,
    radius_m: float = 100.0,
) -> list[dict]:
    """Return equipment nodes within *radius_m* metres of (lat, lon).

    Uses the ProximityMatcher (haversine) on EQUIPMENT-level hierarchy nodes
    that have GPS coordinates stored in the database.

    Returns a list of dicts ready for JSON serialisation, sorted by distance.
    """
    from api.database.models import HierarchyNodeModel
    from tools.processors.equipment_proximity_matcher import get_proximity_matcher

    # Only query nodes with GPS coordinates
    nodes = (
        db.query(HierarchyNodeModel)
        .filter(
            HierarchyNodeModel.node_type == "EQUIPMENT",
            HierarchyNodeModel.gps_lat.isnot(None),
            HierarchyNodeModel.gps_lon.isnot(None),
        )
        .all()
    )

    registry = [
        {
            "equipment_id": n.node_id,
            "equipment_tag": n.tag or n.code or n.node_id,
            "name": n.name,
            "gps_lat": n.gps_lat,
            "gps_lon": n.gps_lon,
        }
        for n in nodes
    ]

    matcher = get_proximity_matcher()
    matches = matcher.find_nearby(lat, lon, registry, radius_m=radius_m)
    return [
        {
            "equipment_tag": m.equipment_tag,
            "equipment_id": m.equipment_id,
            "name": m.name,
            "distance_m": m.distance_m,
            "confidence": m.confidence,
        }
        for m in matches
    ]
