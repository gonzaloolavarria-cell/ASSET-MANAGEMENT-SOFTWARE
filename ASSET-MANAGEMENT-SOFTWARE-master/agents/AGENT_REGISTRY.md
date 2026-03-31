# Registro Maestro de Agentes VSC

Última actualización: 2026-03-11 (Session 25 — GAP-W04 Financial)

## Índice de Agentes

| ID | Agente | Carpeta | Modelo | Max Turns | Milestones | # Skills | Estado |
|----|--------|---------|--------|-----------|------------|----------|--------|
| AG-001 | Orchestrator | `agents/orchestrator/` | Sonnet 4.5 | 20 | Todos | 17 (2 mandatory) | Producción |
| AG-002 | Reliability Engineer | `agents/reliability/` | Opus 4.6 | 40 | 1, 2, 3 | 16 (4 mandatory) | Producción |
| AG-003 | Planning Specialist | `agents/planning/` | Sonnet 4.5 | 30 | 3, 4 | 14 (4 mandatory) | Producción |
| AG-004 | Spare Parts Specialist | `agents/spare-parts/` | Haiku 4.5 | 15 | 3 | 3 (2 mandatory) | Producción |

## Skill Assignment

> **Full skill inventory:** See `skills/SKILL_MASTER_REGISTRY.md` for the complete skill × agent × milestone × classification matrix.

| Agente | Skills (primary) | Skills (cross-agent) | Total | Mandatory | # Tools | Milestones |
|--------|:---:|:---:|:---:|:---:|:---:|:---:|
| AG-001 Orchestrator | 17 | — | 17 | 2 | 24 | all |
| AG-002 Reliability | 11 | +5 cross | 16 | 4 | 49 | 1, 2, 3 |
| AG-003 Planning | 11 | +3 cross | 14 | 4 | 62 | 3, 4 |
| AG-004 Spare Parts | 3 | — | 3 | 2 | 3 | 3 |
| **Total** | **42 unique** | **8 shared** | **50** | **12** | **138** | |

## Mapa de Dependencias entre Agentes

| Agente | Depende de | Tipo de Dependencia |
|--------|-----------|---------------------|
| AG-002 (Reliability) | AG-001 (Orchestrator) | Recibe delegaciones del orquestador |
| AG-003 (Planning) | AG-001 (Orchestrator) | Recibe delegaciones del orquestador |
| AG-003 (Planning) | AG-002 (Reliability) | Consume output de reliability (failure modes, RCM decisions, tasks) |
| AG-004 (Spare Parts) | AG-001 (Orchestrator) | Recibe delegaciones del orquestador |
| AG-004 (Spare Parts) | AG-003 (Planning) | Consume tasks con REPLACE del planning agent |
| AG-001 (Orchestrator) | AG-002, AG-003, AG-004 | Coordina a todos los especialistas |

## Single Writer Ownership

| Entidad | Agente Writer | Agentes Readers |
|---------|:------------:|-----------------|
| Nodos de jerarquía | AG-002 | Todos |
| Assessments de criticidad | AG-002 | Todos |
| Modos de falla (FMECA) | AG-002 | Todos |
| Decisiones RCM | AG-002 | Todos |
| Tareas de mantenimiento | AG-003 | Todos |
| Work packages | AG-003 | Todos |
| Work instructions | AG-003 | Todos |
| Paquete SAP export | AG-003 | AG-001 |
| Asignaciones de materiales | AG-004 | Todos |
| Budget items | AG-003 | Todos |
| ROI calculations | AG-001 | Todos |
| Financial impacts | AG-001 | Todos |

## Estructura de Carpetas

```
agents/
├── orchestrator/
│   ├── CLAUDE.md          # System prompt
│   ├── skills.yaml        # 15 skills (2 mandatory)
│   └── config.py          # Factory function
├── reliability/
│   ├── CLAUDE.md          # System prompt
│   ├── skills.yaml        # 15 skills (4 mandatory, 5 cross-agent)
│   └── config.py          # Factory function
├── planning/
│   ├── CLAUDE.md          # System prompt
│   ├── skills.yaml        # 12 skills (4 mandatory, 2 cross-agent)
│   └── config.py          # Factory function
├── spare-parts/
│   ├── CLAUDE.md          # System prompt
│   ├── skills.yaml        # 3 skills (2 mandatory)
│   └── config.py          # Factory function
├── _shared/
│   ├── __init__.py        # Exports
│   ├── base.py            # AgentConfig + Agent class
│   └── loader.py          # Dynamic agent loading
├── AGENT_REGISTRY.md      # Este documento
└── VSC_Agents_Methodology_v1.md  # Metodología
```
