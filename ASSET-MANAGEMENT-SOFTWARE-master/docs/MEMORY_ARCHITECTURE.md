# Arquitectura del Sistema de Memoria Jerárquica — AMS

> **Versión**: 1.0 — 2026-03-06
> **Módulo principal**: [`agents/_shared/memory.py`](agents/_shared/memory.py)
> **Tests**: [`tests/test_memory.py`](tests/test_memory.py) (83 tests)

---

## 1. Visión General

### Qué es

El sistema de memoria jerárquica es un mecanismo de persistencia que permite a los agentes de AMS (Asset Management Software) **recordar y aplicar requisitos específicos de cada cliente** a lo largo de un proyecto. La memoria se inyecta en el prompt del sistema de cada agente antes de la ejecución, asegurando que los entregables respeten las restricciones del cliente.

### Problema que resuelve

Sin memoria, cada vez que un agente ejecuta una tarea:
- Pierde las preferencias del cliente descubiertas en milestones anteriores
- No aplica patrones confirmados en revisiones previas
- Repite errores que el revisor ya corrigió
- Ignora restricciones específicas del proyecto (nombrado, idioma, estándares)

### Principio fundamental

```
Los agentes LEEN memoria. Solo el workflow ESCRIBE memoria.
```

Este principio (SWMR — Single Writer, Multiple Readers) garantiza que:
- Los agentes no pueden corromper la memoria accidentalmente
- Toda escritura pasa por validación y sanitización
- Hay una única fuente de verdad para cada aprendizaje

### Flujo de datos completo

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FLUJO DE MEMORIA AMS                            │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐     ┌───────────────────┐     ┌──────────────┐   │
│  │  RFI Excel    │────>│ process_ams_rfi.py │────>│  3-memory/   │   │
│  │  (consultor)  │     │  (seeding)         │     │  (archivos)  │   │
│  └──────────────┘     └───────────────────┘     └──────┬───────┘   │
│                                                         │           │
│                    ┌────────────────────────────────────┘           │
│                    │                                                │
│                    ▼                                                │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Agent.get_system_prompt(milestone=N, memory_dir=...)       │   │
│  │                                                             │   │
│  │  1. Carga CLAUDE.md (instrucciones base)                    │   │
│  │  2. Carga Skills del milestone (procedimientos)             │   │
│  │  3. Carga Memoria del cliente (restricciones)    ◄── ÚLTIMA │   │
│  │                                                             │   │
│  │  Prioridad: CLAUDE.md < Skills < MEMORIA (memoria gana)    │   │
│  └─────────────────────────────────────┬───────────────────────┘   │
│                                         │                           │
│                                         ▼                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Agente ejecuta con memoria inyectada en su prompt          │   │
│  │  → Produce entregables respetando restricciones del cliente │   │
│  └─────────────────────────────────────┬───────────────────────┘   │
│                                         │                           │
│                                         ▼                           │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │  Gate Review (aprobación humana)                            │   │
│  │                                                             │   │
│  │  "approve" + feedback ──> save_pattern()   → patterns.md    │   │
│  │  "modify"  + feedback ──> save_deviation() → DEV-M1-0.md   │   │
│  │  "reject"                 (sin aprendizaje)                 │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
│  El patrón/desviación queda disponible para el PRÓXIMO milestone   │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Arquitectura

### 2.1 Estructura de directorios

Cada proyecto tiene un directorio `3-memory/` dentro de su carpeta de proyecto:

```
ASSET-MANAGEMENT-SOFTWARE-CLIENT/
  clients/{client_slug}/
    projects/{project_slug}/
      0-input/              ← Datos de entrada (RFI, historial, etc.)
      1-output/             ← Entregables generados
      2-state/              ← Estado de sesión, checkpoints, gates
      3-memory/             ← MEMORIA DEL CLIENTE (este sistema)
      │
      ├── global-requirements.md            ← Requisitos transversales
      ├── maintenance-strategy/
      │   ├── requirements.md               ← Requisitos de M1-M2
      │   └── patterns.md                   ← Patrones confirmados
      ├── work-identification/
      │   ├── requirements.md               ← Requisitos de captura WO
      │   └── patterns.md
      ├── work-planning/
      │   ├── requirements.md               ← Requisitos de M3-M4
      │   └── patterns.md
      ├── reliability-engineering/
      │   ├── requirements.md               ← Requisitos de análisis
      │   └── patterns.md
      ├── cost-analysis/
      │   ├── requirements.md               ← Requisitos LCC/costo-riesgo
      │   └── patterns.md
      ├── deviations/                       ← Auto-generado por workflow
      │   ├── DEV-M1-0.md
      │   └── DEV-M2-1.md
      └── meetings/                         ← Notas de reuniones
          └── 2026-03-06_meeting.md

      4-intent-specs/       ← Perfil de intención del cliente
      5-templates/          ← Templates personalizados
```

### 2.2 Categorías de memoria

| Categoría | Archivo típico | Descripción | Quién lo llena |
|-----------|---------------|-------------|----------------|
| **global** | `global-requirements.md` | Nombrado, idioma, estándares, restricciones generales | RFI automático + consultor |
| **stage** | `{stage}/requirements.md` | Requisitos específicos de cada etapa de trabajo | RFI automático + consultor |
| **pattern** | `{stage}/patterns.md` | Enfoques confirmados por el revisor en gates | Workflow automático |
| **deviation** | `deviations/DEV-M1-0.md` | Correcciones solicitadas en gate reviews | Workflow automático |

### 2.3 Modelo de datos

```python
@dataclass(frozen=True)
class MemoryContent:
    source: str    # ruta relativa dentro de 3-memory/ (ej: "global-requirements.md")
    category: str  # "global" | "stage" | "pattern" | "deviation"
    body: str      # contenido markdown
```

El dataclass es **frozen** (inmutable) — una vez cargado, ningún agente puede modificar el contenido en memoria.

### 2.4 Mapeo Milestone → Stages

La constante `MILESTONE_TO_STAGES` en [`memory.py:27-32`](agents/_shared/memory.py) es la **única fuente de verdad** que determina qué memoria se carga en cada milestone:

| Milestone | Stages que se cargan | Razón |
|-----------|---------------------|-------|
| **M1** | `maintenance-strategy` | Construir jerarquía y criticidad — necesita guía de nombrado y método |
| **M2** | `maintenance-strategy` + `reliability-engineering` | FMECA requiere jerarquía + disponibilidad de datos de falla |
| **M3** | `work-planning` + `cost-analysis` | Definir tareas y materiales — necesita convenciones SAP y restricciones de presupuesto |
| **M4** | `work-planning` | Exportación SAP — necesita reglas de campos SAP (heredadas de M3) |

**Nota**: `work-identification` existe como stage válido pero actualmente ningún milestone lo carga. Es un punto de extensión para futuros milestones.

---

## 3. Referencia de Archivos de Memoria

### 3.1 global-requirements.md

**Se carga en**: Todos los milestones (siempre)
**Generado por**: `process_ams_rfi.py` desde el cuestionario RFI
**Editable por**: Consultor

Contiene requisitos que aplican a todas las etapas del proyecto:

| Sección | Variables placeholder | Fuente de datos |
|---------|----------------------|-----------------|
| Language | `${PRIMARY_LANGUAGE}`, `${PROCEDURE_LANGUAGE}` | RFI Sheet 2 |
| Naming Conventions | `${NAMING_CONVENTION}`, `${TAG_FORMAT}` | RFI Sheet 2 |
| Criticality Method | `${CRITICALITY_METHOD}` | RFI Sheet 3 |
| CMMS & SAP | `${CMMS_TYPE}`, `${SAP_VERSION}` | RFI Sheet 3 |
| Standards | `${APPLICABLE_STANDARDS}` | RFI Sheet 5 |
| Hard Constraints | `${CONSTRAINT_1}`, `${CONSTRAINT_2}` | RFI Sheet 7 |

### 3.2 maintenance-strategy/requirements.md

**Se carga en**: M1, M2
**Contiene**: Jerarquía de equipos, método de criticidad, profundidad FMECA/RCM, formato de entregable

### 3.3 work-planning/requirements.md

**Se carga en**: M3, M4
**Contiene**: Convenciones SAP (`SAP_SHORT_TEXT_MAX=72`), agrupación de work packages, recursos disponibles, turnos, presupuesto

### 3.4 reliability-engineering/requirements.md

**Se carga en**: M2
**Contiene**: Disponibilidad de datos para análisis Weibull/Pareto, existencia de RCM/FMECA previo, alcance de análisis estadístico

### 3.5 cost-analysis/requirements.md

**Se carga en**: M3
**Contiene**: Horizonte LCC, tasa de descuento, costo de parada/hora, presupuesto de mantenimiento, KPIs objetivo (disponibilidad, MTBF, MTTR)

### 3.6 patterns.md (por stage)

**Se carga en**: Según el milestone del stage
**Auto-generado por**: Workflow cuando el revisor aprueba con feedback
**Formato**:

```markdown
### PAT-AUTO: Confirmed approach
- **Date**: 2026-03-06
- **Feedback**: La jerarquía a 4 niveles funciona bien para esta planta
```

Los archivos de patterns vacíos (solo comentarios/headers) son **ignorados** durante la carga para evitar inyectar ruido.

### 3.7 deviations/ (directorio)

**Auto-generado por**: Workflow cuando el revisor solicita "modify"
**Nombrado**: `DEV-M{milestone}-{attempt}.md` (ej: `DEV-M1-0.md`)
**Formato**:

```markdown
# Deviation

- **Date**: 2026-03-06
- **Action**: Modify requested
- **Feedback**: La jerarquía tiene demasiados niveles, reducir a 4
```

### 3.8 meetings/ (directorio)

**Generado por**: `save_meeting_notes()` desde el workflow
**Nombrado**: `{YYYY-MM-DD}_meeting.md`
**Contiene**: Notas de reuniones con decisiones del cliente

---

## 4. Cómo Funciona (Flujo Técnico)

### 4.1 Fase de Seeding (antes del workflow)

El script [`scripts/process_ams_rfi.py`](scripts/process_ams_rfi.py) procesa el cuestionario RFI del cliente (Excel) y genera los archivos de memoria iniciales:

```
RFI Excel (7 hojas)
    │
    ├─> generate_global_requirements()     → global-requirements.md
    ├─> generate_maintenance_strategy()     → maintenance-strategy/requirements.md
    ├─> generate_work_planning()            → work-planning/requirements.md
    ├─> generate_reliability_requirements() → reliability-engineering/requirements.md
    ├─> generate_cost_analysis_requirements() → cost-analysis/requirements.md
    ├─> generate_standards_appendix()       → (apéndice a global-requirements.md)
    └─> generate_kpi_appendix()             → (apéndice a global-requirements.md)
```

La función `_append_or_create()` es **idempotente** — ejecutar el RFI dos veces no duplica contenido.

### 4.2 Fase de Carga (durante el milestone)

Cuando el workflow inicia un milestone, el agente construye su prompt:

**Código**: [`agents/_shared/base.py:309-340`](agents/_shared/base.py)

```python
def get_system_prompt(self, milestone=None, memory_dir=None):
    prompt = self._system_prompt           # 1. CLAUDE.md base

    if milestone and self.config.agent_dir:
        skills = self.config.load_skills_for_milestone(milestone)
        prompt += format_skills(skills)     # 2. Skills del milestone

    if milestone and memory_dir:
        contents = load_memory_for_milestone(milestone, memory_dir)
        block = format_memory_block(contents)
        prompt += block                     # 3. MEMORIA (última = máxima prioridad)

    return prompt
```

**Función de carga**: [`memory.py:67-79`](agents/_shared/memory.py)

`load_memory_for_milestone(milestone, memory_dir)`:
1. Usa `MILESTONE_TO_STAGES` para obtener los stages relevantes
2. Para cada stage, carga: global-requirements + stage/requirements + stage/patterns
3. **Deduplica** global-requirements si el milestone tiene múltiples stages (ej: M2 carga maintenance-strategy + reliability-engineering, pero global-requirements aparece solo una vez)

### 4.3 Fase de Inyección (en el prompt)

**Función**: [`memory.py:84-102`](agents/_shared/memory.py)

`format_memory_block()` envuelve el contenido en tags XML:

```xml
<client_memory>
# CLIENT MEMORY — MUST follow these requirements

Requirements below OVERRIDE methodology defaults.
If memory conflicts with a skill instruction, memory wins.
Ignore placeholder variables (${...}).

<!-- source: global-requirements.md (global) -->
[contenido del archivo]

<!-- source: maintenance-strategy/requirements.md (stage) -->
[contenido del archivo]

</client_memory>
```

### 4.4 Fase de Aprendizaje (después del gate review)

**Código**: [`agents/orchestration/workflow.py:279-308`](agents/orchestration/workflow.py)

Después de cada decisión de gate:

| Acción del revisor | Qué se guarda | Dónde |
|-------------------|---------------|-------|
| **approve** + feedback | Patrón confirmado | `{stage}/patterns.md` (append) |
| **modify** + feedback | Desviación detectada | `deviations/DEV-M{N}-{attempt}.md` |
| **reject** | Nada | (sin aprendizaje) |

**Flujo de aprendizaje**:
1. `extract_learning(feedback, action)` — extrae estructura del feedback
2. Si feedback < 10 caracteres → se ignora (feedback trivial como "OK")
3. Si "approve" → `save_pattern()` → append a patterns.md del primer stage del milestone
4. Si "modify" → `save_deviation()` → crea DEV-M{N}-{attempt}.md

**Principio de no-falla**: Si el guardado de memoria falla, el workflow **continúa normalmente**. Los fallos se loguean a nivel `debug`.

### 4.5 Ciclo completo (ejemplo)

```
Milestone 1 (inicio limpio)
  │
  ├─ Carga: global-requirements + maintenance-strategy/requirements
  ├─ Agente produce jerarquía + criticidad
  ├─ Gate: Revisor dice "modify" → "Jerarquía demasiado detallada"
  │   └─ Se guarda: deviations/DEV-M1-0.md
  │
  ├─ Milestone 1 (reintento, attempt 1)
  │   ├─ Carga: misma memoria + desviación DEV-M1-0
  │   ├─ Agente ajusta la jerarquía
  │   ├─ Gate: Revisor aprueba → "Jerarquía a 4 niveles funciona bien"
  │   │   └─ Se guarda: maintenance-strategy/patterns.md
  │
  └─ Milestone 2 (nuevo trabajo)
      ├─ Carga: global + maintenance-strategy (ahora incluye el patrón confirmado)
      │         + reliability-engineering/requirements
      └─ Agente beneficia del patrón confirmado al construir FMECA
```

---

## 5. Guía del Consultor — Cómo Usar la Memoria

### 5.1 Antes de iniciar un proyecto

1. **Procesar el RFI**: Ejecutar `process_ams_rfi.py` con el Excel del cuestionario completado por el cliente. Esto genera automáticamente los archivos base en `3-memory/`.

2. **Revisar y completar** `global-requirements.md`:
   - Reemplazar variables `${...}` con valores reales
   - Agregar restricciones descubiertas en entrevistas
   - Agregar estándares aplicables no capturados en el RFI

3. **Revisar requirements.md por stage**:
   - Completar campos faltantes
   - Agregar requisitos específicos del cliente que no están en la metodología estándar

### 5.2 Qué poner en cada archivo

#### global-requirements.md
```markdown
## Language
- Primary language: Español
- Procedure language: Español
- Equipment names: Inglés (nombrado internacional del fabricante)

## Naming Conventions
- Tag format: {Area}-{Tipo}-{Secuencia} (ej: CRU-PP-001)
- Documento: {Proyecto}-{Área}-{Tipo}-{Número} (ej: JFC-CRU-FMECA-001)

## Hard Constraints
- Todas las tareas deben tener estimación de duración
- Máximo 8 modos de falla por equipo en FMECA nivel 1
- Criticidad debe usar matriz 5x5 del cliente
```

#### {stage}/requirements.md
```markdown
## Hierarchy Requirements
- Maximum 4 levels: Site > Area > System > Equipment
- Use OEM nomenclature for equipment names
- Include French names (name_fr) for all equipment

## FMECA Requirements
- Risk matrix: 5x5 (consequence × likelihood)
- Threshold for detailed RCM: RPN > 200
- Include environmental failure modes
```

### 5.3 Cómo dar input a la memoria

Hay **4 formas** de alimentar la memoria:

| Método | Cuándo | Quién | Archivos afectados |
|--------|--------|-------|-------------------|
| **RFI Processing** | Al inicio del proyecto | Script automático | global-requirements, stage requirements |
| **Edición manual** | Pre-milestone o entre milestones | Consultor | Cualquier .md en 3-memory/ |
| **Gate approval** | Después de aprobar un entregable | Workflow automático | `{stage}/patterns.md` |
| **Gate modify** | Después de solicitar modificación | Workflow automático | `deviations/DEV-*.md` |

### 5.4 Buenas prácticas

**Lo que SÍ hacer**:
- Ser específico: "Usar matriz 5x5 del Anexo A" en vez de "usar la matriz del cliente"
- Incluir valores numéricos: "MTBF target: 2,000 horas" en vez de "alto MTBF"
- Documentar excepciones: "Todos los equipos excepto bombas de respaldo"
- Revisar patterns.md después de cada milestone para confirmar que los patrones capturados son correctos

**Lo que NO hacer**:
- No editar archivos en `deviations/` — son gestionados por el sistema
- No borrar patterns.md — contiene aprendizajes acumulados
- No dejar variables `${...}` sin reemplazar si ya tiene el valor real
- No duplicar información que ya está en global-requirements en archivos de stage

### 5.5 Cómo revisar la memoria acumulada

Después de varios milestones, revisar:

1. **`{stage}/patterns.md`** — ¿Los patrones capturados son correctos? ¿Hay contradicciones?
2. **`deviations/`** — ¿Las desviaciones reflejan correcciones reales o fueron errores temporales?
3. **`meetings/`** — ¿Las notas de reuniones capturan las decisiones clave?

---

## 6. Guía del Desarrollador — Cómo Extender

### 6.1 Archivos clave

| Componente | Archivo | Líneas clave |
|-----------|--------|-------------|
| Módulo de memoria | [`agents/_shared/memory.py`](agents/_shared/memory.py) | 172 líneas total |
| Integración en agente | [`agents/_shared/base.py`](agents/_shared/base.py) | L309-340 |
| Resolución de paths | [`agents/_shared/paths.py`](agents/_shared/paths.py) | L154-157 |
| Integración en workflow | [`agents/orchestration/workflow.py`](agents/orchestration/workflow.py) | L174-184, L279-308 |
| RFI seeding | [`scripts/process_ams_rfi.py`](scripts/process_ams_rfi.py) | Funciones `generate_*` |
| Exports públicos | [`agents/_shared/__init__.py`](agents/_shared/__init__.py) | L6-18 |
| Templates | [`templates/client-project/3-memory/`](templates/client-project/3-memory/) | 14 archivos |
| Tests | [`tests/test_memory.py`](tests/test_memory.py) | 83 tests |

### 6.2 Agregar un nuevo stage

1. Agregar el nombre a `_VALID_STAGES` en [`memory.py:34-37`](agents/_shared/memory.py):
   ```python
   _VALID_STAGES = frozenset({
       "maintenance-strategy", "work-identification", "work-planning",
       "reliability-engineering", "cost-analysis",
       "nuevo-stage",  # ← agregar aquí
   })
   ```

2. Agregar el mapeo en `MILESTONE_TO_STAGES` en [`memory.py:27-32`](agents/_shared/memory.py):
   ```python
   MILESTONE_TO_STAGES = {
       1: ["maintenance-strategy"],
       2: ["maintenance-strategy", "reliability-engineering"],
       3: ["work-planning", "cost-analysis"],
       4: ["work-planning"],
       5: ["nuevo-stage"],  # ← nuevo milestone
   }
   ```

3. Crear templates en `templates/client-project/3-memory/nuevo-stage/`:
   - `requirements.md` — con placeholders `${...}`
   - `patterns.md` — con header y comentario HTML

4. Agregar tests en `tests/test_memory.py`

### 6.3 Modificar el mapeo Milestone → Stages

Solo editar `MILESTONE_TO_STAGES` en [`memory.py:27-32`](agents/_shared/memory.py). Es la **única fuente de verdad** — no hay duplicación en ningún otro archivo.

### 6.4 Restricciones de seguridad

| Protección | Función | Ubicación |
|-----------|---------|-----------|
| Path traversal | `_validate_id()` | [`memory.py:107-113`](agents/_shared/memory.py) |
| XSS/Injection | `_sanitize_content()` | [`memory.py:116-119`](agents/_shared/memory.py) |
| SWMR | Write functions solo exportadas internamente | [`__init__.py:14-18`](agents/_shared/__init__.py) |
| Inmutabilidad | `@dataclass(frozen=True)` | [`memory.py:18-23`](agents/_shared/memory.py) |

**`_validate_id()`** rechaza:
- Strings vacíos
- `..` (path traversal)
- `/` y `\` (navegación de directorio)
- Caracteres especiales (solo acepta `[a-zA-Z0-9][a-zA-Z0-9_-]*`)

**`_sanitize_content()`** elimina:
- Tags `<script>...</script>`
- Tags `<iframe>...</iframe>`

### 6.5 Restricciones de calidad (Bad Smells)

Estas restricciones están **verificadas por tests** en `TestBadSmellsPrevention`:

| Restricción | Test | Razón |
|------------|------|-------|
| `memory.py` < 200 líneas | `test_memory_module_under_200_lines` | Prevenir God Module |
| `MemoryContent` es dataclass | `test_memory_content_is_dataclass` | No usar dicts genéricos |
| `MemoryContent` es frozen | `test_memory_content_is_frozen` | Inmutabilidad garantizada |
| `MILESTONE_TO_STAGES` definido una vez | `test_milestone_to_stages_single_definition` | Prevenir shotgun surgery |

### 6.6 Patrones de testing

```python
# Usar tmp_path para aislamiento de I/O
def test_loads_global(tmp_path):
    (tmp_path / "global-requirements.md").write_text("# Global\n- Language: EN")
    result = load_memory_for_stage("maintenance-strategy", tmp_path)
    assert len(result) == 1

# Marcar tests de seguridad
@pytest.mark.security
def test_rejects_path_traversal(tmp_path):
    with pytest.raises(ValueError, match="path traversal"):
        save_deviation(tmp_path, "../../../etc/passwd", "hack")

# Test de integración con Agent
def test_memory_injected_in_prompt(tmp_path):
    (tmp_path / "global-requirements.md").write_text("# Req\n- Use Spanish")
    agent = Agent(config)
    prompt = agent.get_system_prompt(milestone=1, memory_dir=tmp_path)
    assert "<client_memory>" in prompt
```

### 6.7 API pública

Exportada desde [`agents/_shared/__init__.py`](agents/_shared/__init__.py):

| Función | Tipo | Descripción |
|---------|------|-------------|
| `MemoryContent` | Dataclass | Fragmento de memoria inmutable |
| `MILESTONE_TO_STAGES` | Dict | Mapeo milestone → stages |
| `load_memory_for_stage()` | Lectura | Carga global + stage requirements + patterns |
| `load_memory_for_milestone()` | Lectura | Carga memoria para un milestone completo (deduplica) |
| `format_memory_block()` | Formateo | Envuelve en `<client_memory>` tags |

**Funciones de escritura** (NO exportadas en `__init__.py`, solo importables directamente):
- `save_deviation()` — solo llamar desde workflow
- `save_pattern()` — solo llamar desde workflow
- `save_meeting_notes()` — solo llamar desde workflow
- `extract_learning()` — solo llamar desde workflow

---

## 7. Oportunidades de Mejora

### 7.1 Alta prioridad

| # | Mejora | Impacto | Complejidad |
|---|--------|---------|-------------|
| 1 | **Memoria cross-proyecto** | `get_client_memory_dir()` existe en [`paths.py:284-291`](agents/_shared/paths.py) pero no se usa. Permitiría compartir conocimiento entre proyectos del mismo cliente. | Media |
| 2 | **Stage `work-identification` sin uso** | Existe en `_VALID_STAGES` pero ningún milestone lo carga. O asignarlo a un milestone o eliminarlo. | Baja |
| 3 | **Feedback de `reject` se pierde** | `extract_learning()` solo procesa "approve" y "modify". El feedback de "reject" contiene información valiosa que no se persiste. | Baja |

### 7.2 Media prioridad

| # | Mejora | Impacto | Complejidad |
|---|--------|---------|-------------|
| 4 | **Sin versionado de memoria** | No hay historial de cambios en archivos de memoria. Un error de edición puede perder información sin posibilidad de recuperación. Git mitiga parcialmente esto. | Media |
| 5 | **Sin detección de conflictos** | Si un patrón confirmado contradice una desviación posterior, no hay mecanismo para detectar o resolver el conflicto. | Alta |
| 6 | **patterns.md crece sin límite** | No hay estrategia de poda. Después de muchos milestones, patterns.md puede crecer significativamente e inyectar demasiado contenido en el prompt. | Media |

### 7.3 Baja prioridad

| # | Mejora | Impacto | Complejidad |
|---|--------|---------|-------------|
| 7 | **Sin UI de visualización** | No existe una página Streamlit para ver/editar la memoria de un proyecto. Sería útil para consultores no técnicos. | Media |
| 8 | **Sin export/import** | No se puede exportar la memoria de un proyecto y aplicarla a otro. Útil para clientes con múltiples plantas similares. | Baja |
| 9 | **Deviaciones no se cargan en el prompt** | Las desviaciones se guardan en `deviations/` pero `load_memory_for_stage()` no las carga. El agente las ve solo si el consultor las mueve manualmente. | Media |

---

## 8. Modelo de Seguridad

### 8.1 Principios

1. **SWMR (Single Writer, Multiple Readers)**: Solo el workflow escribe memoria. Los agentes solo leen.
2. **Validación de entrada**: Todo ID pasa por `_validate_id()` antes de usarse en paths.
3. **Sanitización de contenido**: Todo contenido escrito pasa por `_sanitize_content()`.
4. **Sin eval/exec**: No se ejecuta código dinámico en ningún punto del módulo.
5. **Fallo no-crítico**: Errores de memoria no detienen el workflow.

### 8.2 Vectores de ataque mitigados

| Vector | Mitigación | Test |
|--------|-----------|------|
| Path traversal (`../../../etc/passwd`) | `_validate_id()` rechaza `..`, `/`, `\` | `TestSecurityPathTraversal` (7 tests) |
| XSS via `<script>` | `_sanitize_content()` elimina tags | `TestSecurityContentSanitization` (6 tests) |
| Code injection en patterns | Contenido se trata como texto plano | `TestSecurityNoCodeExecution` (2 tests) |
| Credential leakage | No hay interpolación de variables de entorno | `TestSecurityNoCredentials` (2 tests) |
| Command injection en IDs | Regex `^[a-zA-Z0-9][a-zA-Z0-9_-]*$` | `test_deviation_id_rejects_special_chars` |

### 8.3 Cobertura de tests

```
Total: 83 tests en tests/test_memory.py
├── Functional:    49 tests (carga, formateo, guardado, extracción)
├── Integration:    9 tests (memoria + agent, memoria + workflow)
├── Security:      17 tests (@pytest.mark.security)
├── Protocol:       4 tests (CLAUDE.md contiene Client Memory Protocol)
└── Bad Smells:     4 tests (restricciones de calidad)

Suite completa: 2,118 tests passing, 0 failures
```

---

## Apéndice A: Protocolo de Memoria en CLAUDE.md

Cada uno de los 4 agentes AMS tiene esta sección al final de su CLAUDE.md:

```markdown
## Client Memory Protocol (MANDATORY)

Before executing ANY skill, you MUST read and follow client memory
injected in `<client_memory>` tags.
Requirements in memory OVERRIDE methodology defaults.
If memory conflicts with a skill instruction, memory wins.
If no memory is present, use methodology defaults.
```

**Agentes con el protocolo**:
- [`agents/orchestrator/CLAUDE.md`](agents/orchestrator/CLAUDE.md)
- [`agents/reliability/CLAUDE.md`](agents/reliability/CLAUDE.md)
- [`agents/planning/CLAUDE.md`](agents/planning/CLAUDE.md)
- [`agents/spare-parts/CLAUDE.md`](agents/spare-parts/CLAUDE.md)

## Apéndice B: Ejemplo de prompt final con memoria inyectada

```
[CLAUDE.md del agente — instrucciones base]

<loaded_skills>
## Skill: assess-criticality
Path: skills/02-maintenance-strategy-development/assess-criticality/CLAUDE.md
...
</loaded_skills>

<client_memory>
# CLIENT MEMORY — MUST follow these requirements

Requirements below OVERRIDE methodology defaults.
If memory conflicts with a skill instruction, memory wins.
Ignore placeholder variables (${...}).

<!-- source: global-requirements.md (global) -->
## Language
- Primary: Español
- Equipment names: Inglés

## Naming Conventions
- Tag format: CRU-{Tipo}-{Seq}

<!-- source: maintenance-strategy/requirements.md (stage) -->
## Hierarchy
- Maximum 4 levels
- Include name_fr for all equipment

<!-- source: maintenance-strategy/patterns.md (pattern) -->
### PAT-AUTO: Confirmed approach
- **Date**: 2026-03-05
- **Feedback**: Jerarquía a 4 niveles funciona bien para CRU

</client_memory>
```
