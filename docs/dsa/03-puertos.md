# 03 — Contratos de ports (domain/ports.py)

Fuente: plan v1.3.1 §Domain, F1.2, F2.1. Los ports son **ABCs pequeños y
específicos** (ISP); `application/` depende solo de ellos (DIP). Las firmas de
este documento son **normativas**: la implementación puede añadir helpers
privados, nunca cambiar estas firmas sin revisar el DSA.

Convenciones: tipado estricto, `dataclasses` congeladas para DTOs, sin
excepciones silenciosas — cada port declara sus errores. Todos los métodos son
síncronos en fase 1 (un proceso, un usuario efectivo por sesión); si se
necesita `async`, es una revisión del DSA, no una decisión local.

## 1. Tipos compartidos (domain/models.py — resumen; esquemas completos en doc 04)

```python
CallType = Literal["goal_extractor", "planner", "verifier", "interviewer", "judge"]
PathDecision = Literal["A", "B", "C"]

@dataclass(frozen=True)
class Goal:
    text: str
    source: Literal["explicit", "inferred", "lesson"]
    confidence: float                      # 1.0 si explicit
    entities: dict[str, str] = field(default_factory=dict)

@dataclass(frozen=True)
class RetrievalHit:
    lesson_id: str
    score: float                           # similitud cruda del vector store
    quality_score: float                   # score × (reuse+1)/(reuse+failure_count+1)
    payload: dict                          # incluye embedder_id, lesson_version, origin…

@dataclass(frozen=True)
class Plan:
    goal: Goal
    lesson_id: str | None                  # None en path C puro
    steps: list[PlanStep]                  # PlanStep{tool, args, rationale}
    expected_tools: list[str]
    acceptance: Acceptance                 # type: rule | llm_judge | hybrid

@dataclass(frozen=True)
class Verdict:
    ok: bool
    evidence: list[str]
    reason: str
    method: Literal["rule", "llm_judge", "hybrid"]
```

## 2. Los 7 ports

### 2.1 LLMPort

```python
class LLMPort(ABC):
    """Contrato único para azure_openai.py y openai_compatible.py.
    Ambos adapters pasan la MISMA suite de contract tests (v1.1)."""

    @abstractmethod
    def complete(self, req: LLMRequest) -> LLMResponse:
        """Una llamada stateless. req.messages ya viene redactado (rule-set pii);
        el adapter NO redacta — eso es del pipeline de seguridad (invariante)."""

    @abstractmethod
    def capabilities(self) -> LLMCapabilities:
        """tool_calling: bool, strict_json_schema: bool, context_window: int.
        Usada por el health-check (canario) y las validaciones de arranque."""

@dataclass(frozen=True)
class LLMRequest:
    call_type: CallType
    model_alias: str                       # mini | full | judge (+ mini_ft experimental)
    system_prompt: PromptRef               # {prompt_id, prompt_version, text} — registry (ADR-015)
    messages: list[Message]
    tools: list[dict] | None = None        # JSON Schema function calling estricto
    response_schema: dict | None = None    # salidas estructuradas (Planner, Verifier…)
    max_tokens: int = 2048
    temperature: float = 0.0
    correlation_id: str = ""
    session_id: str = ""

@dataclass(frozen=True)
class LLMResponse:
    content: str | None
    tool_calls: list[ToolCallRequest]      # {name, arguments(dict), call_id}
    usage: Usage                           # {input_tokens, output_tokens}
    model: str                             # modelo/deployment real resuelto
    backend: Literal["azure_openai", "local"]
    finish_reason: str
```

Errores declarados: `LLMUnavailable`, `LLMContentFiltered`,
`LLMSchemaViolation` (la respuesta no cumple `response_schema` tras el reintento
de formato del adapter).

El **Router** (`llm/router.py`) NO es un port: es un decorador de `LLMPort`
que resuelve `model_alias` según política y presupuesto (doc 02 §7) y es
agnóstico del backend.

### 2.2 EmbedderPort

```python
class EmbedderPort(ABC):
    @property
    @abstractmethod
    def embedder_id(self) -> str: ...      # p. ej. "bge-m3-1024" | "te3-large-3072"

    @property
    @abstractmethod
    def dims(self) -> int: ...             # validado vs colección al arranque (fail-closed)

    @abstractmethod
    def embed_query(self, text: str) -> list[float]: ...
        # aplica query_prefix/instruction del config si el modelo lo requiere

    @abstractmethod
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
        # batching interno según config; aplica passage_prefix
```

### 2.3 VectorStorePort

```python
class VectorStorePort(ABC):
    @abstractmethod
    def ensure_collection(self, spec: CollectionSpec) -> None:
        """spec: {name, dims, distance, metadata: {embedder_id}}. Idempotente.
        Si existe con metadata incompatible → CollectionMismatch (no recrea)."""

    @abstractmethod
    def collection_meta(self, name: str) -> CollectionMeta: ...

    @abstractmethod
    def upsert(self, collection: str, points: list[Point]) -> None: ...

    @abstractmethod
    def search(self, collection: str, vector: list[float], k: int,
               flt: SearchFilter) -> list[RetrievalHit]:
        """OBLIGATORIO (F4.9): flt.pending_review==False se traduce a filtro
        NATIVO del backend (query Qdrant / OData de AI Search) — nunca
        post-filter en Python. Contract test lo verifica en ambos adapters."""

    @abstractmethod
    def delete(self, collection: str, ids: list[str]) -> None: ...
```

### 2.4 ToolRunnerPort

```python
class ToolRunnerPort(ABC):
    @abstractmethod
    def discover(self) -> list[ToolSpec]:
        """Tools de todos los servidores MCP configurados, con prefijo
        (browser., shell.). Tools fuera de este catálogo → rechazo (F4.11)."""

    @abstractmethod
    def call(self, inv: ToolInvocation) -> ToolResult: ...

@dataclass(frozen=True)
class ToolInvocation:
    tool: str                              # nombre prefijado
    args: dict
    step_execution_id: str                 # dedup best-effort en resume (F4.6.6)
    timeout_s: float                       # guardrails.request.tool_timeout_seconds

@dataclass(frozen=True)
class ToolResult:
    ok: bool
    content: str                           # crudo; el Executor lo sanea y envuelve
    error: str | None
    duration_ms: int
    bytes: int                             # contra spotlighting.max_tool_output_bytes
```

El resultado crudo **nunca** llega al LLM: el Executor aplica
`wrap_as_untrusted(sanitize_for_context(content))` sin excepción (F4.6).

### 2.5 LessonRepositoryPort

```python
class LessonRepositoryPort(ABC):
    @abstractmethod
    def load_all(self) -> list[Lesson]: ...          # parsea frontmatter; valida schema

    @abstractmethod
    def get(self, lesson_id: str) -> Lesson: ...

    @abstractmethod
    def save_draft(self, lesson: Lesson) -> str:
        """Fuerza origin=learned, pending_review=True. Corre scan_for_injection
        sobre el .md ANTES de indexar; hit ⇒ pending_review=True + warning (F4.10)."""

    @abstractmethod
    def approve(self, lesson_id: str) -> None:       # learned → buscable (trust gate)

    @abstractmethod
    def bump_reuse(self, lesson_id: str) -> None: ...
    @abstractmethod
    def bump_failure(self, lesson_id: str) -> None: ...
```

Sin `delete` automático en el port: la limpieza del RAG es **manual** (plan
§ciclo de vida). Borrar es una operación de operador sobre el FS + re-ingesta.

### 2.6 CachePort

```python
class CacheKey(NamedTuple):
    call_type: CallType
    prompt_exact_hash: str | None          # planner: hash de prompt normalizado
    prompt_embedding: tuple[float, ...] | None   # goal_extractor: matching semántico
    system_prompt_hash: str
    top_k_lesson_ids: tuple[str, ...]
    model_alias: str
    llm_backend: str
    embedder_id: str

class CachePort(ABC):
    @abstractmethod
    def lookup(self, key: CacheKey) -> LLMResponse | None: ...
    @abstractmethod
    def store(self, key: CacheKey, value: LLMResponse, ttl_s: int) -> None: ...
```

Invariantes (validadas al arranque, fail-closed): solo `cacheable_call_types`
llegan aquí; `verifier`/`interviewer` en la lista ⇒ el arranque falla.
Exactamente uno de `prompt_exact_hash` / `prompt_embedding` es no-nulo según
`cache.semantic.matching[call_type]`.

### 2.7 GuardrailPort

```python
GuardrailStage = Literal["request_in", "tool_call", "tool_output",
                         "response_out", "lesson_ingest"]

@dataclass(frozen=True)
class GuardrailDecision:
    allowed: bool
    rule_key: str | None                   # clave estable del catálogo (p. ej. rm_root_home)
    reason: str                            # motivo humano; genérico hacia el cliente
    evidence: dict                         # para audit/dashboard, nunca para el LLM

class GuardrailPort(ABC):
    @abstractmethod
    def evaluate(self, stage: GuardrailStage, payload: dict) -> GuardrailDecision:
        """Chain of responsibility por stage. FAIL-CLOSED: cualquier excepción
        interna ⇒ GuardrailDecision(allowed=False, reason genérico) — el
        wrapper que lo garantiza es código común, no responsabilidad de cada guard."""

    @abstractmethod
    def health(self) -> dict[str, bool]:   # canary por guard, expuesto en /health
```

## 3. Matriz puerto → adapters

| Port | Adapter 1 (default) | Adapter 2 | Conmutación |
|---|---|---|---|
| LLMPort | `llm/azure_openai.py` | `llm/openai_compatible.py` | `llm.backend` (flag + canario) |
| EmbedderPort | `embedder/fastembed_bge_m3.py` | `embedder/azure_openai_embed.py` | `embedder.backend` (**migración F6.2**) |
| VectorStorePort | `vector_store/qdrant_local.py` | `vector_store/azure_ai_search.py` | `vector_store.backend` (flag + re-ingesta) |
| ToolRunnerPort | `mcp/client.py` + `registry.py` | — | `mcp_servers` (lista) |
| LessonRepositoryPort | `lessons/fs_markdown_repo.py` | — | — |
| CachePort | `cache/semantic_cache_qdrant.py` | — | `cache.semantic.enabled` |
| GuardrailPort | `security/guardrails.py` (chain) | — | claves `guardrails.*` |

## 4. Puertos que NO existen (decisión explícita)

- **`IEverything` / service locator**: prohibido (ISP).
- **Port de métricas/tracing**: la observabilidad es cross-cutting por
  decoradores (`@cost_tracked`) y middleware; no es una dependencia del dominio.
- **Port de escalations/task_state**: son repos de infraestructura con interfaz
  concreta usada solo por Application; se promocionarán a port si aparece un
  segundo backend (YAGNI controlado — misma lógica que §Further #7 para mem0).

## 5. Contract tests (obligaciones LSP)

| Suite | Se ejecuta contra | Casos mínimos |
|---|---|---|
| `tests/infrastructure/contract_llm.py` | `azure_openai.py` y `openai_compatible.py` (mock server) | chat simple; function calling estricto (args tipados); `response_schema` respetado; usage contabilizado; content filter → `LLMContentFiltered`; canario de capabilities |
| `tests/infrastructure/contract_vector_store.py` | `qdrant_local.py` y `azure_ai_search.py` (stub) | upsert+search top-k; **filtro `pending_review` nativo en query** (una lección quarantined con score máximo NO aparece); metadata `embedder_id`; `CollectionMismatch` |
| `tests/infrastructure/contract_embedder.py` | ambos embedders | dims declaradas == longitud real; determinismo; prefijos aplicados |

Regla: un adapter nuevo entra al composition root **solo** si pasa la suite de
contrato de su port sin modificarla.
