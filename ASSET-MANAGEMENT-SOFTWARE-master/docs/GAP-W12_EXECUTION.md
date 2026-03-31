# GAP-W12 Execution Plan — Data Import from External Systems

> **Status:** COMPLETE
> **Created:** 2026-03-11
> **Last Updated:** 2026-03-11 (Session D complete)
> **Estimated Sessions:** 4 (A-D)
> **Related Gaps:** G-02, G-18, GAP-W12

---

## Context

The AMS platform has a `DataImportEngine` (`tools/engines/data_import_engine.py`) that validates pre-parsed `list[dict]` for 3 import types, but **cannot parse actual Excel/CSV files**. Page 15 has a file uploader widget that is completely non-functional. 14 Excel templates exist but only 3 types are validated.

**Workshop requirement (2026-03-10):** Import SAP historical OTs, equipment hierarchies, failure data. PI System/sensor data is future scope.

**Goal:** Users can upload Excel/CSV on Page 15, see auto-detected column mappings, review errors, and import all 14 template types. Agents gain MCP tools. API supports file upload.

---

## Session A: Foundation + Extended Types

### Phase 1: File Parsing Foundation

- [x] **1.1** Create `tools/engines/file_parser_engine.py`
  - `FileParserEngine` with `parse_file()`, `parse_excel()`, `parse_csv()`, `list_sheets()`, `detect_encoding()`
  - Accepts `bytes` (Streamlit + FastAPI compatible)
  - `openpyxl` with `load_workbook(data_only=True, read_only=True)`
  - CSV `csv.Sniffer` auto-delimiter (semicolons for SAP exports)
  - Multi-sheet: skip "Instructions"/"Lookups", parse first data sheet
  - Security: `MAX_FILE_SIZE_BYTES=10MB`, `MAX_ROWS=50_000`, reject `.xlsm`

- [x] **1.2** Add schema models to `tools/models/schemas.py`
  - `FileParseError(BaseModel)`: message, sheet?, row?
  - `FileParseResult(BaseModel)`: success, filename, file_type, sheets_available, sheet_parsed, headers, rows, total_rows, errors

- [x] **1.3** Integrate into `tools/engines/data_import_engine.py`
  - Add `parse_and_validate(file_content, filename, source, sheet_name?, column_mapping?)`
  - Add generic `validate_data(rows, source, column_mapping?)` entry point

- [x] **1.4** Update `tools/engines/__init__.py` — export `FileParserEngine`

- [x] **1.5** Create `tests/test_file_parser_engine.py` (30 tests)
  - Parse actual templates (01, 06, 07), multi-sheet, dates→ISO, numerics, empty rows trimmed
  - Max rows enforcement, oversized file rejection, CSV delimiter detection, encoding

### Phase 2: Extended Import Types

- [x] **2.1** Extend `ImportSource` enum in `tools/models/schemas.py` (3→16 values)
  - Added: CRITICALITY_ASSESSMENT, FAILURE_MODES, MAINTENANCE_TASKS, WORK_ORDER_HISTORY, SPARE_PARTS_INVENTORY, SHUTDOWN_CALENDAR, WORKFORCE, FIELD_CAPTURE, RCA_EVENTS, PLANNING_KPI, DE_KPI, MAINTENANCE_STRATEGY + kept FAILURE_HISTORY, MAINTENANCE_PLAN
  - Backward compatible

- [x] **2.2** Add required columns + aliases in `data_import_engine.py`
  - `_REQUIRED_COLUMNS` for all 14 types (from `generate_templates.py` headers)
  - `_COLUMN_ALIASES` (~48 alias groups)

- [x] **2.3** Add type-specific validation rules
  - FAILURE_MODES: 72-combo (mechanism, cause)
  - CRITICALITY_ASSESSMENT: scores 1-5, method enum
  - MAINTENANCE_TASKS: task_type + constraint enums
  - WORK_ORDER_HISTORY: ISO dates, order_type, status enums
  - SPARE_PARTS_INVENTORY: quantities >= 0, VED class
  - SHUTDOWN_CALENDAR: start < end, shutdown_type enum
  - WORKFORCE: specialty + shift enums
  - FIELD_CAPTURE: capture_type enum
  - RCA_EVENTS: level enum
  - PLANNING_KPI / DE_KPI: ISO dates
  - MAINTENANCE_STRATEGY: 72-combo + tactics_type

- [x] **2.4** Update MCP tool + service to generic entry point
  - `agents/tool_wrappers/reporting_tools.py` → `DataImportEngine.validate_data()`
  - `api/services/reporting_service.py` → same

- [x] **2.5** Tests for extended types in `tests/test_data_import_engine.py` (66 tests)

- [x] **2.6** Run full test suite — 2,713 passed, 3 pre-existing failures (unrelated to GAP-W12)

---

## Session B: UI Improvements

### Phase 3: Page 15 UI

- [x] **3.1** Wire file upload to parser in `streamlit_app/pages/15_reports_data.py`
  - Upload → parse → sheet selector → auto-detect columns → mapping preview → validate → results
  - Expand import_type to all 14 types + template download button
  - Dual input mode: file upload OR JSON paste (backward compatible)

- [x] **3.2** Create column mapping component `streamlit_app/components/column_mapper.py`
  - Two-column: source→target, confidence indicators (green/orange/red), manual override dropdowns

- [x] **3.3** Create error visualization `streamlit_app/components/import_errors.py`
  - Summary metrics, progress bar, detailed error table, download CSV

- [x] **3.4** Data preview with validation
  - First 50 rows via `import_data_preview()`, template download per type

- [x] **3.5** i18n updates — `streamlit_app/i18n/{en,fr,es,ar}.json` (23 new keys under `import.*`)

- [x] **3.6** Tests — 2,500 passed (non-API), pre-existing SQLAlchemy table conflict in API tests unrelated

---

## Session C: Agent Tools + API

### Phase 4: MCP Tool Enhancements

- [x] **4.1** Add `parse_import_file` tool in `reporting_tools.py`
  - Accepts `{file_path, sheet_name?}`, path validation (sandbox to templates/data dirs), returns FileParseResult

- [x] **4.2** Add `detect_import_columns` tool
  - Accepts `{headers, source}`, returns ImportMapping with confidence

- [x] **4.3** Add `parse_and_validate_import` composite tool
  - One-call: parse + detect + validate, returns ImportResult

- [x] **4.4** Update `server.py` AGENT_TOOL_MAP — 3 tools added to orchestrator (24→27) and planning (76→79)
  - Total tool count: 155→158

### Phase 5: API Endpoints

- [x] **5.1** `POST /reporting/import/upload` — file upload in `api/routers/reporting.py`
  - `UploadFile` + `Query(source)`, 10MB limit, extension whitelist (.csv, .xlsx)

- [x] **5.2** Import service `upload_and_validate()` in `reporting_service.py`
  - Parse → detect → validate → audit log, plus `detect_source_from_filename()` helper

- [x] **5.3** `POST /reporting/import/batch` — multi-file, auto-detect source from filename prefix (01-14)

- [x] **5.4** `GET /reporting/import/template/{number}` — returns FileResponse for templates 1-14

- [x] **5.5** Update `streamlit_app/api_client.py` — `upload_and_validate_import()`, `download_template()`

- [x] **5.6** Tests — 26 new tests in `tests/test_import_tools_api.py` (all passing)
  - 6 registration, 4 parse_import_file, 3 detect_import_columns, 2 parse_and_validate, 5 service, 6 API endpoint

- [x] **5.7** Updated existing tests: tool count 155→158, agent tool counts, navigation page count 23→24

---

## Session D: Audit Trail

### Phase 6: Import History

- [x] **6.1** `ImportHistoryModel` in `api/database/models.py`
  - import_id, plant_id, source, filename, file_size_kb, total_rows, valid_rows, error_rows, status, errors_json, imported_by, imported_at

- [x] **6.2** `ImportHistoryEntry` schema + API endpoints
  - `GET /import/history`, `GET /import/history/{id}`
  - Service functions: `record_import_history()`, `list_import_history()`, `get_import_history_entry()`
  - `upload_and_validate()` now calls `record_import_history()` automatically

- [x] **6.3** History tab (Tab 5) on Page 15
  - Status icons (🟢/🟡/🔴), source filter, expandable entries with error details

- [x] **6.4** Tests — 15 new tests across 5 classes (41 total in file)
  - `TestImportHistoryModel`, `TestImportHistorySchema`, `TestImportStatusHelper`, `TestRecordImportHistory`, `TestListImportHistory`, `TestImportHistoryAPIEndpoints`

- [x] **6.5** i18n keys added (history_tab, history_empty, history_source, history_status, etc.)

- [x] **6.6** Bug fix: `record_import_history()` now generates import_id/imported_at explicitly (not relying on ORM defaults before flush)

---

## Critical Files Reference

| File | Role |
|------|------|
| `tools/engines/file_parser_engine.py` | NEW — Excel/CSV parsing |
| `tools/engines/data_import_engine.py` | Existing — validation, extend with parse_and_validate + 11 types |
| `tools/models/schemas.py` | Existing — ImportSource enum (3→14), new FileParseResult |
| `streamlit_app/pages/15_reports_data.py` | Existing — wire file uploader, error viz |
| `agents/tool_wrappers/reporting_tools.py` | Existing — add 3 MCP tools |
| `api/routers/reporting.py` | Existing — add upload/batch/template endpoints |
| `api/services/reporting_service.py` | Existing — add upload_and_validate |
| `templates/generate_templates.py` | Reference — all 14 template column definitions |
| `skills/00-knowledge-base/data-models/failure-modes/MASTER.md` | Reference — 72-combo validation |

## Verification Checklist

- [ ] Unit tests pass: `pytest tests/test_file_parser_engine.py tests/test_data_import_engine.py -v`
- [ ] Template round-trip: parse each of 14 templates → validate → 0 errors on example rows
- [ ] Page 15 works: upload `01_equipment_hierarchy.xlsx` → 5 rows parsed → columns detected → 5/5 valid
- [ ] API works: `curl -F file=@templates/01_equipment_hierarchy.xlsx .../import/upload?source=EQUIPMENT_HIERARCHY`
- [ ] Full suite: `pytest --tb=short -q` — 2,244+ existing + ~64 new tests pass
