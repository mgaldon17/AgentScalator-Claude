# ADR-015 — Prompt registry versionado en git

**Estado**: Aceptada (plan v1.3 #2, F5.5.17).

## Contexto

Los system prompts (Planner, Verifier, GoalExtractor, Interviewer, judge)
cambian el comportamiento tanto como un umbral. Sin versionado, «funcionaba
ayer» es indiagnosticable y un cambio de prompt puede servir respuestas
cacheadas de otro prompt.

## Decisión

Los system prompts viven en `prompts/` como ficheros versionados en git.
`prompt_version` = hash corto del contenido; viaja en telemetría, spans y
**clave de cache** (cambiar un prompt ⇒ cache miss garantizado). Cambiar un
prompt = commit + evals en verde, igual que un umbral. La rúbrica del
LLM-judge forma parte del registry (mitigación de sesgos auditada contra
`verifier_cases.yaml`).

## Consecuencias

- (+) Todo comportamiento es diffeable y correlacionable con métricas.
- (−) Sin ediciones «rápidas» de prompts en caliente; deliberado.
