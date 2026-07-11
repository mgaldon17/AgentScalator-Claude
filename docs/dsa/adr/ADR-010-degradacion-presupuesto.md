# ADR-010 — Degradación de modelo por presupuesto antes del hard stop

**Estado**: Aceptada (plan v1.1 #9, F5.1). Palanca adoptada de Hive.

## Contexto

Un presupuesto duro que corta el servicio al 100% pasa de calidad plena a nada
sin estados intermedios. Agotar presupuesto debería degradar calidad de forma
controlada antes de cortar.

## Decisión

El Router aplica una escalera por sesión: normal (alias por política) → aviso
al usuario (`warn_at_pct: 80`) → **degradado** (`degrade_at_pct: 85`: `full`
prohibido, todo a `mini`, telemetría `degraded=true`) → hard stop al 100%.
El Verifier sigue aplicando en modo degradado: si una tarea `complex` no pasa
con `mini`, **escala a humano** en vez de gastar lo que no hay. El umbral 85 es
inicial; se revisa con la distribución real de coste por tarea del dashboard
(§Further #9).

## Consecuencias

- (+) Degradación de calidad observable y gradual; el corte deja de ser un
  acantilado.
- (+) Aplica a ambos backends (con local, €=0 pero los tokens cuentan igual).
- (−) Una franja de tareas complejas termina en escalación humana cerca del
  límite; es el comportamiento deseado, no un bug.
