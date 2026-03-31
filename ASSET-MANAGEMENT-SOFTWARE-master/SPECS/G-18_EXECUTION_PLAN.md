# G-18 Execution Plan — Phase B Data Import Pipeline

**Status:** DONE
**Started:** 2026-03-11
**Completed:** 2026-03-12
**Effort estimate:** ~1 session

---

## Background

G-18 originally stated: *"DataImportEngine accepts `list[dict]` but has no openpyxl/pandas reader."*

**Discovery at session start:** The core file parsing was **already built**:
- `tools/engines/file_parser_engine.py` — openpyxl + csv parser, 385 lines, security-hardened
- `DataImportEngine.parse_and_validate()` — integrates FileParserEngine
- Page 15 Tab 3 — file upload → parse → local validation display

**Actual gap:** No API layer — the parsing happens only client-side in the Streamlit process.
- No `api/routers/imports.py` → Tab 5 Import History silently fails
- No DB persistence → validated data never ingested
- No MCP tools → agents can't trigger import
- No `ImportHistoryModel` in ORM → no audit trail

---

## Reused (no changes needed)

| Component | Path |
|-----------|------|
| File parsing engine | `tools/engines/file_parser_engine.py` |
| Validation engine | `tools/engines/data_import_engine.py` |
| Schemas | `tools/models/schemas.py` — `ImportSource`, `ImportResult`, `ImportHistoryEntry` |
| UI error components | `streamlit_app/components/import_errors.py` |
| Column mapper widget | `streamlit_app/components/column_mapper.py` |

---

## Checklist

### Phase 1 — DB Model + API Layer

- [x] **Step 0** Create this tracking document (`SPECS/G-18_EXECUTION_PLAN.md`)
- [x] **Step 1** Add `ImportHistoryModel` to `api/database/models.py` *(already existed — skipped)*
  - Fields: `import_id` (UUID), `plant_id`, `source`, `filename`, `total_rows`, `valid_rows`, `error_rows`, `status` (success/partial/failed), `errors` (JSON text), `imported_at`, `imported_by` (nullable)
  - All fields have defaults for backward compat (Alembic-free migration pattern)
- [x] **Step 2** Create `api/services/import_service.py`
  - `import_file(db, plant_id, source, filename, file_bytes, sheet_name=None) → ImportHistoryEntry`
    - calls `DataImportEngine.parse_and_validate()` → `ImportResult`
    - persists to `ImportHistoryModel`
    - returns `ImportHistoryEntry`
  - `list_import_history(db, plant_id, source=None, limit=100) → list[ImportHistoryEntry]`
- [x] **Step 3** Create `api/routers/imports.py`
  - `POST /api/v1/import/file` — multipart: `file`, `source`, `plant_id`, optional `sheet_name`
  - `GET /api/v1/import/history` — query: `plant_id`, `source`, `limit`
  - `GET /api/v1/import/sources` — returns all `ImportSource` values
- [x] **Step 4** Register router in `api/main.py`

### Phase 2 — Streamlit UI

- [x] **Step 5** Add to `streamlit_app/api_client.py`
  - `import_file(plant_id, source, file_bytes, filename, sheet_name=None) → dict`
  - `get_import_history(plant_id, source=None, limit=100) → list[dict]`
  - `list_import_sources() → list[str]`
- [x] **Step 6** Update `streamlit_app/pages/15_reports_data.py` Tab 3 (lines ~208–214)
  - "Validate" button → calls `api_client.import_file()` (parse + validate + persist in one call)
  - Display `import_result_summary()` + `import_error_table()` + `import_data_preview()` from response
  - Show `history_id` on success
  - Tab 5 Import History now works without code changes (endpoint exists)

### Phase 3 — Agent MCP Tools

- [x] **Step 7** Create `agents/tool_wrappers/import_tools.py`
  - `import_data_file(source, filename, file_b64, plant_id, sheet_name=None)` — base64 decode + call API
  - `validate_import_rows(source, rows)` — validate pre-parsed rows
  - `get_import_history(plant_id, source=None, limit=20)` — query history
  - `list_import_sources()` — list available sources
- [x] **Step 8** Register tools
  - `agents/tool_wrappers/registry.py` — add 4 new tools
  - `agents/planning/skills.yaml` — assign to Planning agent (SWMR: data ingestion owned by Planning)
  - Update Planning tool count: 71 → 75

### Phase 4 — Tests + Docs

- [x] **Step 9** Write `tests/test_import_api.py` (15+ tests)
  - POST /import/file: success, partial (some invalid rows), all-fail
  - GET /import/history: filter by source, pagination
  - GET /import/sources: returns list
  - DB persistence: verify `ImportHistoryModel` row created
- [x] **Step 10** Write `tests/test_import_tools.py` (8+ tests)
  - `validate_import_rows`: valid data, invalid data
  - `list_import_sources`: returns expected values
  - `get_import_history`: mocked API response
- [x] **Step 11** Update `MASTER_PLAN.md`
  - Check off: G-18, B-1, B-2, B-3, B-4
  - Update Planning agent tool count (71→75)

---

## Verification

1. `POST /api/v1/import/file` with sample `.xlsx` → `ImportHistoryEntry` with `status: success`
2. Page 15 Tab 3 → upload → Validate → green summary card + history_id shown
3. Page 15 Tab 5 → shows history row from step 2
4. `python -m pytest tests/test_import_api.py -v` → all pass
5. Planning agent has 75 tools in registry

---

## Modified Files Summary

| File | Change |
|------|--------|
| `api/database/models.py` | + `ImportHistoryModel` |
| `api/services/import_service.py` | NEW |
| `api/routers/imports.py` | NEW |
| `api/main.py` | register router |
| `streamlit_app/api_client.py` | + 3 methods |
| `streamlit_app/pages/15_reports_data.py` | wire Tab 3 to API |
| `agents/tool_wrappers/import_tools.py` | NEW |
| `agents/tool_wrappers/registry.py` | + 4 tools |
| `agents/planning/skills.yaml` | + 4 tool entries |
| `MASTER_PLAN.md` | check off G-18 + B-1–B-4 |
| `tests/test_import_api.py` | NEW |
| `tests/test_import_tools.py` | NEW |
