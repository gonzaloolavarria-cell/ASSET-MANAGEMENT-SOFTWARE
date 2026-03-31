"""Tests for tools/processors/image_analyzer.py — G-08 D-2."""

import json
from unittest.mock import MagicMock, patch
import pytest

from tools.processors.image_analyzer import ImageAnalysisService, get_image_analysis_service
from tools.models.schemas import ImageAnalysis, VisualSeverity


# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02"
    b"\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00"
    b"\x00\x01\x01\x00\x05\x18\xd8N\x00\x00\x00\x00IEND\xaeB`\x82"
)  # Minimal valid 1x1 PNG


def _make_service(api_key="sk-ant-test") -> ImageAnalysisService:
    with patch("anthropic.Anthropic"):
        return ImageAnalysisService(api_key=api_key)


def _mock_message(json_body: dict) -> MagicMock:
    msg = MagicMock()
    msg.content = [MagicMock(text=json.dumps(json_body))]
    return msg


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestImageAnalysisServiceInit:
    def test_raises_when_api_key_empty(self):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            ImageAnalysisService(api_key="")

    def test_creates_client_successfully(self):
        service = _make_service()
        assert service._model == "claude-sonnet-4-6"


class TestAnalyze:
    def test_successful_analysis(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({
                "component_identified": "pump",
                "anomalies_detected": ["corrosion", "rust"],
                "severity_visual": "HIGH",
            })
        )
        result = service.analyze(SAMPLE_PNG, "image/png", context_hint="Feed pump")
        assert isinstance(result, ImageAnalysis)
        assert result.component_identified == "pump"
        assert "corrosion" in result.anomalies_detected
        assert result.severity_visual == VisualSeverity.HIGH

    def test_multiple_anomalies_detected(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({
                "component_identified": "belt",
                "anomalies_detected": ["wear", "fraying", "misalignment"],
                "severity_visual": "MEDIUM",
            })
        )
        result = service.analyze(SAMPLE_PNG, "image/jpeg")
        assert len(result.anomalies_detected) == 3
        assert result.severity_visual == VisualSeverity.MEDIUM

    def test_no_anomalies_returns_empty(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({
                "component_identified": "motor",
                "anomalies_detected": [],
                "severity_visual": "LOW",
            })
        )
        result = service.analyze(SAMPLE_PNG, "image/png")
        assert result.anomalies_detected == []
        assert result.severity_visual == VisualSeverity.LOW

    def test_unsupported_image_format_raises(self):
        service = _make_service()
        with pytest.raises(ValueError, match="image/bmp"):
            service.analyze(SAMPLE_PNG, "image/bmp")

    def test_invalid_json_returns_default(self):
        service = _make_service()
        msg = MagicMock()
        msg.content = [MagicMock(text="This is not JSON!")]
        service._client.messages.create = MagicMock(return_value=msg)
        result = service.analyze(SAMPLE_PNG, "image/png")
        assert isinstance(result, ImageAnalysis)
        assert result.anomalies_detected == []
        assert result.severity_visual == VisualSeverity.LOW

    def test_markdown_fences_stripped(self):
        service = _make_service()
        raw_with_fences = "```json\n{\"component_identified\": \"valve\", \"anomalies_detected\": [\"leak\"], \"severity_visual\": \"HIGH\"}\n```"
        msg = MagicMock()
        msg.content = [MagicMock(text=raw_with_fences)]
        service._client.messages.create = MagicMock(return_value=msg)
        result = service.analyze(SAMPLE_PNG, "image/jpeg")
        assert result.component_identified == "valve"
        assert "leak" in result.anomalies_detected

    def test_unknown_severity_defaults_to_low(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({
                "component_identified": "bearing",
                "anomalies_detected": ["noise"],
                "severity_visual": "UNKNOWN_VALUE",
            })
        )
        result = service.analyze(SAMPLE_PNG, "image/png")
        assert result.severity_visual == VisualSeverity.LOW

    def test_context_hint_sent_in_user_message(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({
                "component_identified": "SAG mill",
                "anomalies_detected": [],
                "severity_visual": "LOW",
            })
        )
        service.analyze(SAMPLE_PNG, "image/png", context_hint="SAG Mill BRY-001")
        call_kwargs = service._client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        # Find the text part
        text_parts = [p for p in user_msg if p.get("type") == "text"]
        assert any("SAG Mill BRY-001" in p.get("text", "") for p in text_parts)

    def test_sends_base64_image(self):
        service = _make_service()
        service._client.messages.create = MagicMock(
            return_value=_mock_message({"component_identified": None, "anomalies_detected": [], "severity_visual": "LOW"})
        )
        service.analyze(SAMPLE_PNG, "image/png")
        call_kwargs = service._client.messages.create.call_args.kwargs
        user_msg = call_kwargs["messages"][0]["content"]
        image_parts = [p for p in user_msg if p.get("type") == "image"]
        assert len(image_parts) == 1
        assert image_parts[0]["source"]["type"] == "base64"
        assert image_parts[0]["source"]["media_type"] == "image/png"


class TestFactory:
    def test_raises_when_api_key_not_configured(self):
        with patch("api.config.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = ""
            with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
                get_image_analysis_service()

    def test_creates_service_when_key_set(self):
        with patch("api.config.settings") as mock_settings:
            mock_settings.ANTHROPIC_API_KEY = "sk-ant-test-key"
            with patch("anthropic.Anthropic"):
                service = get_image_analysis_service()
                assert isinstance(service, ImageAnalysisService)
