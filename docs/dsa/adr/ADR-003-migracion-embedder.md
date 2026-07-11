# ADR-003 — Cambiar de embedder es una migración de datos, no un flag

**Estado**: Aceptada (plan v1.1 #2, F6.2).

## Contexto

bge-m3 (1024d) y text-embedding-3-large (3072d) producen vectores
incompatibles: conmutar el embedder invalida **todos** los vectores existentes
y además hace incomparables los scores (los umbrales calibrados dejan de valer).

## Decisión

Colecciones **versionadas** (`lessons_v{n}`) ligadas a un `embedder_id`
(modelo+dims) en metadata y en el payload de cada punto. Migración vía
`scripts/migrate_embeddings.py`: crear colección nueva → re-ingerir desde los
`.md` (fuente de verdad lossless) → **eval suite contra la candidata** → abortar
si las métricas caen > `migration_tolerance` → cutover humano y atómico
(config + restart), conservando la colección anterior como rollback. Al
arranque, mismatch dims/`embedder_id` ⇒ el proceso no arranca (fail-closed).
Recalibrar umbrales con `--sweep` es obligatorio tras migrar.

## Consecuencias

- (+) Elimina la clase entera de errores «config a medias»; rollback trivial.
- (+) El cache se auto-invalida (`embedder_id` en la clave).
- (−) Migrar cuesta una re-ingesta + una pasada de evals; aceptable (corpus de
  decenas de lecciones).
