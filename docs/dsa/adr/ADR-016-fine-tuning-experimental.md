# ADR-016 — Fine-tuning excluido de producción; pista experimental gateada por evals

**Estado**: Aceptada (plan v1.3 #1, F7). Experimental; no bloquea ninguna fase.

## Contexto

El usuario quiere practicar fine-tuning (QLoRA local en Apple Silicon y FT
gestionado de Azure OpenAI) antes de necesitarlo, con criterios objetivos de
cuándo pagaría en producción (LLM Handbook, Caps. 5–6).

## Decisión

FT **fuera de producción** en fase 1. La pista experimental exige TODOS los
criterios de 7.1 verificados con datos de la eval suite: gap de comportamiento
(no de conocimiento — eso es RAG), prompting agotado (≥2 iteraciones del
registry sin mover la métrica), datos suficientes (≥300–500 SFT / ≥200 DPO),
distribución estable, y motivo económico/latencia medible. Salvaguardas: el
**trust gate aplica al training set**; dataset siempre post-redactor y
decontaminado contra el golden set; el modelo FT se registra como alias
`mini_ft` y debe **superar a `mini` sin degradar el resto** (gate de adopción =
misma lógica de paridad); presupuesto propio con hard stop; pista Azure
bloqueada si no hay región EU. La promoción a producción será una revisión del
plan (v1.4+), nunca una decisión implícita.

## Consecuencias

- (+) Competencia desarrollada sin riesgo para producción; adopción solo con
  datos.
- (−) Infraestructura extra (`build_ft_dataset.py`, `ft_datasets/`) mantenida
  como experimental.
