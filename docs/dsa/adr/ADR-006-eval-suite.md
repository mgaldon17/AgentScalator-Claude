# ADR-006 — Eval suite offline como control de seguridad

**Estado**: Aceptada (plan v1.1 #1, F1.5; reforzada v1.2 #3, v1.3 #3).

## Contexto

El score de retrieval decide **autonomía**: path A ejecuta tools reales sin
preguntar. Los umbrales `0.75/0.55` de v1.0 eran números sin método; un umbral
mal calibrado no da una respuesta mediocre — ejecuta la lección equivocada
(fallo silencioso C→A).

## Decisión

Eval suite offline (F1.5) con golden set versionado y agnóstico del runtime,
métricas de retrieval (hit@k, MRR, precision@1) y routing (matriz A/B/C),
gates de CI bloqueantes, modo `--sweep` que **sugiere** umbrales sin
escribirlos, y **abstención calibrada** como requisito con test propio (bajo
`score_threshold_medium` no se inyecta ninguna lección). Estadística honesta:
IC bootstrap, `max_c_to_a_errors: 0` por conteo, con n<50 solo gates por
conteo bloquean. La eval NO entra en el camino de una petición (plano offline;
el Verifier es el plano online).

## Consecuencias

- (+) Los umbrales son defendibles con datos; las regresiones (lección nueva,
  chunking, migración, prompt) se detectan antes del merge/cutover.
- (−) Mantener el golden set es trabajo continuo (≥1 caso por lección nueva,
  objetivo n≥100 en 3 meses). Es el precio de que «confiable» tenga definición
  operativa.
