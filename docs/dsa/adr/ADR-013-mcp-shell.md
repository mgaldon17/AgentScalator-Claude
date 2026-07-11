# ADR-013 — MCP shell propio con allowlist comando+subcomando

**Estado**: Aceptada (plan §Compliance; endurecida v1.3.1 #1). Repo separado.

## Contexto

Desktop Commander da shell general: incompatible con el modelo de seguridad
(la capacidad se compone de tools explícitos con allowlist). Además, la
allowlist de v1.3 incluía `python`, `pip` y `docker`: `python -c`,
`pip install` (setup.py) y `docker -v /:/mnt` son ejecución arbitraria o escape
al host — vaciaban de contenido el catálogo destructivo y el fail-closed.

## Decisión

MCP shell server **propio** (repo separado, tests independientes) con allowlist
**a nivel comando+subcomando**: `winget install`, `winget list`, `az`,
`kubectl get|describe|logs`. **Prohibido** listar intérpretes (`python`, `sh`,
`pwsh`), gestores que ejecutan código arbitrario (`pip`) o `docker` con
montajes de host. Los argumentos pasan además el catálogo destructivo del
cliente. Guardrails idénticos al MCP browser; `require_lesson_allowlist` aplica
también a tools de shell.

## Consecuencias

- (+) El catálogo destructivo vuelve a significar algo: no hay puerta lateral
  de ejecución arbitraria.
- (−) Añadir una capacidad de shell nueva exige ampliar la allowlist con
  revisión (y idealmente un caso de golden set). Es fricción deliberada.
