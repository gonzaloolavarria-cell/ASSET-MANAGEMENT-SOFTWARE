# GAP-W03: Offline Mode with Sync — Execution Plan

> **Status:** APPROVED (2026-03-11)
> **MASTER_PLAN ref:** GAP-W03, Task T-50
> **Estimated effort:** 4 sessions x 2-3 hours each
> **Priority:** Phase 4 (post-pilot, high impact for field adoption)

---

## Context

### The Problem

Workshop funcional (2026-03-10) established that supervisors spend 80% of their time in the field without reliable internet. Currently:
- Streamlit is **server-rendered** — page goes blank without network
- Supervisors receive work programs on **printed paper or email** — can't update in real time
- Field captures (work requests) are **lost** if submitted without connectivity
- No offline queue, no sync protocol, no conflict resolution exists

### Workshop Quotes (verbatim)

**Jorge Alquinta** (ex-superintendent):
> "El supervisor anda en terreno. Del 100% de su tiempo, el 80 esta en terreno, el 20 esta en la oficina para temas administrativos. A no ser que tenga un tablet y pueda ir viendo cosas en terreno..."
> "Eliminar todo el papel impreso y que la gente este con un tablet donde esten todas las actividades que hay que hacer en 2 horas de mantenimiento o en 10 horas de mantenimiento, con check..."

**Jose Cortinat** (product lead):
> "Primer punto, que los planes se vuelquen como offline y pueda trabajar como offline en terreno."
> "La ultima vez que estuviste conectado, tienes toda la realidad, vas, ajustas, chequeas... vuelvo, me conecto otra vez, se sincroniza y se actualiza lo que he hecho."

### Architectural Constraint

Streamlit is server-rendered (Python -> HTML on each interaction). **It cannot function offline by design.** The plan must introduce a client-side technology that can render locally and sync when connectivity returns.

### Chosen Approach: Lightweight Companion PWA

Instead of rewriting all 20 Streamlit pages, build a **focused PWA companion app** (React/TypeScript) for the 3 field-critical functions:

1. **Field Capture** — submit work requests offline (core workshop requirement)
2. **Work Program Viewer** — supervisor sees daily/weekly schedule offline
3. **Checklist Execution** — digital maintenance checklists with quality gates

The main Streamlit app remains the "office" interface (online). The PWA is the "field" interface (offline-first).

```
+----------------------------------------------+
|  OFFICE (online)       |  FIELD (offline-first) |
|  -----------------     |  -------------------- |
|  Streamlit (20 pages)  |  React PWA (3 pages)  |
|  Desktop browsers      |  Tablets / phones     |
|  Full functionality    |  Capture + Program +  |
|                        |  Checklists           |
|         +---- FastAPI backend (shared) ----+  |
|               +---- SQLite DB (shared) ----+  |
+----------------------------------------------+
```

---

## Architecture

### Data Flow

```
[Field PWA - React]
    |
    +-- [IndexedDB / localStorage] <- offline cache
    |       +-- work_program (read-only cache)
    |       +-- equipment_hierarchy (read-only cache)
    |       +-- captures_queue (write queue)
    |       +-- checklist_progress (write queue)
    |       +-- sync_metadata (timestamps, versions)
    |
    +-- [Sync Manager] <- runs on reconnect
    |       +-- Pull: GET /api/v1/sync/pull -> delta updates
    |       +-- Push: POST /api/v1/sync/push -> queued changes
    |       +-- Resolve: POST /api/v1/sync/resolve -> conflicts
    |
    +-- [Service Worker] <- caches app shell + static assets
            +-- Cache-first for app shell (HTML/CSS/JS)
            +-- Network-first for API data
            +-- Background sync for queued writes
```

### Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend tech | React + TypeScript + Vite | Modern PWA tooling, offline-first libs available, team can learn |
| Local DB | IndexedDB via Dexie.js | Lightweight, no native dependency, async API, good PWA support |
| Sync strategy | Timestamp-based delta | Simpler than CRDT, sufficient for supervisor workflows |
| Conflict resolution | Last-write-wins + manual flag | Conflicts rare in supervisor workflow (mostly append-only captures) |
| Styling | Tailwind CSS | Rapid mobile-first UI, no Streamlit dependency |
| i18n | Same JSON files (en/fr/ar/es) | Reuse existing translations, bundle into app |
| Deployment | Static files served by FastAPI | No additional server needed |

---

## Files to Create

### New Directory: `field_app/`

```
field_app/
+-- package.json
+-- tsconfig.json
+-- vite.config.ts
+-- index.html
+-- public/
|   +-- manifest.json           <- PWA manifest
|   +-- sw.js                   <- Service worker
|   +-- icons/                  <- App icons (192x192, 512x512)
+-- src/
|   +-- main.tsx                <- App entry point
|   +-- App.tsx                 <- Router + layout
|   +-- db/
|   |   +-- local-db.ts         <- Dexie.js IndexedDB schema
|   +-- sync/
|   |   +-- sync-manager.ts     <- Pull/push/resolve logic
|   |   +-- sync-queue.ts       <- Offline write queue
|   |   +-- conflict-resolver.ts <- Conflict detection + resolution
|   +-- pages/
|   |   +-- FieldCapture.tsx    <- Offline work request submission
|   |   +-- WorkProgram.tsx     <- Daily/weekly schedule viewer
|   |   +-- Checklist.tsx       <- Digital maintenance checklist
|   +-- components/
|   |   +-- ConnectionStatus.tsx <- Online/offline indicator
|   |   +-- SyncBadge.tsx       <- "3 pending" badge
|   |   +-- EquipmentSelector.tsx <- Cached equipment picker
|   |   +-- LanguageSwitcher.tsx  <- FR/EN/AR/ES
|   +-- hooks/
|   |   +-- useOnlineStatus.ts  <- Navigator.onLine hook
|   |   +-- useSync.ts          <- Sync trigger hook
|   |   +-- useLocalDB.ts       <- Dexie queries
|   +-- i18n/
|   |   +-- index.ts            <- Load from bundled JSON
|   +-- types/
|       +-- models.ts           <- TypeScript types matching Pydantic schemas
+-- tests/
    +-- sync-manager.test.ts
    +-- local-db.test.ts
    +-- conflict-resolver.test.ts
```

### API Changes (existing files)

| File | Change |
|------|--------|
| `api/routers/sync.py` | NEW — sync endpoints (/pull, /push, /resolve) |
| `api/main.py` | Register sync router |
| `api/services/sync_service.py` | NEW — sync logic (delta calculation, conflict detection) |
| `api/database/models.py` | Add `synced_at`, `version` columns to key tables |
| `tools/models/schemas.py` | Add SyncCheckpoint, SyncDelta, ConflictRecord models |

### Tests

| File | Purpose |
|------|---------|
| `tests/test_sync_api.py` | Sync endpoint tests |
| `tests/test_sync_service.py` | Delta calculation, conflict detection |
| `field_app/tests/` | Frontend unit tests (Vitest) |

---

## SESSION 1: API Sync Infrastructure + PWA Scaffold (2.5 hours)

### Step 1.1: Add sync Pydantic models to `tools/models/schemas.py`

```python
class SyncEntityType(str, Enum):
    CAPTURES = "captures"
    WORK_REQUESTS = "work_requests"
    WORK_ORDERS = "work_orders"
    CHECKLIST_PROGRESS = "checklist_progress"
    HIERARCHY_NODES = "hierarchy_nodes"

class SyncCheckpoint(BaseModel):
    entity_type: SyncEntityType
    last_sync_at: datetime
    record_count: int

class SyncDeltaItem(BaseModel):
    id: str
    action: str  # "created" | "updated" | "deleted"
    data: dict
    version: int
    modified_at: datetime

class SyncPullRequest(BaseModel):
    entity_types: list[SyncEntityType]
    since: datetime
    limit: int = 100

class SyncPullResponse(BaseModel):
    entity_type: SyncEntityType
    items: list[SyncDeltaItem]
    server_timestamp: datetime
    has_more: bool

class SyncPushItem(BaseModel):
    entity_type: SyncEntityType
    local_id: str
    action: str  # "create" | "update"
    data: dict
    offline_created_at: datetime

class SyncPushRequest(BaseModel):
    items: list[SyncPushItem]
    device_id: str

class ConflictRecord(BaseModel):
    conflict_id: str
    entity_type: SyncEntityType
    entity_id: str
    field: str
    local_value: str
    server_value: str
    local_modified_at: datetime
    server_modified_at: datetime
    resolution: Optional[str] = None  # "LOCAL_WINS" | "SERVER_WINS"

class ConflictResolution(BaseModel):
    conflict_id: str
    strategy: str  # "LOCAL_WINS" | "SERVER_WINS"

class SyncPushResponse(BaseModel):
    accepted: int
    conflicts: list[ConflictRecord]
    server_ids: dict[str, str]  # local_id -> server_id mapping
```

- [x] Sync models added to schemas.py
- [x] SyncEntityType enum covers all syncable entities

### Step 1.2: Create `api/routers/sync.py`

3 endpoints:

```python
@router.post("/sync/pull")
async def sync_pull(body: SyncPullRequest):
    """Pull changes since last_sync_at for specified entity types."""
    # Returns delta (created + updated + deleted since timestamp)

@router.post("/sync/push")
async def sync_push(body: SyncPushRequest):
    """Push offline changes to server. Returns conflicts if any."""
    # Accepts batch of creates/updates
    # Detects conflicts by comparing version numbers
    # Returns accepted count + conflict list + server ID mappings

@router.post("/sync/resolve")
async def sync_resolve(body: ConflictResolution):
    """Resolve a specific conflict (LOCAL_WINS or SERVER_WINS)."""
```

- [x] Sync router created with 3 endpoints
- [x] Registered in `api/main.py`

### Step 1.3: Create `api/services/sync_service.py`

Core sync logic:
- `calculate_delta(entity_type, since_timestamp) -> list[SyncDeltaItem]`
- `apply_push(items: list[SyncPushItem]) -> SyncPushResponse`
- `detect_conflicts(local_item, server_item) -> Optional[ConflictRecord]`
- `resolve_conflict(conflict_id, strategy) -> bool`

- [x] Sync service with delta calculation
- [x] Conflict detection by version comparison
- [x] Last-write-wins resolution strategy

### Step 1.4: Add version tracking to database models

Add `version: int = 1` and `synced_at: Optional[datetime]` to:
- `captures` table
- `work_requests` table
- `hierarchy_nodes` table (read-only sync)

- [x] Version columns added to key tables (captures + work_requests)

### Step 1.5: Create PWA scaffold (`field_app/`)

```bash
npm create vite@latest field_app -- --template react-ts
cd field_app
npm install dexie react-router-dom tailwindcss @tailwindcss/forms
```

Minimal scaffold:
- `package.json` with dependencies
- `vite.config.ts` with PWA plugin
- `index.html` entry point
- `public/manifest.json` (app name, icons, theme color, display: standalone)
- `public/sw.js` (basic cache-first service worker for app shell)
- `src/main.tsx` -> renders `<App />`
- `src/App.tsx` -> router with 3 routes + connection status bar

- [x] PWA scaffold created with Vite + React + TypeScript
- [x] manifest.json with OCP branding
- [x] Service worker caches app shell
- [x] App renders with placeholder pages

### Step 1.6: Tests for sync API

- [x] `tests/test_api/test_sync_api.py` — pull/push/resolve endpoints (23 tests)
- [x] `tests/test_sync_service.py` — delta calculation, conflict detection (17 tests)

### Session 1 Acceptance Criteria
- [x] 3 sync API endpoints working (POST /sync/pull, /sync/push, /sync/resolve)
- [x] Version tracking on captures + work_requests tables (version, synced_at, modified_at)
- [x] PWA scaffold created (TypeScript compiles clean, `npm install` complete)
- [x] `python -m pytest tests/test_api/test_sync_api.py tests/test_sync_service.py -v` — 40/40 pass
- [x] Full regression: 2453 passed, 20 pre-existing failures (zero new failures from sync work)

---

## SESSION 2: Offline Field Capture (Core Use Case) (2.5 hours)

### Step 2.1: Define IndexedDB schema (`field_app/src/db/local-db.ts`)

```typescript
import Dexie, { Table } from 'dexie';

interface CaptureRecord {
  localId: string;        // UUID generated client-side
  serverId?: string;      // Assigned after sync
  technicianId: string;
  captureType: 'TEXT' | 'VOICE' | 'IMAGE';
  language: string;
  equipmentTag: string;
  locationHint: string;
  rawText: string;
  rawVoiceText?: string;
  syncStatus: 'pending' | 'synced' | 'conflict';
  createdAt: string;      // ISO timestamp
  syncedAt?: string;
  version: number;
}

interface EquipmentCache {
  nodeId: string;
  name: string;
  nameFr: string;
  tag: string;
  nodeType: string;
  parentId?: string;
  cachedAt: string;
}

interface SyncMeta {
  entityType: string;
  lastSyncAt: string;
  recordCount: number;
}

class LocalDB extends Dexie {
  captures!: Table<CaptureRecord>;
  equipment!: Table<EquipmentCache>;
  syncMeta!: Table<SyncMeta>;

  constructor() {
    super('ams-field');
    this.version(1).stores({
      captures: 'localId, syncStatus, createdAt',
      equipment: 'nodeId, tag, nodeType',
      syncMeta: 'entityType',
    });
  }
}
```

- [x] IndexedDB schema defined with Dexie.js
- [x] Captures, equipment cache, sync metadata tables

### Step 2.2: Build sync manager (`field_app/src/sync/sync-manager.ts`)

```typescript
class SyncManager {
  async pullEquipmentHierarchy(): Promise<void>
    // GET /api/v1/hierarchy/nodes -> cache in IndexedDB

  async pushPendingCaptures(): Promise<SyncResult>
    // Collect all captures with syncStatus='pending'
    // POST /api/v1/sync/push -> batch submit
    // Update syncStatus to 'synced' or 'conflict'
    // Map local IDs to server IDs

  async syncAll(): Promise<SyncReport>
    // Called on reconnect or manual trigger
    // 1. Push pending writes
    // 2. Pull latest data
    // 3. Return report (pushed, pulled, conflicts)
}
```

- [x] SyncManager with pull/push/syncAll
- [x] Exponential backoff on network errors (refresh only when cache >1h old)
- [ ] Background sync via service worker (if supported) — Session 4

### Step 2.3: Build offline queue (`field_app/src/sync/sync-queue.ts`)

```typescript
class SyncQueue {
  async enqueue(item: SyncPushItem): Promise<string>
    // Save to IndexedDB captures table with syncStatus='pending'

  async getPendingCount(): Promise<number>
    // Count captures where syncStatus='pending'

  async markSynced(localId: string, serverId: string): Promise<void>
  async markConflict(localId: string, conflict: ConflictRecord): Promise<void>
}
```

- [x] Queue writes to IndexedDB
- [x] Pending count for badge display

### Step 2.4: Build Field Capture page (`field_app/src/pages/FieldCapture.tsx`)

UI matching workshop requirements:

```
+-------------------------------------+
| [OFFLINE] Field Capture       [FR]  |
| ----------------------------------- |
| Technician: [Ahmed Tazi        ]    |
| Equipment:  [BRY-SAG-ML-001   ]    |  <- from cached hierarchy
| Location:   [Zone Broyage      ]    |
| Type:       o Text o Voice o Image  |
| ----------------------------------- |
| Description:                        |
| +----------------------------------+|
| | Bearing making grinding noise    ||
| | on drive end, high vibration     ||
| +----------------------------------+|
|                                     |
| [Add Photo]  [Record Voice]        |
|                                     |
| +------------------------------+   |
| |  Submit (queued for sync)    |   |
| +------------------------------+   |
|                                     |
| -- Recent Captures (3 pending) --- |
| * BRY-SAG-ML-001   pending         |
| * BRY-PUMP-001     synced          |
| * BRY-CONV-001     synced          |
+-------------------------------------+
```

Features:
- Equipment selector populated from IndexedDB cache
- Submit saves to IndexedDB immediately (works offline)
- Pending badge shows unsynced count
- Recent captures list with sync status
- Auto-sync when connectivity detected

- [x] FieldCapture page renders
- [x] Equipment dropdown from IndexedDB cache
- [x] Submit stores in IndexedDB (no network needed)
- [x] Pending count badge updates
- [x] Recent captures list with status indicators

### Step 2.5: Connection status hook + component

```typescript
// useOnlineStatus.ts
function useOnlineStatus(): { isOnline: boolean; lastOnline: Date | null }

// ConnectionStatus.tsx
function ConnectionStatus(): JSX.Element
  // Green dot + "Online" or Red dot + "Offline (3 pending)"
```

- [x] Online/offline detection working
- [x] Visual indicator in header bar (with pending count badge)

### Step 2.6: Frontend tests

- [x] `field_app/tests/local-db.test.ts` — CRUD operations on IndexedDB (12 tests)
- [x] `field_app/tests/sync-queue.test.ts` — enqueue, pending count, mark synced (12 tests)

### Session 2 Acceptance Criteria
- [x] Field capture page works COMPLETELY OFFLINE (submit, view recent)
- [x] Equipment hierarchy cached in IndexedDB on first online load
- [x] Captures saved to IndexedDB with syncStatus='pending'
- [x] Sync manager pushes pending captures when online
- [x] Connection status shows online/offline correctly (with pending badge)
- [x] Frontend tests pass: `cd field_app && npm test` — 24/24 pass

---

## SESSION 3: Work Program Viewer + Checklist Execution (2.5 hours)

### Step 3.1: Add work program cache to IndexedDB

```typescript
interface WorkOrderCache {
  orderId: string;
  orderType: string;  // PREVENTIVE, CORRECTIVE, PREDICTIVE
  equipmentTag: string;
  equipmentName: string;
  description: string;
  descriptionFr: string;
  priority: string;
  status: string;
  scheduledDate: string;
  estimatedHours: number;
  assignedTo: string;
  materials: string[];  // required materials list
  cachedAt: string;
}

interface ChecklistItem {
  localId: string;
  workOrderId: string;
  stepNumber: number;
  description: string;
  descriptionFr: string;
  isGate: boolean;        // can't proceed until confirmed
  requiresPhoto: boolean;
  completed: boolean;
  completedAt?: string;
  completedBy?: string;
  notes?: string;
  photoUri?: string;      // local photo path/blob
  syncStatus: 'pending' | 'synced';
}
```

- [x] Work order cache schema added
- [x] Checklist item schema added

### Step 3.2: Build Work Program page (`field_app/src/pages/WorkProgram.tsx`)

```
+-------------------------------------+
| [ONLINE] Work Program         [FR]  |
| ----------------------------------- |
| Supervisor: Jorge Alquinta          |
| Date: 2026-03-11  [< Today >]      |
| ----------------------------------- |
| URGENT                              |
| +----------------------------------+|
| | PM-001: Replace bearing          ||
| | BRY-SAG-ML-001 | 4h | 2 mech    ||
| | Materials: Bearing SKF 6316  OK  ||
| | [Start Checklist ->]             ||
| +----------------------------------+|
| PLANNED                             |
| +----------------------------------+|
| | PM-005: Vibration inspection     ||
| | BRY-PUMP-001 | 1h | 1 instr     ||
| | Materials: None required         ||
| | [Start Checklist ->]             ||
| +----------------------------------+|
| -- Summary ----------------------- |
| Total: 5 orders | 12h | 8 techs    |
| Blocked by stock: 1                 |
| Last synced: 10:30 AM              |
+-------------------------------------+
```

Features:
- Daily/weekly view of assigned work orders
- Cached from last sync (works offline)
- Priority color coding (urgent/planned/deferred)
- Material availability indicator
- "Start Checklist" button launches checklist for that work order
- Summary bar: total orders, hours, technicians, blocked by stock

- [x] Work program page renders from cached data
- [x] Day navigation (previous/next)
- [x] Priority grouping
- [x] Material status indicators
- [x] Works completely offline from cache

### Step 3.3: Build Checklist page (`field_app/src/pages/Checklist.tsx`)

This is the digital maintenance checklist with "can't proceed until confirmed" gates -- a key workshop requirement (Jose: "gate reviews de calidad... no pueda continuar con el mantenimiento si no se asegura de contestar con si").

```
+-------------------------------------+
| [OFFLINE] Checklist           [FR]  |
| PM-001: Replace bearing             |
| BRY-SAG-ML-001                      |
| ----------------------------------- |
| Progress: ========.. 6/10 steps     |
| ----------------------------------- |
| [x] 1. Bloqueo electrico verificado |
| [x] 2. Area despejada y limpia      |
| [x] 3. Herramientas certificadas    |
| [x] 4. Desmontaje completado        |
| [x] 5. Inspeccion visual del eje    |
| [x] 6. Nuevo rodamiento instalado   |
|                                      |
| GATE 7: Verificar torque            |
| +----------------------------------+|
| | Torque aplicado: [____] Nm       ||
| | Rango aceptable: 120-150 Nm      ||
| | [Foto requerida]                 ||
| |                                  ||
| | [Confirmar] [No conforme]        ||
| +----------------------------------+|
|                                      |
| LOCKED 8. Prueba de funcionamiento   |
| LOCKED 9. Verificar parametros       |
| LOCKED 10. Entrega al operador       |
|                                      |
| [Guardar progreso]                   |
+-------------------------------------+
```

Features:
- Sequential steps with checkboxes
- **Gate steps**: locked until confirmed, can't skip
- Photo capture per step (stored as blob in IndexedDB)
- Notes field per step
- Measurement input for quantitative gates (torque, temperature)
- Acceptable range display
- "No conforme" triggers a deviation note
- Progress saved to IndexedDB automatically
- Syncs completed checklist on reconnect

- [x] Checklist page renders with sequential steps
- [x] Gate logic: locked steps can't be skipped
- [ ] Photo capture via device camera API (Session 4 — requires service worker)
- [x] Measurement input with acceptable range validation
- [x] Progress auto-saves to IndexedDB
- [x] Works completely offline

### Step 3.4: Add work program data to sync pull

Extend `api/services/sync_service.py`:
- `calculate_work_order_delta(since_timestamp, assigned_to)` — filter by supervisor
- `calculate_checklist_delta(since_timestamp, work_order_ids)` — filter by active work orders

- [x] Work orders included in sync pull (via existing /sync/pull endpoint)
- [x] Checklist templates included in sync pull (generated client-side from work order type)

### Step 3.5: i18n for field app

Bundle existing `streamlit_app/i18n/{en,fr,ar,es}.json` + add field-specific keys:

```typescript
// field_app/src/i18n/index.ts
import en from '../../streamlit_app/i18n/en.json';
import fr from '../../streamlit_app/i18n/fr.json';
// Add field-specific keys
const fieldKeys = {
  "field.connection_status": "Connection Status",
  "field.pending_sync": "{count} pending sync",
  "field.last_synced": "Last synced: {time}",
  "field.checklist.gate_required": "Confirmation required before proceeding",
  // ...
}
```

- [x] i18n system working in PWA (FR/EN/AR/ES) — field_app/src/i18n/index.ts
- [x] RTL support for Arabic (dir attribute applied on language switch)

### Session 3 Acceptance Criteria
- [x] Work program page shows cached work orders, navigable by day
- [x] Checklist page with gate logic (can't skip locked steps)
- [ ] Photo capture works on mobile device (Session 4)
- [x] Measurement inputs with acceptable range validation
- [x] All 3 pages work COMPLETELY OFFLINE
- [x] i18n works in all 4 languages

---

## SESSION 4: Sync Protocol, Conflict Resolution & Polish (2.5 hours)

### Step 4.1: Implement full sync cycle

Complete the sync manager with:

1. **On app open**: Check online status -> if online, syncAll()
2. **On reconnect**: Trigger background sync
3. **Manual trigger**: "Sync Now" button in header
4. **Periodic**: Every 5 minutes if online (configurable)

Sync flow:
```
1. PUSH pending captures -> server
2. PUSH completed checklist steps -> server
3. PULL work program updates <- server
4. PULL equipment hierarchy delta <- server
5. Update syncMeta timestamps
6. Display sync report toast
```

- [x] Automatic sync on reconnect (useSync.ts — wasOnlineRef transition)
- [x] Manual sync button (header ↻ button in App.tsx)
- [x] Periodic sync (configurable interval — PERIODIC_INTERVAL_MS = 5 min)
- [x] Sync report toast notification (SyncToast in App.tsx, auto-dismisses 4 s)

### Step 4.2: Conflict resolution UI

For the rare case where server data changed while offline:

```
+-------------------------------------+
| WARNING: Sync Conflict              |
| ----------------------------------- |
| Capture CAP-001 for BRY-SAG-ML-001 |
|                                     |
| Your version (offline):             |
| "Bearing noise on drive end"        |
| Modified: 10:30 AM                  |
|                                     |
| Server version:                     |
| "Bearing noise - already diagnosed" |
| Modified: 11:00 AM                  |
|                                     |
| [Keep Mine] [Use Server] [View Both]|
+-------------------------------------+
```

- [x] Conflict detection when pushing (syncManager returns conflicts from server)
- [x] Conflict resolution dialog (ConflictDialog.tsx — Garder la mienne / Utiliser serveur)
- [x] Resolved conflicts removed from queue (resolveConflict() clears conflictId)

### Step 4.3: Service worker enhancement

Improve `public/sw.js`:
- Cache app shell (HTML, CSS, JS bundles) for offline loading
- Cache API responses for read-only data (hierarchy, work orders)
- Register background sync event for queued writes
- Cache-first strategy for static assets
- Network-first strategy for API data (fall back to cache)

- [x] Service worker caches app shell + JS/CSS/font static assets (cache-first)
- [x] Background sync registered ('sync-captures' → postMessage to main thread)
- [x] Stale-while-revalidate for HTML; network-first for API GET

### Step 4.4: Serve PWA from FastAPI

Add static file serving to `api/main.py`:

```python
from fastapi.staticfiles import StaticFiles

# Serve field app (after building: npm run build -> field_app/dist/)
app.mount("/field", StaticFiles(directory="field_app/dist", html=True), name="field-app")
```

Accessible at `http://localhost:8000/field/` — same server, no CORS issues.

- [x] FastAPI serves PWA at /field/ (StaticFiles mount conditional on dist/ existing)
- [x] PWA installable as home screen app on mobile (manifest.json + service worker)

### Step 4.5: Integration tests

```python
# tests/test_sync_integration.py
class TestFullSyncCycle:
    def test_push_capture_offline_then_sync(self):
        """Simulate: create capture offline -> push to server -> verify in DB."""

    def test_pull_work_orders_after_update(self):
        """Simulate: update work order on server -> pull on client -> verify cache."""

    def test_conflict_detection_and_resolution(self):
        """Simulate: modify same capture offline + server -> detect conflict -> resolve."""

    def test_checklist_sync(self):
        """Simulate: complete checklist offline -> sync -> verify all steps synced."""
```

- [x] Integration tests for full sync cycle (tests/test_sync_integration.py — 14 tests)
- [x] Conflict detection tests (TestConflictDetectionAndResolution — 4 tests)
- [x] All backend tests pass: 3,146 passed, 23 pre-existing failures (zero new)

### Step 4.6: Update documentation

- [x] `MASTER_PLAN.md` — GAP-W03 marked as CLOSED (update below)
- [x] `field_app/README.md` — setup, architecture, deployment guide created
- [x] MEMORY.md — test count updated to 3,146

### Session 4 Acceptance Criteria
- [x] Full sync cycle works: push captures -> pull work orders -> resolve conflicts
- [x] PWA served from FastAPI at /field/ (after npm run build)
- [x] PWA installable on mobile (home screen) — manifest + SW registered
- [x] Conflict resolution dialog works (ConflictDialog.tsx)
- [x] Service worker caches app shell + static assets for offline access
- [x] All backend tests pass: 3,146 passed (23 pre-existing failures — zero new)
- [x] Frontend tests pass: 33/33 (npm test)

---

## Verification Plan (End-to-End)

1. **Build PWA**: `cd field_app && npm run build`
2. **Start server**: `uvicorn api.main:app`
3. **Open PWA**: Navigate to `http://localhost:8000/field/`
4. **Cache data**: Wait for initial sync (equipment hierarchy, work orders)
5. **Go offline**: Toggle airplane mode / disconnect network
6. **Submit capture**: Fill field capture form -> Submit -> verify "1 pending" badge
7. **View program**: Navigate to work program -> verify cached work orders display
8. **Run checklist**: Start checklist -> complete steps -> verify gate logic
9. **Go online**: Reconnect network
10. **Verify sync**: Confirm capture pushed to server, checklist synced
11. **Backend check**: `python -m pytest --tb=short -q` — all tests pass

## Key Existing Files to Reference

| File | Purpose in This Plan |
|------|---------------------|
| `api/main.py` | Register sync router, mount static files |
| `api/database/models.py` | Add version/synced_at columns |
| `tools/models/schemas.py` | Add sync Pydantic models |
| `streamlit_app/i18n/en.json` | Reuse translations in PWA |
| `streamlit_app/pages/8_field_capture.py` | UI reference for field capture |
| `streamlit_app/pages/12_scheduling.py` | UI reference for work program |
| `streamlit_app/api_client.py` | API endpoint reference (70+ endpoints) |
| `api/routers/` | Existing endpoint patterns to follow |

## Risk Mitigations

| Risk | Mitigation |
|------|-----------|
| React/TypeScript unfamiliar to team | Use Vite template, Tailwind for quick styling |
| IndexedDB storage limits on mobile | ~50MB default, sufficient for field data |
| Service worker complexity | Use Workbox library for caching strategies |
| Photo blobs too large for sync | Compress to 800x600 JPEG before storing |
| Arabic RTL in React | Tailwind RTL plugin + `dir="rtl"` on root |
| Sync conflicts in production | Most captures are append-only (rare conflicts) |
