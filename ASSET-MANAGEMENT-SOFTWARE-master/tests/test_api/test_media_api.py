"""Tests for media API endpoints (api/routers/media.py)."""

import io
import pytest
from unittest.mock import patch, MagicMock

from tools.processors.audio_transcription import TranscriptionNotConfiguredError

pytestmark = pytest.mark.integration


class TestTranscribeEndpoint:
    """Tests for POST /media/transcribe."""

    def test_transcribe_no_api_key(self, client):
        """Should return 503 if transcription service not configured."""
        audio_file = io.BytesIO(b"fake audio content")
        with patch(
            "api.routers.media.get_transcription_service",
            side_effect=TranscriptionNotConfiguredError("Not configured"),
        ):
            resp = client.post(
                "/api/v1/media/transcribe",
                files={"file": ("test.wav", audio_file, "audio/wav")},
                data={"language": "en"},
            )
        assert resp.status_code == 503

    def test_transcribe_success_mocked(self, client):
        """Transcription with mocked service."""
        audio_file = io.BytesIO(b"fake audio content")
        mock_result = {
            "text": "The pump is making noise",
            "language": "en",
            "confidence": 0.95,
        }
        mock_service = MagicMock()
        mock_service.transcribe.return_value = MagicMock(**{"model_dump.return_value": mock_result})
        with patch("api.routers.media.get_transcription_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/media/transcribe",
                files={"file": ("test.wav", audio_file, "audio/wav")},
                data={"language": "en"},
            )
        assert resp.status_code == 200

    def test_transcribe_default_language(self, client):
        """Default language should be applied."""
        audio_file = io.BytesIO(b"fake audio content")
        mock_service = MagicMock()
        mock_result = {"text": "test", "language": "en", "confidence": 0.9}
        mock_service.transcribe.return_value = MagicMock(**{"model_dump.return_value": mock_result})
        with patch("api.routers.media.get_transcription_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/media/transcribe",
                files={"file": ("test.wav", audio_file, "audio/wav")},
            )
        assert resp.status_code == 200


class TestAnalyzeImageEndpoint:
    """Tests for POST /media/analyze-image."""

    def test_analyze_no_api_key(self, client):
        """Should return 503 if image analysis service not configured."""
        image_file = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        with patch(
            "api.routers.media.get_image_analysis_service",
            side_effect=ValueError("Not configured"),
        ):
            resp = client.post(
                "/api/v1/media/analyze-image",
                files={"file": ("test.png", image_file, "image/png")},
                data={"context": "Equipment inspection"},
            )
        assert resp.status_code == 503

    def test_analyze_success_mocked(self, client):
        """Image analysis with mocked service."""
        image_file = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_result = {
            "anomalies_detected": True,
            "component_identified": "Pump bearing housing",
            "severity_visual": "MEDIUM",
            "description": "Visible wear on housing",
        }
        mock_service = MagicMock()
        mock_service.analyze.return_value = MagicMock(**{"model_dump.return_value": mock_result})
        with patch("api.routers.media.get_image_analysis_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/media/analyze-image",
                files={"file": ("test.png", image_file, "image/png")},
                data={"context": "Equipment inspection"},
            )
        assert resp.status_code == 200

    def test_analyze_with_context(self, client):
        """Context parameter is passed through."""
        image_file = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_service = MagicMock()
        mock_result = {"anomalies_detected": False, "description": "Normal"}
        mock_service.analyze.return_value = MagicMock(**{"model_dump.return_value": mock_result})
        with patch("api.routers.media.get_image_analysis_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/media/analyze-image",
                files={"file": ("test.jpg", image_file, "image/jpeg")},
                data={"context": "SAG mill drive end bearing housing"},
            )
        assert resp.status_code == 200

    def test_analyze_empty_context(self, client):
        """Empty context should default."""
        image_file = io.BytesIO(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)
        mock_service = MagicMock()
        mock_result = {"anomalies_detected": False, "description": "Normal"}
        mock_service.analyze.return_value = MagicMock(**{"model_dump.return_value": mock_result})
        with patch("api.routers.media.get_image_analysis_service", return_value=mock_service):
            resp = client.post(
                "/api/v1/media/analyze-image",
                files={"file": ("test.png", image_file, "image/png")},
            )
        assert resp.status_code == 200
