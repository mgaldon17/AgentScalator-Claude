# ADR-017 — Un solo tracing y un solo módulo de métricas; OTLP opt-in; sin Prometheus

**Estado**: Aceptada (plan v1.3.1 #4 y #5).

## Contexto

La superposición v1.0/v1.3 dejó duplicidades: `tracing.py` +
`llm_tracing.py`, y `observability/metrics.py` + `infrastructure/metrics/
in_memory.py`. Además, Prometheus era un seam huérfano: tras fijar el ámbito
de equipo (ADR-014), dos backends de export para cero consumidores.

## Decisión

- **Tracing único**: `observability/llm_tracing.py` subsume todo el tracing
  (spans jerárquicos por tarea + export OTLP opt-in vía
  `llm_traces.export_otlp`). `tracing.py` no existe.
- **Métricas únicas**: `infrastructure/metrics/in_memory.py` (ring buffer +
  serie diaria). `observability/metrics.py` no existe.
- **Sin Prometheus**: ni `prometheus_enabled` ni endpoint `/metrics`. Export
  externo = OTLP, opt-in, hacia Application Insights.

## Consecuencias

- (+) Un solo camino para cada dato; el test de cobertura del dashboard
  («toda métrica visible en alguna pestaña») es enumerable.
- (−) Si aparece un consumidor Prometheus real, será una extensión diseñada
  sobre OTLP, no una resurrección del seam.
