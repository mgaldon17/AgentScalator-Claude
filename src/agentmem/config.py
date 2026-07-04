"""Configuration — read from a ``config.yaml`` file, overridable by real env vars.

Replaces the relevant slices of ``agentcore/config.yaml`` (``memory.*`` and
``guardrails``). Resolution order (highest precedence first):

  1. a real environment variable (e.g. ``MEM_COLLECTION=...`` in the shell / Docker),
  2. the ``config.yaml`` file at the repo root (nested by section; point elsewhere with
     ``AGENTMEM_CONFIG=/path/to/file``),
  3. the dataclass defaults below.

So a fresh checkout works with zero setup (the shipped ``config.yaml`` just restates the
defaults), env vars still win for per-deployment overrides, and the file is the single
readable place to edit settings. The YAML is nested for legibility; ``_FIELD_MAP`` is the
single source of truth that flattens each ``section.key`` to the flat ENV name used both
for env-var overrides and by the control dashboard (``dashboard/configfile.py``).
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from ruamel.yaml import YAML

from .constants import EmbedderProvider, LlmBackend, RagBackend

# config.py is at <repo>/src/agentmem/config.py → the repo root is three levels up.
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_CONFIG_FILE = _REPO_ROOT / "config.yaml"
# Secrets (API keys) live ONLY here, never in config.yaml — which references them as
# ${EMBEDDER_API_KEY} / ${LLM_API_KEY}. The .env is gitignored; .env.example is the
# committed template. Point elsewhere with AGENTMEM_DOTENV=/path/to/.env.
_DEFAULT_DOTENV_FILE = _REPO_ROOT / ".env"

# ${VAR} references inside YAML string values, expanded from the environment (which the
# .env populates). Lets config.yaml read secrets without ever storing them.
_ENV_REF = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")

# Single source of truth mapping each flat ENV name to its (section, key) path in the
# nested YAML. config.py uses it to flatten the file into os.environ; the dashboard uses
# it to write the nested file from the flat updates its UI produces. Keep them in sync by
# importing from here — never re-declare the mapping elsewhere.
_FIELD_MAP: dict[str, tuple[str, str]] = {
    # memory
    "QDRANT_HOST": ("memory", "qdrant_host"),
    "QDRANT_PORT": ("memory", "qdrant_port"),
    "MEM_COLLECTION": ("memory", "collection"),
    "MEM_USER": ("memory", "mem_user"),
    # embedder
    "EMBEDDER_PROVIDER": ("embedder", "provider"),
    "EMBEDDER_MODEL": ("embedder", "model"),
    "EMBEDDER_BASE_URL": ("embedder", "base_url"),
    "EMBEDDER_API_KEY": ("embedder", "api_key"),
    "EMBEDDER_DIMS": ("embedder", "dims"),
    "EMBEDDER_CHECK_REACHABLE": ("embedder", "check_reachable"),
    # llm — infer is ALWAYS on (not configurable); backend picks WHO rewrites the lesson.
    "LLM_BACKEND": ("llm", "backend"),
    "LLM_CLAUDE_MODEL": ("llm", "claude_model"),
    "LLM_LOCAL_MODEL": ("llm", "local_model"),
    "LLM_LOCAL_BASE_URL": ("llm", "local_base_url"),
    "LLM_TEMPERATURE": ("llm", "temperature"),
    "LLM_TOP_P": ("llm", "top_p"),
    "LLM_MAX_TOKENS": ("llm", "max_tokens"),
    # guardrails
    "GUARD_URL_ENABLED": ("guardrails", "url_enabled"),
    "GUARD_DESTRUCTIVE_ENABLED": ("guardrails", "destructive_enabled"),
    "GUARD_ALLOW_DOMAINS": ("guardrails", "allow_domains"),
    "GUARD_CHECK_REACHABLE": ("guardrails", "check_reachable"),
    "GUARD_DISABLED_PATTERNS": ("guardrails", "disabled_patterns"),
    "GUARD_CUSTOM_RULES_FILE": ("guardrails", "custom_rules_file"),
    "PROBE_TIMEOUT": ("guardrails", "probe_timeout"),
    "PROBE_USER_AGENT": ("guardrails", "probe_user_agent"),
    # retrieval
    "LESSON_SEARCH_LIMIT": ("retrieval", "search_limit"),
    "LESSON_LIST_LIMIT": ("retrieval", "list_limit"),
    # rag — where lessons + document knowledge live: qdrant (local) / ai_search (Azure).
    "RAG_BACKEND": ("rag", "backend"),
    "RAG_TOP_K": ("rag", "top_k"),
    "RAG_QDRANT_COLLECTION": ("rag", "qdrant_collection"),
    # azure ai search — used only when rag.backend: ai_search. Keyless (Entra ID). service
    # is the SEARCH SERVICE NAME (→ https://<service>.search.windows.net). lessons_index is
    # mem0-managed (written directly, keyless); docs_index is the PDF/Word index a human
    # loads via the Azure Portal from a blob (integrated vectorization on vector_field).
    "AZURE_SEARCH_SERVICE": ("azure_search", "service"),
    "AZURE_SEARCH_LESSONS_INDEX": ("azure_search", "lessons_index"),
    "AZURE_SEARCH_DOCS_INDEX": ("azure_search", "docs_index"),
    "AZURE_SEARCH_VECTOR_FIELD": ("azure_search", "vector_field"),
}

_yaml = YAML()  # round-trip loader (preserves types; comments matter only on write)


def _flatten(value: object) -> str | None:
    """Render a YAML scalar as the string an env var would hold. ``None`` (a YAML key
    present but empty) maps to the empty string; an absent key returns ``None`` upstream
    so the dataclass default applies."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if value is None:
        return ""
    return str(value)


def _load_dotenv(path: Path) -> None:
    """Populate ``os.environ`` from a KEY=VALUE ``.env`` (secrets) WITHOUT overriding
    existing vars. Loaded BEFORE the YAML so config.yaml's ${VAR} references resolve to
    these values. Blank/``#`` lines skipped; surrounding quotes stripped; missing = no-op."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


def _load_config_file(path: Path) -> None:
    """Populate ``os.environ`` from the nested YAML WITHOUT overriding existing vars.

    Each ``section.key`` present in the file is flattened to its flat ENV name (via
    ``_FIELD_MAP``), has any ``${VAR}`` reference expanded from the environment, and is
    applied with ``setdefault`` — which is what gives real env vars precedence over the
    file. A value that is ONLY an unresolved ``${VAR}`` (e.g. a secret whose .env is
    absent) is skipped so the dataclass default applies. Missing file / unreadable /
    non-mapping = no-op (defaults apply)."""
    try:
        data = _yaml.load(path.read_text(encoding="utf-8"))
    except OSError:
        return
    if not isinstance(data, dict):
        return
    for env_name, (section, key) in _FIELD_MAP.items():
        sect = data.get(section)
        if not isinstance(sect, dict) or key not in sect:
            continue
        rendered = _flatten(sect[key])
        if rendered is None:
            continue
        expanded = _ENV_REF.sub(lambda m: os.environ.get(m.group(1), ""), rendered)
        if _ENV_REF.search(rendered) and not expanded:
            continue  # unresolved ${VAR} (secret not in .env) → let the default apply
        os.environ.setdefault(env_name, expanded)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _env_list(name: str) -> list[str]:
    raw = os.environ.get(name, "").strip()
    if not raw:
        return []
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


@dataclass
class Config:
    # --- Qdrant / mem0 (memory.* in config.yaml) ---
    qdrant_host: str = "localhost"
    qdrant_port: int = 6333
    collection: str = "agentcore_lessons"
    # mem0 requires an identity for its filters; all lessons share this namespace.
    mem_user: str = "agentcore"

    # --- Embedder ---
    # Default is a LOCAL, in-process embedder (sentence-transformers via mem0's
    # "huggingface" provider): no server, no API key, fully offline after the model
    # is downloaded once. The multilingual MiniLM handles the Spanish lessons well.
    # To use a remote OpenAI-compatible embedder instead (e.g. LM Studio), set
    # EMBEDDER_PROVIDER=openai (or lmstudio) + EMBEDDER_MODEL/BASE_URL/API_KEY.
    embedder_provider: str = EmbedderProvider.HUGGINGFACE
    embedder_model: str = "paraphrase-multilingual-MiniLM-L12-v2"
    embedder_base_url: str = ""   # only for openai/lmstudio/ollama providers
    embedder_api_key: str = ""    # only for openai-compatible providers
    # Vector dimension of the embedder, written into the Qdrant collection. MUST match
    # the model: 384 for paraphrase-multilingual-MiniLM-L12-v2 (default), 768 for nomic,
    # 1536 for OpenAI text-embedding-3. Changing it requires a fresh collection.
    embedder_dims: int = 384
    # For a REMOTE embedder (ollama / openai / lmstudio), preflight that the endpoint is
    # reachable (and, for ollama, that the model is pulled) before building the store —
    # so a down embedder fails loudly instead of writing empty/garbage vectors to Qdrant.
    # No-op for the local in-process providers (huggingface / fastembed).
    embedder_check_reachable: bool = True

    # --- LLM (llm.* in config.yaml) — the ALWAYS-ON infer/rewrite of a lesson ---
    # Every lesson is rewritten/reconciled by an LLM before it is stored (infer is always
    # on — NOT configurable). ``llm_backend`` picks WHO does it:
    #   * "claude" — the Anthropic API (same Claude family as the agent). mem0 provider
    #                "anthropic"; the key comes from the ANTHROPIC_API_KEY env var.
    #   * "local"  — a local OpenAI-compatible LLM (e.g. qwen via LM Studio). mem0 provider
    #                "openai" at ``llm_local_base_url``; key from LLM_API_KEY (LM Studio
    #                accepts any placeholder).
    # The sampling params apply to whichever backend is active (Anthropic ignores top_p
    # when temperature is set). See store._llm_config.
    llm_backend: str = LlmBackend.CLAUDE
    llm_claude_model: str = "claude-sonnet-5"
    llm_local_model: str = "qwen2.5-7b-instruct-1m"
    llm_local_base_url: str = "http://localhost:1234/v1"
    llm_temperature: float = 0.1
    llm_top_p: float = 1.0
    llm_max_tokens: int = 2000

    # --- Guardrails (guardrails.* in config.yaml) ---
    # Master switches for each guard, plus a per-pattern off-list for the destructive
    # blocklist. These are what the control dashboard toggles (dashboard/server.py).
    guard_url_enabled: bool = True
    guard_destructive_enabled: bool = True
    guard_allow_domains: list[str] = field(default_factory=list)
    guard_check_reachable: bool = True
    # Keys (see guardrails._DESTRUCTIVE_PATTERNS) of destructive patterns to DISABLE.
    guard_disabled_patterns: list[str] = field(default_factory=list)
    # JSON file holding user-defined (custom) destructive rules. Empty => the default
    # <repo>/custom_guardrails.json (resolved in rules_store).
    guard_custom_rules_file: str = ""
    # URL-reachability probe (UrlGuardrail._http_probe).
    probe_timeout: float = 5.0
    probe_user_agent: str = "Mozilla/5.0 (agentmem url-guardrail)"

    # --- Retrieval ---
    lesson_search_limit: int = 8       # default top_k for semantic recall
    lesson_list_limit: int = 1000      # top_k cap when enumerating all lessons

    # --- RAG / storage backend (rag.* in config.yaml) ---
    # Where BOTH the lessons and the document knowledge live. rag_backend switches it:
    #   * "qdrant"    — local Qdrant (offline). Lessons in the mem0 collection; documents in
    #                   rag_qdrant_collection, filled via mcp__memory__rag_ingest.
    #   * "ai_search" — Azure AI Search (keyless). Lessons written directly by mem0 to the
    #                   lessons index; documents loaded by a human via the Azure Portal from
    #                   a blob (integrated vectorization) into the docs index.
    rag_backend: str = RagBackend.QDRANT           # "qdrant" | "ai_search"
    rag_top_k: int = 5                             # default chunks rag_search returns
    rag_qdrant_collection: str = "support_docs"    # qdrant backend: docs collection (not lessons)

    # --- Azure AI Search (azure_search.* in config.yaml) — used only when rag.backend: ai_search ---
    # Auth is KEYLESS (Entra ID / RBAC via DefaultAzureCredential) — no key anywhere. service
    # is the SEARCH SERVICE NAME (→ https://<service>.search.windows.net). Empty => the
    # ai_search backend is inert. lessons_index is mem0-managed (written directly);
    # docs_index is the PDF/Word index a human loads via the portal from a blob, embedded
    # server-side on vector_field (the portal wizard's default column).
    azure_search_service: str = ""
    azure_search_lessons_index: str = "agentmem-lessons"
    azure_search_docs_index: str = "support-docs"
    azure_search_vector_field: str = "text_vector"

    @classmethod
    def from_env(cls) -> "Config":
        return cls(
            qdrant_host=os.environ.get("QDRANT_HOST", cls.qdrant_host),
            qdrant_port=int(os.environ.get("QDRANT_PORT", cls.qdrant_port)),
            collection=os.environ.get("MEM_COLLECTION", cls.collection),
            mem_user=os.environ.get("MEM_USER", cls.mem_user),
            embedder_provider=os.environ.get("EMBEDDER_PROVIDER", cls.embedder_provider),
            embedder_model=os.environ.get("EMBEDDER_MODEL", cls.embedder_model),
            embedder_base_url=os.environ.get("EMBEDDER_BASE_URL", cls.embedder_base_url),
            embedder_api_key=os.environ.get("EMBEDDER_API_KEY", cls.embedder_api_key),
            embedder_dims=int(os.environ.get("EMBEDDER_DIMS", cls.embedder_dims)),
            embedder_check_reachable=_env_bool("EMBEDDER_CHECK_REACHABLE", cls.embedder_check_reachable),
            llm_backend=os.environ.get("LLM_BACKEND", cls.llm_backend),
            llm_claude_model=os.environ.get("LLM_CLAUDE_MODEL", cls.llm_claude_model),
            llm_local_model=os.environ.get("LLM_LOCAL_MODEL", cls.llm_local_model),
            llm_local_base_url=os.environ.get("LLM_LOCAL_BASE_URL", cls.llm_local_base_url),
            llm_temperature=float(os.environ.get("LLM_TEMPERATURE", cls.llm_temperature)),
            llm_top_p=float(os.environ.get("LLM_TOP_P", cls.llm_top_p)),
            llm_max_tokens=int(os.environ.get("LLM_MAX_TOKENS", cls.llm_max_tokens)),
            guard_url_enabled=_env_bool("GUARD_URL_ENABLED", cls.guard_url_enabled),
            guard_destructive_enabled=_env_bool("GUARD_DESTRUCTIVE_ENABLED", cls.guard_destructive_enabled),
            guard_allow_domains=_env_list("GUARD_ALLOW_DOMAINS"),
            guard_check_reachable=_env_bool("GUARD_CHECK_REACHABLE", cls.guard_check_reachable),
            guard_disabled_patterns=_env_list("GUARD_DISABLED_PATTERNS"),
            guard_custom_rules_file=os.environ.get("GUARD_CUSTOM_RULES_FILE", cls.guard_custom_rules_file),
            probe_timeout=float(os.environ.get("PROBE_TIMEOUT", cls.probe_timeout)),
            probe_user_agent=os.environ.get("PROBE_USER_AGENT", cls.probe_user_agent),
            lesson_search_limit=int(os.environ.get("LESSON_SEARCH_LIMIT", cls.lesson_search_limit)),
            lesson_list_limit=int(os.environ.get("LESSON_LIST_LIMIT", cls.lesson_list_limit)),
            rag_backend=os.environ.get("RAG_BACKEND", cls.rag_backend),
            rag_top_k=int(os.environ.get("RAG_TOP_K", cls.rag_top_k)),
            rag_qdrant_collection=os.environ.get("RAG_QDRANT_COLLECTION", cls.rag_qdrant_collection),
            azure_search_service=os.environ.get("AZURE_SEARCH_SERVICE", cls.azure_search_service),
            azure_search_lessons_index=os.environ.get("AZURE_SEARCH_LESSONS_INDEX", cls.azure_search_lessons_index),
            azure_search_docs_index=os.environ.get("AZURE_SEARCH_DOCS_INDEX", cls.azure_search_docs_index),
            azure_search_vector_field=os.environ.get("AZURE_SEARCH_VECTOR_FIELD", cls.azure_search_vector_field),
        )


def custom_rules_path(cfg: Config) -> Path:
    """Resolve the custom-rules JSON file (config value, or the repo-root default)."""
    return Path(cfg.guard_custom_rules_file) if cfg.guard_custom_rules_file \
        else _REPO_ROOT / "custom_guardrails.json"


def load() -> Config:
    """Load the .env secrets and config.yaml (if present) into the environment, then read
    Config from env. The .env is loaded first so config.yaml's ${VAR} secret references
    resolve against it."""
    _load_dotenv(Path(os.environ.get("AGENTMEM_DOTENV", _DEFAULT_DOTENV_FILE)))
    _load_config_file(Path(os.environ.get("AGENTMEM_CONFIG", _DEFAULT_CONFIG_FILE)))
    return Config.from_env()
