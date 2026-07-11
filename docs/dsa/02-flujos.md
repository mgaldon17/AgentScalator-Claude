# 02 — Flujos (diagramas de secuencia)

Fuente: plan v1.3.1 §Agent Loop (flujo canónico), F2–F4.6, F5 (cache), F6.

Convenciones: `GIN`/`GOUT` = cadenas de guardrails de entrada/salida (doc 05);
todo participante emite telemetría correlacionada por `correlation_id` (doc 06);
las llamadas LLM pasan SIEMPRE antes por el rule-set `pii` del redactor.

## 1. Path A — lección con score alto (flujo canónico completo)

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario (API key)
    participant API as FastAPI /tasks
    participant GIN as Guardrails IN
    participant GE as GoalExtractor
    participant R as Retriever<br/>(Embedder+VectorStore)
    participant P as Planner
    participant E as Executor
    participant G as Guardrail por-tool
    participant M as MCP tool
    participant V as Verifier
    participant T as TaskState repo

    U->>API: POST /tasks {prompt, session_id}
    API->>GIN: rate_limit→auth→size→injection→redact→budget→topics
    alt cualquier guard falla o duda
        GIN-->>U: 4xx/5xx (fail-CLOSED, motivo genérico)
    end
    API->>GE: extract(prompt)
    GE-->>API: Goal{text, source, confidence ≥ τ_goal}
    API->>R: embed(goal) → top_k(N)
    Note over R: filtro EN el query: score>τ AND pending_review==false<br/>rerank score × (reuse+1)/(reuse+failure_count+1)
    R-->>API: hits (mejor score > τ_high ⇒ path A)
    API->>P: select_lesson(hits, goal) → Plan{steps, expected_tools, acceptance}
    Note over P: si la lección declara goal:, prevalece (goal_source=lesson)
    loop cada step del plan
        E->>G: validate_tool_call(step)
        Note over G: allowlist efectiva ∩, URL probe,<br/>catálogo destructivo — fail-CLOSED
        G-->>E: allow
        E->>M: call(tool, args, step_execution_id, timeout)
        M-->>E: result
        E->>T: checkpoint(step, args_hash, result_digest)
        Note over E,T: checkpoint ANTES de enviar el resultado al LLM:<br/>un crash durante la llamada LLM no repite el step (F4.6.3)
        E->>E: wrap_as_untrusted(sanitize_for_context(result))
    end
    E->>V: Verifier(plan, trace)
    V-->>API: Verdict{ok, evidence, reason}
    API->>GOUT: PII scrub → cost report → shaping
    API-->>U: Verdict + trace + cost
    Note over API: reuse++ en lecciones aplicadas si ok<br/>telemetría: tokens, backend, path, goal_source, cache_hit…
```

## 2. Goal ambiguo y path C — Interviewer + LessonWriter

```mermaid
sequenceDiagram
    autonumber
    actor U as Usuario
    participant API as FastAPI
    participant GE as GoalExtractor
    participant IV as Interviewer
    participant R as Retriever
    participant P as Planner
    participant E as Executor+Verifier
    participant LW as LessonWriter
    participant VS as VectorStore

    U->>API: POST /tasks {prompt ambiguo}
    API->>GE: extract(prompt)
    Note over GE: rama 1 heurística (regex, 0 tokens) → no aplica<br/>rama 2 LLM mini + schema JSON
    GE-->>API: NeedsUserInput(question)  [confidence < τ_goal]
    API->>IV: ask_goal(prompt)
    IV-->>U: pregunta única de clarificación
    U-->>IV: respuesta
    IV-->>API: Goal normalizado → retrieve
    API->>R: top_k(goal)
    R-->>API: sin candidatas sobre τ_medium ⇒ path C
    Note over R: ABSTENCIÓN CALIBRADA (v1.2): bajo τ_medium NO se inyecta<br/>NINGUNA lección — nunca “la menos mala”
    API->>IV: from_scratch(goal)
    IV-->>API: Plan provisional (batería mínima de preguntas, schema JSON)
    API->>E: ejecutar + verificar (igual que path A)
    E-->>API: Verdict.ok
    API->>LW: draft desde la traza exitosa
    LW->>VS: embed + upsert {origin: learned, pending_review: true}
    Note over LW,VS: TRUST GATE: indexada pero INVISIBLE al retrieval<br/>hasta aprobación humana (/review o resolve+promote)
    API-->>U: Verdict + aviso “lección propuesta pendiente de revisión”
```

Path B (candidatas de score medio) es idéntico salvo el primer salto:
`IV.disambiguate(hits)` en lugar de `from_scratch(goal)`.

## 3. Verificación fallida — reintentos y escalación humana

```mermaid
sequenceDiagram
    autonumber
    participant AL as AgentLoop
    participant P as Planner
    participant E as Executor
    participant V as Verifier
    participant HQ as EscalationQueue (fs_repo)
    participant D as Dashboard/notify

    AL->>E: ejecutar plan
    E->>V: verify(plan, trace)
    V-->>AL: Verdict{ok:false, reason}
    loop mientras retries < agent.max_retries
        AL->>P: re_plan(feedback=Verdict.reason)
        P-->>AL: plan corregido
        AL->>E: ejecutar → verificar
    end
    V-->>AL: Verdict{ok:false} con retries == max
    AL->>HQ: enqueue Escalation{task_id, goal, plan, trace, verdict, reason, status: open}
    Note over AL: failure_count++ en las lecciones aplicadas<br/>(señal de calidad; NUNCA borrado automático)
    HQ->>D: webhook/email (escalations.notify) + WS al dashboard
    Note over HQ: humano: claim → resolve (opcional promote_to_lesson=true<br/>⇒ draft pending_review=true en /review) | dismiss
```

Triggers automáticos de escalación (F4.5.3): `retries == max` con `!ok`;
`GoalExtractor.confidence < τ` en modo batch; guardrail bloquea sin alternativa.

## 4. Crash y resume humano (F4.6)

```mermaid
sequenceDiagram
    autonumber
    participant E as Executor
    participant T as task_state/fs_repo
    participant CR as Composition root (arranque)
    actor H as Humano
    participant API as FastAPI

    E->>T: checkpoint step 1 (línea JSONL, write-temp+rename+fsync)
    E->>T: checkpoint step 2
    Note over E: 💥 SIGKILL durante la llamada LLM post-step-2
    CR->>T: (arranque) escanear status=running huérfanos
    CR->>T: marcar awaiting_resume
    H->>API: GET /tasks?status=awaiting_resume
    H->>API: POST /tasks/{id}/resume
    Note over API: resume NUNCA automático (auto_resume:false):<br/>el mundo pudo cambiar; re-ejecutar efectos exige criterio
    API->>T: leer última línea VÁLIDA (tolera línea final truncada)
    API->>E: reconstruir contexto (plan + steps 1-2 como observaciones<br/>ya spotlighted) y continuar desde current_step_index=3
    Note over E: steps 1-2 NO se re-ejecutan; dedup best-effort<br/>por step_execution_id en MCP propios
```

## 5. Cache semántico — dos estrategias de matching (v1.3.1)

```mermaid
flowchart TB
    Q["Llamada LLM saliente"] --> CT{call_type}
    CT -->|"verifier / interviewer"| NO["SIN cache (lista cerrada,<br/>validada al arranque, fail-closed)"]
    CT -->|goal_extractor| SEM["clave semántica: embedding(prompt)<br/>hit si coseno ≥ 0.97"]
    CT -->|planner| EX["clave EXACTA: hash del prompt normalizado<br/>near-miss 0.97 = MISS"]
    SEM --> K
    EX --> K
    K["clave completa: call_type + prompt + system_prompt_hash +<br/>top_k_lesson_ids + model_alias + llm_backend + embedder_id (+ prompt_version)"]
    K -->|hit| HIT["devolver sin llamar al LLM<br/>telemetría cached=true"]
    K -->|miss| LLMC["llamar LLM → almacenar (ttl 3600s)"]
```

Racional (cambio v1.3.1 #2): un plan es un artefacto ejecutable; un near-miss
semántico puede pertenecer a otra tarea — el mismo fallo silencioso C→A que la
abstención calibrada blinda, reintroducido por otra puerta. En el
`goal_extractor` un near-miss es inocuo: el goal resultante pasa igualmente por
retrieval y umbrales. Todo el cache queda **diferido-con-datos**: la métrica
`cache_hit_ratio_by_call_type` decide si se mantiene tras el primer mes.

## 6. Migración de embedder (F6.2) — colecciones versionadas

```mermaid
flowchart TB
    A["scripts/migrate_embeddings.py"] --> B["crear lessons_v{n+1}<br/>con embedder destino (metadata: embedder_id)"]
    B --> C["re-embeber e ingerir TODOS los .md de lessons/<br/>(fuente de verdad; respeta trust gate y contadores)"]
    C --> D["correr eval suite (F1.5) contra la colección candidata"]
    D --> E{"¿hit@k y routing accuracy<br/>caen ≤ migration_tolerance?"}
    E -->|no pasa| F["ABORTA y reporta métricas incumplidas<br/>(la colección candidata queda para diagnóstico)"]
    E -->|pasa| G["imprime bloque de config del cutover<br/>+ recordatorio: recalibrar umbrales con --sweep<br/>(scores NO comparables entre embedders)"]
    G --> H["CUTOVER humano y atómico:<br/>cambio de config + restart"]
    H --> I["colección anterior se conserva<br/>rollback = revertir config"]
    H --> J["cache: invalidación automática<br/>(embedder_id está en la clave)"]
```

Conmutar **vector store** (F6.1) sí es solo un adapter + re-ingesta con el
mismo embedder. Conmutar **LLM backend** (F6.3) es un flag + canario de tool
calling bloqueante; el contrato de serving del endpoint local (contexto ≥16k,
cuantización ≥Q5/AWQ, batching) vive en la capa de serving, fuera del codebase.

## 7. Degradación por presupuesto (F5.1) — máquina de estados del Router

```mermaid
stateDiagram-v2
    [*] --> Normal
    Normal: alias por política (default mini;<br/>escalate_on → full)
    Normal --> Aviso: usage ≥ warn_at_pct (80%)
    Aviso: igual que Normal + aviso al usuario
    Aviso --> Degradado: usage ≥ degrade_at_pct (85%)
    Degradado: full PROHIBIDO — todo a mini<br/>telemetría degraded=true
    Degradado --> Parado: usage ≥ 100% y hard_stop
    Parado: corte de servicio de la sesión
    note right of Degradado
        El Verifier sigue aplicando: si una tarea
        complex no pasa con mini → escala a humano,
        no gasta lo que no hay.
    end note
```
