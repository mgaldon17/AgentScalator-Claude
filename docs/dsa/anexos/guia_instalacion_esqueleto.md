# Esqueleto de `docs/guia_instalacion.md` (entregable de F5.5)

> Guía paso a paso para el **usuario final del Digital Twin** (ingeniero de
> soporte L2/L3, sin conocimientos del stack interno). Español, estilo
> checklist, sin jerga de arquitectura. **Regla de calidad**: un ingeniero sin
> contexto completa la instalación en < 30 minutos siguiendo solo la guía
> (walkthrough real con checklist firmada en F5.5).
>
> Este anexo fija el esqueleto que el plan exige al DSA; los `TODO` se rellenan
> durante F5.5 con los valores reales.

---

# Guía de instalación — Digital Twin de Soporte

## 1. Requisitos previos

| Requisito | Detalle | ¿Lo tengo? |
|---|---|---|
| Sistema operativo | Windows 10/11 o Linux (TODO: versiones probadas) | ☐ |
| Python | 3.11+ (`python --version`) | ☐ |
| Docker Desktop | para Qdrant (`docker --version`) | ☐ |
| Red corporativa | acceso a TODO: endpoints | ☐ |
| Credenciales | nada que teclear si Managed Identity; API key de dev si aplica (TODO: cómo pedirla) | ☐ |

## 2. Instalación en 6 pasos

> Cada paso con bloques separados **PowerShell** y **bash**.

1. Clonar el repositorio — `TODO: url`
2. Arrancar Qdrant — `docker compose up -d`
3. Crear el entorno — `python -m venv .venv` + activación + `pip install -e .`
4. Configurar — copiar `config.example.yaml` → `config.yaml` y rellenar **solo**
   los campos marcados `# OBLIGATORIO` (tabla TODO: campo → dónde obtener el valor)
5. Cargar lecciones iniciales — `python -m ai_agent ingest`
6. Arrancar el servicio y abrir el dashboard — `TODO: comando` →
   `http://127.0.0.1:8080/dashboard`

## 3. Verificar la instalación

- [ ] `GET /health` — todo en verde (captura TODO); los checks N/A del backend
      local aparecen como N/A, no como error.
- [ ] Lanzar la tarea de prueba incluida (`lessons/example_task.md`) — TODO: comando.
- [ ] Reconocer un `Verdict.ok` (captura TODO: qué campos mirar).

## 4. Elegir backend de LLM

> Dos recuadros; solo cambian 2–3 campos de config en cada caso.

**Opción A — Azure OpenAI (Repsol)**: `llm.backend: azure_openai` + TODO campos.
Úsala si: TODO (criterio en una frase).

**Opción B — LLM local (Ollama)**: `llm.backend: local` + `base_url` + modelos.
Úsala si: TODO.

## 5. Operación diaria

| Tarea | Cómo |
|---|---|
| Lanzar una tarea | CLI: TODO · HTTP: `POST /tasks` con `X-API-Key` |
| Leer el dashboard | una frase por pestaña (Overview / Alertas / Lecciones / Escalations / Cost / Calidad / Guardrails / Compliance) — TODO |
| Tarea escalada a humano | claim → resolve (→ promote a lección si procede) — TODO pasos |
| Aprobar una lección aprendida | pestaña Review — TODO |
| Reanudar una tarea `awaiting_resume` | revisar checkpoints → `POST /tasks/{id}/resume` — TODO |

## 6. Resolución de problemas

| Síntoma | Causa probable | Acción |
|---|---|---|
| `/health` devuelve 503 | un guardrail o check falló (fail-closed) | TODO: leer qué check y su remedio |
| «canario de tool calling falla» al arrancar | el modelo local no soporta function calling fiable | TODO: modelo recomendado |
| «mismatch de dims embedder/colección» | config a medias tras cambio de embedder | TODO: correr migración F6.2 |
| Presupuesto agotado / respuestas degradadas | budget de sesión | TODO: cómo ver Cost y ampliar |
| Tarea atascada | crash previo | ver `awaiting_resume` y §5 |

## 7. A quién acudir

- Propietario de la plataforma: TODO
- Canal de soporte: TODO
