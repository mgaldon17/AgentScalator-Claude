# 05 — Seguridad (guardrails profundos, 3 canales, fail-CLOSED)

Fuente: plan v1.3.1 F4, F5.5 (compliance), §guardrails/compliance del config.
Divergencia deliberada respecto a SE: **todo guardrail falla CERRADO** (ADR-005).

## 1. Modelo de amenazas (resumen operativo)

| Canal | Amenaza | Defensa primaria | Defensa secundaria |
|---|---|---|---|
| **Input** (prompt del usuario) | prompt-injection directa, exfiltración, abuso | `scan_for_injection` (firmas conservadoras) + `sanitize_for_context` | rate limit, auth, `max_body_bytes`, topic denylist, canary token |
| **Indirect** (output de tools) | página/fichero con instrucciones embebidas | `wrap_as_untrusted` (spotlighting) — paso insaltable del Executor | `scan_tool_output` con las mismas firmas, límite de bytes |
| **Stored** (memory poisoning) | lección aprendida maliciosa entra al retrieval | **trust gate estructural**: `learned ⇒ pending_review=true`, filtro en el propio query | `scan_for_injection` sobre el `.md` antes de indexar; aprobación humana |
| **Tool impact** | tool destructiva, URL alucinada, tool fuera de ámbito | allowlist efectiva por step + catálogo destructivo + URL probe | timeouts, `denied_global`, catálogo MCP cerrado |
| **Compliance** | PII/secretos hacia el LLM o los logs | pipeline único `security/redaction.py` (rule-sets `secrets`+`pii`), fail-closed | audit sin contenido; prompt log solo post-redactor |

## 2. Cadenas de guardrails (orden normativo)

### 2.1 IN (por request) — paso 2 del flujo canónico

```
rate_limit → auth (X-API-Key) → size (max_body_bytes) →
injection detector → redaction (secrets+pii) → budget check → topic denylist
```

Cualquier deny o excepción ⇒ 4xx/5xx con **motivo genérico hacia el cliente**
(el motivo real y la evidencia van al audit y al dashboard, nunca al LLM).

### 2.2 Por tool-call (dentro del Executor) — paso 7

```
allowlist efectiva → URL probe (si el tool declara url_argument) →
catálogo destructivo (+ custom_rules_file) → timeout
```

**Allowlist efectiva por step** (F4.11):
`lesson.tools_allowed ∩ (allowed_global | catálogo_MCP_completo) − denied_global`.
Reglas: tool fuera del catálogo MCP conocido → rechazo; lección sin
`tools_allowed` con `require_lesson_allowlist=true` → rechazo **en ingest** (no
en runtime); `denied_global` gana siempre, aunque la lección lo permita.

### 2.3 Sobre el output de cada tool — insaltable

```
scan_tool_output → sanitize_for_context (control/invisible/bidi, bound length)
→ wrap_as_untrusted (marcadores + directiva de no obedecer)
```

Test obligatorio (F4): el texto plano del tool **no** llega jamás al modelo.

### 2.4 OUT (por respuesta) — paso 10

```
PII scrub → detección de canary token (leak ⇒ abortar) → cost report → shaping
```

### 2.5 En ingest de lecciones

```
schema del frontmatter → require_lesson_allowlist → scan_for_injection del .md
(hit ⇒ pending_review=true forzado + warning) → embed → upsert
```

## 3. Matriz fail-closed (qué pasa cuando el propio guardrail falla)

| Componente | Fallo interno | Comportamiento |
|---|---|---|
| `scan_for_injection` | excepción | deny 5xx genérico (nunca allow) |
| `redaction.py` (cualquier rule-set) | no arranca / excepción | arranque falla · request 5xx; ninguna llamada LLM sin redactar |
| URL probe | TLS raro, timeout, DNS ambiguo | deny (`fail_closed_on_ambiguous: true`) |
| catálogo destructivo | regex corrupta / `custom_rules_file` inválido | arranque falla |
| archivado SOX | Blob inaccesible | NO borra local, exit 2 |
| cualquier guard en `/health` | canary falla | `/health` 503 — fail-closed extremo |
| validaciones de config | incoherencia | arranque falla con mensaje accionable |

Coste asumido de fail-closed (plan F4): cobertura de tests exhaustiva por gate
y health-check propio — un guardrail caído para el servicio, así que debe ser
observable al instante.

## 4. Detector de inyección (firmas conservadoras portadas de SE)

Firmas activables por config (`guardrails.prompt_injection.signatures`):
`instruction_override`, `role_markers`, `exfiltration` (imperativos de
exfiltración de secretos), `disable_guardrails`, `invisible_unicode`
(control/invisible/bidi), leak del `canary_token`. Estrategia
`heuristic_then_llm`: heurística primero; el clasificador LLM (≤
`max_llm_classifier_tokens`) solo si la heurística no decide. El canary token
se inserta en el system prompt; su aparición en una respuesta aborta la tarea.

## 5. Catálogo destructivo (keys estables)

| Key | Cubre |
|---|---|
| `rm_root_home` | `rm -rf /`, `rm -rf ~` y variantes |
| `mkfs` | formateo de dispositivos |
| `dd_to_device` | `dd of=/dev/…` |
| `fork_bomb` | `:(){ :|:& };:` y equivalentes |
| `force_push_main` | `git push --force` a main/master |
| `host_shutdown` | shutdown/reboot del host |
| `chmod_777_root` | permisos recursivos peligrosos en / |

Operación: `guardrails.tools.disabled_patterns: [key]` desactiva una regla sin
deploy; `custom_rules_file` añade reglas JSON propias. Cada veto registra la
`rule_key` + motivo humano en audit y en la pestaña Guardrails.

## 6. Trust gate estructural (canal stored)

1. `Lesson.origin ∈ {learned, human_authored}`; todo draft del LessonWriter
   nace `learned + pending_review=true`.
2. El filtro `pending_review == false` va **dentro del query** de ambos
   backends de vector store (nunca post-filter Python) — contract test lo
   verifica con una lección envenenada de score máximo.
3. Salida de cuarentena solo por decisión humana: `/review` (dashboard) o
   `POST /escalations/{id}/resolve` con `promote_to_lesson=true`.
4. El trust gate aplica también al **training set** de F7: lecciones
   `pending_review=true` y trazas sin `Verdict.ok` nunca entran al dataset
   (memory poisoning vía fine-tuning es el mismo ataque por otro canal).

## 7. Pipeline único de redacción (v1.3.1 #3)

`security/redaction.py`, dos rule-sets, **una** implementación y **un** punto
de fallo fail-closed:

| Rule-set | Patrones | Se aplica a |
|---|---|---|
| `secrets` | jwt, api_key, email, password, aws_secret | inputs, outputs y logs |
| `pii` | dni_es, iban, credit_card, corporate_email, jwt (presidio opcional) | **antes de cada llamada LLM**, ambos backends; prompt log |

La redacción previa a escritura del prompt log es **invariante de código**
(v1.3.1 #8): no existe clave de config para desactivarla.

## 8. URL guardrail (anti-alucinación)

`_http_probe(url)` con `guardrails.url.probe.timeout`: veta si scheme no es
http(s), host fuera de `allow_domains` (si la lista no está vacía), DNS falla,
o la respuesta es 404/410. Ambiguos (TLS, timeout) → deny. Se aplica a todo
tool que declare `url_argument` en su spec.

## 9. MCP shell propio (repo separado — Repsol)

- Allowlist **a nivel comando+subcomando** (v1.3.1 #1):
  `["winget install", "winget list", "az", "kubectl get", "kubectl describe", "kubectl logs"]`.
- **Prohibido** listar intérpretes (`python`, `sh`, `pwsh`), gestores que
  ejecutan código arbitrario (`pip`) o `docker` con montajes de host: vacían el
  catálogo destructivo y el fail-closed (ejecución arbitraria / escape al host).
- Los argumentos pasan **además** el catálogo destructivo del cliente.
- Guardrails idénticos al MCP browser; tests independientes en su repo.
- `require_lesson_allowlist: true` también para tools de shell.

## 10. Autenticación, rate limit y compliance

| Control | Diseño |
|---|---|
| Auth API | `X-API-Key` contra `runtime.api_keys` (env); dashboard con `auth_required: true` (401 sin key) |
| Rate limit | slowapi, bucket de tokens: `per_ip 60/min`, `per_api_key 300/min` → 429 |
| Auth LLM (azure) | Managed Identity en `mode: production`; API key **solo** `mode: dev`; `/health` reporta `auth_mode` |
| Data residency | arranque falla si el endpoint Azure no está en `region_allowlist` EU; con backend local el check se registra **N/A visible** en `/health` — nunca se oculta |
| Content filter (azure) | canario en `/health` que debe rechazar; con local → N/A documentado en README |
| Content-logging opt-out | checklist manual en portal Azure, documentado en README |
| Sesiones | `session_id` aísla budget, cache namespace y TaskState (dos sesiones concurrentes no comparten estado mutable) |

## 11. Verificación de seguridad (mapa a tests de F4)

Batería mínima que el repo debe mantener en verde: payloads OWASP LLM01
bloqueados; canary leak aborta; inyección en tool output nunca llega en claro
al modelo; lección quarantined invisible en ambos vector stores y visible tras
promote; `ToolNotAllowed` / `denied_global` / ingest sin allowlist; 429 y
`max_body_bytes`; URL probe (DNS, 404, ambiguo→deny); excepción del scanner →
5xx; catálogo destructivo con `disabled_patterns` respetado. Más la batería
manual de 5–10 inyecciones OWASP del plan §Verificación.
