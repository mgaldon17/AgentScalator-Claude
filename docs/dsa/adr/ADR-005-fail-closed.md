# ADR-005 — Política fail-CLOSED en todos los guardrails

**Estado**: Aceptada (plan §Refuerzos, F4). Divergencia deliberada respecto a SE (fail-open).

## Contexto

Un guardrail que falla en abierto es un guardrail que un atacante puede apagar
provocándole una excepción. SE optó por fail-open para no bloquear al
ingeniero; este sistema ejecuta tools reales con autonomía (path A), así que el
coste de un falso allow supera al de un falso deny.

## Decisión

Ante error interno o ambigüedad de **cualquier** guardrail: **denegar**. El
wrapper que lo garantiza es código común del `GuardrailPort` (ninguna regla
individual puede olvidarlo). Alcance: detector de inyección (excepción ⇒ 5xx),
redactor (no arranca ⇒ no hay llamadas LLM), URL probe (TLS/timeout ambiguo ⇒
deny), archivado SOX (falla ⇒ no borrar, exit 2), validaciones de arranque
(incoherencia ⇒ no arranca), `/health` (guard caído ⇒ 503).

## Consecuencias

- (+) La seguridad no depende de que nada se rompa.
- (−) Coste operativo explícito: cobertura de tests exhaustiva por gate y
  health-check propio, porque un guardrail caído para el servicio y debe ser
  visible al instante (pestaña Guardrails + alerta `guardrail_veto_spike`).
