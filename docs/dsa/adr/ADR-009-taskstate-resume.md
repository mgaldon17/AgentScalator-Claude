# ADR-009 — TaskState con checkpoints; resume exclusivamente humano

**Estado**: Aceptada (plan v1.1 #8, F4.6). Adoptado del análisis de Hive.

## Contexto

Sin checkpoints, un crash/restart/timeout en mitad de una lección larga pierde
la tarea — inaceptable para flujos de soporte con efectos (emails enviados,
comandos ejecutados) que no deben repetirse.

## Decisión

`TaskState` persistido en JSONL append-only (un fichero por tarea, una línea
por checkpoint; write-temp + rename + fsync; la última línea válida define el
estado, tolerando una línea final truncada). **Checkpoint tras cada step
ejecutado y ANTES de la llamada LLM posterior**: si el proceso muere durante
la llamada LLM, el step con efectos no se repite. Al arranque, las tareas
`running` huérfanas pasan a `awaiting_resume`. **El resume nunca es
automático** (`auto_resume: false`): un humano decide vía
`POST /tasks/{id}/resume`, porque el mundo puede haber cambiado desde el crash.
Dedup best-effort por `step_execution_id` en los MCP propios; los tools sin
soporte se re-ejecutan solo tras confirmación en el resume (§Further #8).

## Consecuencias

- (+) Ningún crash pierde trabajo ni duplica efectos; recovery auditable.
- (−) Latencia de reanudación depende de un humano; asumido por seguridad.
- TaskState es estado operativo, no evidencia SOX (el audit ya registra los
  eventos); retención 30 días con compactación de tareas `done`.
