# ADR-007 — Baseline del SE actual y gate de paridad para el cutover

**Estado**: Aceptada (plan v1.2 #1 y #2, F1.5.3.5).

## Contexto

El Support-Engineer está en producción sin ninguna medición. Migrar a `ai_agent`
sin baseline sería un acto de fe; y el modo de fallo silencioso del SE
(auto-inyección de lección equivocada, C→A) es hoy invisible.

## Decisión

`run_evals.py --target se-mcp` ejecuta el MISMO golden set contra la memoria
del SE vía su servidor MCP, clasificando su decisión equivalente a A/B/C con
sus umbrales de auto-inyección actuales. Produce `baseline-se.json`,
**versionado en git** (excepción al gitignore de reports). El cutover exige
`métrica ≥ baseline − parity_tolerance (0.02)` en hit@k y routing accuracy, y
**C→A ≤ baseline sin tolerancia** (ideal 0). Sin paridad demostrada, no hay
migración.

## Consecuencias

- (+) Valor inmediato (2–4 tardes, 100% portable): detecta ya los fallos
  silenciosos del SE y calibra su umbral, sin esperar al sistema nuevo.
- (+) La migración se convierte en una decisión con datos.
- (−) Hay que mantener el runner con dos targets; el formato agnóstico del
  golden set (v1.2) lo hace barato.
