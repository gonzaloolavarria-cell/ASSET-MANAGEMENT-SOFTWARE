# G-02 Execution Document — Import Pipeline Completion

> **Gap:** G-02 — Import pipeline incomplete
> **Related Gaps:** G-18 (Import engine can't parse files)
> **Related Workshop Gap:** GAP-W12 (Data Import from External Systems)
> **Sessions:** A–D (Session 26 + 27)
> **Status:** ✅ CLOSED
> **Last Updated:** 2026-03-11 (Session 27 — Session D: Import History complete)

---

## Summary

G-02 identified three missing pieces in the import pipeline:

1. `DataImportEngine` could only accept `list[dict]` — no file parsing
2. No MCP tool wrappers for import operations
3. No validation error UI on Page 15

All three were addressed via GAP-W12 (4 sessions: A–D). Import History (audit trail) was added in Session D. All tests pass. G-02 is fully closed.

---

## What Was Built

### Session A — File Parsing Engine

| Deliverable | File | Description |
|-------------|------|-------------|
| `FileParserEngine` | `tools/engines/file_parser_engine.py` | Parses `.xlsx` (openpyxl) and `.csv` (csv.Sniffer); 10 MB limit; sheet selector |
| `DataImportEngine` extended | `tools/engines/data_import_engine.py` | `ImportSource` expanded from 3 → 14 types; `_REQUIRED_COLUMNS` + `_COLUMN_ALIASES`; `parse_and_validate()` |
| New schemas | `tools/models/schemas.py` | `FileParseResult`, `FileParseError`, `ImportResult`, `ImportValidationError`, `ImportSource` |

### Session B — Page 15 Upload Pipeline

| Deliverable | File | Description |
|-------------|------|-------------|
| Page 15 wired | `streamlit_app/pages/15_reports_data.py` | Upload → parse → sheet selector → column mapper → validate → error display → DB ingest |
| Column mapper | `streamlit_app/components/column_mapper.py` | Source→target column mapping with confidence color-coding |
| Error display | `streamlit_app/components/import_errors.py` | Summary metrics, error table (row/col/msg/severity), download CSV, data preview |
| i18n keys | `streamlit_app/i18n/*.json` | 23 new `import.*` keys in EN/FR/ES/AR |

### Session C — MCP Tools + API Endpoints

| Deliverable | File | Description |
|-------------|------|-------------|
| Import MCP tools | `agents/tool_wrappers/import_tools.py` | `import_data_file`, `get_import_history`, `list_import_sources` |
| Reporting MCP tools | `agents/tool_wrappers/reporting_tools.py` | `parse_import_file`, `detect_import_columns`, `parse_and_validate_import` |
| Import router | `api/routers/imports.py` | `POST /import/file`, `GET /import/history`, `GET /import/sources` |
| Reporting router additions | `api/routers/reporting.py` | `POST /reporting/import/upload`, `POST /reporting/import/batch`, `GET /reporting/import/template/{n}` |
| Import service | `api/services/import_service.py` | `import_file()`, `list_import_history()`, `_result_status()` |
| Reporting service additions | `api/services/reporting_service.py` | `upload_and_validate()`, `detect_source_from_filename()` |
| API client methods | `streamlit_app/api_client.py` | `upload_and_validate_import()`, `download_template()`, `import_file()` |
| Tests | `tests/test_import_tools_api.py` | 26 initial tests |

### Session D — Import History (Audit Trail)

| Deliverable | File | Description |
|-------------|------|-------------|
| `ImportHistoryModel` ORM | `api/database/models.py` | Full audit columns; indexed on `plant_id` + `source`; `uuid4` PK |
| `ImportHistoryEntry` schema | `tools/models/schemas.py` | Pydantic v2 model; `ImportSource` enum field; optional `imported_by` |
| Service methods | `api/services/reporting_service.py` | `record_import_history()`, `list_import_history()`, `get_import_history_entry()`, `_import_status()` |
| `upload_and_validate()` wired | `api/services/reporting_service.py` | Every upload now auto-persists a history record |
| History API endpoints | `api/routers/reporting.py` | `GET /reporting/import/history` (filter + paginate) + `GET /reporting/import/history/{import_id}` |
| API client methods | `streamlit_app/api_client.py` | `get_import_history()`, `get_import_history_entry()` |
| Import History tab | `streamlit_app/pages/15_reports_data.py` | Tab 5: status badges (🟢🟡🔴), expandable error details, source filter |
| i18n keys | `streamlit_app/i18n/*.json` | 10 `import.history_*` keys + `common.refresh` in EN/ES/FR/AR |
| Tests (8 classes) | `tests/test_import_tools_api.py` | ORM model, schema, status helper, record, list, API endpoints |

---

## Architecture

```
User (Page 15)
    │
    ├── Tab 3: Upload New File
    │     FileParserEngine ──► DataImportEngine.parse_and_validate()
    │           │                         │
    │     openpyxl / csv              column detection + validation
    │           │                         │
    │     POST /import/file ──► import_service.import_file()
    │           │                         │
    │     ImportHistoryModel ◄── record_import_history()
    │
    └── Tab 5: Import History
          GET /reporting/import/history ──► list_import_history()
                                                │
                                          ImportHistoryModel
                                          (SQLite → PostgreSQL ready)
```

---

## Data Model: ImportHistoryModel

```python
class ImportHistoryModel(Base):
    __tablename__ = "import_history"
    import_id    = String(50)  PK  # uuid4 — generated before ORM flush
    plant_id     = String(50)      # e.g. "OCP-JFC" (defaults to "")
    source       = String(50)      # ImportSource enum value
    filename     = String(255)
    file_size_kb = Integer         # nullable
    total_rows   = Integer
    valid_rows   = Integer
    error_rows   = Integer
    status       = String(20)      # "success" | "partial" | "failed"
    errors_json  = Text            # JSON-encoded list[ImportValidationError]
    imported_by  = String(100)     # nullable (future auth hook)
    imported_at  = DateTime        # datetime.now() generated at service layer
```

**Status logic (`_import_status`):**
- `error_rows == 0` → `"success"`
- `0 < error_rows < total_rows` → `"partial"`
- `error_rows == total_rows` → `"failed"`

---

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/import/file` | Parse + validate + persist (primary endpoint) |
| GET | `/api/v1/import/history` | List history (filter: plant_id, source; paginate) |
| GET | `/api/v1/import/sources` | List available ImportSource values |
| POST | `/api/v1/reporting/import/upload` | Parse + validate via reporting router |
| POST | `/api/v1/reporting/import/batch` | Batch upload (auto-detect source from filename prefix) |
| GET | `/api/v1/reporting/import/template/{n}` | Download Excel template (1–14) |
| GET | `/api/v1/reporting/import/history` | List history via reporting router (filter + paginate) |
| GET | `/api/v1/reporting/import/history/{id}` | Get single history entry or 404 |

---

## Test Coverage

| Test Class | Count | Coverage |
|------------|-------|----------|
| `TestImportToolsRegistered` | 6 | Tool registry + orchestrator/planning maps + tool count ≥ 158 |
| `TestParseImportFileTool` | 4 | File parsing, path traversal blocked, disallowed dir, nonexistent |
| `TestDetectImportColumnsTool` | 3 | Exact match (confidence=1.0), aliases, no match (confidence=0.0) |
| `TestParseAndValidateImportTool` | 2 | Full pipeline (template + explicit column mapping) |
| `TestReportingServiceImport` | 5 | upload_and_validate, bad extension, oversized file, source detection |
| `TestImportAPIEndpoints` | 6 | Template download, upload, bad extension, batch, unknown prefix |
| `TestImportHistoryModel` | 2 | `__tablename__`, all required columns present |
| `TestImportHistorySchema` | 1 | Round-trip: construct → model_dump |
| `TestImportStatusHelper` | 4 | success / partial / failed / zero rows |
| `TestRecordImportHistory` | 2 | `db.add()` called, correct status with errors |
| `TestListImportHistory` | 2 | Empty list, not-found returns None |
| `TestImportHistoryAPIEndpoints` | 4 | List endpoint, plant filter, 404, upload creates history entry |
| **Total** | **~41** | |

---

## Verification Checklist

- [x] `pytest tests/test_import_tools_api.py -v` — all 41 tests pass
- [x] `pytest --tb=short -q` — full suite passes (0 failures)
- [x] `ImportHistoryModel.__tablename__ == "import_history"` ✓
- [x] `record_import_history()` calls `db.add()` with correct fields ✓
- [x] `upload_and_validate()` automatically persists history ✓
- [x] `GET /reporting/import/history` returns 200 with list ✓
- [x] `GET /reporting/import/history/{nonexistent}` returns 404 ✓
- [x] Status: all_valid→"success", partial→"partial", all_failed→"failed" ✓
- [x] `import_id` and `imported_at` generated explicitly (no ORM default timing issue) ✓
- [x] MASTER_PLAN.md: G-02 CLOSED, T-13/T-14/T-15/T-16 struck through, B-1–B-4 done ✓
- [x] `docs/GAP-W12_EXECUTION.md`: Session D all items checked ✓
