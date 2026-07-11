# ADR-014 — Ámbito equipo pequeño: sin canary/shadow/cohortes

**Estado**: Aceptada (plan v1.3 #4, F5.5.20). Decisión del usuario.

## Contexto

El sistema sirve a un equipo pequeño, no a poblaciones de usuarios. La
infraestructura de despliegue gradual (canary, shadow mode, cohortes) sería
sobreingeniería sin consumidores.

## Decisión

El procedimiento de cambio de comportamiento (umbral, prompt, lección, modelo)
es: **evals en verde → commit → aviso en el canal del equipo → ventana de
observación en dashboard** (las métricas continuas de calidad son el «canary
humano»). Consecuencias en el diseño: sin Prometheus ni export externo salvo
OTLP opt-in (v1.3.1 #5); alerting = webhook/email + pestaña del dashboard, sin
stack externo; multi-tenant real excluido (API keys + session isolation
bastan).

## Consecuencias

- (+) Menos piezas que operar; el dashboard concentra toda la observación.
- (−) Si el ámbito crece a decenas de usuarios, esta decisión se revisa
  explícitamente (revisión del plan, no deriva silenciosa).
