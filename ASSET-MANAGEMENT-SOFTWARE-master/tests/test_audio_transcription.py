"""Tests for tools/processors/audio_transcription.py — G-08 D-1.

openai package may not be installed in the test environment; we mock the module
at sys.modules level so TranscriptionService.__init__ receives the mock.
"""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch
import pytest

from tools.models.schemas import AudioTranscriptionResult


# ── Mock openai module at the top level ──────────────────────────────────────
# This ensures TranscriptionService can be instantiated without openai installed.

_mock_openai_client = MagicMock()
_mock_openai_mod = MagicMock()
_mock_openai_mod.OpenAI.return_value = _mock_openai_client

# Inject mock before importing TranscriptionService
sys.modules.setdefault("openai", _mock_openai_mod)

from tools.processors.audio_transcription import (  # noqa: E402
    TranscriptionNotConfiguredError,
    TranscriptionService,
    UnsupportedAudioFormatError,
    get_transcription_service,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

SAMPLE_WAV = b"RIFF\x00\x00\x00\x00WAVEfmt " + b"\x00" * 16 + b"data\x00\x00\x00\x00"
SAMPLE_WEBM = b"\x1a\x45\xdf\xa3" + b"\x00" * 20  # Minimal WebM magic bytes


def _make_service(api_key="sk-test-abc", model="whisper-1") -> TranscriptionService:
    service = TranscriptionService(api_key=api_key, model=model)
    # Reset mock client state for isolation
    service._client = MagicMock()
    return service


# ── Unit Tests ────────────────────────────────────────────────────────────────

class TestTranscriptionServiceInit:
    def test_raises_when_api_key_empty(self):
        with pytest.raises(TranscriptionNotConfiguredError, match="OPENAI_API_KEY"):
            TranscriptionService(api_key="")

    def test_raises_when_openai_not_installed(self):
        # Temporarily remove openai from sys.modules to simulate missing package
        saved = sys.modules.pop("openai", None)
        # Also remove from the module's namespace so it re-imports
        import tools.processors.audio_transcription as _mod
        orig_openai = getattr(_mod, "openai", None)
        try:
            # Simulate ImportError inside __init__
            with patch.dict(sys.modules, {"openai": None}):
                with pytest.raises((TranscriptionNotConfiguredError, ImportError)):
                    TranscriptionService(api_key="sk-test")
        finally:
            if saved is not None:
                sys.modules["openai"] = saved

    def test_creates_client_successfully(self):
        service = _make_service()
        assert service._model == "whisper-1"


class TestTranscribe:
    def _mock_response(self, text="Pompe défaillante", lang="fr", duration=5.3):
        resp = MagicMock()
        resp.text = text
        resp.language = lang
        resp.duration = duration
        return resp

    def test_successful_transcription(self):
        service = _make_service()
        service._client.audio.transcriptions.create.return_value = self._mock_response(
            "Pompe défaillante", "fr", 5.3
        )
        result = service.transcribe(SAMPLE_WAV, "audio/wav", language_hint="fr")
        assert isinstance(result, AudioTranscriptionResult)
        assert result.text == "Pompe défaillante"
        assert result.language_detected == "fr"
        assert result.duration_seconds == 5.3
        assert result.confidence == 1.0

    def test_transcription_with_language_hint_ar(self):
        service = _make_service()
        service._client.audio.transcriptions.create.return_value = self._mock_response(
            "خلل في المضخة", "ar", 4.0
        )
        result = service.transcribe(SAMPLE_WEBM, "audio/webm", language_hint="ar")
        assert result.language_detected == "ar"
        call_kwargs = service._client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["language"] == "ar"

    def test_no_language_hint_uses_auto_detect(self):
        service = _make_service()
        service._client.audio.transcriptions.create.return_value = self._mock_response(
            "SAG mill bearing noise", "en"
        )
        service.transcribe(SAMPLE_WAV, "audio/wav")
        call_kwargs = service._client.audio.transcriptions.create.call_args.kwargs
        assert "language" not in call_kwargs

    def test_unsupported_mime_type_raises(self):
        service = _make_service()
        with pytest.raises(UnsupportedAudioFormatError, match="video/mp4"):
            service.transcribe(b"\x00", "video/mp4")

    def test_uses_verbose_json_response_format(self):
        service = _make_service()
        service._client.audio.transcriptions.create.return_value = self._mock_response()
        service.transcribe(SAMPLE_WAV, "audio/wav", language_hint="en")
        call_kwargs = service._client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["response_format"] == "verbose_json"

    def test_text_is_stripped(self):
        service = _make_service()
        service._client.audio.transcriptions.create.return_value = self._mock_response(
            "  vibration on motor  "
        )
        result = service.transcribe(SAMPLE_WAV, "audio/wav")
        assert result.text == "vibration on motor"


class TestLanguageMapping:
    def test_french_alias(self):
        service = _make_service()
        resp = MagicMock()
        resp.text, resp.language, resp.duration = "test", "fr", 1.0
        service._client.audio.transcriptions.create.return_value = resp
        service.transcribe(SAMPLE_WAV, "audio/wav", language_hint="french")
        call_kwargs = service._client.audio.transcriptions.create.call_args.kwargs
        assert call_kwargs["language"] == "fr"

    def test_unknown_language_hint_uses_auto_detect(self):
        service = _make_service()
        resp = MagicMock()
        resp.text, resp.language, resp.duration = "test", "en", 1.0
        service._client.audio.transcriptions.create.return_value = resp
        service.transcribe(SAMPLE_WAV, "audio/wav", language_hint="zulu")
        call_kwargs = service._client.audio.transcriptions.create.call_args.kwargs
        assert "language" not in call_kwargs


class TestSupportedFormats:
    @pytest.mark.parametrize("mime_type", [
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/webm",
        "audio/ogg",
        "audio/flac",
    ])
    def test_supported_mime_types(self, mime_type):
        service = _make_service()
        resp = MagicMock()
        resp.text, resp.language, resp.duration = "ok", "en", 1.0
        service._client.audio.transcriptions.create.return_value = resp
        result = service.transcribe(SAMPLE_WAV, mime_type)
        assert result.text == "ok"


class TestFactory:
    def test_raises_when_api_key_not_configured(self):
        with patch("api.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = ""
            mock_settings.WHISPER_MODEL = "whisper-1"
            with pytest.raises(TranscriptionNotConfiguredError):
                get_transcription_service()

    def test_creates_service_when_key_set(self):
        with patch("api.config.settings") as mock_settings:
            mock_settings.OPENAI_API_KEY = "sk-test-key"
            mock_settings.WHISPER_MODEL = "whisper-1"
            service = get_transcription_service()
            assert isinstance(service, TranscriptionService)
