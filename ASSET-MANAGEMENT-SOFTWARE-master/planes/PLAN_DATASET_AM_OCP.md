# Plan de Generacion Dataset AM OCP (Version Auditoria/Paralela)

**Proyecto:** DB_AM_OCP_SYNTHETIC_2026
**Blueprint base:** AMSA_BBP_PM_04_Rev_0
**Ubicacion datos:** `DB_AM_OCP_SYNTHETIC_2026/`
**Ultima actualizacion:** 2026-03-31 (v4 — Checklist Jose: diccionario datos, cierre OT, mapeo prioridades)

---

## 1. Objetivo

Generar un dataset sintetico completo para una Planta Concentradora, alineado estrictamente al Blueprint AMSA_BBP_PM_04_Rev_0, que permita realizar un Gap Analysis contra la base de datos previa. Los datos residen en `DB_AM_OCP_SYNTHETIC_2026/` sin modificar datos existentes.

---

## 2. Marco Normativo

| Parametro | Valor Blueprint |
|-----------|----------------|
| Centro Planificacion | AN01 |
| Grupos Planificacion Planta | P01 (Area Seca), P02 (Area Ripio), P03 (Area Humeda) |
| Grupos Planificacion Mina | M01-M05 (registrados en config, no en datos operacionales) |
| Areas Empresa | SEC, RIP, HUM (Planta) + PER, CAR, TRA, APO, AUX, TAL (Mina) |
| Tipos OT | PM01, PM02, PM03, PM06, PM07 (NO existe PM04) |
| Clases Actividad PM07 | RP1 (Mayor), RP2 (Menor) |
| Criticidad ABC | 1=Alto, 2=Medio, 3=Bajo (numerico) |
| Notificaciones | A1, A2, A3 con catalogos M001-M003, P001-P002 |
| Status Notificacion | ZPM00001: APRO/RECH |
| Prioridad | Clase Z1: I, A, M, B |
| Tipos Equipo SAP | M (Maquinas), Q (Inspeccion/Medida) |
| Tipo Ubicacion Tecnica | M (Sistema tecnico estandar) |
| Jerarquia | 6 niveles: NN-NN-NN-AAAANN-XXXX-XXXX |
| Hoja Ruta | Tipo A, Grupos PLA/MIN |
| Plan Mantenimiento | Tipo PM |
| Categorias Valor | ZMANT001, ZMANT002, ZMANT003 |
| Turnos Planta | 7x7 (Viernes-Jueves) 08:00-20:00, 1h break |
| Puestos Trabajo | 8-char: PASMEC01, PAHELE01, etc. (Blueprint Tables 7-9) |
| Depuracion | Excluidos: Maintenance Task (04 original) y RCA (11 original) por directiva J. Cortinat |

---

## 3. Estructura de la Planta Concentradora

```
AMSA-OCP (Corporativo)
  └── 02 - Planta Concentradora
       ├── 01 - Chancado (P01 Area Seca)
       │    ├── 01 - Chancado Primario (CHAN01, CHAN02, ALIM01, ALIM02)
       │    ├── 02 - Chancado Secundario (COSE01, COSE02)
       │    ├── 03 - Chancado Terciario (COTE01, COTE02)
       │    └── 04 - Clasificacion y Harneo (HARV01-03, CORR01-03)
       ├── 02 - Molienda (P02 Area Ripio)
       │    ├── 01 - Molienda SAG (MSAG01, MSAG02)
       │    ├── 02 - Molienda Bolas (MBOL01-03)
       │    ├── 03 - Bombeo Pulpa (BOMB01-05)
       │    └── 04 - Clasificacion Hidrociclones (HCIC01-03)
       ├── 03 - Flotacion (P03 Area Humeda)
       │    ├── 01 - Rougher (CFRO01-04)
       │    ├── 02 - Cleaner-Scavenger (CFCL01-02, CFSC01-02)
       │    └── 03 - Acondicionamiento Reactivos (AGIT01-02, DREA01-03)
       ├── 04 - Espesado (P03 Area Humeda)
       │    ├── 01 - Espesador Concentrado (ESPC01-02)
       │    └── 02 - Espesador Relaves (ESPR01, BREL01-02)
       └── 05 - Filtrado (P01 Area Seca)
            ├── 01 - Filtro Prensa (FILT01-03)
            ├── 02 - Secado y Despacho (SECA01, CORR04-05)
            └── 03 - Servicios Planta (COMP01-02, BAGP01-02, ANPH01, FLMT01, DENS01, VIBM01)
```

**Totales:** 59 equipos Nivel 4 | 141 sistemas Nivel 5 | 265 equipos Nivel 6 | 488 ubicaciones tecnicas

---

## 4. Plan de Entregables y Estado

### Fase 1: Datos Maestros y Transaccionales (Plantillas 01-14)

| # | Entregable | Archivo | Registros | Min Req | Estado |
|---|-----------|---------|-----------|---------|--------|
| 01 | Jerarquia de Equipos (6 niveles + BOM) | `01_equipment_hierarchy.xlsx` | 894 | 200 | COMPLETADO |
| 02 | Evaluacion de Criticidad (ABC 1/2/3) | `02_criticality_assessment.xlsx` | 465 | 200 | COMPLETADO |
| 03 | Modos de Falla FMECA | `03_failure_modes.xlsx` | 274 | 200 | COMPLETADO |
| 04 | Puntos de Medida (CINI_PM_004, tipo M) | `04_measurement_points.xlsx` | 255 | 200 | COMPLETADO |
| 05 | Paquetes de Trabajo | `05_work_packages.xlsx` | 235 | 200 | COMPLETADO |
| 06 | Historial OTs (PM01/02/03/06/07) | `06_work_order_history.xlsx` | 200 | 200 | COMPLETADO |
| 07 | Inventario Repuestos (VED/FSN/ABC) | `07_spare_parts_inventory.xlsx` | 201 | 200 | COMPLETADO |
| 08 | Calendario Paradas | `08_shutdown_calendar.xlsx` | 221 | 200 | COMPLETADO |
| 09 | Fuerza Laboral (turno 7x7 Blueprint) | `09_workforce.xlsx` | 200 | 200 | COMPLETADO |
| 10 | Capturas de Campo | `10_field_capture.xlsx` | 220 | 200 | COMPLETADO |
| 11 | Maestro Puestos de Trabajo (CINI_PM_001) | `11_work_centers.xlsx` | 44 | Config | COMPLETADO |
| 12 | KPIs Planificacion (semanal x PG) | `12_planning_kpi_input.xlsx` | 208 | 200 | COMPLETADO |
| 13 | KPIs Eliminacion Defectos (mensual x PG) | `13_de_kpi_input.xlsx` | 204 | 200 | COMPLETADO |
| 14 | Estrategias Mantenimiento RCM | `14_maintenance_strategy.xlsx` | 284 | 200 | COMPLETADO |

### Fase 2: Estructuras Blueprint Complementarias (Plantillas 15-22)

| # | Entregable | Archivo | Registros | Min Req | Estado |
|---|-----------|---------|-----------|---------|--------|
| 15 | Catalogos y Perfiles (D/B/C/5 + asignaciones) | `15_catalog_profiles.xlsx` | 296 | 200 | COMPLETADO |
| 16 | Hojas de Ruta Detalladas (CINI_PM_005/006) | `16_route_sheets.xlsx` | 1,015 | 200 | COMPLETADO |
| 17 | Planes Mantenimiento Formales (CINI_PM_007) | `17_maintenance_plans.xlsx` | 818 | 200 | COMPLETADO |
| 18 | Documentos MAF/DMS (CINI_PM_008) | `18_dms_maf_documents.xlsx` | 271 | 200 | COMPLETADO |
| 19 | Clasificacion SAP (CINI_PM_011) | `19_classification.xlsx` | 215 | 200 | COMPLETADO |
| 20 | Asignaciones Financieras (CO/PS/FI-AA) | `20_financial_assignments.xlsx` | 142 | Config | COMPLETADO |
| 21 | Puntos Configuracion (CONF_PM_001-058) | `21_configuration_points.xlsx` | 58 | 58 | COMPLETADO |
| 22 | Estructura Organizacional (indicadores, rangos, estado instalacion) | `22_org_structure_config.xlsx` | 94 | Config | COMPLETADO |

### Fase 3: Datos Transaccionales SAP — Criticos (Plantillas 23-25)

| # | Entregable | Archivo | Registros | Min Req | Estado |
|---|-----------|---------|-----------|---------|--------|
| 23 | Backlog Activo (IW38 ordenes abiertas) | `23_active_backlog.xlsx` | 80 | 80 | COMPLETADO |
| 24 | Notificaciones SAP (IW28/IW29 avisos PM) | `24_notifications.xlsx` | 220 | 200 | COMPLETADO |
| 25 | Documentos de Medicion (IK11/IK12 lecturas) | `25_measurement_documents.xlsx` | 307 | 200 | COMPLETADO |

### Fase 4: Datos Transaccionales SAP — Enriquecimiento (Plantillas 26-30)

| # | Entregable | Archivo | Registros | Min Req | Estado |
|---|-----------|---------|-----------|---------|--------|
| 26 | Confirmaciones de Tiempo (IW41/IW42) | `26_time_confirmations.xlsx` | 208 | 200 | COMPLETADO |
| 27 | Movimientos de Material (MB21/MIGO/MB51) | `27_material_movements.xlsx` | 200 | 200 | COMPLETADO |
| 28 | BOM de Equipos (IB01/CS01) | `28_equipment_bom.xlsx` | 246 | 200 | COMPLETADO |
| 29 | Historial de Costos (IW39/KOB1) | `29_cost_history.xlsx` | 123 | Config | COMPLETADO |
| 30 | Datos de Confiabilidad (TTF + Weibull) | `30_reliability_data.xlsx` | 178 | Config | COMPLETADO |

### Plantillas Excluidas (Directiva J. Cortinat)

| # | Entregable | Razon Exclusion | Estado |
|---|-----------|-----------------|--------|
| -- | Maintenance Task (original 04) | Excluido por direccion tecnica | N/A |
| -- | RCA Events (original 11) | Excluido por direccion tecnica | N/A |

---

## 4.1 Especificacion Detallada — Fase 3 (Plantillas 23-25)

### 23 — Backlog Activo (`23_active_backlog.xlsx`)

**Transaccion SAP:** IW38 filtrado por status CRTD/REL (ordenes abiertas)
**Modulo AMS bloqueado:** Modulo 3 — Backlog Optimization
**Referencia Blueprint:** Step 1 "Current Backlog ~80 items", Step 2 "GET /backlog"
**Modelo Pydantic:** `BacklogItem` (schemas.py)

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| backlog_id | S26-BKL-NNNN-XXXX | ID sintetico | synth_id() |
| work_request_id | S26-WR-NNNN-XXXX | Link a solicitud trabajo | — |
| aufnr | Numerico | Numero orden SAP | Rangos por tipo en T27 |
| auart | PM01/PM02/PM03 | Tipo orden (solo correctivo/preventivo/inspeccion) | T26 |
| equipment_tag | OCP-CON1-XXXXX | Tag equipo | Template 01 |
| equnr | Numerico | Numero equipo SAP | Template 01 |
| sap_func_loc | NN-NN-NN-AAAANN | Ubicacion tecnica | Template 01 |
| area | Texto | Area proceso (Chancado, Molienda, etc.) | Template 01 |
| planning_group | P01/P02/P03 | Grupo planificacion | T5 |
| priority | I/A/M/B | Prioridad Z1 | T24, T29 |
| status | Enum | AWAITING_MATERIALS, AWAITING_SHUTDOWN, AWAITING_RESOURCES, AWAITING_APPROVAL, SCHEDULED, IN_PROGRESS | BacklogStatus |
| blocking_reason | Texto | Razon bloqueo (null si SCHEDULED/IN_PROGRESS) | — |
| created_date | ISO 8601 | Fecha creacion (2026-01-15 a 2026-03-25) | — |
| age_days | Entero | Dias desde creacion | Calculado |
| estimated_duration_hours | Decimal | Duracion estimada (2.0-120.0) | — |
| required_specialties | CSV | MEC, ELE, INS, LUB, SOL | Template 11 |
| materials_ready | TRUE/FALSE | Disponibilidad materiales | — |
| shutdown_required | TRUE/FALSE | Requiere parada | — |
| groupable | TRUE/FALSE | Agrupable en WP | — |
| work_center | 8-char | Puesto trabajo responsable | Template 11 |
| description | Max 72 chars | Texto corto SAP | — |

**Distribucion:**
- Status: AWM:15, AWS:12, AWR:10, AWA:18, SCH:15, INP:10
- Prioridad: I:5, A:20, M:35, B:20
- Tipo OT: PM01:30, PM02:25, PM03:25
- Equipos ABC=1 reciben ~60% de los items
- Fecha corte: 2026-03-30 (snapshot unico)

### 24 — Notificaciones SAP (`24_notifications.xlsx`)

**Transaccion SAP:** IW28 (modificar aviso) / IW29 (lista avisos)
**Modulo AMS bloqueado:** Modulo 1-2 — Field Capture → Planner
**Referencia Blueprint:** T20 (clases avisos A1/A2/A3), T21 (rangos), T24 (prioridad), T25 (status ZPM00001)
**Modelo Pydantic:** `StructuredWorkRequest` (schemas.py)

**Sheet 1 — Notificaciones Abiertas (80 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| qmnum | Numerico | Numero notificacion (rango 1-4999999) | T21 |
| qmart | A1/A2/A3 | Clase aviso (averia/predictivo/preventivo) | T20 |
| qmart_desc | Texto | Descripcion clase | T20 |
| equipment_tag | OCP-CON1-XXXXX | Tag equipo | Template 01 |
| equnr | Numerico | Numero equipo SAP | Template 01 |
| sap_func_loc | NN-NN-NN-AAAANN | Ubicacion tecnica | Template 01 |
| area | Texto | Area proceso | Template 01 |
| planning_group | P01/P02/P03 | Grupo planificacion | T5 |
| notification_catalog | M001-M003/P001-P002 | Catalogo asignado | T22-T23, Template 15 |
| user_status_schema | ZPM00001 | Esquema status usuario (solo A1/A2) | T25 |
| user_status | APRO/RECH | Status usuario (solo A1/A2) | T25 |
| priority | I/A/M/B | Prioridad Z1 | T24 |
| priority_class | Z1 | Clase prioridad | T24 |
| reported_by | Worker ID | Reportado por (ref Template 09) | Template 09 |
| reported_date | ISO 8601 | Fecha reporte (2026-01-01 a 2026-03-30) | — |
| description | Max 72 chars | Texto corto | — |
| long_text | Texto | Descripcion extendida | — |
| damage_code | Codigo | Codigo dano (catalogo B de Template 15) | Template 15 |
| cause_code | Codigo | Codigo causa (catalogo 5 de Template 15) | Template 15 |
| object_part_code | Codigo | Parte objeto (catalogo B de Template 15) | Template 15 |
| linked_order | Numerico | Orden vinculada (ref Template 23) | Template 23 |
| system_status | OSNO/NOPR | Status sistema | SAP Standard |
| work_center | 8-char | Puesto trabajo responsable | Template 11 |

**Sheet 2 — Notificaciones Cerradas (140 registros):**
Mismas columnas + `completed_date`, `system_status=NOCO`, `linked_order` referencia Template 06.

**Distribucion tipo:** A1: 50%, A2: 20%, A3: 30%

### 25 — Documentos de Medicion (`25_measurement_documents.xlsx`)

**Transaccion SAP:** IK11 (crear documento medicion) / IK12 (visualizar)
**Modulo AMS bloqueado:** Health Score Engine, Condition Monitoring
**Referencia Blueprint:** T17 (puntos medida tipo M), CINI_PM_004
**Modelo Pydantic:** `KPIMetrics.condition_status` (schemas.py)

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| measurement_doc_id | S26-MDOC-NNNNNN | ID documento | synth_id() |
| measurement_point_id | 12-digit | ID punto medida | Template 04 |
| equipment_tag | OCP-CON1-XXXXX | Tag equipo | Template 01 |
| sap_func_loc | NN-NN-NN-AAAANN | Ubicacion tecnica | Template 01 |
| characteristic | TEMP_BRG_DE, VIB_RAD_DE, etc. | Caracteristica medida | Template 04 MEAS_TYPES |
| reading_date | ISO 8601 | Fecha lectura (2025-10-01 a 2026-03-30) | — |
| reading_time | HH:MM | Hora lectura (alineado turno 08:00-20:00) | T10 |
| measured_value | Decimal | Valor medido (realista por tipo) | — |
| unit_of_measure | C/mm-s/bar/%/L-min/A/kW/h/pH/kg-m3/m3-h | UoM | Template 04 |
| counter_reading | Entero | Para contadores (COUNTER_HRS, COUNTER_CYC) | Template 04 |
| valuation_code | 1/2/3 | 1=OK, 2=Warning, 3=Alarm | Vs limites Template 04 |
| lower_limit | Decimal | Limite inferior | Template 04 |
| upper_limit | Decimal | Limite superior | Template 04 |
| target_value | Decimal | Valor objetivo | Template 04 |
| is_counter | TRUE/FALSE | Tipo contador | Template 04 |
| recorded_by | Worker ID | Tecnico registrador | Template 09 |
| work_center | 8-char | Puesto trabajo | Template 11 |

**Logica generacion:**
- 6 meses de lecturas (2025-10-01 a 2026-03-30)
- Equipos ABC=1: 1 lectura/semana por punto
- Equipos ABC=2/3: 1 lectura/quincenal
- 5-10% de lecturas violan upper_limit (valuation_code=3) — simula degradacion
- Patron de drift: valores inician cerca del target y tienden hacia limites para algunos equipos

---

## 4.2 Especificacion Detallada — Fase 4 (Plantillas 26-30)

### 26 — Confirmaciones de Tiempo (`26_time_confirmations.xlsx`)

**Transaccion SAP:** IW41/IW42 (confirmacion individual/colectiva)
**Uso:** KPIs MTTR, utilizacion laboral, analisis planned vs actual

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| confirmation_id | S26-CONF-NNNN-XXXX | ID confirmacion | synth_id() |
| aufnr | Numerico | Numero orden (solo cerradas) | Template 06 |
| operation_number | 0010/0020/0030/0040 | Numero operacion | Template 16 |
| work_center | 8-char | Puesto trabajo | Template 11 |
| worker_id | Worker ID | Trabajador | Template 09 |
| specialty | MEC/ELE/INS/LUB/SOL | Especialidad | Template 11 |
| start_date | ISO 8601 | Fecha inicio | — |
| start_time | HH:MM | Hora inicio (turno 08:00-20:00) | T10 |
| end_date | ISO 8601 | Fecha fin | — |
| end_time | HH:MM | Hora fin | — |
| actual_work_hours | Decimal | Horas netas trabajadas | — |
| travel_time_hours | Decimal | Tiempo traslado (0.5-2.0) | — |
| setup_time_hours | Decimal | Tiempo preparacion (0.5-1.5) | — |
| final_confirmation | TRUE/FALSE | Ultima operacion de la orden | — |
| system_status_after | PCNF/CNF | Status despues confirmacion | SAP Standard |

**Validacion:** Suma `actual_work_hours` por orden ≈ `duration_hours` en Template 06 (+/- 15%)

### 27 — Movimientos de Material (`27_material_movements.xlsx`)

**Transaccion SAP:** MB21/MIGO/MB51
**Uso:** Inventory turns KPI, trazabilidad material, analisis consumo

**Sheet 1 — Reservas (80 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| reservation_id | S26-RES-NNNN | ID reserva | synth_id() |
| aufnr | Numerico | Numero orden | Template 06 |
| material_code | S26-MAT-NNNN | Codigo material | Template 07 |
| description | Texto | Descripcion material | Template 07 |
| quantity_reserved | Decimal | Cantidad reservada | — |
| unit_of_measure | EA/KG/L/M | UoM | Template 07 |
| movement_type | 261 | Tipo movimiento (salida a orden) | SAP Standard |
| storage_location | ALM-XXX-NN | Ubicacion almacen | — |
| status | OPEN/PARTIALLY_DELIVERED/FULLY_DELIVERED | Estado reserva | — |
| cost_center | CC-XX-XXX-YYY | Centro costo | Template 20 |

**Sheet 2 — Movimientos (120 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| movement_doc_id | S26-MOV-NNNN | ID documento | synth_id() |
| material_code | S26-MAT-NNNN | Codigo material | Template 07 |
| movement_type | 261/262/101/311 | Tipo (salida/anulacion/entrada/traslado) | SAP Standard |
| quantity | Decimal | Cantidad | — |
| aufnr | Numerico | Orden (para 261/262) | Template 06 |
| total_cost_usd | Decimal | Costo total | — |

**Distribucion tipos:** 261: 60%, 101: 25%, 311: 10%, 262: 5%

### 28 — BOM de Equipos (`28_equipment_bom.xlsx`)

**Transaccion SAP:** IB01/CS01
**Uso:** Recomendacion repuestos, MRP, analisis where-used

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| bom_id | S26-BOM-NNNN | ID BOM | synth_id() |
| equipment_tag | OCP-CON1-XXXXX | Equipo padre (nivel 4) | Template 01 |
| item_number | 0010/0020/0030... | Numero posicion (incrementos de 10) | SAP Standard |
| component_category | L/N/D | Stock/Non-stock/Documento | SAP Standard |
| material_code | S26-MAT-NNNN | Codigo material | Template 07 |
| component_desc | Texto | Descripcion componente | Template 07 |
| quantity | Decimal | Cantidad por ensamble | — |
| item_category | SPARE/WEAR/CONSUMABLE | Tipo repuesto | — |
| critical_spare | TRUE/FALSE | Repuesto critico | — |
| lead_time_days | Entero | Tiempo entrega | Template 07 |

**Logica:** 3-5 lineas BOM por equipo, cruzando `applicable_equipment` de Template 07

### 29 — Historial de Costos (`29_cost_history.xlsx`)

**Transaccion SAP:** IW39/KOB1
**Uso:** KPIs financieros mantenimiento, presupuesto, analisis varianza

**Sheet 1 — Costos por Orden (150 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| aufnr | Numerico | Numero orden (cerradas) | Template 06 |
| auart | PM01-PM07 | Tipo orden | T26 |
| value_category | ZMANT001/002/003 | Mano obra/Materiales/Servicios ext | T30 |
| amount_usd | Decimal | Monto USD | — |
| cost_center | CC-XX-XXX-YYY | Centro costo | Template 20 |
| wbs_element | WBS code | Elemento PEP | Template 20 |

**Sheet 2 — Resumen Mensual (50 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| period | YYYY-MM | Periodo (2025-07 a 2026-03) | — |
| area | Texto | Area proceso | Template 01 |
| planning_group | P01/P02/P03 | Grupo planificacion | T5 |
| cost_labour_usd | Decimal | Costo mano obra (ZMANT001) | T30 |
| cost_materials_usd | Decimal | Costo materiales (ZMANT002) | T30 |
| cost_external_usd | Decimal | Costo servicios externos (ZMANT003) | T30 |
| budget_usd | Decimal | Presupuesto | Template 20 |
| variance_pct | Decimal | Varianza % | Calculado |
| maintenance_cost_per_hour | Decimal | Costo por hora mantenimiento | Calculado |

### 30 — Datos de Confiabilidad (`30_reliability_data.xlsx`)

**Uso:** Mantenimiento predictivo, parametros Weibull, MTBF/MTTR
**Modelo Pydantic:** `WeibullParameters`, `FailurePrediction` (schemas.py)

**Sheet 1 — Time-to-Failure (150 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| equipment_tag | OCP-CON1-XXXXX | Tag equipo (foco en ABC=1) | Template 01 |
| failure_event_id | Ref | Link a orden PM01 | Template 06 |
| failure_date | ISO 8601 | Fecha falla | Template 06 |
| previous_failure_date | ISO 8601 | Falla previa mismo equipo | Template 06 |
| time_to_failure_days | Entero | Dias entre fallas | Calculado |
| operating_hours | Entero | Horas operacion entre fallas | — |
| failure_mechanism | Enum 18 valores | Mecanismo falla | Template 03, SRC-09 |
| failure_cause | Enum 44 valores | Causa falla | Template 03, SRC-09 |
| failure_pattern | A-F | Patron falla (Nowlan & Heap) | — |
| repair_duration_hours | Decimal | Duracion reparacion | Template 06 |

**Sheet 2 — Parametros Weibull (50 registros)**

| Columna | Tipo | Descripcion | Referencia |
|---------|------|-------------|------------|
| equipment_tag | OCP-CON1-XXXXX | Tag equipo | Template 01 |
| equipment_class | Texto | Clase equipo (BOMBA_PULPA, MOLINO_SAG, etc.) | — |
| sample_size | Entero | Tamano muestra TTF | Sheet 1 |
| beta | Decimal | Parametro forma (>1 desgaste, <1 mortalidad infantil, =1 aleatorio) | — |
| eta | Decimal | Parametro escala (vida caracteristica en dias) | — |
| gamma | Decimal | Parametro ubicacion (periodo libre falla) | — |
| r_squared | Decimal | Bondad ajuste | — |
| failure_pattern | A-F | Patron derivado de beta | — |
| recommended_interval_days | Entero | Intervalo optimo | — |

---

## 5. Cobertura Blueprint AMSA_BBP_PM_04_Rev_0

### Seccion 2 — Estructura Organizacional

| Entidad Blueprint | Tabla BP | Plantilla(s) | Estado |
|-------------------|----------|-------------|--------|
| Centro Emplazamiento AN01 | T3 | 06, 05 | CUBIERTO |
| Centro Planificacion AN01 | T4 | 06, 05, 01 | CUBIERTO |
| Grupos Planificacion M01-M05, P01-P03 | T5 | 22 (completo), 06/05/12/13 (P01-P03) | CUBIERTO |
| Areas Empresa (9 areas) | T6 | 22 (completo), 06/12/13 (SEC/RIP/HUM) | CUBIERTO |
| Convencion nombres WC internos | T7 | 11 (sheet Naming Convention) | CUBIERTO |
| Convencion nombres WC externos | T8 | 11 (sheet Naming Convention) | CUBIERTO |
| Puestos Trabajo (22 WCs) | T9 | 11 (sheet Work Centers) | CUBIERTO |
| Turnos (4x3, 7x7) | T10 | 11 (sheet Shift Schedules), 09 | CUBIERTO |

### Seccion 3 — Datos Maestros

| Entidad Blueprint | Tabla BP | Plantilla(s) | Estado |
|-------------------|----------|-------------|--------|
| Indicador estructura CORPO | T11-12 | 22 (sheet Structure Indicators) | CUBIERTO |
| Indicador estructura MANTE (6 niveles) | T13 | 22 (sheet Structure Indicators), 01 | CUBIERTO |
| Maestro Ubicaciones Tecnicas tipo M | T14 | 01 | CUBIERTO |
| Maestro Equipos tipo M/Q | T15 | 01 | CUBIERTO |
| Rangos numeros equipos | T16 | 22 (sheet Number Ranges) | CUBIERTO |
| Puntos de Medida tipo M | T17 | 04 | CUBIERTO |
| Rangos numeros puntos medida | T18 | 22 (sheet Number Ranges) | CUBIERTO |
| Indicador ABC 1/2/3 | T19 | 01, 02 | CUBIERTO |
| Elemento PEP / Centro Costo en objetos | -- | 20 (sheets PEP WBS, Cost Centers) | CUBIERTO |

### Seccion 4 — Administracion Procesos Mantenimiento

| Entidad Blueprint | Tabla BP | Plantilla(s) | Estado |
|-------------------|----------|-------------|--------|
| Clases Avisos A1/A2/A3 | T20 | 06 | CUBIERTO |
| Rangos numeros avisos | T21 | 22 (sheet Number Ranges) | CUBIERTO |
| Catalogos D/B/C/5 | T22 | 15 (sheet Catalogs) | CUBIERTO |
| Perfiles Catalogo | T23 | 15 (sheets Catalog Profiles, Assignments) | CUBIERTO |
| Prioridades avisos Z1 | T24 | 06 | CUBIERTO |
| Esquema status ZPM00001 | T25 | 06 | CUBIERTO |
| Clases ordenes PM01-PM07 | T26 | 06 | CUBIERTO |
| Rangos numeros ordenes | T27 | 22 (sheet Number Ranges) | CUBIERTO |
| Clases actividad PM07 RP1/RP2 | T28 | 06 | CUBIERTO |
| Prioridades ordenes Z1 | T29 | 06 | CUBIERTO |
| Categorias valor ZMANT001-003 | T30 | 06 | CUBIERTO |
| Estado instalacion 0/1 | T31 | 22 (sheet Installation Status) | CUBIERTO |
| Puestos trabajo responsable (supervisores) | T32-33 | 11 (sheet Supervisor Work Centers) | CUBIERTO |
| Tipo hoja ruta A | T34 | 16, 05, 14 | CUBIERTO |
| Grupo planificacion hoja ruta PLA/MIN | T35 | 16 | CUBIERTO |
| Estrategias mantenimiento | T36 | 14 | CUBIERTO |
| Tipo plan mantenimiento PM | T37 | 17, 05, 14 | CUBIERTO |

### Seccion 4.3 — Configuracion y Carga Inicial

| Entidad Blueprint | Codigo | Plantilla(s) | Estado |
|-------------------|--------|-------------|--------|
| 58 Puntos de Configuracion | CONF_PM_001-058 | 21 | CUBIERTO |
| Carga masiva puestos trabajo | CINI_PM_001 | 11 | CUBIERTO |
| Carga masiva ubicaciones tecnicas | CINI_PM_002 | 01 | CUBIERTO |
| Carga masiva equipos | CINI_PM_003 | 01 | CUBIERTO |
| Carga masiva puntos medida | CINI_PM_004 | 04 | CUBIERTO |
| Hojas ruta planes mantenimiento | CINI_PM_005 | 16 | CUBIERTO |
| Hojas ruta standard jobs | CINI_PM_006 | 16 | CUBIERTO |
| Planes y posiciones mantenimiento | CINI_PM_007 | 17 | CUBIERTO |
| Documentos MAF con DMS | CINI_PM_008 | 18 | CUBIERTO |
| Exit determinacion clase orden | CINI_PM_009 | 21 (CONF_PM_055) | CUBIERTO |
| Formulario impresion orden | CINI_PM_010 | 21 (CONF_PM_056) | CUBIERTO |
| Clases y caracteristicas | CINI_PM_011 | 19 | CUBIERTO |

### Integraciones

| Integracion | Plantilla(s) | Estado |
|-------------|-------------|--------|
| CO (centros costo, tipos actividad) | 20, 11 | CUBIERTO |
| PS (elementos PEP/WBS) | 20 | CUBIERTO |
| FI-AA (activos fijos) | 20 | CUBIERTO |
| MM (materiales, reservas) | 07, 27 | CUBIERTO |

### Datos Transaccionales SAP (Fase 3-4 — Gap Analysis AMS)

| Entidad Transaccional | Transaccion SAP | Plantilla(s) | Estado |
|-----------------------|-----------------|-------------|--------|
| Backlog activo (ordenes abiertas) | IW38 (CRTD/REL) | 23 | COMPLETADO |
| Notificaciones PM (avisos) | IW28/IW29 | 24 | COMPLETADO |
| Documentos de medicion (lecturas) | IK11/IK12 | 25 | COMPLETADO |
| Confirmaciones tiempo | IW41/IW42 | 26 | COMPLETADO |
| Reservas y movimientos material | MB21/MIGO/MB51 | 27 | COMPLETADO |
| BOM de equipos | IB01/CS01 | 28 | COMPLETADO |
| Costos por orden | IW39/KOB1 | 29 | COMPLETADO |
| Datos confiabilidad (TTF/Weibull) | — (calculado) | 30 | COMPLETADO |

---

## 6. Resumen Volumetrico

| Metrica | Fase 1-2 | Fase 3 | Fase 4 | Total |
|---------|----------|--------|--------|-------|
| Plantillas generadas | 22 | 3 | 5 | 30 |
| Plantillas con 200+ registros | 16 | 2 | 3 | 21 |
| Plantillas config/analisis (<200) | 6 | 1 (backlog 80) | 2 (costos 123, confiab 178) | 9 |
| Total registros | 6,814 | 607 | 955 | 8,376 |

| Metrica Estructural | Valor |
|---------------------|-------|
| Equipos Nivel 4 | 59 |
| Sistemas Nivel 5 | 141 |
| Equipos Nivel 6 | 265 |
| Ubicaciones Tecnicas | 488 |
| Ordenes de Trabajo (historial) | 200 (PM01:50, PM02:70, PM03:25, PM06:25, PM07:30) |
| Ordenes Abiertas (backlog) | 80 (PM01:30, PM02:25, PM03:25) |
| Notificaciones | 220 (abiertas:80, cerradas:140) |
| Documentos Medicion | 307 (6 meses lecturas) |
| SAP Mock JSONs | 5 (existentes) + 3 (Fase 3) + 4 (Fase 4) = 12 (+ reliability_data.json = 13) |
| Scripts generadores | `generate_synthetic_dataset.py` (Fase 1), `generate_missing_templates.py` (Fase 2), `generate_gap_templates.py` (Fase 3) |

---

## 6.1 Entregables Adicionales (Checklist Jose Cortinat)

| # | Entregable | Archivo | Estado |
|---|-----------|---------|--------|
| 00 | Diccionario de Datos / Glosario Codigos | `00_data_dictionary.xlsx` | COMPLETADO |

**Contenido `00_data_dictionary.xlsx` (5 hojas):**
- **SAP Codes:** 60+ codigos SAP (AUART, QMART, status, prioridades, categorias valor, tipos movimiento, etc.)
- **Organizational Codes:** 60+ codigos organizacionales (PG, BA, CC, WBS, puestos trabajo, especialidades, almacenes)
- **Catalog Codes:** 50+ codigos catalogo (B-xxx partes objeto, C-xxx sintomas, 5-xxx causas)
- **Priority Mapping:** Mapeo explicito SAP (I/A/M/B) ↔ AMS (1_EMERGENCY/2_URGENT/3_NORMAL/4_PLANNED)
- **Template Index:** Indice de las 30 plantillas con campos clave, referencias cruzadas, y transacciones SAP

**Campos de cierre OT agregados a Template 06:**
- `cause_description` — Descripcion de la causa raiz encontrada
- `solution_description` — Accion correctiva ejecutada
- `closure_comments` — Notas de cierre y recomendaciones

---

## 7. Discrepancias Conocidas Menores

| # | Item | Detalle | Impacto |
|---|------|---------|---------|
| 1 | Valor "ALL" en KPIs 12/13 | Filas resumen planta usan ALL como PG/BA | Bajo — convencion reporting |
| 2 | criticality_rank en 02 | Score bruto (18-56) en vez de 1/2/3 final | Bajo — clasificacion 1/2/3 correcta en 01 |
| 3 | Grupo hoja ruta en 05 | Dice "Planta" en vez de codigo "PLA" | Bajo — corregido en plantilla 16 |

---

## 8. Gap Analysis — Justificacion Fase 3-4

### Contexto

Las plantillas 01-22 cubren 100% del Blueprint AMSA_BBP_PM_04_Rev_0 (configuracion SAP PM). Sin embargo, al comparar contra las entidades que la aplicacion AMS consume (`tools/models/schemas.py`, API endpoints en `api/routers/`, SAP mock service en `api/services/sap_service.py`), se identificaron **8 gaps en datos transaccionales/operacionales**.

La aplicacion AMS necesita datos que simulen la **operacion diaria** del sistema SAP PM, no solo su configuracion. Los gaps bloquean modulos especificos:

### Impacto por Modulo AMS

| Modulo AMS | Entidad Requerida | Template Gap | Prioridad |
|------------|-------------------|-------------|-----------|
| Modulo 3: Backlog Optimization | `BacklogItem` (schemas.py) | 23 | CRITICO — sin datos el modulo no funciona |
| Modulo 1: Field Capture | `StructuredWorkRequest` → SAP Notification | 24 | CRITICO — output del modulo sin destino |
| Modulo 2: Planner Assistant | Notifications como input | 24 | CRITICO — input del modulo incompleto |
| Health Score Engine | `condition_status_score()` | 25 | CRITICO — dimension "Condition" sin datos |
| KPI Engine | MTTR detallado | 26 | IMPORTANTE — enriquece calculo |
| Inventory KPI | Turns, consumo | 27 | IMPORTANTE — trazabilidad material |
| Spare Parts Engine | Where-used, BOM | 28 | IMPORTANTE — recomendacion repuestos |
| Financial Dashboard | Costos por categoria | 29 | IMPORTANTE — presupuesto y varianza |
| Weibull Engine | Time-to-failure | 30 | IMPORTANTE — mantenimiento predictivo |

### Cambios Codigo AMS Requeridos

| Archivo | Cambio | Fase |
|---------|--------|------|
| `tools/models/schemas.py` (ImportSource enum) | +3 valores: ACTIVE_BACKLOG, SAP_NOTIFICATIONS, MEASUREMENT_DOCUMENTS | 3 |
| `tools/engines/data_import_engine.py` (_REQUIRED_COLUMNS) | +3 mappings columnas requeridas | 3 |
| `api/services/sap_service.py` (file_map) | +3 entradas: IW38_BACKLOG, IW28, IK12 → JSONs | 3 |
| `sap_mock/data/` | +3 archivos JSON (backlog, notifications, measurement_docs) | 3 |
| `tools/models/schemas.py` (ImportSource enum) | +5 valores Fase 4 | 4 COMPLETADO |
| `tools/engines/data_import_engine.py` | +5 mappings adicionales | 4 COMPLETADO |
| `api/services/sap_service.py` | +4 entradas: IW42, MB51, CS03, KOB1 | 4 COMPLETADO |
| `sap_mock/data/` | +4 archivos JSON (+1 reliability_data) | 4 COMPLETADO |

---

## 9. Proximos Pasos

### Inmediatos (Fase 3) — COMPLETADO 2026-03-31
- [x] Generar plantillas 23-25 (`generate_gap_templates.py`) — 607 registros
- [x] Generar JSONs correspondientes en `sap_mock/data/` — 3 archivos
- [x] Extender `ImportSource` (schemas.py), `_REQUIRED_COLUMNS` (data_import_engine.py), `file_map` (sap_service.py)
- [x] Verificar cross-references con plantillas existentes (01, 04, 06, 07, 09, 11, 15)

### Siguientes (Fase 4) — COMPLETADO 2026-03-31
- [x] Generar plantillas 26-30 (`generate_gap_templates.py`) — 955 registros
- [x] Generar JSONs correspondientes en `sap_mock/data/` — 4 archivos adicionales
- [x] Extender `ImportSource` (schemas.py), `_REQUIRED_COLUMNS` (data_import_engine.py), `file_map` (sap_service.py)
- [x] Validar integridad referencial completa (30 plantillas)

### Pendientes Generales
- [ ] Subir cambios a GitHub
- [ ] Ejecutar Gap Analysis comparativo contra datos previos
- [ ] Validar con equipo tecnico (J. Cortinat) las exclusiones 04/11
- [ ] Procesar archivos RFI como ETL real (transformar datos GFSN01 a plantillas)
