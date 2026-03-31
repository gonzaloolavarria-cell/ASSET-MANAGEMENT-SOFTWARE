# G-08: Voice/Image Capture — Execution Plan

**Status:** ✅ COMPLETE — Both sessions done
**Session:** 1 of 2 ✅ | 2 of 2 ✅
**Last updated:** 2026-03-12
**Priority:** P3 — Production Hardening
**Phase:** D — Field Capture Integration
**Effort:** 2 sessions

---

## Context

**Gap:** Voice/image capture not wired — `identify-work-request` skill defines the flow but Deepgram/Whisper and Claude Vision aren't integrated.

**Outcome:** A field technician speaks into their phone (FR/AR/EN), takes a photo of a broken component, and AMS automatically creates a `StructuredWorkRequest` (DRAFT) with equipment TAG, validated failure mode (72-combo), priority, and spare parts.

**Phase D exit criteria:**
- Technician records voice note in French → transcribed to text within 3 seconds
- Photo of corroded pipe → `component_identified`, `anomalies_detected`, `severity_visual` detected
- VOICE+IMAGE capture → complete `StructuredWorkRequest` (TAG + FM + priority + spare parts)
- GPS auto-fills equipment TAG when within 20m of known location
- Page 8 functional on 390px mobile screen
- 0 regressions in existing 2,713+ tests
- Graceful degradation when `OPENAI_API_KEY` not set

---

## What Already Exists

| Component | File | Status |
|-----------|------|--------|
| Field Capture UI | `streamlit_app/pages/8_field_capture.py` | UI skeleton only (manual text simulation) |
| Work Request Queue | `streamlit_app/pages/9_work_requests.py` | Complete ✅ |
| Data Models | `tools/models/schemas.py` | `FieldCaptureInput`, `CaptureImage`, `StructuredWorkRequest`, `ImageAnalysis` ✅ |
| identify-work-request skill | `skills/01-work-identification/identify-work-request/CLAUDE.md` | Defined, not wired ⚠️ |
| Deterministic processor | `tools/processors/field_capture_processor.py` | EXACT/FUZZY/ALIAS FM matching ✅ |
| API endpoints | `api/routers/capture.py` | JSON-only, no file uploads ⚠️ |
| Capture service | `api/services/capture_service.py` | Orchestrates processor ✅ |
| API client | `streamlit_app/api_client.py` | Basic capture methods ✅ |

---

## Architecture After G-08

```
Page 8 (Field Capture — Mobile-Ready)
  ├─ Step 1: Identify → technician_id + GPS → ProximityMatcher → suggested TAG
  ├─ Step 2a: VOICE → st.audio_input() → POST /media/transcribe → text
  ├─ Step 2b: IMAGE → st.camera_input() → POST /media/analyze-image → anomalies
  └─ Step 3: Submit → POST /capture/ (JSON with transcription + image analysis)
                ↓
        capture_service.process_capture()
          ├─ FieldCaptureProcessor (deterministic: FM keywords, priority, spare parts)
          ├─ ImageAnalysisService (Claude Vision → ImageAnalysis)
          ├─ LLMCaptureEnhancer (if confidence < 0.7 → enhanced StructuredWorkRequest)
          └─ Persist: FieldCaptureModel + WorkRequestModel
                ↓
        Page 9 (Work Requests) → Planner: APPROVE / REJECT / RECLASSIFY
```

---

## Files to Create

| File | Purpose | Session |
|------|---------|---------|
| `tools/processors/audio_transcription.py` | Whisper API wrapper | S1 |
| `tools/processors/image_analyzer.py` | Claude Vision wrapper | S1 |
| `tools/processors/llm_capture_enhancer.py` | LLM enhancement layer (D-3) | S1 |
| `tools/processors/equipment_proximity_matcher.py` | GPS proximity matching (D-5) | S2 |
| `api/routers/media.py` | Transcribe + analyze-image endpoints | S1 |
| `streamlit_app/components/audio_recorder.py` | Reusable audio recording widget | S1 |
| `tests/test_audio_transcription.py` | Unit tests | S1 |
| `tests/test_image_analyzer.py` | Unit tests | S1 |
| `tests/test_llm_capture_enhancer.py` | Unit tests | S1 |
| `tests/test_field_capture_integration.py` | Integration tests | S2 |

## Files to Modify

| File | What Changes | Session |
|------|-------------|---------|
| `tools/models/schemas.py` | Add `AudioTranscriptionResult`, `GPSCoordinates`; update `CaptureImage` | S1 |
| `api/config.py` | Add `OPENAI_API_KEY`, `WHISPER_MODEL` | S1 |
| `.env.example` | Add `OPENAI_API_KEY=sk-...` | S1 |
| `api/main.py` | Register `/media` router | S1 |
| `api/database/models.py` | Add audio/GPS fields to `FieldCaptureModel`, GPS to `HierarchyNodeModel` | S1 |
| `api/services/capture_service.py` | Wire image analyzer + LLM enhancer | S1 |
| `streamlit_app/api_client.py` | Add `transcribe_audio()`, `analyze_image()`, `ai_enhance_capture()` | S1 |
| `streamlit_app/pages/8_field_capture.py` | Real audio/image/GPS UI | S1-S2 |
| `api/routers/capture.py` | Add `GET /capture/nearby` endpoint | S2 |
| `api/seed.py` | Add mock GPS coords for OCP-JFC equipment | S2 |
| `MASTER_PLAN.md` | Mark G-08 + D-1/D-2/D-3/D-4/D-5 complete | S2 |

---

## SESSION 1 — Core Audio + Vision Integration

### Phase 0: Setup ✅
- [x] Create `docs/G-08_EXECUTION.md` (this file)
- [x] Add `OPENAI_API_KEY` and `WHISPER_MODEL` to `api/config.py`
- [x] Add `OPENAI_API_KEY=sk-...` to `.env.example`
- [x] Add `openai>=1.0.0` to `requirements.txt`
- [x] Add `streamlit-js-eval>=0.1.5` to `requirements.txt` (GPS)
- [x] Add to `tools/models/schemas.py`:
  - [x] `AudioTranscriptionResult` model
  - [x] `GPSCoordinates` model
  - [x] `gps_data: Optional[GPSCoordinates]` field on `CaptureImage`
  - [x] `LLM_ENHANCED` and `GPS_PROXIMITY` values on `ResolutionMethod` enum
  - [x] `ALIAS_MATCH` added to `ResolutionMethod` enum

### Phase 1: D-1 — Voice Transcription (Whisper API) ✅
- [x] Create `tools/processors/audio_transcription.py`
  - [x] `TranscriptionNotConfiguredError` exception
  - [x] `TranscriptionService` class
  - [x] `transcribe(audio_bytes, mime_type, language_hint) -> AudioTranscriptionResult`
  - [x] Language mapping (fr/ar/en/es → Whisper lang codes)
  - [x] Graceful fallback when `OPENAI_API_KEY` not configured
- [x] Add `POST /media/transcribe` to `api/routers/media.py`
- [x] Register `/media` router in `api/main.py`
- [x] Add `transcribe_audio(audio_bytes, filename, language)` to `streamlit_app/api_client.py`
- [x] Write `tests/test_audio_transcription.py` — 20 tests, all passing

### Phase 2: D-2 — Image Analysis (Claude Vision) ✅
- [x] Create `tools/processors/image_analyzer.py`
  - [x] `ImageAnalysisService` class (uses `anthropic.Anthropic()`, model=claude-sonnet-4-6)
  - [x] `analyze(image_bytes, mime_type, context_hint) -> ImageAnalysis`
  - [x] System prompt: industrial maintenance, OCP phosphate mining context
  - [x] Structured JSON response parsing with markdown fence stripping
- [x] Add `POST /media/analyze-image` to `api/routers/media.py`
- [x] Add `analyze_image(image_bytes, filename, context)` to `streamlit_app/api_client.py`
- [x] Write `tests/test_image_analyzer.py` — 13 tests, all passing

### Phase 3: D-3 — Skill Wiring (LLM Enhancer) ✅
- [x] Create `tools/processors/llm_capture_enhancer.py`
  - [x] `LLMCaptureEnhancer` class (Claude Haiku, cost-efficient)
  - [x] `enhance(capture_input, partial_result, image_analysis) -> StructuredWorkRequest`
  - [x] Triggers only when `confidence_score < 0.7` or no FM detected
  - [x] System prompt embeds 72-combo FM matrix, T-16 rule, SAP 72 char limit
  - [x] Sets `resolution_method = "LLM_ENHANCED"`
  - [x] Graceful fallback on any Claude error
- [x] Update `api/services/capture_service.py`:
  - [x] Accept `image_analysis_json` and `gps_lat/lon` in data dict
  - [x] Wire `LLMCaptureEnhancer` as Step 3 in capture pipeline
  - [x] Extended return dict with `resolution_method`, `failure_mode_code`, `image_analysis`
- [x] Write `tests/test_llm_capture_enhancer.py` — 15 tests, all passing

### Phase 4: Update Page 8 UI (audio + images) ✅
- [x] Update `streamlit_app/pages/8_field_capture.py`:
  - [x] Responsive CSS for mobile (breakpoint 768px)
  - [x] 3-step guided flow: Identify → Capture → Submit
  - [x] VOICE mode: `st.audio_input()` + "Transcribir" button + editable textarea
  - [x] IMAGE mode: `st.camera_input()` + `st.file_uploader()` + thumbnail + "Analizar" button
  - [x] VOICE+IMAGE mode: both inputs shown
  - [x] GPS capture via `streamlit-js-eval` (graceful degradation if unavailable)
  - [x] Show analysis results (anomalies, component, severity) before submission
  - [x] 4-metric result display (tag, confidence, priority, resolution method)
  - [x] Session state management (clear on submit)

### Phase 5: Update DB Models ✅
- [x] Add to `api/database/models.py` → `FieldCaptureModel`:
  - [x] `audio_file_path: Optional[str]`
  - [x] `audio_transcription: Optional[str]`
  - [x] `gps_lat: Optional[float]`
  - [x] `gps_lon: Optional[float]`
  - [x] `image_analysis_result: Optional[str]` (JSON string)
- [x] Add `gps_lat: Optional[float]`, `gps_lon: Optional[float]` to `HierarchyNodeModel`

---

## SESSION 2 — Mobile UI + GPS + Polish + Tests

### Phase 6: D-4 — Mobile-Responsive UI ✅
- [x] Add responsive CSS to Page 8 (breakpoint 768px) — done in Session 1
- [x] Restructure layout as 3-step guided flow (Identify → Capture → Submit)
- [x] `st.camera_input()` as primary mobile path
- [x] All buttons: `use_container_width=True`

### Phase 7: D-5 — GPS Metadata + Proximity Matching ✅
- [x] Create `tools/processors/equipment_proximity_matcher.py`
  - [x] `ProximityMatcher` with haversine distance
  - [x] `find_nearby(lat, lon, equipment_registry, radius_m=100) -> list[EquipmentMatch]`
  - [x] Confidence: <20m = HIGH, <100m = MEDIUM
- [x] Add `streamlit-js-eval` geolocation call to Page 8 (done Session 1)
- [x] Add `GET /capture/nearby?lat&lon&radius_m` to `api/routers/capture.py`
- [x] Add `find_nearby_equipment(lat, lon)` to `streamlit_app/api_client.py`
- [x] Update `api/seed.py` with mock GPS coords (OCP-JFC1: 33.26°N, -8.51°W, 500m spread)

### Phase 8: Integration Testing ✅
- [x] Write `tests/test_proximity_matcher.py` — 19 tests
- [x] Write `tests/test_field_capture_integration.py` — 22 tests
  - [x] TEXT → processor → work request
  - [x] VOICE (mocked) → raw_voice_text populated
  - [x] IMAGE (pre-computed JSON) → image_analysis stored in DB + response
  - [x] VOICE+IMAGE → full pipeline
  - [x] GPS stored in FieldCaptureModel
  - [x] Proximity matching sorted by distance (GET /capture/nearby)
  - [x] LLM enhancer graceful fallback on error
  - [x] List captures
- [x] Run: `python -m pytest --tb=short -q` → 3166 passed, 6 pre-existing failures (not G-08)
- [x] G-08 suite: 89/89 tests passing

### Phase 9: Documentation + Plan Closeout ✅
- [x] Update `MASTER_PLAN.md`: mark G-08 + D-1 through D-5 as `[x]`
- [x] Update `memory/MEMORY.md` with G-08 implementation notes
- [x] Mark this doc STATUS → ✅ COMPLETE

---

## Risks & Mitigations

| Risk | Mitigation |
|------|-----------|
| `OPENAI_API_KEY` unavailable at OCP | `faster-whisper` local fallback; manual text mode |
| `st.audio_input()` needs Streamlit ≥1.36 | Check version; fallback to `st.file_uploader(type=["wav","mp3"])` |
| Claude Vision latency 2-5s | Spinner, cache results, async processing |
| GPS unavailable on desktop | Manual lat/lon input fallback |
| Multipart upload complexity | Keep `/capture/` JSON-only; new `/media/` router for files |
| SQLite column additions break tests | All new columns nullable with defaults |
