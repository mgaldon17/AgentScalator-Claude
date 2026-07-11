# 07 — Evaluación offline (eval suite F1.5)

Fuente: plan v1.3.1 F1.5 completa (incl. 3.5 baseline, 3.6 abstención, 3.7
estadística), F6 (gates de migración), `evaluation:` del config.

## 1. Posición en la arquitectura (normativo, v1.2)

La eval suite **NO sustituye al Verifier ni añade pasos al agent loop**. Son
planos de control distintos:

| | Verifier | Eval suite |
|---|---|---|
| Plano | online, por tarea | offline, agregado |
| Pregunta | ¿esta ejecución cumple los criterios de la lección? | ¿el sistema recupera, decide y juzga bien? |
| Cuándo | en cada tarea de producción | CI, ingestas, migraciones, calibración |
| Analogía SOX | control operativo por transacción | auditoría periódica del control |

Puntos de contacto, siempre **de la eval hacia el loop**: (a) calibra los
umbrales que el loop usa; (b) audita al LLM-judge del Verifier contra
`verifier_cases.yaml`; (c) hace de gate en CI, ingestas y migraciones. Una
petición de producción jamás pasa por la eval suite.

**Por qué es control de seguridad**: el score de retrieval decide *autonomía*
(path A = auto-ejecutar tools reales). Un umbral mal calibrado no produce una
respuesta mediocre — ejecuta la lección equivocada.

## 2. Runner (`scripts/run_evals.py`)

Pipeline por caso: `embed(prompt)` → `search()` (con trust gate) → rerank de
calidad → decisión de path con los umbrales del config activo. Determinista:
`temperature=0` donde aplique; el retrieval es determinista.

| Modo | Qué hace |
|---|---|
| (default) | métricas + gates; exit ≠ 0 si algún gate falla |
| `--sweep` | barre `threshold_high` (0.60–0.90/0.02) y `threshold_medium` (0.40–0.70/0.02); reporta la pareja que maximiza routing accuracy **sujeta a C→A = 0**. **Solo sugiere; nunca escribe el config** — cambiar un umbral es decisión humana con commit |
| `--target se-mcp` | ejecuta el MISMO golden set contra la memoria del Support-Engineer vía su MCP (`search` + sus umbrales de auto-inyección) → `baseline-se.json` |
| `--perf` | latencia p50/p95 y tok/s por alias contra el backend activo; informativo, no bloquea gates |

Salida: `evals/reports/eval-YYYY-MM-DD-HHMM.json` (esquema en doc 04 §10) +
resumen markdown. El widget «Evals» del dashboard muestra el último report y su
delta.

## 3. Métricas

**Retrieval**: hit@k (k=`evaluation.k`=3), MRR, precision@1.
**Routing**: accuracy global + matriz de confusión A/B/C; la celda crítica es
`esperado C → predicho A` (auto-ejecución indebida) con gate propio por conteo.
**Goal accuracy** (casos con `expected_goal`): match exacto normalizado o
semántico judge-based. **Judge accuracy**: sobre `verifier_cases.yaml`.

## 4. Gates (config `evaluation.gates`)

| Gate | Valor | Tipo |
|---|---|---|
| `min_hit_at_k` | 0.90 | proporcional |
| `min_precision_at_1` | 0.80 | proporcional |
| `min_routing_accuracy` | 0.85 | proporcional |
| `max_c_to_a_errors` | **0** | **conteo absoluto** — robusto a cualquier n |
| `min_judge_accuracy` | 0.85 | proporcional (solo si hay verifier_cases) |
| `min_goal_accuracy` | 0.85 | proporcional (solo casos con expected_goal) |

Integración: CI en cada PR (bloquea merge); post-ingest y post-aprobación de
lección en modo `warn` (loguea deltas); migraciones F6 (contra la colección
candidata, ANTES del cutover).

## 5. Metodología estadística (v1.3 — gates honestos con el tamaño muestral)

1. **IC 95% bootstrap** (1.000 remuestreos) para cada métrica proporcional; el
   report los muestra siempre. El gate compara contra el límite inferior del IC
   solo cuando `use_ci_lower_bound=true` (recomendado al crecer el set). Con
   n=30, accuracy 0.85 lleva ±~0.10 de ruido — el report no lo esconde.
2. **Eventos críticos por conteo**: `max_c_to_a_errors: 0` en vez de proporción.
3. **n pequeño**: si n < `min_cases_for_proportional_gates` (50), el report
   avisa y **solo los gates por conteo son bloqueantes**.
4. **Sesgos del LLM-judge y mitigación**: posición (aleatorizar orden al
   comparar alternativas), verbosidad (rúbrica que puntúa evidencia, no
   longitud), auto-preferencia (el alias `judge` puede ser modelo distinto al
   generador). La rúbrica del judge es un prompt del registry versionado.
5. **Crecimiento del golden set**: objetivo n≥100 en 3 meses; cada escalación
   resuelta y cada lección nueva aportan ≥1 caso.

## 6. Abstención calibrada (requisito v1.2, con test propio)

Bajo `score_threshold_medium` el sistema no inyecta **ninguna** lección (path C
limpio: Interviewer o escalación, nunca «la menos mala»). El umbral se calibra
con `--sweep`. Test canónico: caso path C sembrado con una lección señuelo de
score 0.50 → no se inyecta nada.

## 7. Baseline del SE y gate de paridad (v1.2)

- `baseline-se.json` es la **línea base oficial** del sistema en producción:
  versionado en git (excepción al gitignore de reports), mismo esquema que el
  target local.
- Valor inmediato: detecta HOY los fallos silenciosos del SE (celda C→A) y
  calibra su umbral de auto-inyección — sin esperar al sistema nuevo.
- **Gate de paridad del cutover**: el sistema nuevo debe cumplir
  `métrica ≥ baseline_se − parity_tolerance (0.02)` en hit@k y routing
  accuracy; **C→A sin tolerancia** (≤ baseline, ideal 0). Sin paridad
  demostrada, no hay migración.

## 8. Umbrales calibrables (marcados `# ← F1.5` en config)

| Clave | Default inicial | Calibración |
|---|---|---|
| `agent.rag.score_threshold_high` | 0.75 | `--sweep` (routing accuracy s.a. C→A=0) |
| `agent.rag.score_threshold_medium` | 0.55 | `--sweep` (abstención) |
| `agent.goal_inference.confidence_threshold` | 0.70 | casos con `expected_goal` |

Regla: tras **cualquier** migración de embedder los scores no son comparables →
recalibración obligatoria con `--sweep` contra la colección nueva (el script de
migración lo recuerda en su salida).

## 9. Tests de la propia suite (meta-verificación, plan §Verificación F1.5)

- Métricas deterministas sobre corpus fijo.
- Regresión sembrada (umbral a 0.99) rompe gates con exit ≠ 0.
- `--sweep` produce sugerencia sin tocar el config.
- Caso `C→A` sembrado dispara su gate específico.
- `--target se-mcp` produce `baseline-se.json` con el mismo esquema.
- Señuelo 0.50 en caso C → no se inyecta (abstención).
- Simulación de cutover con candidato bajo `baseline − parity_tolerance` →
  gate de paridad bloquea nombrando la métrica incumplida.
