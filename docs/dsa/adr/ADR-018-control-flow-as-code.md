# ADR-018 — Rechazo de topologías multi-agente dinámicas (control-flow-as-code)

**Estado**: Aceptada (plan §Decisiones — excluido; §Comparativa con Hive).

## Contexto

Hive demuestra generación dinámica de grafos de agentes y auto-evolución con
redeploy. Es expresivo, pero el flujo de control se convierte en datos
generados en runtime: imposible de auditar ex-ante, incompatible con SOX y con
el requisito de comprensibilidad.

## Decisión

El agent loop es **fijo y explícito** (Retrieve → Plan → Execute → Verify, con
Interviewer/LessonWriter como ramas declaradas). Renuncia consciente de
expresividad a cambio de comprensibilidad, determinismo y auditabilidad:
**control-flow-as-code, no as-generated-data**. Sí se adoptan de Hive las
piezas compatibles: checkpoints + recovery (ADR-009), degradación por
presupuesto (ADR-010), session isolation.

## Consecuencias

- (+) Cada camino posible del agente existe en el código y tiene tests y
  diagramas (doc 02); el audit refleja un flujo conocido.
- (−) Un caso futuro que exija fan-out paralelo será una **extensión diseñada**
  (revisión del DSA), no una propiedad emergente.
