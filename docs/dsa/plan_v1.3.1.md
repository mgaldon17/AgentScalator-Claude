# Plan v1.3.1: Agente IA modular con RAG local/cloud, LLM conmutable y MCP tools

> **Objetivo del documento**: contrato de entrada para que Claude genere el
> **DSA (Design & Software Architecture)** completo. Todo lo que el DSA necesite
> decidir está decidido aquí; lo que quede abierto está en §Further considerations.

## Registro de cambios v1.3 → v1.3.1 (revisión de coherencia — solo quita o consolida)

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | **MCP shell: fuera `python`, `pip` y `docker` del allowlist**; allowlist a nivel comando+subcomando. | `python -c`, `pip install` (setup.py) y `docker -v /:/mnt` son ejecución arbitraria/escape al host: vaciaban de contenido el catálogo destructivo y el fail-closed. |
| 2 | **Cache: matching por call_type** — `planner` pasa a EXACT-MATCH (hash de prompt normalizado); el matching semántico queda solo para `goal_extractor`. Cache entero marcado "diferido-con-datos". | Un plan cacheado por similitud 0.97 puede pertenecer a una tarea distinta: es el fallo silencioso C→A reintroducido por otra puerta. Incoherente con la abstención calibrada del retrieval. |
| 3 | **Pipeline único de redacción** (`security/redaction.py` con rule-sets `secrets` + `pii`); eliminado `pii_redactor.py`. | Dos módulos solapados (jwt en ambos), dos puntos de fallo fail-closed para la misma responsabilidad. |
| 4 | **Un solo tracing y un solo módulo de métricas**: `llm_tracing.py` subsume a `tracing.py` (OTLP incluido); eliminado `observability/metrics.py` (queda `infrastructure/metrics/in_memory.py`). | Duplicidad v1.0/v1.3. |
| 5 | **Eliminado Prometheus** (`prometheus_enabled`, endpoint `/metrics` estilo Prometheus). Export externo = OTLP bajo `llm_traces.export_otlp`. | Seam huérfano tras fijar ámbito de equipo (v1.3): dos backends de export para cero consumidores. |
| 6 | **Aclarado**: el "dashboard mínimo" de F4.5 es la primera iteración DEL MISMO dashboard de F5.5, no una app aparte. | Ambigüedad que el DSA podría heredar como dos implementaciones. |
| 7 | Regla de alerta `budget_burn` añadida al config (el texto la mencionaba; el config no la tenía). | Deriva texto-config. |
| 8 | `prompt_log.redact_before_write` eliminado del config: la redacción previa a escritura es **invariante de código**, no opción. | Una clave cuyo único valor legal es `true` no es configuración. |

## Registro de cambios v1.2 → v1.3

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | **Fase 7 (experimental) — Fine-tuning: criterios de decisión + pista de práctica** en backend local (QLoRA sobre Mac) y en Azure OpenAI (fine-tuning gestionado). Excluido de producción; habilitado como experimento gateado por evals. | Petición del usuario: poder practicar fine-tuning durante las pruebas con ambos backends, con criterios objetivos (del LLM Handbook, Caps. 5-6) de cuándo pagaría en producción. |
| 2 | **Capa de observabilidad LLM** (basada en Cap. 11 del handbook): trazas jerárquicas por tarea (spans del agent loop), versionado de system prompts, métricas de calidad continuas en producción (distribuciones de score, tasas A/B/C, drift de queries) y alerting por umbrales. | El plan tenía logging/audit/dashboard pero no observabilidad *específica de LLM*: sin trazas por span ni señales de degradación de calidad en producción, los problemas solo se ven cuando un usuario los reporta. |
| 3 | **Metodología estadística de la eval suite**: intervalos de confianza bootstrap, gates por conteo para eventos críticos, mitigación de sesgos del LLM-judge, plan de crecimiento del golden set. | Con n=30 casos, un gate de accuracy 0.85 tiene ±10 puntos de ruido; los gates deben ser estadísticamente honestos. |
| 4 | **Ámbito de despliegue fijado: equipo pequeño.** Sin canary/shadow/cohortes; el procedimiento de cambio es evals → aviso al equipo → ventana de observación en dashboard. | Decisión del usuario: el sistema sirve a su equipo, no a poblaciones grandes de usuarios; la infraestructura de despliegue gradual sería sobreingeniería. |

## Registro de cambios v1.1 → v1.2

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | **Golden set portable + baseline del SE actual**: el golden set de F1.5 se define en formato agnóstico del runtime y se ejecuta TAMBIÉN contra el Support-Engineer existente (vía su MCP de memoria), produciendo un informe baseline versionado. | El SE actual está en producción sin ninguna medición: la eval es la definición operativa de "confiable". Medirlo primero da (a) detección inmediata del modo de fallo silencioso C→A (auto-inyección de lección equivocada) y (b) una vara objetiva para la migración. |
| 2 | **Gate de paridad en la migración SE → sistema nuevo**: el cutover exige que el sistema nuevo iguale o supere el baseline del SE (− tolerancia) sobre el mismo golden set. | Sin baseline, migrar es un acto de fe; con él, es una decisión con datos. |
| 3 | **Abstención calibrada como requisito explícito de F1.5** (no solo sweep): por debajo de `score_threshold_medium` el sistema NO inyecta ninguna lección (path C limpio) y el umbral se calibra con el golden set. | La capacidad de decir "no sé" es la medida anti-fallo-silencioso más rentable; se eleva de detalle de implementación a requisito verificado. |
| 4 | Aclaración normativa: **la eval suite NO sustituye al Verifier ni añade pasos al agent loop** — son planos de control distintos (online por-tarea vs offline agregado). Puntos de contacto documentados. | Evitar que el DSA los fusione o meta la eval en el camino de una petición. |

## Registro de cambios v1.0 → v1.1

| # | Cambio | Motivo |
|---|--------|--------|
| 1 | **Nueva Fase 1.5 — Evaluación offline** (golden set, métricas de retrieval y routing, calibración de umbrales, gate de CI) | v1.0 tenía Verifier (online, por tarea) pero ninguna evaluación agregada; los umbrales `0.75/0.55` eran números sin método. Aquí el score decide **autonomía** (path A ejecuta tools sin preguntar), así que la calibración es de seguridad, no solo de calidad. |
| 2 | **F6 corregida — migración de embedder con colecciones versionadas** | Cambiar embedder (bge-m3 1024d ↔ text-embedding-3-large 3072d) invalida todos los vectores. El seam del puerto no basta: hace falta re-ingesta a colección nueva + validación con evals + cutover atómico. |
| 3 | **Semantic cache con scoping por `call_type`** | La clave v1.0 no distinguía tipos de llamada. Cachear el Verifier es incorrecto (su veredicto depende de la traza de ejecución, que no está en la clave). Solo GoalExtractor y Planner son cacheables. |
| 4 | **LLM backend conmutable**: `llm.backend: azure_openai \| local` (endpoint OpenAI-compatible: Ollama/vLLM/LM Studio) | Requisito nuevo: ejecutar con Azure OpenAI o con LLM local sin tocar código. Nuevo adapter `openai_compatible.py` del mismo `LLMPort`. |
| 5 | **config.yaml como panel de control**: todos los scores, umbrales y números operativos viven en config; ninguno hardcodeado | Los valores calibrables se marcan con comentario `# calibrado por F1.5`. |
| 6 | Política de **prompt logging para debugging** decidida (log separado del audit SOX, redactado, retención corta) | v1.0 dejaba la tensión audit (`args_hash`) vs. debugging sin resolver. |
| 7 | Árbol de ficheros: eliminados duplicados `dashboard/`/`escalations/`; añadidos `evals/`, `scripts/run_evals.py`, `scripts/migrate_embeddings.py`, `infrastructure/llm/openai_compatible.py` | Limpieza + soporte de cambios 1, 2 y 4. |
| 8 | **Nueva Fase 4.6 — Persistencia de TaskState + checkpoints + crash recovery** (`POST /tasks/{id}/resume`) | Gap identificado al comparar con Hive: sin checkpoint, un crash o restart en mitad de una lección pierde la tarea. Inaceptable para flujos largos de soporte. |
| 9 | **Degradación de modelo por presupuesto** (full→mini antes del hard stop) en el Router | Palanca de coste adoptada de Hive: agotar presupuesto degrada calidad de forma controlada antes de cortar el servicio. |
| 10 | **Guía de instalación paso a paso para ingeniero de soporte** (`docs/guia_instalacion.md`) como entregable de F5.5 | Onboarding del usuario final del Digital Twin sin conocimientos del stack. |
| 11 | F1.5: casos con `expected_goal` en el golden set (evalúa el GoalExtractor aislado). F6.3: contrato de serving del LLM local (contexto mínimo, cuantización, batching) | Cierre de los dos matices de la revisión de Caps. 7-8 del handbook. |

---

## Contexto (decisiones del usuario, confirmadas)

- **Lenguaje/runtime**: Python + orquestación propia mínima (sin LangChain/SK/MAF).
- **Rol MCP**: la app es *cliente MCP*; consume `mcp_browser_server` actual + otros MCPs.
- **LLM conmutable (v1.1)**: `llm.backend: azure_openai | local`.
  - `azure_openai`: compliance/coste corporativo (Managed Identity, EU, content filter).
  - `local`: endpoint OpenAI-compatible (Ollama `/v1`, vLLM, LM Studio). Mismo
    `LLMPort`, adapter distinto. Requiere modelos con **tool calling** fiable
    (p. ej. Qwen3); el health-check lo verifica con un canario de function calling.
- **RAG conmutable**: `vector_store.backend: qdrant | azure_ai_search` y
  `embedder.backend: local | azure`. Cuatro combinaciones válidas; el composition
  root cablea adapters según config. **Cambiar de embedder es una migración de
  datos, no un flag** (ver F6).
- **RAG stack local por defecto**: embedder BGE-M3 (fastembed/ONNX) + Qdrant en Docker.
- **Lección**: 1 fichero `.md` por lección con frontmatter YAML. El **usuario** carga
  lecciones manualmente **y** el **agente** debe poder escribir nuevas al completar
  una tarea con éxito. Requiere **Verifier** que cierre el loop con **N reintentos** máximos.
- **UI/deployment fase 1**: API HTTP local (FastAPI) + cliente CLI/web ligero.
  Multi-usuario ready → aplican rate-limit y auth desde el día 1.
- **Cost levers**: todas — router de modelos, semantic cache (con scoping por
  `call_type`, v1.1), contexto mínimo, resumen de conversación, presupuesto duro,
  tool-calling estricto.
- **Extra seguridad**: **guardrails profundos** con allowlist/denylist de tools
  (por lección y globales).
- **Config unificada**: un único `config.yaml` controla TODO número operativo:
  backends (LLM/embedder/vector store), deployments/modelos, umbrales RAG,
  umbrales de evaluación y gates de CI, `max_retries`, presupuesto, guardarraíles,
  cache (tipos de llamada cacheables), chunking, prefijos del embedder.
- **Goal handling**: si el goal viene explícito en la lección seleccionada o en el
  prompt del usuario, se usa. Si no, se **infiere** con LLM barato + schema; si la
  confianza < umbral, el Interviewer pregunta al usuario.
- **Refuerzos tras análisis de Support-Engineer**:
  - **Prompt-injection en 3 canales**: stored (memory poisoning), indirect (tool
    output), input. Con **structural trust gate** (learned = quarantined),
    heuristic detector, `sanitize_for_context` (control/invisible/bidi unicode),
    spotlighting envolvente y `PostToolUse` scan.
  - **Trust gate estructural**: lecciones `origin=learned` nacen `pending_review=true`
    y **nunca** entran en retrieval hasta aprobación humana. Sólo `human_authored`
    (o `learned` aprobadas) son buscables.
  - **Contadores de calidad**: `reuse` / `failure_count` en cada lección; el retrieval
    reordena por `score × (reuse+1)/(reuse+failure_count+1)`. **Sin decay temporal;
    sin borrado automático — la limpieza es manual**.
  - **URL reachability probe** anti-alucinación sobre tools con `url_argument`.
  - **Destructive-command catalog** con keys estables (`rm_root_home`, `mkfs`,
    `dd_to_device`, `fork_bomb`, `force_push_main`, `host_shutdown`, `chmod_777_root`)
    + `guardrails.tools.disabled_patterns` para desactivar sin deploy.
  - **Política fail-CLOSED en guardrails** (divergencia deliberada de SE): ante
    duda o error interno del guardrail, **denegar**. Coste: gates deben tener
    cobertura de tests exhaustiva y health-check propio.
  - **Human escalation queue**: cola persistente + endpoints + entrada mínima en
    dashboard; se materializa el "fallback a humano" del Digital Twin.
- **Compliance Repsol + operación** (aplica cuando `llm.backend=azure_openai`;
  con `local` los checks de región/content-filter se omiten y quedan registrados
  como N/A en `/health` — la PII redaction y el audit log aplican SIEMPRE):
  - **Data residency EU**: recursos Azure OpenAI y Qdrant Cloud (futuro) sólo en
    `West Europe` / `Sweden Central` / `Spain Central`.
  - **Managed Identity (Entra ID)** para autenticar contra Azure OpenAI. **Sin
    API keys en código ni en `config.yaml`** en producción; API key sólo
    permitida en modo dev.
  - **Content-logging opt-out** en Azure OpenAI (no data retention by Microsoft).
  - **PII/PCI redaction** *antes* de enviar prompts al modelo (regex + biblioteca
    dedicada; falla-cerrado si el redactor no arranca). Aplica a ambos backends.
  - **Content filter** de Azure OpenAI a nivel corporativo: configurado y
    verificado por health-check (solo backend azure).
  - **MCP shell server propio** (no Desktop Commander): allowlist explícita de
    comandos permitidos, denylist reforzada; guardarraíles idénticos al MCP browser.
  - **Audit log local** JSON line-delimited por cada acción del agente + rotación
    por día + script cron de purga a 48h con archivado previo a Azure Blob Storage
    (SOX). Sin borrado si el archivo falla (fail-closed en compliance).
  - **Prompt log de debugging (v1.1)**: log SEPARADO del audit, con prompts y
    completions ya redactados (post-PII-redactor), retención corta configurable
    (default 7 días), sin archivado. Permite diagnosticar planes malos sin
    contaminar la cadena SOX. Desactivable en config.
  - **Dashboard in-app** (FastAPI + HTMX + Chart.js + WebSocket) con métricas en
    tiempo real, incluida la última ejecución de la eval suite (v1.1).
  - **README** en estilo Support-Engineer, corporativo y en español únicamente.
- **Objetivo final**: este plan v1.1 es el input para que **Claude** produzca el
  **DSA completo** (diagramas C4/secuencia, contratos de ports, esquemas de datos,
  decisiones ADR). El DSA no debe reabrir decisiones ya tomadas aquí.

---

## TL;DR

Aplicación Python con **arquitectura hexagonal** (Ports & Adapters) en 4 capas
(Domain, Application, Infrastructure, Interface) + cross-cutting Security y
Observability. El núcleo es un **agent loop** de 4 pasos: `Retrieve → Plan →
Execute → Verify`, con **reintentos limitados** y fallback a un **Interviewer**
socrático cuando no hay lección relevante. Al éxito, el **LessonWriter** propone
un `.md` nuevo (previa aprobación humana) y lo indexa. Todos los recursos
externos (LLM ×2 backends, embedder ×2, vector store ×2, MCP tools, lesson repo,
cache) viven detrás de **puertos**, con adapters conmutables desde `config.yaml`.
La calidad del retrieval y del routing A/B/C se mide con una **eval suite offline
(F1.5)** que calibra los umbrales y actúa como gate de CI y de migraciones.
Seguridad y coste son responsabilidades transversales aplicadas por decoradores
y middleware.

---

## Arquitectura por capas (hexagonal)

```
┌────────────────────────────────────────────────────────────────────────┐
│ Interface (Delivery)                                                   │
│  ├─ FastAPI HTTP: /tasks, /lessons, /escalations, /health              │
│  └─ CLI ligera (typer) → llama a la API HTTP                           │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ DTOs
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Application (Use cases / Orquestación)                                 │
│  ├─ AgentLoop (orchestrator)                                           │
│  ├─ Planner (RAG lookup + selección de lección)                        │
│  ├─ Executor (ejecuta pasos vía MCP tools con allowlist)               │
│  ├─ Verifier (aplica criterios de aceptación de la lección)            │
│  ├─ Interviewer (preguntas socráticas cuando no hay lección)           │
│  └─ LessonWriter (drafts .md desde traza + gate humano)                │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ Ports (ABC)
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Domain (Núcleo)                                                        │
│  ├─ Entidades: Lesson, Task, Turn, ToolCall, Verdict, Plan, CostLedger │
│  ├─ Ports: LLMPort, EmbedderPort, VectorStorePort, ToolRunnerPort,     │
│  │          LessonRepositoryPort, CachePort, GuardrailPort             │
│  └─ Policies: retries, thresholds RAG, presupuesto, allowlist          │
└──────────────────────────────────┬─────────────────────────────────────┘
                                   │ implementa
┌──────────────────────────────────▼─────────────────────────────────────┐
│ Infrastructure (Adapters)                                              │
│  ├─ llm/azure_openai.py + llm/openai_compatible.py + llm/router.py    │
│  ├─ embedder/fastembed_bge_m3.py + embedder/azure_openai_embed.py      │
│  ├─ vector_store/qdrant_local.py + vector_store/azure_ai_search.py     │
│  ├─ mcp/client.py + mcp/registry.py  (stdio, discovers servers)        │
│  ├─ lessons/fs_markdown_repo.py                                        │
│  └─ cache/semantic_cache_qdrant.py                                     │
└────────────────────────────────────────────────────────────────────────┘

Cross-cutting: Security (guardrails, prompt injection, rate limit, redaction,
tool allowlist), Observability (JSON logs + audit + prompt-log debug +
export OTLP opt-in), Evaluation (golden set + métricas + gates),
Config (Pydantic Settings + config.yaml único).
```

**Principios aplicados (SOLID + hexagonal):**
- **SRP**: cada módulo un motivo de cambio (Verifier no sabe de RAG, etc.).
- **OCP**: nuevos LLMs/vector stores = nuevo adapter, sin tocar Application.
- **LSP**: adapters intercambiables detrás del mismo Port. Los 2 adapters de
  `LLMPort` (azure/local) comparten suite de tests de contrato (v1.1).
- **ISP**: ports pequeños y específicos (no una `IEverything`).
- **DIP**: Application depende de Ports (abstracciones), no de SDKs concretos.
- **Composition root**: `main.py` cablea Ports → Adapters según `config.yaml`
  (única fuente de wiring). Al arranque valida compatibilidad
  embedder ↔ colección (dims) y capacidades del LLM (tool calling) — fail-closed.

---

## Agent Loop (flujo canónico)

```
1.  Ingesta:               receive(user_goal_or_prompt, session_id)
2.  Guardrail IN chain:    rate_limit → auth → size → injection detector →
                           PII redact → budget check → topic denylist
                           (fail-CLOSED: error/duda → 4xx/5xx)
3.  Goal extraction:       GoalExtractor(prompt)
    ├─ goal explícito en prompt: use it
    ├─ inferible con LLM mini + schema JSON, confidence ≥ τ_goal: use it
    └─ confidence < τ_goal: jump a Interviewer.ask_goal → reanudar
4.  Retrieve:              embed(goal) → vector_store.top_k(N)
                           filter( score>τ  AND  pending_review==false )   ← trust gate
                           rerank por (score × (reuse+1)/(reuse+failure_count+1))
5.  Decision:
    ├─ lección con score > τ_high:   path A      # τ calibrados por F1.5
    ├─ candidatas score medio:        path B
    └─ nada:                          path C
6.  Plan:                  Planner → Plan(goal, steps, expected_tools, acceptance)
                           - Si la lección declara `goal:` úsalo; si no, usa el inferido
7.  Execute (max_retries = config.agent.max_retries):
    for step in plan.steps:
        # Guardrail IN por tool: URL probe, destructive-cmd blocklist,
        # allowlist ∩ (denied_global − ...)  (fail-CLOSED)
        validate_tool_call(step)
        result = call MCP tool via ToolRunnerPort

        # PostToolUse scan: envolver el output como UNTRUSTED DATA + spotlighting
        wrapped = sanitize_for_context(result) → wrap_as_untrusted(wrapped)
        collect wrapped
8.  Verify:                Verifier(plan, trace) → Verdict{ok, evidence, reason}
    ├─ ok:                 goto 9
    ├─ !ok and retries<N:  Planner.re_plan(feedback) → goto 7
    └─ !ok and retries==N: HumanEscalation.enqueue(trace, hint) → goto 10
9.  Learn (solo path B/C exitoso):
    LessonWriter drafts .md (origin=learned, pending_review=true)
    → embed y upsert PERO NO auto-inject (trust gate estructural)
    → aparece en /escalations o /review para aprobación humana
    Si Verdict.ok: reuse++ en lecciones aplicadas.
    Si Verdict.!ok tras reintentos: failure_count++ (no se borra, sólo señal).
10. Guardrail OUT chain:   PII scrub → cost report → response shaping
11. Persist telemetría:    tokens, model, backend, retries, path, verdict,
                           goal_source, latency, cache_hit, escalated
```

---

## Cómo hablamos con el LLM (modelo de interacción, ambos backends)

**Punto crítico**: el LLM — sea Azure OpenAI o un endpoint local OpenAI-compatible
(Ollama `/v1`, vLLM, LM Studio) — **NO es un proceso interactivo**. Es un endpoint
HTTPS stateless. El LLM **no ejecuta nada**, no tiene red, no toca la máquina.

**Consecuencias arquitectónicas:**
1. **El LLM recibe texto** (system + user + tools schema) y **devuelve texto
   o `tool_calls` estructurados**. Nada más. Sin acceso a disco, sin red interna,
   sin credenciales corporativas.
2. **Los MCP tools son procesos LOCALES** que arranca Python por `stdio`. El LLM
   sólo *sugiere* intenciones (tool_calls); nuestro **Executor** decide si obedecer
   tras aplicar guardrails, y ejecuta.
3. **Autenticación**: backend azure → Managed Identity (Entra ID) en producción,
   sin API keys. Backend local → sin auth o token estático del servidor local
   (`${LOCAL_LLM_API_KEY}` opcional); nunca sale de la máquina/red local.
4. **"Instala X" no es una función del LLM** — es una **lección** en el RAG que
   enseña al Planner cómo componer llamadas MCP para lograr ese goal. Si no
   existe la lección o el MCP tool, el agente **no puede** instalar nada. Ese es
   el modelo de seguridad: la capacidad se compone de tools MCP explícitos con
   allowlist, no de "el LLM lo hará".
5. **Para Repsol** no usaremos Desktop Commander. Construiremos un **MCP shell
   server propio** con allowlist explícita de comandos, guardrails idénticos al
   MCP browser.
6. **Paridad de capacidades entre backends (v1.1)**: el agent loop exige
   function calling estricto y JSON schema. El adapter local verifica en el
   health-check que el modelo configurado responde correctamente a un canario de
   tool calling; si falla → arranque en error (fail-closed). El Router y los
   alias (`mini`/`full`/`judge`) funcionan igual en ambos backends: en local los
   alias apuntan a modelos servidos (p. ej. `mini: qwen3:8b`, `full: qwen3:35b`).

---

## Fases de implementación

### Fase 0 — Cimientos (skeleton + config + observabilidad)
Objetivo: proyecto ejecutable "hello world" con HTTP, config tipada, logs JSON.
1. Estructura de paquetes (ver §Estructura) + `pyproject.toml`.
2. `config/settings.py` con Pydantic Settings: carga `config.yaml`, resuelve
   `${VAR}`, valida tipos y **valida coherencia entre backends** (p. ej.
   `vector_size` debe cuadrar con el embedder activo; `llm.backend=local`
   requiere `llm.local.base_url`).
3. `observability/logging.py` — JSON line-delimited, `correlation_id` por request.
4. `interface/http/app.py` con `/health` y middleware de logging.
5. `main.py` composition root vacío (registra ports pendientes).
6. `docker-compose.yml` con Qdrant.

### Fase 1 — Domain + RAG read-path
Objetivo: "dada una consulta, devuelve top-K lecciones".
1. `domain/models.py`: `Lesson`, `LessonId`, `LessonChunk`, `RetrievalHit`.
2. `domain/ports.py`: `EmbedderPort`, `VectorStorePort`, `LessonRepositoryPort`.
3. `infrastructure/embedder/fastembed_bge_m3.py`.
4. `infrastructure/vector_store/qdrant_local.py`.
5. `infrastructure/lessons/fs_markdown_repo.py` (lee `.md` + frontmatter YAML).
6. Comando `ingest` (CLI): recorre `LESSONS_DIR`, valida schema, embed, upsert.
   Registra en el payload de cada punto: `embedder_id` (modelo + dims) y
   `lesson_version` (v1.1 — necesario para F6 y para el cache).
7. Endpoint `POST /lessons/search { query, k }` para prueba manual.

### Fase 1.5 — Evaluación offline (NUEVA en v1.1) *depende de F1; blocking para calibrar umbrales; gate de CI desde que existe*
Objetivo: medir retrieval y routing de forma agregada y reproducible; convertir
los umbrales del config en valores calibrados y defendibles; detectar regresiones
al añadir lecciones, cambiar chunking o migrar embedder/vector store.

**Por qué es crítica aquí**: en este sistema el score de retrieval decide
**autonomía** (path A = auto-ejecutar tools reales sin preguntar). Un umbral mal
calibrado no produce una respuesta mediocre — ejecuta la lección equivocada.
La eval suite es por tanto un control de seguridad, no solo de calidad.

**Relación con el Verifier (normativo, v1.2)**: la eval suite NO sustituye al
Verifier ni introduce pasos en el agent loop. Son planos distintos: el Verifier
es control online por tarea (¿esta ejecución cumple los criterios de la
lección?); la eval es control offline agregado (¿el sistema recupera, decide y
juzga bien?). Una petición de producción nunca pasa por la eval suite. Puntos de
contacto, siempre de la eval hacia el loop: (a) calibra los umbrales que el loop
usa, (b) audita al LLM-judge del Verifier contra `verifier_cases.yaml`,
(c) hace de gate en CI, ingestas y migraciones. Analogía: Verifier = control
operativo por transacción; eval suite = auditoría periódica del control (SOX).

**1. Golden set** — `evals/golden_set.yaml`, versionado en git, **formato
agnóstico del runtime (v1.2)**: los casos no referencian APIs internas, solo
`prompt`, `expected_lesson_id`, `expected_path`, `expected_goal?`, `tags`. Esto
permite ejecutar el MISMO golden set contra el sistema nuevo y contra el
Support-Engineer actual.
```yaml
cases:
  - id: gs-001
    prompt: "exporta la última página del listado AMI de servicenow"
    expected_lesson_id: sn-ami-export-last-page   # null si expected_path=C
    expected_path: A            # A | B | C
    tags: [servicenow, sox]
  - id: gs-014
    prompt: "a ver esa cosa de servicenow"
    expected_lesson_id: null
    expected_path: C            # demasiado ambiguo: debe ir a Interviewer
    tags: [ambiguous]
```
- Tamaño inicial: 20-40 casos. Composición mínima: ≥50% casos path A (hit claro),
  ≥20% casos path C (queries sin lección — miden falsos positivos, los peligrosos),
  resto path B. Cada lección nueva relevante añade ≥1 caso.
- Los casos path C son la prioridad: miden que el sistema NO ejecuta cuando no debe.
- **Casos con `expected_goal` (v1.1)**: un subconjunto de casos incluye el campo
  opcional `expected_goal` para evaluar el GoalExtractor de forma aislada
  (match semántico judge-based o exacto normalizado). Métrica: goal accuracy;
  gate propio en `evaluation.gates.min_goal_accuracy`.

**2. Verifier judge set (opcional pero recomendado)** — `evals/verifier_cases.yaml`:
trazas fixture (JSON) con veredicto humano conocido (`ok`/`!ok` + motivo). Mide
accuracy del LLM-judge del Verifier. 10-15 casos bastan para detectar un judge roto.

**3. Runner** — `scripts/run_evals.py`:
- Para cada caso: `embed(prompt)` → `search()` (con trust gate) → rerank → decisión
  de path con los umbrales del config activo.
- **Métricas de retrieval**: hit@k (¿la lección esperada está en top-k?), MRR,
  precision@1.
- **Métricas de routing**: accuracy global + matriz de confusión A/B/C. La celda
  crítica es `esperado C → predicho A` (auto-ejecución indebida): tiene su propio
  gate, más estricto.
- **Modo calibración** (`--sweep`): barre `score_threshold_high` y
  `score_threshold_medium` en los rangos de `config.evaluation.sweep`, reporta la
  pareja que maximiza routing accuracy sujeta a `C→A = 0`. **Solo sugiere; nunca
  escribe el config** — el cambio de umbral es una decisión humana con commit.
- **Salida**: `evals/reports/eval-YYYY-MM-DD-HHMM.json` + resumen markdown.
  Exit code ≠ 0 si algún gate de `config.evaluation.gates` falla.
- Determinismo: `temperature=0` donde aplique; el retrieval es determinista.

**3.5 Baseline del SE actual y gate de paridad (NUEVO v1.2)**:
- `run_evals.py --target se-mcp`: segundo target del runner que ejecuta el
  golden set contra la memoria del Support-Engineer existente a través de su
  servidor MCP (`search` de lecciones), aplicando sus umbrales de auto-inyección
  actuales para clasificar la decisión equivalente a A/B/C.
- Produce `evals/reports/baseline-se.json`, versionado (excepción al gitignore
  de reports): es la línea base oficial del sistema en producción.
- **Uso inmediato**: detecta HOY los fallos silenciosos del SE (celda C→A) y
  calibra su umbral de auto-inyección — valor entregado sin esperar al sistema
  nuevo (2-4 tardes de esfuerzo, portable al 100%).
- **Gate de paridad**: el cutover SE → sistema nuevo requiere que el sistema
  nuevo cumpla `métrica ≥ baseline_se − evaluation.parity_tolerance` en hit@k,
  routing accuracy y C→A (esta última sin tolerancia: ≤ baseline, ideal 0).
  Sin paridad demostrada, no hay migración.

**3.6 Abstención calibrada (requisito explícito, v1.2)**: por debajo de
`score_threshold_medium`, el sistema no inyecta NINGUNA lección en el contexto
(path C limpio: Interviewer o escalación, nunca "la menos mala"). El umbral de
abstención se calibra con el golden set (`--sweep`) y tiene test propio: un caso
path C sembrado con una lección señuelo de score 0.50 NO debe inyectarla.

**3.7 Metodología estadística (NUEVO v1.3)** — los gates deben ser honestos con
el tamaño muestral:
- **Intervalos de confianza**: el report incluye IC 95% por bootstrap (1.000
  remuestreos) para cada métrica proporcional. Con n=30, accuracy 0.85 ±~0.10:
  el report lo muestra y el gate compara contra el límite inferior del IC solo
  cuando `evaluation.gates.use_ci_lower_bound=true` (recomendado al crecer el set).
- **Gates por conteo para eventos críticos**: los modos de fallo peligrosos se
  gatean por conteo absoluto, no por proporción — `max_c_to_a_errors: 0` es
  robusto a cualquier n; "accuracy ≥ X" con n pequeño no lo es.
- **Sesgos del LLM-judge y mitigación**: el judge del Verifier se audita contra
  `verifier_cases.yaml` conociendo sus sesgos documentados — posición (aleatorizar
  orden cuando compare alternativas), verbosidad (rúbrica que puntúe evidencia,
  no longitud), auto-preferencia (el alias `judge` puede ser modelo distinto al
  generador). La rúbrica del judge es parte del prompt registry versionado (v1.3).
- **Crecimiento del golden set**: objetivo n≥100 en 3 meses de operación; cada
  escalación resuelta y cada lección nueva aportan casos. El report avisa si
  n < `evaluation.min_cases_for_proportional_gates` (default 50) y en ese caso
  solo los gates por conteo son bloqueantes.

**4. Integración**:
- **CI**: job que corre `run_evals.py` en cada PR; gates bloquean el merge.
- **Post-ingest**: tras `ingest` o aprobación de lección `learned`, corre en modo
  warn (no bloquea, loguea deltas de métricas).
- **Migraciones (F6)**: la eval suite corre contra la colección candidata ANTES
  del cutover; si las métricas caen por debajo de baseline − tolerancia, no se migra.
- **Dashboard**: widget "Evals" en Overview con métricas del último report y delta
  vs. anterior.

**5. Entregables**: `evals/golden_set.yaml`, `evals/verifier_cases.yaml`,
`scripts/run_evals.py`, sección `evaluation:` en config, job de CI, test de que
el runner detecta una regresión sembrada (mover un umbral a 0.99 debe romper gates).

### Fase 2 — Agent Loop mínimo (path A) *depende de Fase 1*
Objetivo: ejecutar una lección conocida end-to-end.
1. `domain/ports.py`: `LLMPort`, `ToolRunnerPort`.
2. `infrastructure/llm/azure_openai.py` (chat, function calling estricto, lee
   `config.llm.deployments`) **y** `infrastructure/llm/openai_compatible.py`
   (mismo contrato contra `llm.local.base_url`; mapea alias → `llm.local.models`).
   Ambos pasan la **misma suite de tests de contrato de `LLMPort`** (v1.1).
3. `infrastructure/mcp/client.py` (stdio; abre servidores según `config.mcp_servers`).
4. `infrastructure/mcp/registry.py` (indexa tools de cada servidor y las prefija por `name`).
5. `application/planner.py` — `select_lesson(hits, goal) → Plan`.
6. `application/executor.py` — itera `plan.steps`, invoca tools con validación allowlist.
7. `application/verifier.py` — evalúa `Plan.acceptance` (rule / llm_judge / híbrido).
8. `application/agent_loop.py` — orquesta 1-7 del flujo (sin GoalExtractor ni
   Interviewer aún; se asume goal explícito).
9. Endpoint `POST /tasks { prompt }` → devuelve `Verdict + trace + cost`.

### Fase 2.5 — GoalExtractor *depende de Fase 2, blocking para Fase 3*
Objetivo: convertir prompts imprecisos en un `goal` normalizado antes del retrieve.
1. `application/goal_extractor.py`:
   - Rama 1 (barata, sin tokens): heurística — si el prompt es imperativo corto y
     contiene una única acción reconocible por regex → devuelve
     `Goal{text, source="explicit", confidence=1.0}`.
   - Rama 2 (LLM mini): prompt de una línea + schema JSON con
     `{goal, entities, confidence, needs_clarification}`.
     Modelo = alias `mini` (resuelto por el backend activo),
     `max_tokens ≤ config.agent.goal_inference.max_inference_tokens`.
   - Rama 3: si `confidence < config.agent.goal_inference.confidence_threshold`
     o `needs_clarification=true` → devuelve `NeedsUserInput(question)` que el
     AgentLoop enruta al Interviewer.
2. AgentLoop llama al GoalExtractor entre pasos 2 y 3 del flujo canónico.
3. Cuando una lección seleccionada trae `goal:` propio, prevalece sobre el inferido
   (se registra `goal_source` en telemetría: `explicit|inferred|lesson`).

### Fase 3 — Interviewer + LessonWriter (paths B, C) *depende de Fase 2.5*
Objetivo: cerrar el ciclo de aprendizaje.
1. `application/interviewer.py` — dos modos:
   - `ask_goal(prompt)` — pregunta única para clarificar goal.
   - `disambiguate(hits) / from_scratch(goal)` — batería de preguntas mínimas
     (schema JSON) hasta confianza ≥ umbral; produce `Plan` provisional.
2. `application/lesson_writer.py` — de una traza exitosa (path B/C) sintetiza un
   draft `.md` con frontmatter (id, title, **goal**, tags, precondiciones, pasos,
   tools_allowed, acceptance, ejemplos I/O).
3. Endpoint `POST /lessons/draft` (requiere `X-Approve: true` para persistir).
4. Reingesta automática tras persistir (embed + upsert) + run de evals en modo warn.

### Fase 4 — Guardrails de seguridad (3 canales, fail-CLOSED) *parallel with Fase 3*
Objetivo: defensa en profundidad contra los tres canales de prompt-injection y
las tools destructivas. **Todo guardrail o hook falla CLOSED**: ante error interno
o duda, deniega. Coste operativo: gates con cobertura de tests exhaustiva y
`/health` reporta su estado.

**Canal 1 — Input / user prompt**
1. `security/rate_limit.py` (slowapi, per-IP + per-API-key, bucket de tokens).
2. Auth: API key en `X-API-Key` validada contra `settings.runtime.api_keys`.
3. `security/prompt_injection.py`:
   - `scan_for_injection(text) -> list[Hit]` con firmas conservadoras portadas de SE:
     instruction-override, role markers, imperatives de exfiltración,
     "disable guardrails", unicode invisible/bidi, canary token leak.
   - `sanitize_for_context(text, max_len)` — strip control/invisible + bound length.
   - Estrategia según `config.guardrails.prompt_injection.strategy`.
   - **Fail-CLOSED**: si el detector lanza excepción → deny con motivo genérico.
4. `security/redaction.py` — **pipeline ÚNICO de redacción (v1.3.1)** con dos
   rule-sets: `secrets` (jwt, api_key, password, aws_secret — sobre inputs,
   outputs y logs) y `pii` (dni_es, iban, credit_card, corporate_email;
   presidio opcional — ANTES de cada llamada LLM, ambos backends). Fail-CLOSED.
   Sustituye al par redaction.py + pii_redactor.py de versiones anteriores.

**Canal 2 — Indirect / tool output**
5. `security/spotlighting.py`:
   - `wrap_as_untrusted(text, source)` — envuelve el output entre marcadores
     explícitos con directiva de no obedecer instrucciones embebidas.
   - `scan_tool_output(text) -> list[Hit]` — mismas signatures aplicadas al
     output antes de spotlighting.
6. `application/executor.py` invoca `wrap_as_untrusted(sanitize_for_context(result))`
   **antes** de agregar el resultado al contexto del LLM. Este paso NO puede saltarse.

**Canal 3 — Stored / memory poisoning (trust gate estructural)**
7. `domain/models.py::Lesson` gana: `origin` (`learned | human_authored`),
   `pending_review: bool`, `reuse: int = 0`, `failure_count: int = 0`.
8. `application/lesson_writer.py` marca todo draft `origin=learned, pending_review=true`.
9. `search()` filtra `pending_review == false` **en el propio query** de ambos
   backends de vector store (no en post-filter Python).
10. `fs_markdown_repo.py` corre `scan_for_injection` sobre el `.md` **antes** de
    indexar; hit → fuerza `pending_review=true` y warning.

**Canal común — Tool input / impact (guardrails profundos)**
11. `security/allowlist.py`:
    - Efectivo por step = `lesson.tools_allowed ∩ (allowed_global | all_tools) − denied_global`.
    - Si `require_lesson_allowlist=true` y la lección no declara → rechazo en ingest.
    - Tools no listadas en catálogo MCP conocido → rechazo.
12. `security/url_guardrail.py`: `_http_probe(url)` con timeout de config; veta si
    scheme no http(s), host no en allowlist, DNS falla o 404/410.
    **Fail-CLOSED en ambiguos (TLS, timeout)**.
13. `security/destructive_guardrail.py`: catálogo con keys estables + motivo humano
    + regex. `guardrails.tools.disabled_patterns` para desactivar sin deploy;
    `guardrails.tools.custom_rules_file` para reglas adicionales.

**Límites**
14. `guardrails.request.max_body_bytes`, `tool_timeout_seconds`, `task_timeout_seconds`.
15. **Health-check**: `/health` verifica que todos los guardrails están cargados y
    responden a un canary; si alguno falla → 503 (fail-CLOSED extremo).

### Fase 4.5 — Human escalation queue *depende de Fase 4*
Objetivo: materializar el "fallback a humano" del Digital Twin.
1. `domain/models.py::Escalation`: `id, task_id, goal, plan, trace, verdict, reason,
   status (open|claimed|resolved|dismissed), created_at, resolved_at, resolved_by`.
2. `infrastructure/escalations/fs_repo.py` — JSON append-only + índice en memoria.
3. Triggers automáticos: `retries == max_retries` con `Verdict.!ok`;
   `GoalExtractor.confidence < threshold` en modo batch; `Executor` bloquea por
   guardrail sin alternativa.
4. Endpoints: `GET /escalations?status=open`, `POST /escalations/{id}/claim`,
   `POST /escalations/{id}/resolve` (opcional `promote_to_lesson=true`),
   `POST /escalations/{id}/dismiss`.
5. Resolver una escalación puede generar un draft de lección (entra en `/review`
   con `pending_review=true`).
6. **Dashboard — primera iteración (v1.3.1: aclaración)**: pestañas
   `Escalations` y `Review` DEL MISMO dashboard de F5.5 (misma app FastAPI/HTMX
   montada en `/dashboard`); F5.5 lo completa con el resto de pestañas. NO es
   una aplicación aparte. Antes de producción.

### Fase 4.6 — Persistencia de TaskState + crash recovery (NUEVA en v1.1) *depende de Fase 4.5*
Objetivo: que ningún crash, restart o timeout pierda una tarea en curso. Adoptado
del análisis de Hive (checkpoint-based recovery), implementado al estilo del
resto del sistema: explícito, simple, auditable.

1. `domain/models.py::TaskState`: `task_id, session_id, goal, lesson_id, plan,
   current_step_index, completed_steps[] (con tool, args_hash, result_digest,
   verdict parcial), retries_used, status
   (running | awaiting_resume | verifying | done | failed | escalated),
   cost_so_far, created_at, updated_at`.
2. `infrastructure/task_state/fs_repo.py` — persistencia JSON append-only en
   `task_state/` (mismo patrón que escalations): un fichero por tarea, cada
   checkpoint es una línea. La última línea válida define el estado. Escritura
   atómica (write-temp + rename).
3. **Checkpoint tras cada step verificado por guardrails y ejecutado**: el
   Executor persiste ANTES de enviar el resultado al LLM (si el proceso muere
   durante la llamada LLM, el step ejecutado no se repite — crítico para tools
   con efectos: no se reenvía un email ni se re-ejecuta un comando).
4. **Recovery al arranque**: el composition root escanea `task_state/` buscando
   `status=running` huérfanos → los marca `awaiting_resume` y los lista en
   `GET /tasks?status=awaiting_resume` y en el dashboard.
5. **`POST /tasks/{id}/resume`**: reconstruye el contexto desde los checkpoints
   (plan + steps completados como observaciones ya spotlighted) y continúa desde
   `current_step_index`. **Decisión de seguridad**: resume NUNCA es automático —
   un humano (o política explícita `task_state.auto_resume: false` por defecto)
   decide, porque el mundo puede haber cambiado desde el crash y re-ejecutar
   pasos con efectos requiere criterio.
6. **Idempotencia**: cada step lleva `step_execution_id` único; el MCP shell/browser
   server puede deduplicar si recibe el mismo id dos veces (best-effort; los
   tools sin soporte se re-ejecutan solo tras confirmación en el resume).
7. Retención: `task_state.max_age_days` (default 30) con purga; tareas `done`
   se compactan a una línea de resumen. El audit log ya registra los eventos;
   TaskState es estado operativo, no evidencia SOX.
8. **Session isolation (v1.1)**: `session_id` en TaskState + budget + cache
   namespace ⇒ dos sesiones concurrentes no comparten estado mutable.

### Fase 5 — Coste (todas las palancas) *parallel with Fase 4*
Objetivo: minimizar tokens/€ por tarea.
1. `infrastructure/llm/router.py` — política por alias, agnóstica del backend:
   - default: alias `mini`.
   - escalation: si `verifier` marca ambigüedad, tarea `complex` en la lección, o
     `retry_gte_2` → alias `full`.
   - **degradación por presupuesto (v1.1, adoptado de Hive)**: cuando
     `usage ≥ degrade_at_pct·budget`, el router deja de conceder escalations a
     `full` y fuerza `mini` para todo (degradación de calidad controlada antes
     del corte). Orden de agotamiento: `full` prohibido → aviso al usuario →
     `hard_stop` al 100%. Cada degradación se registra en telemetría
     (`degraded=true`) y el Verifier sigue aplicando: si una tarea `complex` no
     pasa el Verifier con `mini`, escala a humano en vez de gastar lo que no hay.
2. `infrastructure/cache/semantic_cache_qdrant.py` — **scoping v1.1**:
   - Clave = `(call_type, embedding(prompt), system_prompt_hash, top_k_lesson_ids,
     model_alias, llm_backend, embedder_id)`.
   - **Solo se cachean los `call_type` de `config.cache.semantic.cacheable_call_types`**
     (default: `[goal_extractor, planner]`).
   - **Verifier NUNCA cacheable**: su veredicto depende de la traza de ejecución
     concreta, que no está (ni debe estar) en la clave. Interviewer tampoco
     (interactivo). Lista cerrada validada al arranque: si config incluye
     `verifier` → arranque falla (fail-closed).
   - **Matching por call_type (v1.3.1)**: `planner` → **EXACT-MATCH** (hash del
     prompt normalizado). Un plan es un artefacto ejecutable: un near-miss
     semántico (0.97) puede pertenecer a una tarea distinta — el mismo fallo
     silencioso C→A que el retrieval blinda con abstención calibrada,
     reintroducido por otra puerta. `goal_extractor` → semántico
     (coseno ≥ `similarity_threshold`): ahí un near-miss es inocuo porque el
     goal resultante pasa igualmente por retrieval y umbrales.
   - `embedder_id` en la clave ⇒ cambiar de embedder invalida la parte semántica
     automáticamente (coherente con F6). Namespace por `model` y `temperature=0`.
   - **Diferido-con-datos (v1.3.1)**: a escala de equipo el hit-rate puede no
     justificar el cache; `cache_hit_ratio_by_call_type` del dashboard decide
     si se mantiene tras el primer mes (misma lógica que el reranker).
3. **Contexto mínimo**: solo top-K lecciones (K=1-3). Historial se resume.
4. **Summarizer** cada N turnos (`ConversationCompactor`).
5. **Token budget** por sesión (`domain/policies.py`), `CostLedger` por turno;
   corte + aviso cuando `usage ≥ warn_at_pct·budget`.
6. **Function calling estricto** con JSON Schema para todas las salidas
   estructuradas (Planner, Verifier, Interviewer, GoalExtractor).
7. Decorador `@cost_tracked` sobre llamadas LLM: registra `input_tokens`,
   `output_tokens`, `model`, `backend`, `call_type`, `cost_estimate`, `cached`.
   Con backend local el coste €=0 pero los tokens se contabilizan igual
   (presupuesto y compactor aplican a ambos backends).

### Fase 5.5 — Compliance Repsol + Observabilidad + Dashboard *depende de F5*
Objetivo: artefacto **auditable, corporativo y operable en tiempo real**.

**Compliance (P0; los checks Azure-only se marcan N/A con backend local):**
1. `infrastructure/llm/azure_openai.py` — **Managed Identity** en `production`;
   API key sólo en `mode: dev`. `/health` reporta `auth_mode` y `llm_backend`.
2. `config/settings.py` valida que `llm.endpoint` está en dominios EU si
   `llm.backend=azure_openai`; arranque falla si no. Con `local`: check N/A.
3. Redacción PII: la ejecuta el rule-set `pii` del pipeline único
   `security/redaction.py` (v1.3.1) **antes** de cada llamada LLM,
   **ambos backends**. Falla-CLOSED si no arranca.
4. `llm.content_filter.required: true` — health-check con prompt canario que debe
   rechazar (solo backend azure; con local se registra N/A y el riesgo queda
   documentado en README).
5. `llm.content_logging_optout: true` — checklist manual en README (azure).
6. **MCP shell server propio** (repo separado): allowlist explícita de comandos,
   guardrails idénticos, tests independientes.

**Audit log + prompt log de debugging (v1.1) + rotación + archivado (P0):**
7. `observability/audit_log.py` — JSON-line a `logs/audit-YYYY-MM-DD.jsonl`.
   Campos: `ts, correlation_id, session_id, user, event_type, tool, args_hash,
   tokens_in, tokens_out, model, backend, verdict, duration_ms,
   cost_estimate_eur, escalated`. **Sin contenido de prompts** (SOX/PII).
8. `observability/prompt_log.py` (NUEVO v1.1) — log SEPARADO
   `logs/prompts-YYYY-MM-DD.jsonl` con `correlation_id, call_type, prompt_redacted,
   completion_redacted, model, backend`. Escribe SIEMPRE post-PII-redactor.
   Retención corta (`observability.prompt_log.max_age_days`, default 7), purga
   local sin archivado, desactivable. Une debugging con audit vía `correlation_id`.
9. Middleware FastAPI + hook en `Executor` emiten al audit log cada:
   request, tool_call, llm_call, verdict, escalation, error.
10. `scripts/rotate_audit_logs.py`: ficheros > 48h → archiva a Azure Blob
    (immutable, 7 años SOX) y borra local. **Fail-CLOSED**: si el archivado
    falla, NO borra (exit 2). El prompt-log NO se archiva: se purga a los N días.
11. `infrastructure/archival/azure_blob.py` — Managed Identity, retention immutable.

**Dashboard in-app tiempo real (P0):**
12. `dashboard/app.py` — FastAPI en `/dashboard`, HTMX + Tailwind + Chart.js.
13. `WS /dashboard/stream` — eventos del ring-buffer (últimos 15 min).
14. Pestañas: **Overview** (tokens/min, coste €/día, retries, Verifier ok-rate,
    tareas activas, **último eval report + delta** — v1.1, **banner de alertas
    activas** — v1.3), **Alertas** (v1.3: historial completo con estado
    `active|acknowledged|resolved`, regla que disparó, valor observado vs
    umbral, timestamp; botón *acknowledge*; las alertas nuevas llegan por el
    WebSocket y se reflejan en <1s con badge en la pestaña), **Lecciones**
    (total, pending_review, top/bottom por reuse, aprobar/rechazar),
    **Escalations**, **Cost** (cache hit ratio por call_type — v1.1, mini vs
    full, tasa de degradación por presupuesto, presupuesto restante),
    **Calidad** (v1.3: TODAS las series continuas del punto 18 — distribución
    de scores de retrieval por semana, tasas path A/B/C en el tiempo, verifier
    ok-rate por lección, disagreement rules-vs-judge, goals sin cobertura, y
    latencias p50/p95 por alias del `--perf`), **Guardrails** (vetos por regla,
    últimas 50 denegaciones, health por guard), **Compliance** (región,
    auth_mode, backend LLM activo, content_filter, redactor, archivado, próxima
    purga; checks N/A visibles con backend local).
    **Regla de cobertura (v1.3): toda métrica capturada por la capa de
    observabilidad (puntos 16-19 y `dashboard.metrics`) debe ser visible en
    alguna pestaña — no existen métricas "solo en fichero"; el test de F5.5
    lo verifica por enumeración.**
15. `infrastructure/metrics/in_memory.py` — contadores rodantes por evento.

**Capa de observabilidad LLM (NUEVO v1.3, basada en Cap. 11 del handbook):**
16. `observability/llm_tracing.py` — **traza jerárquica por tarea**: un árbol de
    spans `task → goal_extraction → retrieve → plan → step_1..n → verify → learn`,
    cada span con atributos: `call_type, model, backend, tokens_in/out, latency,
    cache_hit, degraded, scores` (en retrieve: top-k scores y lección elegida).
    Correlacionado por `correlation_id` con audit y prompt log. Persistencia
    local JSON + export OTel/OTLP opt-in (`llm_traces.export_otlp`). Es la vista
    "¿dónde se gastó el tiempo/tokens y qué decidió cada paso?" de una tarea.
17. **Prompt registry versionado** — los system prompts (Planner, Verifier,
    GoalExtractor, Interviewer, judge) viven en `prompts/` como ficheros
    versionados en git con `prompt_version` (hash corto). La versión viaja en
    telemetría, trazas y clave de cache. Cambiar un prompt = commit + evals,
    igual que un umbral. Sin esto, "funcionaba ayer" es indiagnosticable.
18. **Métricas de calidad continuas en producción** (ring buffer + serie diaria
    persistida): distribución semanal de scores de retrieval (shift = señal de
    drift), tasas path A/B/C en el tiempo (subida de C = faltan lecciones;
    subida de A con verifier ok-rate bajando = umbral degradado), verifier
    ok-rate por lección, disagreement rules-vs-judge en acceptance híbrido,
    goals entrantes sin cobertura en el golden set (drift de queries → señal
    para añadir casos/lecciones).
19. **Alerting por umbrales** (`observability.alerts` en config): reglas simples
    evaluadas sobre la serie diaria — `verifier_ok_rate < X`, `c_rate_spike`,
    `budget_burn_rate`, `guardrail_veto_spike`, `escalations_open > N`.
    **Doble canal (v1.3)**: (a) webhook/email vía `escalations.notify` (para
    cuando nadie mira la web) y (b) **entidad `Alert` persistida**
    (`logs/alerts.jsonl`: regla, valor observado, umbral, ts, estado
    `active|acknowledged|resolved`) que se publica por el WebSocket del
    dashboard y alimenta la pestaña Alertas y el banner de Overview. El
    acknowledge desde la web cambia el estado; una regla cuyo valor vuelve a
    rango pasa a `resolved` automáticamente. Sin stack de alerting externo:
    a escala de equipo, webhook + pestaña bastan.
20. **Ámbito de despliegue (decisión v1.3)**: el sistema sirve a un equipo
    pequeño. NO hay canary, shadow mode ni cohortes de usuarios. El procedimiento
    de cambio de comportamiento (umbral, prompt, lección, modelo) es:
    evals en verde → commit → aviso en el canal del equipo → ventana de
    observación en dashboard (las métricas del punto 18 son el "canary humano").
    Si el ámbito crece a decenas de usuarios, se revisará esta decisión.


### Fase 6 — Migración de backends (REESCRITA en v1.1) *depende de F5.5*
Objetivo: conmutar vector store y embedder de forma segura. La clave: **cambiar
de vector store es un flag; cambiar de embedder es una migración de datos.**

**6.1 Vector store (qdrant ↔ azure_ai_search) — sí es solo un adapter:**
1. `azure_ai_search.py` implementa `VectorStorePort` (search con filtro
   `pending_review`, upsert, colecciones/índices versionados).
2. `vector_store.backend` conmuta el adapter en el composition root.
3. Requiere re-ingesta al nuevo backend (mismo embedder ⇒ mismos vectores;
   `scripts/migrate_embeddings.py --target-store` los copia o re-embebe).

**6.2 Embedder (bge-m3 ↔ text-embedding-3-large) — migración de datos:**
Las dims difieren (1024 vs 3072): **todos los vectores existentes quedan
inválidos**. El seam del puerto cubre el código; los datos exigen:
1. **Colecciones versionadas**: el nombre incluye versión
   (`lessons_v{n}`); cada colección queda ligada a un `embedder_id`
   (modelo + dims) guardado en su metadata y en el payload de cada punto.
2. **Validación al arranque (fail-closed)**: el composition root compara dims
   del embedder activo vs. metadata de la colección configurada; mismatch →
   arranque falla con mensaje claro. Esto elimina la clase entera de errores
   de "config a medias".
3. **`scripts/migrate_embeddings.py`**: fuente de verdad = los `.md` en
   `lessons/` (la re-ingesta es lossless y barata). Flujo:
   a) crea `lessons_v{n+1}` con el embedder destino,
   b) re-embebe e ingesta todas las lecciones (respetando trust gate y contadores),
   c) **corre la eval suite (F1.5) contra la colección candidata**,
   d) compara vs. baseline: si `hit@k` o routing accuracy caen más de
      `evaluation.migration_tolerance` → aborta y reporta,
   e) si pasa: imprime el bloque de config a cambiar (colección + backend).
      **El cutover es un cambio de config + restart, humano y atómico.**
   f) la colección anterior se conserva hasta validar en operación (rollback = 
      revertir config).
4. **Cache semántico**: `embedder_id` está en la clave (F5) ⇒ el cambio de
   embedder lo invalida solo; no hay estado que migrar.
5. **Umbrales**: los scores de similitud NO son comparables entre embedders.
   La migración obliga a recalibrar `score_threshold_*` con `run_evals.py --sweep`
   contra la colección nueva. El script lo recuerda en su salida.

**6.3 LLM backend (azure_openai ↔ local) — flag + health-check + contrato de serving:**
Sin estado persistente que migrar. `llm.backend` conmuta; el health-check de
tool-calling (canario) valida el modelo local antes de servir. El cache
distingue backend en la clave (respuestas no se cruzan).

**Contrato de serving del endpoint local (v1.1)** — la optimización de inferencia
vive en la capa de serving (vLLM/Ollama/LM Studio), fuera de este codebase, pero
el plan fija los requisitos mínimos que el endpoint debe cumplir:
- **Context window servida** ≥ `system prompt + top_k lecciones + tool schemas +
  historial compactado + margen` (estimación operativa: ≥ 16k tokens; validado
  por el health-check consultando `/v1/models` o config del servidor).
- **Cuantización**: recomendada Q5/AWQ o superior. Cuantizaciones agresivas
  (Q3/Q2) degradan el tool-calling estructurado — motivo adicional por el que el
  canario de function calling existe y es bloqueante.
- **Batching**: para multi-usuario, vLLM (continuous batching) sobre Ollama
  (concurrencia limitada). Con un solo usuario, cualquiera vale.
- **Smoke test de rendimiento**: `run_evals.py --perf` reporta latencia p50/p95
  y tok/s por alias contra el backend activo (informativo, no bloquea gates) —
  permite comparar backends con datos en el dashboard.

### Fase 7 (experimental) — Fine-tuning: criterios y pista de práctica (NUEVA en v1.3)
Objetivo doble: (a) fijar los **criterios objetivos** (LLM Handbook, Caps. 5-6)
que justificarían fine-tuning en producción, y (b) definir una **pista de
práctica** ejecutable durante las pruebas con ambos backends, para desarrollar
la competencia antes de necesitarla. El fine-tuning sigue EXCLUIDO de producción
en fase 1: esta fase es experimental y no bloquea ninguna otra.

**7.1 Criterios de decisión (cuándo pagaría FT en producción)** — se requieren
TODOS, verificados con datos de la eval suite, nunca por intuición:
1. **El gap es de comportamiento, no de conocimiento**: los fallos dominantes en
   la matriz de evals son de formato/estilo/adherencia a schema (Planner que
   rompe el JSON, judge inconsistente, verbosidad), no de retrieval. Si el fallo
   es de conocimiento → más/mejores lecciones, nunca FT.
2. **RAG + prompting han tocado techo**: ≥2 iteraciones de prompt (registry
   versionado, F5.5) sin mover la métrica objetivo.
3. **Datos suficientes y de calidad**: ≥300-500 ejemplos curados para SFT de
   estilo/formato con LoRA (≥1.000 ideal); pares preferido/rechazado ≥200 para
   DPO. Fuente: trazas exitosas verificadas + lecciones aprobadas.
4. **Distribución estable**: las tareas del dominio no cambian cada mes (si no,
   el modelo fine-tuneado caduca más rápido de lo que se entrena).
5. **Motivo económico o de latencia medible**: p. ej. un `mini` fine-tuneado
   sustituyendo a `full` en el Planner con paridad de evals = ahorro real.

**7.2 Pista local (práctica en Mac M5 32GB)**:
1. **Dataset**: `scripts/build_ft_dataset.py` genera pares instrucción→respuesta
   desde (a) trazas con `Verdict.ok` (input: goal + lecciones inyectadas;
   output: plan/respuesta del paso correspondiente) y (b) lecciones
   `human_authored`. **El trust gate aplica a los datos de entrenamiento**:
   lecciones `pending_review=true` y trazas no verificadas NUNCA entran al
   dataset (memory poisoning vía fine-tuning es el mismo ataque por otro canal).
   Todo el dataset pasa el PII redactor antes de persistirse. Formato: JSONL
   chat estándar, versionado con hash en `ft_datasets/`.
2. **Curación** (Cap. 5 del handbook): dedup semántico (embeddings + umbral),
   filtrado por reglas (longitud, schema válido), decontaminación contra el
   golden set (ningún caso de eval puede estar en el training set — si no, la
   eval post-FT miente).
3. **SFT**: QLoRA sobre Qwen3-8B (o el alias `mini` local) con Unsloth (Linux/
   NVIDIA) o MLX-LM (Apple Silicon). Hiperparámetros de partida documentados
   (r=16, alpha=32, lr=2e-4, 2-3 epochs) — punto de partida, no dogma.
4. **DPO (segunda pasada, opcional)**: pares donde preferido = salida aprobada
   por humano/verifier y rechazado = salida del modelo base ante el mismo input.
5. **Evaluación antes/después con la MISMA eval suite**: el modelo FT se sirve
   como alias nuevo (`mini_ft`) en `llm.local.models` y se corre
   `run_evals.py` + `verifier_cases` contra ambos alias. **Gate de adopción**:
   `mini_ft` debe superar a `mini` en la métrica objetivo SIN degradar el resto
   (misma lógica de paridad que las migraciones). El adapter LoRA se versiona
   junto al hash del dataset y la config de entrenamiento (reproducibilidad).

**7.3 Pista Azure OpenAI (práctica gestionada)**:
1. Fine-tuning gestionado de Azure OpenAI sobre el modelo del alias `mini`
   (verificar en el momento: disponibilidad del modelo y de la región EU del
   `region_allowlist` para training y hosting; si no hay región EU disponible,
   la pista Azure queda bloqueada por compliance y se practica solo en local).
2. Mismo dataset JSONL de 7.2 (formato chat compatible), mismos gates de
   curación y decontaminación.
3. El modelo resultante se despliega como deployment propio y se registra como
   alias `mini_ft` en `llm.azure_openai.deployments` → el Router puede A/B
   entre `mini` y `mini_ft` por config, y la eval suite compara.
4. Coste: el training y el hosting del deployment FT se contabilizan aparte
   (`fine_tuning.budget_eur`); el experimento tiene presupuesto propio y
   hard stop.

**7.4 Qué NO hacer**: fine-tunear conocimiento (eso es RAG), entrenar sobre
datos sin verificar o sin redactar, adoptar un modelo FT sin gate de evals,
o mantener el FT como dependencia de producción mientras esta fase sea
experimental. Si el experimento demuestra valor con los criterios de 7.1,
la promoción a producción será una revisión de este plan (v1.4+), no una
decisión implícita.

---

## Estructura de ficheros propuesta

```
ai_agent/
├── pyproject.toml
├── docker-compose.yml                 # qdrant
├── main.py                            # composition root (valida coherencia backends)
├── config.yaml                        # ← ÚNICA fuente de config (ver §Contrato)
├── config/
│   └── settings.py                    # Pydantic Settings: config.yaml + ${VAR}
├── domain/
│   ├── models.py
│   ├── ports.py
│   └── policies.py
├── application/
│   ├── agent_loop.py
│   ├── goal_extractor.py
│   ├── planner.py
│   ├── executor.py
│   ├── verifier.py
│   ├── interviewer.py
│   ├── lesson_writer.py
│   └── compactor.py
├── infrastructure/
│   ├── llm/{azure_openai.py, openai_compatible.py, router.py}
│   ├── embedder/{fastembed_bge_m3.py, azure_openai_embed.py}
│   ├── vector_store/{qdrant_local.py, azure_ai_search.py}
│   ├── mcp/{client.py, registry.py}
│   ├── lessons/fs_markdown_repo.py
│   ├── cache/semantic_cache_qdrant.py
│   ├── escalations/fs_repo.py
│   ├── task_state/fs_repo.py         # v1.1: checkpoints + recovery (Fase 4.6)
│   ├── archival/azure_blob.py
│   └── metrics/in_memory.py
├── security/
│   ├── guardrails.py                  # chain of responsibility, fail-CLOSED
│   ├── prompt_injection.py
│   ├── spotlighting.py
│   ├── url_guardrail.py
│   ├── destructive_guardrail.py
│   ├── rate_limit.py
│   ├── redaction.py                   # v1.3.1: pipeline único (rule-sets secrets + pii)
│   └── allowlist.py
├── observability/
│   ├── logging.py                     # JSON logs generales
│   ├── audit_log.py                   # audit SOX (sin contenido)
│   ├── prompt_log.py                  # v1.1: debugging, redactado, retención corta
│   ├── llm_tracing.py                 # v1.3: spans por tarea + export OTLP (único tracing, v1.3.1)
│   └── in_memory_ring.py
├── prompts/                           # v1.3: system prompts versionados (prompt registry)
├── ft_datasets/                       # v1.3: datasets JSONL de fine-tuning (hash-versionados)
├── evals/                             # v1.1
│   ├── golden_set.yaml
│   ├── verifier_cases.yaml
│   └── reports/                       # gitignored salvo baseline
├── dashboard/
│   ├── app.py
│   ├── ws.py
│   ├── templates/
│   └── static/
├── interface/
│   ├── http/{app.py, routes.py, deps.py, middleware.py}
│   └── cli/main.py
├── scripts/
│   ├── ingest_lessons.py
│   ├── run_evals.py                   # v1.1: métricas + gates + --sweep
│   ├── migrate_embeddings.py          # v1.1: re-embed + eval + cutover asistido
│   ├── build_ft_dataset.py            # v1.3: dataset FT desde trazas verificadas + lecciones
│   └── rotate_audit_logs.py
├── docs/
│   └── guia_instalacion.md            # v1.1: guía paso a paso para ingeniero de soporte
├── lessons/
│   └── example_task.md
├── logs/                              # audit-*.jsonl + prompts-*.jsonl (gitignored)
├── escalations/                       # cola persistente (JSON append-only)
├── task_state/                        # v1.1: checkpoints por tarea (gitignored)
└── tests/
    ├── domain/...
    ├── application/...
    ├── infrastructure/...             # incluye contract tests de LLMPort ×2
    ├── security/...
    ├── observability/...
    ├── evals/...                      # tests del runner
    └── dashboard/...
```

**Repos hermanos (fuera de este paquete):**
- `mcp_shell_server/` — MCP shell propio con allowlist de comandos (Repsol).
- `mcp_browser_server/` — ya existe (no se modifica).

---

## `config.yaml` (contrato — única fuente de configuración y panel de control)

Un solo fichero YAML controla todo. Pydantic Settings lo carga y valida al
arranque; env vars **solo** como overrides puntuales (`${VAR}`). Los valores
marcados `# ← F1.5` se calibran con la eval suite, nunca a ojo.

```yaml
runtime:
  host: 127.0.0.1
  port: 8080
  api_keys: ["${AGENT_API_KEY}"]      # header X-API-Key
  mode: dev                           # dev | production

llm:
  backend: azure_openai               # azure_openai | local  ← SWITCH v1.1
  azure_openai:
    endpoint: https://myaoai.openai.azure.com
    api_key: "${AZURE_OPENAI_API_KEY}"  # solo mode=dev; prod = Managed Identity
    api_version: "2024-10-21"
    deployments:                      # alias → deployment en Azure
      mini: gpt-4o-mini
      full: gpt-4o
      judge: gpt-4o-mini
  local:                              # endpoint OpenAI-compatible (Ollama/vLLM/LM Studio)
    base_url: http://localhost:11434/v1
    api_key: "${LOCAL_LLM_API_KEY}"   # opcional; muchos servidores locales no lo requieren
    models:                           # alias → modelo servido
      mini: qwen3:8b
      full: qwen3:35b-a3b
      judge: qwen3:8b
    verify_tool_calling_on_start: true  # canario de function calling; fail-closed
  default: mini
  router:
    escalate_on: [ambiguous_verdict, complex_lesson, retry_gte_2]
    to: full
  temperature: 0.0
  max_output_tokens: 2048
  content_filter:
    required: true                    # solo aplica a backend azure_openai
  content_logging_optout: true        # checklist manual Azure portal

embedder:
  backend: local                      # local | azure  ← SWITCH (cambiar = MIGRACIÓN F6.2)
  local:
    model: BAAI/bge-m3
    embedder_id: bge-m3-1024          # identidad ligada a colección y cache
    device: cpu
    max_tokens: 512
    query_prefix: ""
    passage_prefix: ""
    instruction: null
    batch_size: 32
  azure:
    endpoint: https://myaoai.openai.azure.com
    api_key: "${AZURE_OPENAI_API_KEY}"
    api_version: "2024-10-21"
    deployment: text-embedding-3-large
    embedder_id: te3-large-3072
    max_tokens: 8191
    batch_size: 16

vector_store:
  backend: qdrant                     # qdrant | azure_ai_search  ← SWITCH
  qdrant:
    url: http://localhost:6333
    api_key: null
    collection_lessons: lessons_v1    # versionada; ligada a un embedder_id (F6.2)
    collection_cache: cache_v1
    vector_size: 1024                 # validado vs embedder activo al arranque (fail-closed)
    distance: cosine
  azure_ai_search:
    endpoint: https://mysearch.search.windows.net
    api_key: "${AZURE_SEARCH_API_KEY}"
    index_lessons: lessons-v1
    index_cache: cache-v1

mcp_servers:
  - name: browser
    transport: stdio
    command: python
    args: ["c:/Users/r115906/git/MCP/mcp_browser_server.py"]
    env: {}
    tools_prefix: browser.

lessons:
  dir: ./lessons
  auto_reingest_on_write: true
  run_evals_after_ingest: warn        # v1.1: warn | block | off
  chunking:
    strategy: whole_file              # whole_file | headings | fixed
    fixed_tokens: 400

agent:
  max_retries: 3
  rag:
    top_k: 3
    score_threshold_high: 0.75        # path A (auto-execute)  ← F1.5 (--sweep)
    score_threshold_medium: 0.55      # path B (disambiguate)  ← F1.5 (--sweep)
    quality_rerank_enabled: true      # score × (reuse+1)/(reuse+failure_count+1)
  goal_inference:
    enabled: true
    model_alias: mini
    max_inference_tokens: 200
    confidence_threshold: 0.7         # ← F1.5 si se añaden casos de goal al golden set
  compactor:
    every_n_turns: 6
    summary_max_tokens: 300
  budget:
    tokens_per_session: 20000
    warn_at_pct: 80
    degrade_at_pct: 85                # v1.1: full prohibido a partir de aquí (router degrada a mini)
    hard_stop: true

task_state:                           # ← NUEVO v1.1 (Fase 4.6)
  storage_dir: ./task_state
  auto_resume: false                  # resume SIEMPRE humano por defecto
  max_age_days: 30
  checkpoint_fsync: true              # durabilidad del checkpoint (write-temp + rename + fsync)

fine_tuning:                          # ← NUEVO v1.3 (Fase 7, experimental)
  enabled: false                      # false en producción fase 1
  datasets_dir: ./ft_datasets         # JSONL versionados por hash; post-redactor SIEMPRE
  min_sft_examples: 300               # gate de datos (criterio 7.1.3)
  min_dpo_pairs: 200
  decontaminate_against: evals/golden_set.yaml   # ningún caso de eval en training
  local:
    base_model_alias: mini
    method: qlora                     # qlora | lora
    toolkit: mlx                      # mlx (Apple Silicon) | unsloth (CUDA)
    output_alias: mini_ft             # se registra en llm.local.models
  azure_openai:
    base_model_alias: mini
    output_alias: mini_ft             # se registra en llm.azure_openai.deployments
    require_eu_region: true           # si no hay región EU para FT → pista bloqueada
    budget_eur: 50                    # presupuesto propio del experimento; hard stop

evaluation:                           # ← NUEVO v1.1 (Fase 1.5)
  golden_set: evals/golden_set.yaml
  verifier_cases: evals/verifier_cases.yaml
  k: 3                                # para hit@k
  gates:                              # exit != 0 en CI si se incumplen
    min_hit_at_k: 0.90
    min_precision_at_1: 0.80
    min_routing_accuracy: 0.85
    max_c_to_a_errors: 0              # esperado C → predicho A: auto-ejecución indebida
    min_judge_accuracy: 0.85          # solo si verifier_cases existe
    min_goal_accuracy: 0.85           # v1.1: solo sobre casos con expected_goal
  sweep:                              # rangos para run_evals.py --sweep
    threshold_high: {min: 0.60, max: 0.90, step: 0.02}
    threshold_medium: {min: 0.40, max: 0.70, step: 0.02}
  migration_tolerance: 0.03           # caída máx. de métricas admisible en F6
  parity_tolerance: 0.02              # v1.2: gate de paridad cutover SE → sistema nuevo
  baseline_report: evals/reports/baseline-se.json   # v1.2: línea base del SE actual (versionado)
  targets: [local, se-mcp]            # v1.2: runtimes evaluables con el mismo golden set
  reports_dir: evals/reports

guardrails:
  tools:
    denied_global: ["browser.pw_logout", "browser.pw_close"]
    allowed_global: null
    require_lesson_allowlist: true
    disabled_patterns: []
    custom_rules_file: null
  url:
    check_reachable: true
    allow_domains: []
    probe:
      timeout: 5.0
      user_agent: "Mozilla/5.0 (agent url-guardrail)"
      fail_closed_on_ambiguous: true
  topics:
    denied_keywords: []
  prompt_injection:
    enabled: true
    strategy: heuristic_then_llm
    canary_token: "__CANARY_9F3A__"
    max_llm_classifier_tokens: 60
    signatures:
      instruction_override: true
      role_markers: true
      exfiltration: true
      disable_guardrails: true
      invisible_unicode: true
  spotlighting:
    enabled: true
    max_tool_output_bytes: 65536
  redaction:                          # rule-set "secrets" del pipeline único (v1.3.1)
    patterns: [jwt, api_key, email, password, aws_secret]
  rate_limit:
    per_ip: "60/minute"
    per_api_key: "300/minute"
  request:
    max_body_bytes: 1048576
    tool_timeout_seconds: 30
    task_timeout_seconds: 300
  fail_mode: closed

escalations:
  storage_dir: ./escalations
  auto_enqueue_on:
    - retries_exhausted
    - goal_confidence_below_threshold_batch
    - guardrail_blocked_no_alternative
  notify:
    webhook_url: null
    email_to: null

cache:
  semantic:
    enabled: true
    matching:                         # v1.3.1: estrategia por call_type
      planner: exact                  # hash de prompt normalizado; NUNCA fuzzy para planes
      goal_extractor: semantic
    similarity_threshold: 0.97        # solo aplica a matching semántico
    ttl_seconds: 3600
    cacheable_call_types: [goal_extractor, planner]   # v1.1: lista cerrada
    never_cacheable: [verifier, interviewer]          # validado al arranque; fail-closed
    key_includes: [call_type, prompt, system_prompt_hash,
                   top_k_lesson_ids, model_alias, llm_backend, embedder_id]

observability:
  log_level: INFO
  log_format: json
  metrics_enabled: true
  llm_traces:                         # v1.3: trazas jerárquicas por tarea (spans del loop)
    enabled: true
    dir: ./logs/traces
    export_otlp: false                # opt-in → Application Insights
  alerts:                             # v1.3: reglas sobre la serie diaria; canal = escalations.notify
    verifier_ok_rate_min: 0.80
    c_rate_spike_pct: 30              # subida relativa semanal de path C
    budget_burn_max_pct_per_hour: 25  # v1.3.1: consumo de presupuesto de sesión demasiado rápido
    escalations_open_max: 10
    guardrail_veto_spike_pct: 50
  audit_log:
    enabled: true                     # NUNCA desactivar en prod
    dir: ./logs
    rotate_by: day
    ring_buffer_minutes: 15
  prompt_log:                         # v1.1: debugging separado del audit SOX
    # v1.3.1: la redacción previa a escritura es INVARIANTE de código, no opción de config
    enabled: true
    dir: ./logs
    max_age_days: 7                   # purga local, sin archivado
  archive:
    enabled: true
    max_age_hours: 48
    backend: azure_blob               # azure_blob | none (dev)
    azure_blob:
      account_url: https://myrepsolstor.blob.core.windows.net
      container: audit-logs
      prefix: "digital-twin/{year}/{month}/{day}/"
      retention_days: 2555            # 7 años SOX
      immutability: true
      auth: managed_identity
    fail_mode: closed
  purge:
    enabled: true
    schedule_hint: "windows_task_scheduler_or_cron_daily_04:00"
    script: scripts/rotate_audit_logs.py

dashboard:
  enabled: true
  mount_path: /dashboard
  auth_required: true
  refresh_interval_seconds: 5
  websocket_enabled: true
  metrics:
    - tokens_per_minute
    - cost_eur_per_day
    - retries_avg
    - verifier_ok_rate
    - active_tasks
    - lesson_top_reuse
    - lesson_bottom_reuse
    - escalations_open
    - cache_hit_ratio_by_call_type    # v1.1
    - guardrail_veto_counts
    - compliance_status
    - eval_last_report                # v1.1
    - alerts_active                   # v1.3: banner Overview + pestaña Alertas (push por WS)
    - alerts_history                  # v1.3: historial con ack/resolve
    - retrieval_score_distribution    # v1.3: serie semanal (señal de drift)
    - path_rates_over_time            # v1.3: tasas A/B/C en el tiempo
    - verifier_ok_rate_by_lesson      # v1.3
    - judge_rules_disagreement        # v1.3
    - uncovered_goals                 # v1.3: goals sin caso en golden set
    - degradation_rate                # v1.3: % llamadas con degraded=true
    - latency_p50_p95_by_alias        # v1.3: --perf y producción
    - tasks_awaiting_resume           # v1.3

compliance:
  region_allowlist: ["westeurope", "swedencentral", "spaincentral"]
  auth_mode: managed_identity         # managed_identity | api_key(dev only)
  content_filter_required: true
  content_logging_optout_confirmed: true
  pii_redaction:                      # rule-set "pii" del MISMO pipeline security/redaction.py (v1.3.1)
    enabled: true                     # fail-CLOSED; aplica a AMBOS backends LLM
    patterns: [dni_es, iban, credit_card, corporate_email, jwt]
    library: presidio
  data_classification: internal
  mcp_shell:
    server_name: shell
    # v1.3.1: allowlist a nivel comando+subcomando. PROHIBIDO listar intérpretes
    # (python, sh, pwsh), gestores que ejecutan código arbitrario (pip) o docker
    # con montajes de host: vacían el catálogo destructivo. Los argumentos pasan
    # además el destructive_guardrail.
    allow_commands: ["winget install", "winget list", "az", "kubectl get",
                     "kubectl describe", "kubectl logs"]
    require_lesson_allowlist: true
```

**Reglas de resolución de config:**
- Un único punto de carga: `config/settings.py` parsea el YAML, resuelve `${VAR}`,
  valida tipos y expone un `Settings` inmutable.
- **Validaciones cruzadas al arranque (fail-closed, v1.1)**:
  `vector_size` == dims del embedder activo; colección ligada al `embedder_id`
  activo; `llm.backend=local` ⇒ canario de tool calling OK;
  `cacheable_call_types ∩ never_cacheable = ∅`.
- Ningún módulo lee `os.environ` directamente. Wiring solo en `main.py`.
- Cambios en `config.yaml` requieren restart (no hot-reload en fase 1).
- Un test unitario carga `config.example.yaml` para detectar regresiones de schema.

---

## Contrato de "lección" (frontmatter YAML + markdown)

```markdown
---
id: sn-ami-export-last-page
title: Exportar filas de la última página en ServiceNow AMI
version: 1.2.0
origin: human_authored                # human_authored | learned
pending_review: false                 # learned → true por defecto (trust gate)
reuse: 0                              # ++ cuando Verifier.ok tras aplicar esta lección
failure_count: 0                      # ++ cuando Verifier.!ok tras aplicar esta lección
goal: >-                              # ← si presente, prevalece sobre el inferido
  Obtener y capturar las filas visibles de la última página de un listado
  ServiceNow AMI (patrón *_list.do) para evidencia SOX.
tags: [servicenow, sox, export]
preconditions:
  - session_active: true
  - page_url_matches: '.*_list\.do.*'
tools_allowed:                        # ← guardrail profundo por lección
  - browser.pw_open
  - browser.pw_servicenow_pagination_info
  - browser.pw_servicenow_wait_ready
  - browser.pw_servicenow_visible_rows
  - browser.pw_screenshot
acceptance:
  type: hybrid                        # rule | llm_judge | hybrid
  rules:
    must_screenshot: true
    url_matches: '.*sysparm_first_row=\d+.*'
  llm_judge_prompt: |
    Evalúa si la traza demuestra que se capturaron ≥1 filas de la última página.
cost:
  max_tokens: 4000
  preferred_model: mini
---

## Pasos
1. Llamar `browser.pw_servicenow_pagination_info` para obtener `total`, `page_size`.
2. Calcular `first_row = (ceil(total/page_size) - 1) * page_size`.
3. `browser.pw_open` con `?sysparm_first_row={first_row}`.
4. `browser.pw_servicenow_wait_ready`.
5. `browser.pw_servicenow_visible_rows`.
6. `browser.pw_screenshot`.
```

**Reglas de ciclo de vida de la lección:**
- Nace `origin=learned, pending_review=true` cuando la produce `LessonWriter`.
- Nace `origin=human_authored, pending_review=false` cuando la crea un humano
  (fichero `.md` en `lessons/` o `POST /lessons` con `X-Approve`).
- Un `learned` sale de cuarentena vía `POST /escalations/{id}/resolve` con
  `promote_to_lesson=true` **o** vía dashboard `/review`.
- `reuse` / `failure_count` son sólo señal de calidad. **No hay decay temporal ni
  borrado automático.** La limpieza del RAG es manual.
- Retrieval filtra `pending_review==false` y rerankea por
  `score × (reuse+1)/(reuse+failure_count+1)`.
- Toda lección nueva/modificada relevante añade ≥1 caso al golden set (F1.5).

---

## Guía de instalación para ingeniero de soporte (NUEVO v1.1, entregable de F5.5)

`docs/guia_instalacion.md` — guía paso a paso **para el usuario final del Digital
Twin** (ingeniero de soporte L2/L3, sin conocimientos del stack interno). En
español, estilo checklist, sin jerga de arquitectura. El DSA debe incluir su
esqueleto; contenido obligatorio:

1. **Requisitos previos** (tabla): Windows 10/11 o Linux, Python 3.11+, Docker
   Desktop (para Qdrant), acceso a red corporativa, credenciales según backend
   (nada que teclear si Managed Identity; API key de dev si aplica).
2. **Instalación en 6 pasos numerados** (PowerShell y bash en bloques separados):
   clonar repo → `docker compose up -d` → crear venv + `pip install -e .` →
   copiar `config.example.yaml` a `config.yaml` y rellenar SOLO los campos
   marcados `# OBLIGATORIO` → `python -m ai_agent ingest` (carga lecciones
   iniciales) → arrancar servicio + abrir dashboard.
3. **Verificación de instalación**: qué debe mostrar `/health` (todo verde),
   cómo lanzar la tarea de prueba incluida (`lessons/example_task.md`) y qué
   aspecto tiene un `Verdict.ok`.
4. **Selección de backend**: dos recuadros "Opción A: Azure OpenAI (Repsol)" /
   "Opción B: LLM local (Ollama)" con los 2-3 campos de config que cambian en
   cada caso y cómo saber cuál usar.
5. **Operación diaria**: cómo lanzar una tarea (CLI y HTTP), cómo leer el
   dashboard (qué significa cada pestaña en una frase), qué hacer cuando una
   tarea escala a humano (claim → resolve → promote), cómo aprobar una lección
   aprendida, cómo reanudar una tarea `awaiting_resume`.
6. **Resolución de problemas** (tabla síntoma → causa probable → acción):
   `/health` 503, canario de tool calling falla, mismatch de dims
   embedder/colección, presupuesto agotado, tarea atascada.
7. **A quién acudir**: propietario de la plataforma y canal de soporte.

Regla de calidad: un ingeniero sin contexto debe completar la instalación en
< 30 minutos siguiendo solo la guía. Se valida en F5.5 con un walkthrough real.

---

## Verificación

**Automatizada (por fase):**
- **F0**: `pytest` verde con test de `/health`; Qdrant responde;
  `config.example.yaml` parsea y produce `Settings` tipado; validaciones
  cruzadas fallan con configs incoherentes sembradas (dims mismatch,
  `verifier` en cacheable_call_types, backend local sin base_url).
- **F1**: `LessonRepository` parsea frontmatter completo; `POST /lessons/search`
  con corpus de 10 lecciones devuelve top-K correcto; payload de cada punto
  incluye `embedder_id`; conmutar `embedder.backend` en config solo cambia el
  adapter, no la Application.
- **F1.5 (evals)**: el runner reproduce métricas deterministas en corpus fijo;
  sembrar una regresión (umbral 0.99) rompe los gates con exit ≠ 0; `--sweep`
  produce sugerencia sin tocar config; caso `esperado C → predicho A` sembrado
  dispara su gate específico; casos con `expected_goal` puntúan el GoalExtractor;
  **(v1.2)** `--target se-mcp` produce `baseline-se.json` con las mismas métricas
  y esquema que el target local; caso path C con lección señuelo de score 0.50 →
  NO se inyecta nada (test de abstención); simulación de cutover con métricas
  del candidato por debajo de `baseline − parity_tolerance` → gate de paridad
  bloquea con mensaje que nombra la métrica incumplida.
- **F2**: integración con MCP browser stub ejecutando path A completo →
  `Verdict.ok=true`; **contract tests de `LLMPort` pasan idénticos contra
  `azure_openai.py` y `openai_compatible.py`** (mock server); tool calling
  estricto verificado en ambos; canario de function calling del backend local
  falla → arranque en error.
- **F2.5 (GoalExtractor)**: prompt imperativo trivial → `source=explicit` sin
  LLM; prompt ambiguo con LLM mockeado `confidence=0.9` → `source=inferred`;
  `confidence < 0.7` → `NeedsUserInput`; lección con `goal:` sobrescribe y
  registra `goal_source=lesson`.
- **F3**: goal sin lección → ≥1 pregunta del Interviewer; tras `X-Approve` la
  lección aparece indexada; la reingesta dispara evals en modo warn.
- **F4 (guardrails 3 canales, fail-CLOSED)**:
  - Input: payload OWASP LLM01 → bloqueado; canary token en respuesta → aborta.
  - Tool-output: contenido con inyección pasa por `wrap_as_untrusted`; test
    verifica marcadores y que el texto plano NO llega al modelo.
  - Stored: lección `learned, pending_review=true` NO aparece en `search()` de
    NINGUNO de los dos backends de vector store; tras promote sí.
  - Tool fuera de `lesson.tools_allowed` → `ToolNotAllowed`; tool en
    `denied_global` → rechazo aunque la lección la permita; lección sin
    allowlist con `require_lesson_allowlist=true` → falla en ingest.
  - Rate-limit → 429; `max_body_bytes` respetado.
  - URL guardrail: DNS inexistente → deny; 404 → deny; dominio válido → allow;
    TLS/timeout ambiguo → deny (fail-closed).
  - `scan_for_injection` lanza excepción → 5xx genérico (nunca allow).
  - Destructive catalog: `rm -rf ~` → deny `rm_root_home`; con
    `disabled_patterns: [rm_root_home]` → pasa; `dd of=/dev/sda` → deny.
- **F4.5 (escalations)**: `max_retries=1` con lección que falla → 1 entrada
  `open` con trace; `resolve` con `promote_to_lesson=true` → draft
  `pending_review=true` visible en `/review`.
- **F4.6 (task state, v1.1)**:
  - Matar el proceso (SIGKILL) entre step 2 y 3 de una lección de 5 pasos →
    al arrancar, la tarea aparece `awaiting_resume`; `POST /tasks/{id}/resume`
    continúa desde el step 3 sin re-ejecutar 1-2 (verificado por contador de
    llamadas del MCP stub).
  - Checkpoint se escribe ANTES de la llamada LLM post-step (orden verificado).
  - `auto_resume=false` por defecto: ninguna tarea se reanuda sola.
  - Fichero de estado corrupto (última línea truncada) → recovery usa la última
    línea válida; nunca crashea el arranque.
  - Dos sesiones concurrentes no comparten budget ni cache namespace.
- **F5 (coste)**:
  - Router escala a `full` cuando `escalate_on` matchea.
  - **Degradación (v1.1)**: con `usage ≥ degrade_at_pct·budget`, una tarea
    `complex` recibe `mini` (no `full`) y se registra `degraded=true`; si el
    Verifier falla con `mini` en ese estado → escala a humano sin reintentar
    con `full`; al 100% → hard stop con aviso.
  - Cache: hit devuelve sin llamar al LLM SOLO para `call_type` cacheable;
    **(v1.3.1)** prompt de Planner 97% similar pero distinto → MISS
    (exact-match); mismo prompt normalizado byte a byte → HIT;
    llamada del Verifier con clave idéntica NUNCA sirve de cache (test
    explícito); config con `verifier` en `cacheable_call_types` → arranque falla.
  - Rerank de calidad: a igual score, `reuse=5/fail=0` antes que `reuse=0/fail=3`.
- **F5.5**: auth MI arranca sin API key; endpoint fuera de región → arranque
  falla; content filter canario en `/health` (N/A visible con backend local);
  PII redactada en el payload real capturado; redactor caído → 5xx; audit log
  con campos completos por tarea; prompt log redactado y purgado a `max_age_days`;
  rotación 48h archiva a Blob y NO borra si el archivado falla (exit 2);
  dashboard 401 sin key, WS < 1s, widget evals con delta;
  **walkthrough real de `docs/guia_instalacion.md` < 30 min por un ingeniero
  sin contexto** (checklist firmada).
- **F6**: conmutar `vector_store.backend` arranca con adapter stub sin tocar
  Application; **mismatch dims embedder/colección → arranque falla**;
  `migrate_embeddings.py` sobre corpus de prueba: crea `lessons_v2`, corre evals,
  aborta si métricas caen > `migration_tolerance`, imprime bloque de cutover;
  cambio de `embedder_id` invalida el cache (miss garantizado);
  `run_evals.py --perf` reporta p50/p95 y tok/s por alias.
- **F5.5-obs (v1.3)**: una tarea completa produce un árbol de spans con todos
  los pasos del loop y atributos completos; cambiar un system prompt cambia el
  `prompt_version` en telemetría y provoca cache miss; regla de alerta sembrada
  (`verifier_ok_rate_min: 0.99`) dispara notificación por el canal configurado
  **Y aparece en la pestaña Alertas por WebSocket en <1s con estado `active`;
  el acknowledge desde la web persiste en `alerts.jsonl`; cuando el valor
  vuelve a rango la alerta pasa a `resolved` sola. Test de cobertura total:
  enumeración programática de `dashboard.metrics` vs widgets renderizados —
  cualquier métrica sin widget rompe el test**; el report de evals muestra IC
  95% bootstrap y, con n < 50, solo los gates por conteo bloquean.
- **F7 (v1.3, experimental)**: `build_ft_dataset.py` excluye lecciones
  `pending_review=true` y trazas sin `Verdict.ok` (test con corpus sembrado);
  ningún ejemplo del dataset matchea casos del golden set (decontaminación);
  el dataset persiste solo post-redactor (payload capturado sin PII);
  alias `mini_ft` registrado se evalúa con la misma suite y el report compara
  ambos alias lado a lado; con `require_eu_region: true` y región no-EU
  simulada → pista Azure bloqueada con mensaje claro; presupuesto
  `budget_eur` agotado → hard stop del experimento.

**Manual:**
- Lección ServiceNow end-to-end desde CLI: screenshots + `Verdict.ok`.
- Batería de 5-10 prompt-injections OWASP LLM01 → bloqueo/neutralización.
- Tarea con `tokens_per_session: 100` → degradación y corte con aviso.
- Tarea con `max_retries: 1` que falla → traza + hint + escalación.
- Crash real (kill -9) en mitad de una lección con efectos → resume humano
  correcto sin duplicar efectos.

---

## Decisiones

- **Incluido**: agente RAG-first, verifier con reintentos, allowlist por lección,
  eval suite offline con gates (v1.1), persistencia de tareas con checkpoints y
  resume humano (v1.1), degradación de modelo por presupuesto (v1.1), API HTTP +
  CLI, rate limit + auth desde día 1, semantic cache con scoping por call_type
  (v1.1), router de modelos, dual backend LLM azure/local (v1.1), migration
  seams a Azure AI Search / Azure OpenAI Embeddings con migración de datos
  versionada (v1.1), guía de instalación para el usuario final (v1.1).
- **Excluido explícitamente (fase 1)**:
  - Fine-tuning **en producción** — pero con pista experimental y criterios de
    promoción definidos en Fase 7 (v1.3); la promoción exige revisión del plan.
  - Despliegue gradual multi-cohorte (canary/shadow): el ámbito es un equipo
    pequeño; el procedimiento es evals → aviso → observación en dashboard (v1.3).
  - UI web rica (CLI + endpoints + dashboard operativo bastan).
  - Autoscaling / despliegue Kubernetes (fase de migración cloud).
  - Multi-tenant real (API keys + session isolation bastan para equipo pequeño).
  - Reranker cross-encoder — **diferido, no descartado**: se decide con datos de
    la eval suite (F1.5); si `hit@k` es alto con dense-only sobre decenas de
    lecciones, no compensa. Las dos decisiones están acopladas.
  - Topologías multi-agente dinámicas / DAG paralelo (estilo Hive): renuncia
    consciente de expresividad a cambio de comprensibilidad, determinismo y
    auditabilidad. Si un caso futuro exige fan-out paralelo, será una extensión
    diseñada, no una propiedad emergente.
  - Optimización de inferencia en el codebase: vive en la capa de serving;
    este plan solo fija el contrato (F6.3).

---

## Further considerations (puntos a decidir para el DSA final)

1. **Ámbito del Verifier**: reglas deterministas vs LLM-judge. Recomendación:
   **híbrido** — reglas si la lección las declara, LLM-judge como fallback con
   alias `judge`. El judge se audita contra `verifier_cases.yaml` (F1.5).
2. **Aprobación de lecciones**: bloqueante (`X-Approve`) vs asíncrona.
   Recomendación: **bloqueante** hasta confianza operativa.
3. **Vector store del semantic cache**: misma instancia Qdrant, colección aparte
   (`cache_v1`). Decidido.
4. **Cliente MCP**: SDK oficial `mcp`. Decidido.
5. **Ubicación**: repo nuevo, separado del MCP browser server. Decidido.
6. **Formato de acceptance**: schema JSON (`must_contain`, `must_not_contain`,
   `must_screenshot`, `llm_judge_prompt` opcional). Decidido.
7. **`mem0` vs Qdrant directo**: evaluar en F1 tras PoC; si `qdrant_local.py`
   supera ~200 LOC no triviales, considerar `mem0.infer=false`.
8. **Deduplicación de efectos en resume (v1.1)**: el `step_execution_id` es
   best-effort; decidir en el DSA qué tools del MCP shell/browser propios
   implementan dedup real y cuáles exigen confirmación humana en el resume.
9. **Umbral de degradación (v1.1)**: `degrade_at_pct=85` es un valor inicial;
   revisar con datos reales de distribución de coste por tarea del dashboard.

---

## Contrato del README (estilo Support-Engineer, corporativo, sólo español)

**Requisitos:** mismo estilo visual que el README de Support-Engineer (tablas,
secciones cortas y densas, Mermaid para big picture y flujo de petición),
**sólo español**, tono corporativo Repsol (compliance visible, sin hipérbole).

**Estructura obligatoria:**
1. `# Digital Twin de Soporte — Agente IA con RAG y MCP` + tagline corporativo.
2. **Aviso de compliance** (blockquote): data residency EU, Managed Identity,
   content-logging opt-out, PII redaction, audit SOX 48h + 7 años.
3. `## ¿Qué es?` — 1 párrafo + tabla (RAG de lecciones, guardarraíles, dashboard).
4. `## Visión general` — Mermaid de capas (idéntico a este plan).
5. `## Cómo fluye una petición` — Mermaid sequenceDiagram
   Usuario→FastAPI→AgentLoop→LLM (azure|local)→MCP tools.
6. `## Lecciones` — qué es, ciclo learned→review→aprobada, contadores, ejemplo.
7. `## Guardarraíles` — 3 canales + tabla de guards + política fail-CLOSED.
8. `## Compliance Repsol` — tabla checklist con estado y verificación.
9. `## Fiabilidad` (v1.1) — checkpoints, crash recovery, resume humano,
   degradación por presupuesto: 1 párrafo + tabla.
10. `## Calidad y evals` (v1.1) — golden set, gates, cómo correr
    `run_evals.py`, política de calibración de umbrales.
11. `## Panel de control` — tabla de pestañas/widgets.
12. `## Estructura del proyecto` — árbol de ficheros.
13. `## Arranque rápido` — 6 pasos + **enlace a `docs/guia_instalacion.md`**
    para el paso a paso completo de usuario final.
14. `## Servidores MCP` — tabla browser/shell + `.mcp.json` de ejemplo.
15. `## Configuración` — tabla `sección.clave | env override | default | descripción`.
16. `## Comandos CLI` — `ingest`, `run`, `resume` (v1.1), `evals` (v1.1),
    `review`, `escalate`.
17. `## Seguridad — modelo de amenazas` — corta, enlaza a `SECURITY.md`.
18. `## Contribuir` — añadir lección (+ caso de golden set), tests, linters.
19. Footer licencia interna Repsol.

**Longitud objetivo**: 400-600 líneas. Legible en 5-8 min por un ingeniero L3.

---

## Comparativa con Support-Engineer (SE) — resumen

SE es un Digital Twin construido sobre **Claude Code como runtime**; el bucle
agentic es nativo del modelo y el repo aporta memoria de lecciones (Qdrant vía
MCP), hooks y dashboard. No es "mejor" ni "peor": optimiza restricciones
distintas. Nuestro requisito de runtime corporativo (Azure OpenAI / local)
impone construir la orquestación en Python.

**Adoptado de SE**: prompt-injection 3 canales, trust gate estructural,
contadores reuse/failure con rerank, URL probe, destructive catalog keyed,
escalación humana como flujo de primera clase, `${VAR}` en YAML, reglas custom
en JSON.

**Divergencias deliberadas**: fail-CLOSED en todos los guardrails (SE fail-open);
runtime Azure OpenAI/local (SE Claude Code); GoalExtractor en código (SE en
system prompt); lecciones estructuradas con frontmatter (SE title+content);
allowlist por lección (SE solo global); sin decay ni borrado automático.

**Adoptado de Hive (v1.1)**: checkpoints + crash recovery + resume,
degradación de modelo por presupuesto, session isolation.
**Rechazado de Hive**: generación dinámica de grafos y auto-evolución con
redeploy — incompatibles con SOX y con el requisito de flujo de control
comprensible y auditable (control-flow-as-code, no as-generated-data).
