# D-4 Execution Plan: Mobile-Responsive Field Capture UI

> **Task:** T-28 | **Gap:** G-08 + G-13 | **Phase:** D (Field Capture Integration)
> **Status:** COMPLETE | **Created:** 2026-03-12 | **Completed:** 2026-03-12
> **Acceptance Criteria:** Touch-friendly, works on mobile browsers, camera/mic access

---

## Context

The AMS has two field capture UIs:
1. **Streamlit Page 8** — Desktop/tablet, fully functional (voice/image/GPS via Whisper + Claude Vision)
2. **React PWA Field App** (`field_app/`) — Mobile-first, offline-capable, but **missing media capture**

D-4 completes the React PWA by adding camera, microphone, and GPS integration — making it a fully functional mobile field capture tool. The API endpoints (`/media/transcribe`, `/media/analyze-image`, `/capture/nearby`) are already built. This is purely frontend work.

**Architecture decision:** Media blobs (audio/image) are stored offline in IndexedDB, then processed via server APIs when online. The server never receives raw blobs — only processed text and analysis JSON. The existing sync protocol is unchanged.

---

## Phase 1: IndexedDB Schema Extension

- [x] **1.1** Extend `CaptureRecord` interface in `field_app/src/db/local-db.ts`:
  - `audioBlob?: Blob` — raw audio (webm/opus)
  - `imageBlob?: Blob` — raw image (jpeg)
  - `imageThumbnail?: string` — base64 compressed preview
  - `gpsLat?: number`, `gpsLon?: number`, `gpsAccuracy?: number`
  - `transcriptionResult?: { text, language_detected, duration_seconds }`
  - `imageAnalysisResult?: { component_identified, anomalies_detected, severity_visual }`
  - `mediaProcessingStatus?: 'pending' | 'processing' | 'complete' | 'failed'`
- [x] **1.2** Add Dexie `version(3)` with `mediaProcessingStatus` index
- [x] **1.3** Extend `NewCapture` in `field_app/src/sync/sync-queue.ts` with media + GPS fields
- [x] **1.4** Update `enqueue()` — set `mediaProcessingStatus: 'pending'` when blobs present
- [x] **1.5** Test: update `sync-queue.test.ts` for media + GPS fields
- [x] **1.6** Test: add `capture-db-v3.test.ts` (v2→v3 migration, blob storage/retrieval)

---

## Phase 2: Media Capture Hooks

- [x] **2.1** Create `field_app/src/hooks/useCamera.ts`:
  - `<input type="file" accept="image/*" capture="environment">` (cross-device reliable)
  - Thumbnail via offscreen canvas (300px wide, JPEG 0.6)
  - Returns: `{ isSupported, capturedImage, thumbnail, captureFromCamera, captureFromGallery, clearImage, error }`
- [x] **2.2** Create `field_app/src/hooks/useAudioRecorder.ts`:
  - MediaRecorder API, MIME: `webm;codecs=opus` → `ogg;codecs=opus` → `mp4`
  - Live duration counter, auto-stop at 120s
  - Returns: `{ isSupported, isRecording, duration, audioBlob, startRecording, stopRecording, clearRecording, error }`
- [x] **2.3** Create `field_app/src/hooks/useGeolocation.ts`:
  - `getCurrentPosition()` with `enableHighAccuracy: true, timeout: 15000`
  - Returns: `{ isSupported, position, isLocating, getPosition, error }`
- [x] **2.4** Test: `media-capture.test.ts` — mock browser APIs, test degradation

---

## Phase 3: Media API Client

- [x] **3.1** Create `field_app/src/api/media-api.ts`:
  - `transcribeAudio(blob, language)` → `POST /media/transcribe` (FormData)
  - `analyzeImage(blob, context)` → `POST /media/analyze-image` (FormData)
  - `findNearbyEquipment(lat, lon, radiusM)` → `GET /capture/nearby`
- [x] **3.2** Test: `media-api.test.ts` — mock fetch, error handling

---

## Phase 4: Media Processing Service

- [x] **4.1** Create `field_app/src/sync/media-processor.ts`:
  - `processAllPending()` — find captures with `mediaProcessingStatus === 'pending'`
  - Audio: `transcribeAudio()` → store result, populate `rawText`
  - Image: `analyzeImage()` → store result in `imageAnalysisResult`
  - Sequential processing, status transitions (pending → processing → complete/failed)
- [x] **4.2** Integrate into `sync-manager.ts` `syncAll()` — media processing BEFORE push
- [x] **4.3** Extend push payload with GPS + analysis JSON fields
- [x] **4.4** Test: `media-processor.test.ts`

---

## Phase 5: FieldCapture.tsx Wizard Rewrite

- [x] **5.1** Create `field_app/src/components/capture/CaptureWizard.tsx`:
  - Progress dots (3 steps), Next/Back buttons, step validation
- [x] **5.2** Create `StepIdentify.tsx` — Equipment + GPS:
  - Technician ID, equipment selector, GPS button → nearby equipment suggestions
  - Location hint fallback, language + capture type
- [x] **5.3** Create `StepCapture.tsx` — Voice/Image/Text:
  - TEXT: textarea (existing)
  - VOICE: circular record button (80px), duration counter, playback, transcribe button (online), editable result
  - IMAGE: "Take Photo" + "Gallery" buttons, thumbnail preview, analyze button (online), analysis results
- [x] **5.4** Create `StepReview.tsx` — Review + Submit:
  - Summary card, submit with online/offline messaging
- [x] **5.5** Rewrite `FieldCapture.tsx` — use CaptureWizard, enhanced RecentCaptures list
- [x] **5.6** Mobile UX:
  - All tap targets ≥ 44px
  - No hover-only interactions
  - `active:scale-95 transition-all` on buttons

---

## Phase 6: Internationalization

- [x] **6.1** Voice keys (`capture.voice.*`) — 11 keys x4 languages
- [x] **6.2** Image keys (`capture.image.*`) — 11 keys x4 languages
- [x] **6.3** GPS keys (`capture.gps.*`) — 6 keys x4 languages
- [x] **6.4** Wizard keys (`capture.step.*`) — 5 keys x4 languages
- [x] **6.5** Media processing keys (`capture.media.*`) — 4 keys x4 languages
- [x] **6.6** All in FR (primary), EN, ES, AR

---

## Phase 7: Service Worker & Manifest

- [x] **7.1** Bump `sw.js` cache to `ams-field-v3`
- [x] **7.2** Add `.webm`, `.ogg`, `.mp4` to `STATIC_EXTS`
- [x] **7.3** Change manifest orientation to `"any"` (landscape support)

---

## Phase 8: Streamlit Page 8 CSS

- [x] **8.1** Add `@media (max-width: 480px)` — smaller padding, 100% buttons, 44px inputs, stack columns
- [x] **8.2** Add `@media (min-width: 769px) and (max-width: 1024px)` tablet breakpoint
- [x] **8.3** Add `@media (hover: none)` — remove hover-only effects

---

## Phase 9: Testing & Verification

- [x] **9.1** `cd field_app && npx vitest run` — all field app tests pass
- [x] **9.2** `python -m pytest --tb=short -q` — 0 regressions in Python suite
- [x] **9.3** `cd field_app && npm run build` — production build succeeds
- [x] **9.4** Manual: Chrome DevTools mobile (390px) — all 3 capture types work
- [x] **9.5** Manual: Offline capture → reconnect → auto-sync processes media
- [x] **9.6** Manual: All 4 languages render correctly (AR RTL)

---

## Phase 10: Documentation

- [x] **10.1** Update `MASTER_PLAN.md` — mark D-4 `[x]`, update G-08
- [x] **10.2** Update `docs/G-08_EXECUTION.md`
- [x] **10.3** Update `MEMORY.md`

---

## Key Files Reference

| Category | File | Lines |
|----------|------|-------|
| **DB Schema** | `field_app/src/db/local-db.ts` | 134 |
| **Sync Queue** | `field_app/src/sync/sync-queue.ts` | 99 |
| **Sync Manager** | `field_app/src/sync/sync-manager.ts` | 287 |
| **Capture Page** | `field_app/src/pages/FieldCapture.tsx` | 400 |
| **i18n** | `field_app/src/i18n/index.ts` | 329 |
| **Service Worker** | `field_app/public/sw.js` | 129 |
| **Manifest** | `field_app/public/manifest.json` | ~20 |
| **Streamlit Page 8** | `streamlit_app/pages/8_field_capture.py` | 260 |
| **Media: Transcribe** | `api/routers/media.py` | 104 |
| **Media: Analyze** | `tools/processors/image_analyzer.py` | ~100 |
| **Proximity** | `api/routers/capture.py` (GET /nearby) | 66 |

## Existing Patterns to Reuse

- **ChecklistItem.photoBlob** (`local-db.ts:75`) — base64 photo storage pattern (use same for `imageThumbnail`)
- **`apiFetch<T>()`** (`sync-manager.ts:65-75`) — typed fetch wrapper (reuse for GET /capture/nearby)
- **`FormData` uploads** — follow Streamlit `api_client.py` pattern for multipart (`transcribe_audio`, `analyze_image`)
- **`active:scale-95`** — touch feedback pattern from `ConflictDialog.tsx`
- **`items-end sm:items-center`** — mobile bottom-sheet pattern from `ConflictDialog.tsx`

---

## Session Log

| Session | Date | Phases | Notes |
|---------|------|--------|-------|
| — | 2026-03-12 | Planning | Execution plan created |
| 1 | 2026-03-12 | 1-10 | All phases complete. 33 field app tests pass, build succeeds, 113 Python tests pass |
