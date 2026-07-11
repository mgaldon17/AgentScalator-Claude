# 08 — Configuración (config.yaml como panel de control)

Fuente: plan v1.3.1 §config.yaml (contrato completo — no se duplica aquí; el
YAML del plan es normativo), §Reglas de resolución, F0.2.

## 1. Pipeline de carga (`config/settings.py`)

```
.env (gitignored, solo secretos)
  → parseo de config.yaml
  → resolución de placeholders ${VAR} contra el entorno
  → validación de tipos (Pydantic Settings, nested por sección)
  → validaciones cruzadas (fail-closed, §3)
  → Settings INMUTABLE expuesto al composition root
```

Reglas duras:

- **Un único punto de carga**; ningún módulo lee `os.environ` directamente
  (verificable por grep en CI). Wiring solo en `main.py`.
- Env vars **solo** como overrides puntuales vía `${VAR}`; los secretos (API
  keys) viven exclusivamente en `.env` — nunca en `config.yaml` ni en código.
- Cambios en `config.yaml` requieren restart (sin hot-reload en fase 1).
- Un test unitario carga `config.example.yaml` en cada CI para detectar
  regresiones de schema.
- `config.example.yaml` marca con `# OBLIGATORIO` los campos que el usuario
  final debe rellenar (insumo de la guía de instalación).

## 2. Propiedad por sección (quién consume cada bloque)

| Sección | Consumidor principal |
|---|---|
| `runtime` | interface/http (host, port, api_keys, mode dev/production) |
| `llm` | adapters LLM + Router + health-checks (canario, content filter) |
| `embedder` / `vector_store` | adapters RAG + validación dims/`embedder_id` |
| `mcp_servers` | mcp/client + registry |
| `lessons` | fs_markdown_repo + ingest + chunking |
| `agent` | policies del dominio (retries, umbrales RAG, goal inference, compactor, budget) |
| `task_state` | task_state/fs_repo + recovery (auto_resume, fsync) |
| `fine_tuning` | F7 experimental (gates de datos, presupuesto propio) |
| `evaluation` | run_evals.py (gates, sweep, paridad, targets) |
| `guardrails` | security/* (cadenas, catálogo, URL probe, rate limit, límites) |
| `escalations` | fs_repo + notify (webhook/email — también canal de alertas) |
| `cache` | semantic_cache (matching por call_type, listas cerradas) |
| `observability` | logging/audit/prompt_log/llm_tracing/alerts/archive/purge |
| `dashboard` | app del dashboard (pestañas, métricas — lista cerrada del test de cobertura) |
| `compliance` | validaciones de arranque + pestaña Compliance + MCP shell |

## 3. Validaciones cruzadas al arranque (fail-closed — tabla normativa)

| # | Validación | Error si falla |
|---|---|---|
| 1 | `vector_store.*.vector_size` == `EmbedderPort.dims` del embedder activo | mismatch de dims |
| 2 | metadata `embedder_id` de la colección configurada == embedder activo | colección de otra migración (F6.2) |
| 3 | `llm.backend=local` ⇒ `llm.local.base_url` presente y canario de tool calling OK | backend local inoperante |
| 4 | `llm.backend=azure_openai` ⇒ endpoint en `compliance.region_allowlist` | residencia de datos EU |
| 5 | `mode=production` + backend azure ⇒ auth Managed Identity (sin API key) | compliance auth |
| 6 | `cache.semantic.cacheable_call_types ∩ never_cacheable = ∅` (y `verifier` jamás cacheable) | config de cache peligrosa |
| 7 | rule-sets `secrets` y `pii` del redactor compilan y pasan self-test | redacción caída |
| 8 | catálogo destructivo + `custom_rules_file` compilan | guardrail caído |
| 9 | lecciones con `require_lesson_allowlist=true` sin `tools_allowed` | rechazo en ingest |
| 10 | `dashboard.metrics` ⊆ métricas registradas (y test de widgets, F5.5) | métrica huérfana |

Mensajes de error accionables: nombran la clave de config, el valor observado y
el esperado. «Config a medias» debe ser imposible de servir.

## 4. Registro de valores calibrables (`# ← F1.5`)

Los números operativos NUNCA se hardcodean; los calibrables se marcan en el
YAML y su cambio exige evals en verde + commit (doc 07 §8): umbrales RAG,
confidence del GoalExtractor y, con datos del dashboard,
`degrade_at_pct` (§Further #9) y la permanencia del cache (ADR-08,
diferido-con-datos).

## 5. Overrides y entornos

- `mode: dev` habilita API key para Azure y relaja **solo** lo que el plan
  permite explícitamente (auth LLM); jamás desactiva guardrails, redacción ni
  audit (audit `enabled` NUNCA off en prod).
- `AGENTMEM`-style: no aplica — este sistema no usa mapa plano de env; el
  contrato es YAML anidado + `${VAR}`.
- Backend local: los checks Azure-only (región, content filter, opt-out) se
  registran **N/A visibles** en `/health` y en la pestaña Compliance; PII
  redaction y audit aplican SIEMPRE, a ambos backends.
