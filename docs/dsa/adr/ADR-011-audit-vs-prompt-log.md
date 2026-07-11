# ADR-011 — Audit SOX sin contenido, separado del prompt log de debugging

**Estado**: Aceptada (plan v1.1 #6, F5.5.7–8).

## Contexto

Tensión irresoluble en un solo log: la cadena SOX exige evidencia inmutable de
7 años **sin contenido sensible** (`args_hash`), pero diagnosticar un plan malo
exige ver prompts y completions.

## Decisión

Dos logs con contratos opuestos, unidos por `correlation_id`:

| | Audit | Prompt log |
|---|---|---|
| Contenido | metadatos, `args_hash`, nunca prompts | prompts/completions **ya redactados** |
| Retención | 48h local → Azure Blob immutable 7 años | 7 días, purga local, sin archivado |
| Fallo de archivado | NO borrar, exit 2 (fail-closed) | n/a |
| Desactivable | NUNCA en prod | sí (el log; su redacción es invariante de código, v1.3.1 #8) |

## Consecuencias

- (+) Debugging sin contaminar la cadena SOX; la PII nunca toca disco en claro.
- (−) Dos escritores y una purga que mantener; el `correlation_id` es la
  costura obligatoria entre ambos y con las trazas.
