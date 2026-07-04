"""Document RAG — switchable backend: local Qdrant OR cloud Azure AI Search.

The knowledge the agent (Claude Code) reads through ``mcp__memory__rag_search``. Which
backend is live is a single config switch (``rag.backend``):

  * ``qdrant`` — a Qdrant collection embedded in-process with the SAME local embedder as the
    lesson store (offline, no cloud). It reuses mem0 over a SEPARATE collection
    (``rag.qdrant_collection``), so documents never mix with lessons. Fill it with
    ``mcp__memory__rag_ingest``.
  * ``ai_search`` — an Azure AI Search index a human loads via the Azure Portal ("Import and
    vectorize data" from a blob, which sets up integrated vectorization so the query is
    embedded server-side). Read-only from here; auth is KEYLESS (Entra ID via
    ``DefaultAzureCredential``). Ingest is a portal task, not ours.

Both backends return the same shape: ``[{text, source, score}]``, best match first. All
heavy deps (mem0/qdrant, azure-*) are imported lazily so this module stays importable in a
minimal env and only the CHOSEN backend's deps are needed.
"""

from __future__ import annotations

import logging
from functools import cached_property

from .config import Config
from .constants import Mem0Key, RagBackend

_log = logging.getLogger("agentmem.rag")

# mem0 identity namespace for document chunks (kept distinct from the lessons' namespace so
# a docs collection and a lessons collection never cross-contaminate on shared filters).
_DOCS_USER = "docs"


def chunk_text(text: str, *, chunk_chars: int = 1200, overlap: int = 150) -> list[str]:
    """Split text into overlapping, whitespace-bounded chunks (never mid-word). Whitespace
    is normalised first so chunk sizes are predictable; ``overlap`` is clamped below
    ``chunk_chars`` to guarantee forward progress. Blank input => ``[]``."""
    normalised = " ".join(text.split())
    if not normalised:
        return []
    overlap = max(0, min(overlap, chunk_chars - 1))
    chunks: list[str] = []
    start, n = 0, len(normalised)
    while start < n:
        end = min(start + chunk_chars, n)
        if end < n:
            space = normalised.rfind(" ", start, end)
            if space > start:
                end = space
        chunks.append(normalised[start:end].strip())
        if end >= n:
            break
        start = max(end - overlap, start + 1)
    return [c for c in chunks if c]


class LocalQdrantRag:
    """Local document RAG: mem0 over a dedicated Qdrant collection, embedded in-process by
    the same local embedder the lesson store uses. Fully offline."""

    def __init__(self, cfg: Config) -> None:
        self._cfg = cfg

    @cached_property
    def _mem(self):
        from mem0 import Memory  # lazy: only the local backend needs mem0/qdrant

        from .store import _mem0_config

        conf = _mem0_config(self._cfg)
        # Point mem0 at the DOCUMENTS collection, not the lessons one.
        conf["vector_store"]["config"]["collection_name"] = self._cfg.rag_qdrant_collection
        return Memory.from_config(conf)

    def ingest(self, text: str, source: str | None = None) -> int:
        """Chunk ``text`` and store each chunk (verbatim, infer=False) under the docs
        namespace. Returns the number of chunks written."""
        chunks = chunk_text(text)
        for i, chunk in enumerate(chunks):
            self._mem.add(
                chunk, user_id=_DOCS_USER,
                metadata={"source": source or "", "ordinal": i}, infer=False,
            )
        _log.info("ingested %d chunks (source=%s) into '%s'",
                  len(chunks), source, self._cfg.rag_qdrant_collection)
        return len(chunks)

    def search(self, query: str, top_k: int) -> list[dict]:
        res = self._mem.search(query, top_k=top_k, filters={Mem0Key.USER_ID: _DOCS_USER})
        out = []
        for it in (res or {}).get(Mem0Key.RESULTS, []):
            md = it.get(Mem0Key.METADATA) or {}
            out.append({
                "text": it.get(Mem0Key.MEMORY, ""),
                "source": md.get("source") or None,
                "score": it.get("score"),
            })
        return out


class AzureSearchRag:
    """Cloud document RAG: read an Azure AI Search index (loaded via the Azure Portal).

    Keyless (Entra ID / RBAC via ``DefaultAzureCredential``). A hybrid query is issued —
    semantic text plus a ``VectorizableTextQuery`` (the index's integrated vectorizer
    embeds the query server-side). If the index has no vectorizer, it falls back to plain
    text search so retrieval still works."""

    def __init__(self, cfg: Config) -> None:
        if not cfg.azure_search_service:
            raise RuntimeError(
                "azure_search.service is not set — the ai_search RAG needs it (config.yaml)."
            )
        self._cfg = cfg

    @cached_property
    def _client(self):
        from azure.identity import DefaultAzureCredential
        from azure.search.documents import SearchClient

        endpoint = f"https://{self._cfg.azure_search_service}.search.windows.net"
        return SearchClient(
            endpoint,
            self._cfg.azure_search_docs_index,
            DefaultAzureCredential(),
        )

    @staticmethod
    def _row(result) -> dict:
        """Flatten one search hit: keep the text fields, drop the raw embedding vector
        (a list of floats) and Azure's @search.* metadata (except the score)."""
        text_parts, source = [], None
        for key, value in result.items():
            if key.startswith("@search."):
                continue
            if isinstance(value, list) and value and isinstance(value[0], (int, float)):
                continue  # the embedding vector — never surface it to the model
            if key in ("title", "parent_id", "source") and source is None and value:
                source = str(value)
            if isinstance(value, str) and value.strip():
                text_parts.append(value)
        return {
            "text": "\n".join(text_parts),
            "source": source,
            "score": result.get("@search.score"),
        }

    def search(self, query: str, top_k: int) -> list[dict]:
        from azure.core.exceptions import HttpResponseError
        from azure.search.documents.models import VectorizableTextQuery

        try:
            results = self._client.search(
                search_text=query,
                vector_queries=[VectorizableTextQuery(
                    text=query, k_nearest_neighbors=top_k,
                    fields=self._cfg.azure_search_vector_field,
                )],
                top=top_k,
            )
            return [self._row(r) for r in results]
        except HttpResponseError as exc:
            # Index has no vectorizer / a different vector field — fall back to plain text.
            _log.warning("vector query failed (%s); falling back to text search", exc)
            results = self._client.search(search_text=query, top=top_k)
            return [self._row(r) for r in results]

    def ingest(self, text: str, source: str | None = None) -> int:  # noqa: ARG002
        raise RuntimeError(
            "the ai_search RAG (Azure AI Search) is loaded via the Azure Portal "
            "('Import and vectorize data' from a blob), not through rag_ingest. Switch "
            "rag.backend to 'qdrant' to ingest here."
        )


def build_rag(cfg: Config):
    """Construct the RAG backend selected by ``rag.backend``. Returns ``None`` when the
    chosen backend is not configured (ai_search with no service) so the tools can report it
    cleanly instead of raising at import time."""
    backend = (cfg.rag_backend or RagBackend.QDRANT).lower()
    if backend == RagBackend.AI_SEARCH:
        return AzureSearchRag(cfg) if cfg.azure_search_service else None
    return LocalQdrantRag(cfg)
