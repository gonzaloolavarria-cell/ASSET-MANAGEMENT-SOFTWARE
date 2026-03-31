# Gobernanza del Sistema AMS (Asset Management Software)

**Sistema:** AMS — Multi-Agent Maintenance Strategy Development
**Versión:** Phase 11 — Cross-System Improvement (2026-03-06)
**Agentes:** 4 (Orchestrator, Reliability, Planning, Spare Parts)
**Skills:** 40 | **Tools MCP:** 128 | **Engines determinísticos:** 38

## Resumen Ejecutivo

AMS gestiona 5 preocupaciones de gobernanza con niveles de separación desiguales. **Spec** y **Validación** están bien aisladas en archivos dedicados (schemas Pydantic, validators, scoring engine). **Intent** ahora cuenta con un sistema dedicado adoptado de OR SYSTEM (3-level loading IP-L1/L2/L3 con `intent-profile.yaml`). **Reglas de Código** siguen mezcladas dentro de los archivos CLAUDE.md de cada agente. **Arquitectura** tiene separación parcial: SWMR vive en código Python, pero las reglas mandatorias están embebidas en prompts.

---

## 1. Intent (+Propósito)

### Dónde vive

| Archivo                                                         | Tipo                       | Descripción                                                                               |
| --------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------------------------------ |
| `agents/orchestrator/CLAUDE.md`                               | Mixto                      | Intent master: rol, workflow 4-milestone, decision framework + Intent Protocol (MANDATORY) |
| `agents/reliability/CLAUDE.md`                                | Mixto                      | Intent dominio: hierarchy, criticality, FMECA, RCM + Intent Protocol (MANDATORY)           |
| `agents/planning/CLAUDE.md`                                   | Mixto                      | Intent dominio: work packages, SAP export, work instructions + Intent Protocol (MANDATORY) |
| `agents/spare-parts/CLAUDE.md`                                | Mixto                      | Intent dominio: material assignment, confidence scoring + Intent Protocol (MANDATORY)      |
| `agents/*/skills.yaml` (x4)                                   | Dedicado                   | Qué skills carga cada agente por milestone                                                |
| `skills/SKILL_CLASSIFICATION.md`                              | Dedicado                   | Clasifica 41 skills: 27 capability-uplift + 14 encoded-preference                          |
| `templates/client-project/4-intent-specs/intent-profile.yaml` | **Dedicado (NUEVO)** | Template IP-L1/L2/L3: summary, domain_intent, full_context, trade_off_matrix, veto_rules   |
| `agents/_shared/paths.py`                                     | **Dedicado (NUEVO)** | `load_intent_profile()`, `validate_intent_profile()`, `get_intent_domain()`          |
| `agents/_shared/base.py`                                      | Mixto                      | `_format_intent_block()` — inyección de `<client_intent>` tags en system prompt      |

### Lógica

**3-Level Intent Loading (IP-L1/L2/L3)** — adoptado de OR SYSTEM:

```
intent-profile.yaml (en 4-intent-specs/ del proyecto)
  ├→ IP-L1 (siempre): intent_summary (~200 tokens)
  │     client, project, trade_off_priority, risk_appetite, hard_limits
  ├→ IP-L2 (por dominio): domain_intent.{domain} (~500-800 tokens)
  │     Goals específicos, KPIs, constraints del dominio
  └→ IP-L3 (on demand): full_context (~3500-5000 tokens)
        Realidad organizacional, stakeholders
```

**Carga programática:**

```python
# agents/_shared/paths.py
profile = load_intent_profile(client_slug, project_slug)  # → dict | None
is_valid, warnings = validate_intent_profile(profile)      # → (bool, list[str])
domain = get_intent_domain(profile, "reliability")          # → dict | None
```

**Inyección en system prompt** (`Agent.get_system_prompt()`):

```
base_prompt + <loaded_skills> + <client_memory> + <client_intent>
```

Orden de precedencia: **Memory > Intent > Methodology**

**Fallback v3.1**: Si no existe `intent-profile.yaml`, el sistema opera sin constraints de intent, scoring de 6 dimensiones en vez de 7.

**RFI seed**: `scripts/process_ams_rfi.py` genera `intent-profile.yaml` mínimo (IP-L1) desde respuestas RFI.

### Resultado

- System prompt enriquecido con `<client_intent>` tags (trade-off priorities, KPIs, risk appetite, hard limits)
- 7ma dimensión QA activada (Intent Alignment, 15%) cuando hay perfil
- Agentes respetan intent protocol mandatorio (4 CLAUDE.md actualizados)
- Fallback graceful a v3.1 mode sin intent
- 17 tests dedicados (`tests/test_intent_profile.py`)

### Evaluación de independencia

**PARCIAL → MEJORADO** — El sistema de intent ahora tiene archivos dedicados: `intent-profile.yaml` (template), funciones de carga/validación en `paths.py`, inyección via `_format_intent_block()` en `base.py`. Los CLAUDE.md de cada agente ahora incluyen un "Intent Protocol (MANDATORY)" section dedicada. La mejora es significativa vs el estado anterior (MEZCLADO), aunque el protocol section sigue viviendo dentro de los CLAUDE.md mixtos.

---

## 2. Reglas de Arquitectura

### Dónde vive

| Archivo                                                                          | Tipo     | Descripción                                                                              |
| -------------------------------------------------------------------------------- | -------- | ----------------------------------------------------------------------------------------- |
| `agents/orchestration/session_state.py`                                        | Dedicado | SWMR:`ENTITY_OWNERSHIP` dict + `write_entities()` enforcement                         |
| `skills/00-knowledge-base/architecture/conflict-resolution-protocol-or.md`     | Dedicado | Protocolo 5-step de resolución de conflictos                                             |
| `skills/00-knowledge-base/architecture/ref-06-software-architecture-vision.md` | Dedicado | Visión de arquitectura del sistema                                                       |
| `agents/orchestrator/CLAUDE.md` (líneas 31-50)                                | Mixto    | 4 reglas mandatorias (human approval, no domain work, no skip validation, no auto-submit) |
| `agents/AGENT_REGISTRY.md`                                                     | Dedicado | Matriz de agentes, modelos, milestones, tool counts, ownership                            |

### Lógica

**SWMR (Single Writer, Multiple Reader):**

```python
ENTITY_OWNERSHIP = {
    "hierarchy_nodes": RELIABILITY,      # Solo reliability escribe
    "criticality_assessments": RELIABILITY,
    "failure_modes": RELIABILITY,
    "maintenance_tasks": PLANNING,       # Solo planning escribe
    "work_packages": PLANNING,
    "material_assignments": SPARE_PARTS, # Solo spare_parts escribe
    "quality_scores": ORCHESTRATOR,      # Solo orchestrator escribe
}
```

`write_entities()` valida ownership antes de permitir escritura → `RuntimeError` si el agente no es el dueño. `read_entities()` está abierto a todos.

**4 Reglas Mandatorias** (en orchestrator CLAUDE.md):

1. Human Approval en cada gate — no auto-advance
2. Never Perform Domain Work — orchestrator solo coordina
3. Never Skip Validation — `validate_quality` antes de cada gate
4. Never Auto-Submit to SAP — todo es DRAFT

### Resultado

- `RuntimeError` si agente incorrecto intenta escribir una entidad
- Gate rechazado si falta aprobación humana
- Conflict Resolution Brief (CRB) cuando hay conflicto entre agentes

### Evaluación de independencia

**PARCIAL** — SWMR está dedicado en código Python (`session_state.py`). Conflict resolution está dedicado en markdown. Pero las 4 reglas mandatorias están embebidas en el CLAUDE.md del orchestrator junto con su intent y code rules.

---

## 3. Spec (Especificaciones)

### Dónde vive

| Archivo                                     | Tipo     | Descripción                                                                |
| ------------------------------------------- | -------- | --------------------------------------------------------------------------- |
| `tools/models/schemas.py`                 | Dedicado | Pydantic models: enums, base models, validación de campos                  |
| `tools/engines/quality_score_config.yaml` | Dedicado | Pesos, umbrales, grades, overrides por tipo de entregable                   |
| `templates/*.xlsx` (14 archivos)          | Dedicado | Estructura de captura de datos (hierarchy, criticality, FM, tasks, WP, SAP) |
| `templates/generate_templates.py`         | Dedicado | Generador programático de los 14 Excel templates                           |
| `agents/AGENT_REGISTRY.md`                | Dedicado | Matriz 4 agentes: modelo, milestones, tools, ownership                      |
| `skills/SKILL_ALIGNMENT_MATRIX.md`        | Dedicado | Mapeo de overlap AMS ↔ OR SYSTEM                                           |

### Lógica

**Pydantic models** (`schemas.py`) definen:

- Enumeraciones: `EquipmentCriticality` (AA/A+/A/B/C/D), `NodeType` (6 niveles), `WorkOrderType`, `Priority`
- BaseModel classes para cada entidad del dominio (hierarchy node, criticality, failure mode, task, work package)
- Validación de campos en tiempo de serialización/deserialización

**YAML config** (`quality_score_config.yaml`) define:

- Pesos default (sin intent): tech_accuracy 30%, completeness 25%, consistency 15%, format 10%, actionability 10%, traceability 10%
- Pesos con intent: tech_accuracy 25%, intent_alignment 15%
- Umbrales: AMS pass=85, OR pass=91, warning=70, critical=50
- Grades: A>=91, B>=80, C>=70, D>=50
- Overrides por entregable (fmeca: tech_accuracy 35%; sap: format 20%)

**Excel templates** (14 archivos) definen estructura de captura: columnas, validaciones de datos, formatos condicionales.

### Resultado

- Schemas tipados con validación automática vía Pydantic
- 14 archivos Excel generados programáticamente con `generate_templates.py`
- Configuración de scoring en YAML versionable

### Evaluación de independencia

**DEDICADO** — Cada tipo de spec tiene su archivo propio. Schemas en Python, config en YAML, templates en Excel, registry en Markdown. Buena separación de preocupaciones.

---

## 4. Reglas de Código

### Dónde vive

| Archivo                                  | Tipo     | Descripción                                                         |
| ---------------------------------------- | -------- | -------------------------------------------------------------------- |
| `agents/planning/CLAUDE.md`            | Mixto    | T-16 Rule, 7 WP elements, naming conventions (72 chars, verb prefix) |
| `agents/spare-parts/CLAUDE.md`         | Mixto    | Confidence scoring (0.95/0.70/0.40), flag <0.60                      |
| `agents/orchestrator/CLAUDE.md`        | Mixto    | Session state is source of truth, all outputs DRAFT                  |
| `tools/validators/naming_validator.py` | Dedicado | Equipment tag patterns, component codes, task naming                 |
| `agents/_shared/base.py`               | Mixto    | temperature=0.0, max_turns por agente, timeout=300s                  |

### Lógica

**Reglas de dominio** embebidas en prompts de agentes:

- **T-16 Rule**: Tareas REPLACE deben tener materiales; INSPECT no
- **7 Mandatory WP Elements**: Work Permit, LOTO, Material list, Inspection checklists, JRA, Execution procedure, Work order
- **Task Naming**: Max 72 chars, prefijo verbal (INSPECT/REPLACE/MONITOR)
- **WP Naming**: Max 40 chars, ALL CAPS
- **Confidence Scoring**: BOM=0.95, Catalog=0.70, Generic=0.40

**Reglas de API loop** hardcodeadas en `base.py`:

- `temperature=0.0` (determinístico)
- `max_turns`: Orchestrator=20, Reliability=40, Planning=30, Spare_Parts=15
- `timeout=300s`

**Naming validator** (`naming_validator.py`): validación programática de patrones de nombre.

### Resultado

- Validación de nombres en runtime (naming_validator)
- Auto-restricción de agentes vía prompt (T-16, 7 elements, naming)
- Parámetros de API loop determinísticos

### Evaluación de independencia

**MEZCLADO** — `naming_validator.py` es un archivo dedicado, pero la mayoría de reglas de código (T-16, 7 WP elements, naming conventions, confidence scoring) están embebidas en los CLAUDE.md junto con intent y scope boundaries. No hay un `CODE_RULES.md` centralizado.

---

## 5. Reglas de Validación

### Dónde vive

| Archivo                                            | Tipo     | Descripción                                                                                                               |
| -------------------------------------------------- | -------- | -------------------------------------------------------------------------------------------------------------------------- |
| `tools/validators/quality_validator.py`          | Dedicado | 40+ reglas: H-01 a H-04 (hierarchy), C-01 a C-07 (criticality), FM-01 a FM-15, T-01 a T-12, WP-01 a WP-10, SAP-01 a SAP-08 |
| `tools/engines/quality_score_engine.py`          | Dedicado | Strategy pattern: carga ScorerStrategy por tipo de entregable                                                              |
| `tools/engines/scoring_strategies/` (6 archivos) | Dedicado | HierarchyScorer, CriticalityScorer, FMECAScorer, TaskScorer, WorkPackageScorer, SAPScorer                                  |
| `tools/engines/quality_score_config.yaml`        | Dedicado | Pesos, umbrales, grades (compartido con Spec)                                                                              |
| `tools/validators/rfi_validator.py`              | Dedicado | Validación de respuestas RFI, data availability                                                                           |
| `tools/validators/confidence_validator.py`       | Dedicado | Validación de niveles de confianza de materiales                                                                          |
| `tools/validators/naming_validator.py`           | Dedicado | Validación de naming (compartido con Code Rules)                                                                          |
| `agents/orchestration/workflow.py`               | Mixto    | `_run_validation()` y `_run_quality_scoring()` integran validators en gates                                            |

### Lógica

**Strategy Pattern** — Quality Score Engine:

```
QualityScoreEngine
  ├→ HierarchyScorer     (7 dimensiones ponderadas)
  ├→ CriticalityScorer   (7 dimensiones ponderadas)
  ├→ FMECAScorer         (override: tech_accuracy=35%)
  ├→ TaskScorer          (7 dimensiones ponderadas)
  ├→ WorkPackageScorer   (7 dimensiones ponderadas)
  └→ SAPScorer           (override: format=20%)
```

**Quality Validator** — Reglas determinísticas por dominio:

- H-01 a H-04: Profundidad, componentes, parent-child
- C-01 a C-07: Consecuencias, probabilidades, scoring
- FM-01 a FM-15: Tabla 72-combo, naming
- T-01 a T-12: Naming, frecuencia, recursos
- WP-01 a WP-10: 7 elementos mandatorios
- SAP-01 a SAP-08: Longitud de campos, cross-references

**Workflow integration**: `workflow.py` invoca ambos (validator + scorer) antes de cada gate. El resultado se muestra en el gate summary.

### Resultado

- `ValidationResult`: rule_id, severity (ERROR/WARNING/INFO), message
- `DeliverableQualityScore`: 7 dimensiones, score 0-100, grade A/B/C/D
- `SessionQualityReport`: scores agregados por milestone
- Gate summary con score y grade para decisión humana

### Evaluación de independencia

**DEDICADO** — Cada validator tiene su archivo propio. El scoring engine tiene su archivo + 6 strategies + config YAML. La integración con el workflow es el único punto mixto (workflow.py llama a los validators). Excelente separación de preocupaciones.

---

## Tabla Resumen

| Preocupación     | Independencia                | Archivos dedicados                                                                     | Archivos mixtos                                 |
| ----------------- | ---------------------------- | -------------------------------------------------------------------------------------- | ----------------------------------------------- |
| Intent            | **PARCIAL** (mejorado) | skills.yaml (x4), skills/SKILL_CLASSIFICATION.md, intent-profile.yaml, paths.py (3 funciones) | 4 agent CLAUDE.md (con Intent Protocol section) |
| Arquitectura      | **PARCIAL**            | session_state.py, conflict-resolution-protocol.md, AGENT_REGISTRY.md                   | orchestrator CLAUDE.md                          |
| Spec              | **DEDICADO**           | schemas.py, quality_score_config.yaml, 14 Excel, generate_templates.py                 | —                                              |
| Reglas de Código | **MEZCLADO**           | naming_validator.py                                                                    | 4 agent CLAUDE.md, base.py                      |
| Validación       | **DEDICADO**           | quality_validator.py, quality_score_engine.py, 6 strategies, 3 validators              | workflow.py                                     |

## Mapa de Dependencias

```
Intent ──────────→ Reglas de Código (las code rules están en los mismos CLAUDE.md)
   │                     │
   ▼                     ▼
Arquitectura ────→ Validación (SWMR protege entidades; validators verifican calidad)
   │                     ▲
   ▼                     │
  Spec ──────────────────┘ (schemas.py define tipos que validators verifican)
```

---

## Roadmap de Mejora

| Prioridad | Acción                                                                                                                                                                                                                                                                                                         | Preocupación     | Estado         | Esfuerzo | Impacto                                                    |
| --------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------- | -------------- | -------- | ---------------------------------------------------------- |
| P1        | ~~Extraer intent a sistema dedicado~~ → **COMPLETADO**: Implementado sistema de intent 3-level (IP-L1/L2/L3) adoptado de OR SYSTEM. `intent-profile.yaml` template, 3 funciones en `paths.py`, inyección `<client_intent>` en system prompt, Intent Protocol en 4 CLAUDE.md, RFI seed, 17 tests. | Intent            | **DONE** | Medio    | Intent separado del prompt, carga programática, testeable |
| P2        | Crear `docs/CODE_RULES.md` centralizado extrayendo T-16, 7 WP, naming, confidence scoring de los CLAUDE.md                                                                                                                                                                                                    | Reglas de Código | Pendiente      | Medio    | Single source of truth para reglas de dominio              |
| P3        | Consolidar las 4 reglas mandatorias de arquitectura en `docs/ARCHITECTURE_RULES.md`                                                                                                                                                                                                                           | Arquitectura      | Pendiente      | Bajo     | Documentación explícita separada del prompt              |
| P4        | No necesario — Spec y Validación ya están bien separadas                                                                                                                                                                                                                                                     | Spec, Validación | N/A            | —       | —                                                         |
