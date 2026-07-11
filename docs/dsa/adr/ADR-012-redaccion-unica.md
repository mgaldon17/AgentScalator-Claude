# ADR-012 — Pipeline único de redacción con rule-sets `secrets` + `pii`

**Estado**: Aceptada (plan v1.3.1 #3; sustituye al par redaction.py + pii_redactor.py).

## Contexto

v1.3 tenía dos módulos solapados (jwt aparecía en ambos): dos implementaciones,
dos puntos de fallo fail-closed y dos superficies de test para la misma
responsabilidad.

## Decisión

Un único `security/redaction.py` con dos rule-sets: `secrets` (jwt, api_key,
email, password, aws_secret — sobre inputs, outputs y logs) y `pii` (dni_es,
iban, credit_card, corporate_email; presidio opcional — **antes de cada llamada
LLM, ambos backends**). Un solo self-test en el arranque, un solo punto
fail-closed: si el redactor no arranca, no hay llamadas LLM.

## Consecuencias

- (+) Una responsabilidad, un módulo, un modo de fallo (SRP aplicado a la
  seguridad).
- (+) La redacción previa a escritura del prompt log es invariante de código,
  no clave de config (v1.3.1 #8).
- (−) Los dos rule-sets comparten release: un cambio en `pii` re-testea también
  `secrets`. Aceptable frente a la duplicidad anterior.
