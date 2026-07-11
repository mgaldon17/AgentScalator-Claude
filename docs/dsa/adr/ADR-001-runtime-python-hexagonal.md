# ADR-001 — Runtime propio en Python con arquitectura hexagonal

**Estado**: Aceptada (plan v1.3.1, §Contexto y §Arquitectura). No reabrible por el DSA.

## Contexto

El requisito corporativo impone ejecutar sobre Azure OpenAI o un LLM local
OpenAI-compatible — no sobre Claude Code (runtime del SE actual). El agente
necesita un bucle Retrieve → Plan → Execute → Verify con guardrails profundos,
auditabilidad SOX y backends conmutables.

## Decisión

Aplicación Python con **orquestación propia mínima** — sin LangChain, Semantic
Kernel ni MAF — organizada en 4 capas hexagonales (Domain, Application,
Infrastructure, Interface) más cross-cutting Security/Observability/Evaluation/
Config. Todos los recursos externos viven detrás de 7 **ports** (ABC); solo
`main.py` cablea adapters según `config.yaml`. La implementación vive en un
**repo nuevo** (`ai_agent`), separado de Support-Engineer y del MCP browser
server (§Further #5).

## Consecuencias

- (+) Control total del flujo: comprensible, determinista, auditable
  (control-flow-as-code, ver ADR-018); sin dependencias de frameworks con
  churn alto.
- (+) Conmutación de backends por config sin tocar Application (OCP/DIP).
- (−) Hay que construir a mano lo que un framework regala (retry, tracing,
  tool plumbing); el plan lo acota a lo mínimo y lo cubre con fases F0–F5.5.

## Alternativas rechazadas

LangChain/SK/MAF (opacidad del flujo, incompatible con el requisito de
auditabilidad); seguir sobre Claude Code (incumple el requisito de runtime
corporativo).
