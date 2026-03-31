"""Tests for tools/processors/llm_capture_enhancer.py — G-08 D-3."""

import json
from datetime import datetime
from unittest.mock import MagicMock, patch
import pytest

from tools.processors.llm_capture_enhancer import LLMCaptureEnhancer, CONFIDENCE_THRESHOLD
from tools.models.schemas import (
    AIClassification,
    CaptureType,
    EquipmentIdentification,
    FieldCaptureInput,
    ImageAnalysis,
    Language,
    Priority,
    ProblemDescription,
    ResolutionMethod,
    StructuredWorkRequest,
    Validation,
    VisualSeverity,
    WorkOrderType,
    WorkRequestStatus,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

def _make_enhancer(api_key="sk-ant-test") -> LLMCaptureEnhancer:
    with patch("anthropic.Anthropic"):
        return LLMCaptureEnhancer(api_key=api_key)


def _capture(voice_text="Pompe centrifuge en panne", lang="fr") -> FieldCaptureInput:
    return FieldCaptureInput(
        timestamp=datetime.now(),
        technician_id="TECH-001",
        technician_name="Ahmed",
        capture_type=CaptureType.VOICE,
        language_detected=Language.FR,
        raw_voice_text=voice_text,
    )


def _work_request(
    equipment_confidence: float = 0.4,
    failure_mode_code: str | None = None,
    equipment_tag: str = "UNKNOWN",
) -> StructuredWorkRequest:
    return StructuredWorkRequest(
        source_capture_id="cap-001",
        created_at=datetime.now(),
        status=WorkRequestStatus.DRAFT,
        equipment_identification=EquipmentIdentification(
            equipment_id="eq-001",
            equipment_tag=equipment_tag,
            confidence_score=equipment_confidence,
            resolution_method=ResolutionMethod.FUZZY_MATCH,
        ),
        problem_description=ProblemDescription(
            original_text="Pompe centrifuge en panne",
            structured_description="Pump failure",
            structured_description_fr="Panne pompe",
            failure_mode_code=failure_mode_code,
            failure_mode_detected="WEARS | Metal to metal contact" if failure_mode_code else None,
        ),
        ai_classification=AIClassification(
            work_order_type=WorkOrderType.PM03_CORRECTIVE,
            priority_suggested=Priority.NORMAL,
            priority_justification="Degraded performance",
            estimated_duration_hours=4.0,
            required_specialties=["mechanical"],
        ),
    )


def _image_analysis() -> ImageAnalysis:
    return ImageAnalysis(
        anomalies_detected=["corrosion", "rust patches"],
        component_identified="pump casing",
        severity_visual=VisualSeverity.HIGH,
    )


def _mock_message(data: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(data))]
    return msg


GOOD_RESPONSE = {
    "equipment_tag": "BRY-SAG-PMP-001",
    "equipment_id": "eq-sag-pmp-001",
    "equipment_confidence": 0.87,
    "failure_mode_detected": "CORRODES | Corrosive environment",
    "failure_mode_code": "CORRODES+CORROSIVE_ENVIRONMENT",
    "affected_component": "pump casing",
    "structured_description": "BRY-SAG-PMP-001 CORRODES corrosive env",
    "structured_description_fr": "BRY-SAG-PMP-001 CORRODES env corrosif",
    "work_order_type": "PM03_CORRECTIVE",
    "priority_suggested": "2_URGENT",
    "priority_justification": "Corrosion severity HIGH requires prompt action",
    "safety_flags": [],
    "required_specialties": ["mechanical", "piping"],
}


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestInit:
    def test_raises_when_api_key_empty(self):
        with pytest.raises(ValueError):
            LLMCaptureEnhancer(api_key="")

    def test_uses_haiku_by_default(self):
        enhancer = _make_enhancer()
        assert "haiku" in enhancer._model.lower()


class TestNeedsEnhancement:
    def test_low_confidence_needs_enhancement(self):
        enhancer = _make_enhancer()
        wr = _work_request(equipment_confidence=CONFIDENCE_THRESHOLD - 0.1, failure_mode_code="WEARS+METAL_TO_METAL_CONTACT")
        assert enhancer.needs_enhancement(wr) is True

    def test_no_failure_mode_needs_enhancement(self):
        enhancer = _make_enhancer()
        wr = _work_request(equipment_confidence=0.9, failure_mode_code=None)
        assert enhancer.needs_enhancement(wr) is True

    def test_high_confidence_with_fm_no_enhancement(self):
        enhancer = _make_enhancer()
        wr = _work_request(equipment_confidence=0.9, failure_mode_code="WEARS+METAL_TO_METAL_CONTACT")
        assert enhancer.needs_enhancement(wr) is False


class TestEnhance:
    def test_low_confidence_triggers_llm(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        result = enhancer.enhance(capture, wr)
        assert result.equipment_identification.equipment_tag == "BRY-SAG-PMP-001"
        assert result.equipment_identification.resolution_method == ResolutionMethod.LLM_ENHANCED
        assert result.equipment_identification.confidence_score == pytest.approx(0.87)

    def test_enhanced_failure_mode_code_applied(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        result = enhancer.enhance(capture, wr)
        assert result.problem_description.failure_mode_code == "CORRODES+CORROSIVE_ENVIRONMENT"

    def test_enhanced_priority_applied(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        result = enhancer.enhance(capture, wr)
        assert result.ai_classification.priority_suggested == Priority.URGENT

    def test_sap_short_text_truncated_to_72_chars(self):
        enhancer = _make_enhancer()
        long_response = dict(GOOD_RESPONSE, structured_description="A" * 100)
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(long_response))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        result = enhancer.enhance(capture, wr)
        assert len(result.problem_description.structured_description) <= 72

    def test_high_confidence_skips_llm(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock()
        capture = _capture()
        wr = _work_request(equipment_confidence=0.95, failure_mode_code="WEARS+METAL_TO_METAL_CONTACT")
        result = enhancer.enhance(capture, wr)
        # LLM should NOT be called
        enhancer._client.messages.create.assert_not_called()
        assert result is wr  # Returns original unchanged

    def test_status_always_draft(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.3)
        result = enhancer.enhance(capture, wr)
        assert result.status == WorkRequestStatus.DRAFT

    def test_image_analysis_included_in_context(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        ia = _image_analysis()
        enhancer.enhance(capture, wr, image_analysis=ia)
        call_kwargs = enhancer._client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        assert "corrosion" in user_msg or "pump casing" in user_msg

    def test_falls_back_on_claude_error(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(side_effect=Exception("API error"))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.3)
        result = enhancer.enhance(capture, wr)
        # Should fall back to partial_wr (not raise)
        assert result is wr

    def test_falls_back_on_invalid_json(self):
        enhancer = _make_enhancer()
        msg = MagicMock()
        msg.content = [MagicMock(text="not valid json at all!")]
        enhancer._client.messages.create = MagicMock(return_value=msg)
        capture = _capture()
        wr = _work_request(equipment_confidence=0.3)
        result = enhancer.enhance(capture, wr)
        # Should fall back gracefully
        assert result is wr

    def test_original_spare_parts_preserved(self):
        enhancer = _make_enhancer()
        enhancer._client.messages.create = MagicMock(return_value=_mock_message(GOOD_RESPONSE))
        capture = _capture()
        wr = _work_request(equipment_confidence=0.4)
        # spare_parts_suggested should be empty list (preserved)
        result = enhancer.enhance(capture, wr)
        assert result.spare_parts_suggested == []
