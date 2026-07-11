# ADR-004 — Trust gate estructural para lecciones aprendidas

**Estado**: Aceptada (plan §Refuerzos tras análisis de SE, F4 canal 3).

## Contexto

El agente escribe lecciones nuevas al completar tareas (LessonWriter). Una
lección envenenada que entre al retrieval se auto-inyecta en tareas futuras:
memory poisoning persistente — el canal de ataque más rentable contra un
agente con memoria.

## Decisión

Toda lección `origin=learned` nace `pending_review=true` y **nunca** entra en
retrieval hasta aprobación humana (`/review` o resolve+promote de una
escalación). El filtro `pending_review==false` se aplica **dentro del query**
de ambos backends de vector store (no post-filter Python) y está cubierto por
contract test. El `.md` pasa `scan_for_injection` antes de indexar (hit ⇒
cuarentena forzada). El mismo gate aplica al dataset de fine-tuning (F7).

## Consecuencias

- (+) El poisoning queda estructuralmente aislado: la cuarentena no depende de
  detectar el ataque, solo de no haber aprobado la lección.
- (−) Fricción humana: cada lección aprendida exige revisión. Asumido — es la
  definición de confianza del sistema, y a escala de equipo el volumen es bajo.
