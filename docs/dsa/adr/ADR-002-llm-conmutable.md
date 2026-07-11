# ADR-002 — LLM conmutable `azure_openai | local` tras un único LLMPort

**Estado**: Aceptada (plan v1.1 #4, §F6.3, §Cómo hablamos con el LLM).

## Contexto

Se necesita ejecutar el mismo agente con Azure OpenAI (compliance/coste
corporativo: Managed Identity, EU, content filter) o con un endpoint local
OpenAI-compatible (Ollama `/v1`, vLLM, LM Studio) sin tocar código.

## Decisión

`llm.backend: azure_openai | local` conmuta entre dos adapters del mismo
`LLMPort`: `azure_openai.py` y `openai_compatible.py`. Ambos pasan **la misma
suite de contract tests** (LSP). Los alias `mini/full/judge` se resuelven por
backend (deployments Azure ↔ `llm.local.models`). El backend local exige
modelos con tool calling fiable; un **canario de function calling en el
health-check es bloqueante** (fail-closed) al arranque. El contrato de serving
local (contexto ≥16k, cuantización ≥Q5/AWQ, batching) vive en la capa de
serving, fuera del codebase.

## Consecuencias

- (+) Cambiar de backend = flag + restart; el cache no cruza respuestas
  (`llm_backend` en la clave); paridad de capacidades verificada, no supuesta.
- (−) Doble superficie de test; features exclusivas de un backend (content
  filter) se reportan N/A visibles en `/health`, nunca se simulan.
