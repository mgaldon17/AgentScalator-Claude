"""Mem0LessonStore — the lesson store backed by mem0 over Qdrant (semantic memory).

Ported from ``agentcore/infrastructure/mem0_store.py``. Stores each lesson as a mem0
memory: the procedure text is the memory body and the metadata carries
title/origin/reuse/failure_count/pending_review. With ``infer=False`` (the default,
configurable) mem0 keeps the procedure verbatim (no LLM fact-extraction) and only its
embedder/vector store are exercised; ``infer=True`` lets mem0's single LLM call rewrite/
reconcile the text on write. mem0's sync API is run in a thread so the store stays async.

``mem0ai`` + ``qdrant-client`` (and ``httpx``, used only by the embedder preflight) are
required at runtime (see pyproject) but imported lazily, so importing this module — and
unit-testing the pure helpers (``_mem0_config``, ``_to_lesson``) — needs none of them.
"""

from __future__ import annotations

import asyncio
import logging
import os

from .config import Config
from .constants import EmbedderProvider, LlmBackend, LlmProvider, RagBackend, Mem0Key, MetaKey
from .lesson import Lesson, LessonOrigin
from .ports import LessonStore

_log = logging.getLogger("agentmem.store")

# Remote embedder providers and where to probe them. The local in-process providers
# (huggingface / fastembed) are absent here — they need no network and are never checked.
# Typed with str keys (StrEnum members ARE str) so a plain ``provider.lower()`` indexes it.
_REMOTE_EMBEDDERS: dict[str, str] = {
    EmbedderProvider.OLLAMA: "http://localhost:11434",  # default when base_url is empty
    EmbedderProvider.OPENAI: "https://api.openai.com/v1",
    EmbedderProvider.LMSTUDIO: "http://localhost:1234/v1",
}

# Default namespace / list cap when the store is built without a Config (e.g. tests).
# Production values come from Config (mem_user / lesson_list_limit) via build_store.
_USER = "agentcore"
_LIST_LIMIT = 1000


def _to_lesson(item: dict) -> Lesson:
    md = item.get(Mem0Key.METADATA) or {}
    try:
        origin = LessonOrigin(str(md.get(MetaKey.ORIGIN, LessonOrigin.LEARNED)))
    except ValueError:
        origin = LessonOrigin.LEARNED
    return Lesson(
        lesson_id=str(item.get(Mem0Key.ID, "")),
        title=str(md.get(MetaKey.TITLE, "")),
        content=str(item.get(Mem0Key.MEMORY, "")),
        origin=origin,
        reuse=int(md.get(MetaKey.REUSE, 0) or 0),
        failure_count=int(md.get(MetaKey.FAILURE_COUNT, 0) or 0),
        pending_review=bool(md.get(MetaKey.PENDING_REVIEW, False)),
    )


def _metadata(lesson: Lesson) -> dict:
    return {
        MetaKey.TITLE: lesson.title,
        MetaKey.ORIGIN: str(lesson.origin),
        MetaKey.REUSE: lesson.reuse,
        MetaKey.FAILURE_COUNT: lesson.failure_count,
        MetaKey.PENDING_REVIEW: lesson.pending_review,
    }


class Mem0LessonStore:
    def __init__(
        self, memory, *, user: str = _USER, list_limit: int = _LIST_LIMIT, infer: bool = False
    ) -> None:
        self._mem = memory          # a mem0.Memory instance
        self._user = user           # namespace for mem0's identity filters
        self._list_limit = list_limit
        self._infer = infer         # True => mem0's LLM rewrites/reconciles text on add()

    async def add(self, lesson: Lesson) -> None:
        res = await asyncio.to_thread(
            self._mem.add, lesson.content,
            user_id=self._user, metadata=_metadata(lesson), infer=self._infer,
        )
        items = (res or {}).get(Mem0Key.RESULTS) or []
        if items:  # adopt mem0's id so get/update/delete address the same record
            lesson.lesson_id = str(items[0].get(Mem0Key.ID, lesson.lesson_id))

    async def get(self, lesson_id: str) -> Lesson | None:
        item = await asyncio.to_thread(self._mem.get, lesson_id)
        return _to_lesson(item) if item else None

    async def update(self, lesson: Lesson) -> None:
        await asyncio.to_thread(
            self._mem.update, lesson.lesson_id, lesson.content, metadata=_metadata(lesson)
        )

    async def delete(self, lesson_id: str) -> bool:
        if await self.get(lesson_id) is None:
            return False
        await asyncio.to_thread(self._mem.delete, lesson_id)
        return True

    async def search(self, query: str, *, limit: int = 8) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.search, query, top_k=limit, filters={Mem0Key.USER_ID: self._user}
        )
        return [_to_lesson(it) for it in (res or {}).get(Mem0Key.RESULTS, [])]

    async def list(self, *, pending_review: bool | None = None) -> list[Lesson]:
        res = await asyncio.to_thread(
            self._mem.get_all, filters={Mem0Key.USER_ID: self._user}, top_k=self._list_limit
        )
        lessons = [_to_lesson(it) for it in (res or {}).get(Mem0Key.RESULTS, [])]
        if pending_review is not None:
            lessons = [l for l in lessons if l.pending_review == pending_review]
        return lessons

    async def reinforce(self, lesson_id: str) -> None:
        lesson = await self.get(lesson_id)
        if lesson is not None:
            lesson.reinforce()
            await self.update(lesson)

    async def record_failure(self, lesson_id: str) -> None:
        lesson = await self.get(lesson_id)
        if lesson is not None:
            lesson.record_failure()
            await self.update(lesson)

    async def resolve(self, lesson_id: str) -> Lesson | None:
        """Flip pending_review off (a human accepted a learned lesson)."""
        lesson = await self.get(lesson_id)
        if lesson is None:
            return None
        lesson.pending_review = False
        await self.update(lesson)
        return lesson


def _embedder_config(cfg: Config) -> dict:
    """mem0 embedder config for the configured provider.

    ``azure_openai`` (the cloud default) takes ``azure_kwargs`` (endpoint/deployment/
    api_version) with NO api_key, so mem0's AzureOpenAIEmbedding falls back to
    ``DefaultAzureCredential`` (keyless). Local (no server): ``huggingface`` /
    ``fastembed`` only need a model name. ``ollama`` takes its own base URL;
    ``openai``/``lmstudio`` take a base URL + key. The model name is always passed."""
    provider = cfg.embedder_provider.lower()
    embedder_cfg: dict = {"model": cfg.embedder_model}
    if provider == EmbedderProvider.AZURE_OPENAI:
        embedder_cfg["azure_kwargs"] = {
            "azure_endpoint": cfg.embedder_base_url,
            "azure_deployment": cfg.embedder_model,
            "api_version": cfg.embedder_api_version,
        }
        if cfg.embedder_api_key:   # optional; empty => keyless (DefaultAzureCredential)
            embedder_cfg["azure_kwargs"]["api_key"] = cfg.embedder_api_key
        return embedder_cfg
    if provider in (EmbedderProvider.HUGGINGFACE, EmbedderProvider.FASTEMBED):
        return embedder_cfg
    if provider == EmbedderProvider.OLLAMA:
        if cfg.embedder_base_url:
            embedder_cfg["ollama_base_url"] = cfg.embedder_base_url
        return embedder_cfg
    # openai / lmstudio and other OpenAI-compatible providers
    if cfg.embedder_base_url:
        embedder_cfg["openai_base_url"] = cfg.embedder_base_url
    if cfg.embedder_api_key:
        embedder_cfg["api_key"] = cfg.embedder_api_key
    return embedder_cfg


def _check_embedder_reachable(cfg: Config) -> None:
    """Preflight a REMOTE embedder so we never write empty/garbage vectors to Qdrant.

    Local providers (huggingface/fastembed) embed in-process → skipped. For a remote
    provider we probe the endpoint; for ollama we additionally confirm the model is
    actually pulled (an up-but-modelless ollama would silently fail to embed). Raises a
    clear RuntimeError instead of letting the store build against a dead embedder."""
    import httpx  # lazy — keeps the module importable in a minimal env (see module docstring)

    provider = cfg.embedder_provider.lower()
    if provider not in _REMOTE_EMBEDDERS:
        return
    base = (cfg.embedder_base_url or _REMOTE_EMBEDDERS[provider]).rstrip("/")
    try:
        if provider == EmbedderProvider.OLLAMA:
            resp = httpx.get(f"{base}/api/tags", timeout=cfg.probe_timeout)
            resp.raise_for_status()
            pulled = {m.get("name", "").split(":")[0] for m in resp.json().get("models", [])}
            wanted = cfg.embedder_model.split(":")[0]
            if wanted not in pulled:
                raise RuntimeError(
                    f"ollama is up at {base} but the embedder model '{cfg.embedder_model}' "
                    f"is not pulled — run `ollama pull {cfg.embedder_model}`. Refusing to "
                    f"build the store so no empty vectors are written to Qdrant."
                )
        else:  # openai / lmstudio and other OpenAI-compatible endpoints
            resp = httpx.get(f"{base}/models", timeout=cfg.probe_timeout)
            resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(
            f"embedder '{provider}' not reachable at {base} ({exc}). Start it (e.g. "
            f"`ollama serve`) or fix embedder.base_url. Set embedder.check_reachable: false "
            f"to skip this preflight. Refusing to build the store so no empty vectors are "
            f"written to Qdrant."
        ) from exc


def _vector_store_config(cfg: Config) -> dict:
    """mem0 ``vector_store`` block for the configured RAG backend (the lessons store).

    ``qdrant`` (local) is host/port/collection. ``ai_search`` targets Azure AI Search
    keyless: mem0 embeds locally and upserts the vectors into the lessons index directly
    (no api_key => DefaultAzureCredential). ``embedding_model_dims`` MUST match the embedder
    either way."""
    if cfg.rag_backend.lower() == RagBackend.AI_SEARCH:
        return {
            "provider": "azure_ai_search",
            "config": {
                "service_name": cfg.azure_search_service,
                "collection_name": cfg.azure_search_lessons_index,
                "embedding_model_dims": cfg.embedder_dims,
                # no api_key => mem0's AzureAISearch uses DefaultAzureCredential (keyless)
            },
        }
    return {
        "provider": "qdrant",
        "config": {
            "host": cfg.qdrant_host,
            "port": cfg.qdrant_port,
            "collection_name": cfg.collection,
            # mem0's vector store does NOT derive this from the embedder; it must
            # match the model's output dim or the store rejects the vectors.
            "embedding_model_dims": cfg.embedder_dims,
        },
    }


def _llm_config(cfg: Config) -> dict:
    """mem0 ``llm`` block for the ALWAYS-ON infer/rewrite. ``llm_backend`` picks WHO:

    * ``claude`` — mem0 provider ``anthropic`` (the key is read from ANTHROPIC_API_KEY by
      mem0). Anthropic rejects temperature+top_p together, so mem0 keeps temperature.
    * ``local``  — mem0 provider ``openai`` at ``llm_local_base_url`` (LM Studio / qwen);
      the key is read from LLM_API_KEY (LM Studio accepts any placeholder)."""
    if cfg.llm_backend.lower() == LlmBackend.CLAUDE:
        return {
            "provider": LlmProvider.ANTHROPIC,
            "config": {
                "model": cfg.llm_claude_model,
                "temperature": cfg.llm_temperature,
                "max_tokens": cfg.llm_max_tokens,
                # api_key omitted => mem0's AnthropicLLM reads ANTHROPIC_API_KEY from env.
            },
        }
    return {
        "provider": LlmProvider.OPENAI,
        "config": {
            "model": cfg.llm_local_model,
            "openai_base_url": cfg.llm_local_base_url,
            "api_key": os.environ.get("LLM_API_KEY", "lm-studio"),
            "temperature": cfg.llm_temperature,
            "top_p": cfg.llm_top_p,
            "max_tokens": cfg.llm_max_tokens,
        },
    }


def _mem0_config(cfg: Config) -> dict:
    """Translate our ``Config`` into mem0's nested config schema (vector_store + embedder
    + llm). Pure — no mem0 import, no I/O — so the mapping is unit-testable on its own.

    infer is ALWAYS on for this store, so the ``llm`` block is always exercised at add()
    time (mem0's fact-extraction call); its sampling params apply there, never to search."""
    return {
        "vector_store": _vector_store_config(cfg),
        "embedder": {"provider": cfg.embedder_provider, "config": _embedder_config(cfg)},
        "llm": _llm_config(cfg),
    }


def build_store(cfg: Config) -> LessonStore:
    """Construct a mem0-backed store from an already-loaded ``Config`` (callers inject it
    via ``build_store(load())`` — config loading stays out of here). Preflights the
    embedder, maps the config (``_mem0_config``), then wraps mem0's ``Memory`` in a
    ``Mem0LessonStore``."""
    try:
        from mem0 import Memory
    except ImportError as exc:  # pragma: no cover - optional extra
        raise RuntimeError(
            "agentmem needs the 'mem0ai' package: pip install -e '.'"
        ) from exc

    if cfg.embedder_check_reachable:
        _check_embedder_reachable(cfg)

    _log.info(
        "building mem0 store (rag_backend=%s, collection=%s, llm_backend=%s, infer=on)",
        cfg.rag_backend, cfg.collection, cfg.llm_backend,
    )
    return Mem0LessonStore(
        Memory.from_config(_mem0_config(cfg)),
        user=cfg.mem_user,
        list_limit=cfg.lesson_list_limit,
        infer=True,   # infer is ALWAYS on — the lesson is rewritten by the LLM on write
    )
