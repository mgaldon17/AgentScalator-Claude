# ADR-008 — Cache con scoping por call_type; planner exact-match; verifier nunca cacheable

**Estado**: Aceptada (plan v1.1 #3; endurecida v1.3.1 #2). Cache entero **diferido-con-datos**.

## Contexto

Cachear llamadas LLM ahorra coste, pero cachear mal reintroduce el fallo
silencioso C→A: un plan cacheado por similitud 0.97 puede pertenecer a una
tarea distinta y ejecutarse igual. Y el veredicto del Verifier depende de la
traza concreta, que no está en la clave.

## Decisión

Solo `goal_extractor` y `planner` son cacheables (lista cerrada validada al
arranque; `verifier`/`interviewer` en la lista ⇒ el arranque falla).
Matching por `call_type`: `planner` → **EXACT-MATCH** (hash de prompt
normalizado; near-miss = MISS); `goal_extractor` → semántico (coseno ≥ 0.97),
inocuo porque el goal resultante pasa igualmente por retrieval y umbrales.
Clave completa: `call_type + prompt + system_prompt_hash + top_k_lesson_ids +
model_alias + llm_backend + embedder_id (+ prompt_version)`. Permanencia
decidida con datos: `cache_hit_ratio_by_call_type` tras el primer mes.

## Consecuencias

- (+) Coherente con la abstención calibrada: ninguna puerta trasera al C→A.
- (+) Invalidación automática al cambiar embedder, backend o prompt.
- (−) Menos hits en el planner (exact-match); asumido — un plan es un artefacto
  ejecutable, no una respuesta aproximable.
