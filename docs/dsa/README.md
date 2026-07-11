# DSA — Digital Twin de Soporte (`ai_agent`)

> **Design & Software Architecture** del agente IA modular con RAG local/cloud,
> LLM conmutable y MCP tools. Generado a partir del contrato de entrada
> [`plan_v1.3.1.md`](plan_v1.3.1.md). **Este DSA no reabre ninguna decisión ya
> tomada en el plan**: las formaliza como ADRs y las baja a nivel de contrato,
> esquema y diagrama para que la implementación sea mecánica.

| Campo | Valor |
|---|---|
| Fuente normativa | `plan_v1.3.1.md` (copiado en este directorio, inmutable) |
| Versión DSA | 1.0 |
| Idioma | Español (contrato del plan: corporativo, solo español) |
| Repo destino de la implementación | **Repo nuevo** (`ai_agent`), separado de Support-Engineer y del MCP browser server (ADR-001 / plan §Further considerations #5) |
| Ámbito de despliegue | Equipo pequeño — sin canary/shadow/cohortes (ADR-014) |

## Regla de oro

Toda afirmación de este DSA es **derivada** del plan v1.3.1. Si un documento de
este DSA contradice al plan, gana el plan y el documento tiene un bug. Los
puntos que el plan deja abiertos están recogidos en cada documento bajo el
epígrafe *«Decisión del DSA»* y provienen únicamente de §Further considerations.

## Mapa de documentos

| Doc | Contenido | Insumo del plan |
|---|---|---|
| [01-arquitectura.md](01-arquitectura.md) | C4 (contexto, contenedores, componentes), capas hexagonales, composition root y arranque fail-closed, vista de despliegue | §Arquitectura por capas, §Cómo hablamos con el LLM, F0 |
| [02-flujos.md](02-flujos.md) | Diagramas de secuencia: agent loop paths A/B/C, reintentos y escalación, crash/resume, migración de embedder, cache | §Agent Loop, F2–F4.6, F6 |
| [03-puertos.md](03-puertos.md) | Contratos de los 7 ports (ABC + DTOs) y obligaciones de los contract tests | §Domain, F1, F2 |
| [04-datos.md](04-datos.md) | Esquemas de datos: lección, payloads Qdrant, TaskState, Escalation, Alert, audit/prompt/trace, golden set, eval report, clave de cache | §Contrato de lección, F1.5, F4.5, F4.6, F5.5 |
| [05-seguridad.md](05-seguridad.md) | Cadenas de guardrails, 3 canales de prompt-injection, trust gate, catálogo destructivo, redacción, MCP shell, matriz fail-closed | F4, §Guardrails del config, compliance |
| [06-observabilidad.md](06-observabilidad.md) | Logs (general/audit/prompt), trazas jerárquicas, prompt registry, métricas continuas, alerting, dashboard | F5.5, §observability del config |
| [07-evaluacion.md](07-evaluacion.md) | Eval suite: runner, métricas, gates, estadística (bootstrap/conteo), baseline SE y gate de paridad, sweep | F1.5, F6 |
| [08-configuracion.md](08-configuracion.md) | Pipeline de carga de config, validaciones cruzadas fail-closed, registro de valores calibrables | §config.yaml (contrato), F0 |
| [adr/](adr/) | 18 ADRs — decisiones registradas (todas «Aceptada»; ninguna se reabre) | §Decisiones, changelogs v1.0→v1.3.1 |
| [anexos/guia_instalacion_esqueleto.md](anexos/guia_instalacion_esqueleto.md) | Esqueleto de `docs/guia_instalacion.md` exigido por F5.5 | §Guía de instalación |

## Índice de ADRs

| ADR | Decisión |
|---|---|
| [ADR-001](adr/ADR-001-runtime-python-hexagonal.md) | Runtime propio en Python con arquitectura hexagonal; sin frameworks de orquestación |
| [ADR-002](adr/ADR-002-llm-conmutable.md) | LLM conmutable `azure_openai \| local` tras un único `LLMPort` con tests de contrato |
| [ADR-003](adr/ADR-003-migracion-embedder.md) | Cambiar de embedder es una migración de datos con colecciones versionadas, no un flag |
| [ADR-004](adr/ADR-004-trust-gate.md) | Trust gate estructural: lecciones `learned` en cuarentena hasta aprobación humana |
| [ADR-005](adr/ADR-005-fail-closed.md) | Política fail-CLOSED en todos los guardrails |
| [ADR-006](adr/ADR-006-eval-suite.md) | Eval suite offline como control de seguridad: gates de CI, calibración, abstención calibrada |
| [ADR-007](adr/ADR-007-baseline-paridad.md) | Baseline del SE actual y gate de paridad para el cutover |
| [ADR-008](adr/ADR-008-cache-scoping.md) | Cache semántico con scoping por `call_type`; planner exact-match; verifier nunca cacheable |
| [ADR-009](adr/ADR-009-taskstate-resume.md) | TaskState con checkpoints; resume exclusivamente humano |
| [ADR-010](adr/ADR-010-degradacion-presupuesto.md) | Degradación de modelo por presupuesto antes del hard stop |
| [ADR-011](adr/ADR-011-audit-vs-prompt-log.md) | Audit SOX sin contenido, separado del prompt log de debugging redactado |
| [ADR-012](adr/ADR-012-redaccion-unica.md) | Pipeline único de redacción con rule-sets `secrets` + `pii` |
| [ADR-013](adr/ADR-013-mcp-shell.md) | MCP shell propio con allowlist comando+subcomando; sin intérpretes, `pip` ni `docker` |
| [ADR-014](adr/ADR-014-ambito-equipo.md) | Ámbito equipo pequeño: sin canary/shadow; evals → aviso → observación |
| [ADR-015](adr/ADR-015-prompt-registry.md) | Prompt registry versionado en git; `prompt_version` en telemetría y cache |
| [ADR-016](adr/ADR-016-fine-tuning-experimental.md) | Fine-tuning excluido de producción; pista experimental gateada por evals |
| [ADR-017](adr/ADR-017-observabilidad-unica.md) | Un solo tracing (`llm_tracing`) y un solo módulo de métricas; OTLP opt-in; sin Prometheus |
| [ADR-018](adr/ADR-018-control-flow-as-code.md) | Rechazo de topologías multi-agente dinámicas: control-flow-as-code |

## Trazabilidad fases → documentos

| Fase del plan | Documentos que la diseñan |
|---|---|
| F0 Cimientos | 01, 08 |
| F1 Domain + RAG read-path | 01, 03, 04 |
| F1.5 Evaluación offline | 07, 04 (esquemas golden set / report) |
| F2 Agent loop mínimo | 02, 03 |
| F2.5 GoalExtractor | 02 (§flujo goal), 03 |
| F3 Interviewer + LessonWriter | 02, 04 (lección) |
| F4 Guardrails | 05 |
| F4.5 Escalations | 02, 04 |
| F4.6 TaskState + recovery | 02, 04, ADR-009 |
| F5 Coste | 02 (§cache), 03 (`CachePort`), ADR-008/010 |
| F5.5 Compliance + observabilidad + dashboard | 05, 06 |
| F6 Migraciones | 02 (§migración), 07 (§gates), ADR-003 |
| F7 Fine-tuning experimental | ADR-016 (el detalle operativo queda en el plan §F7; no requiere diseño adicional en fase 1) |

## Glosario mínimo

- **Path A/B/C**: decisión de routing del retrieval — A = lección con score alto
  (auto-ejecución), B = candidatas de score medio (desambiguar), C = nada
  (Interviewer / escalación). La celda peligrosa es `esperado C → predicho A`.
- **Trust gate**: filtro estructural `pending_review == false` aplicado dentro
  del query del vector store; una lección `learned` no aprobada no existe para
  el retrieval.
- **Fail-CLOSED**: ante error interno o ambigüedad de un guardrail, denegar.
- **`embedder_id`**: identidad `modelo+dims` que liga colección, payload y clave
  de cache; un mismatch aborta el arranque.
- **SE**: Support-Engineer, el sistema actual en producción sobre Claude Code,
  usado como baseline de paridad.
