"""Pure-logic tests for the document RAG — no Qdrant, no Azure, no network.

Covers the chunker, the backend switch (local vs cloud, and the inert cloud case), and the
Azure hit-flattening (which must drop the raw embedding vector before it reaches the model).
"""

from __future__ import annotations

from agentmem.config import Config
from agentmem.rag import AzureSearchRag, LocalQdrantRag, build_rag, chunk_text


def test_chunk_text_empty_and_blank():
    assert chunk_text("") == []
    assert chunk_text("   \n\t ") == []


def test_chunk_text_size_and_word_boundaries():
    words = " ".join(f"word{i}" for i in range(200))
    chunks = chunk_text(words, chunk_chars=50, overlap=10)
    assert len(chunks) > 1
    assert all(len(c) <= 50 for c in chunks)
    assert all(not c.startswith(" ") and not c.endswith(" ") for c in chunks)


def test_chunk_text_overlap_terminates_when_overlap_exceeds_size():
    chunks = chunk_text("abcdefghij " * 5, chunk_chars=8, overlap=999)
    assert chunks and all(len(c) <= 8 for c in chunks)


def test_build_rag_defaults_to_ai_search():
    # default rag_backend = "ai_search"; with a service set it builds the Azure backend.
    cfg = Config()
    assert cfg.rag_backend == "ai_search"
    cfg.azure_search_service = "mysvc"
    assert isinstance(build_rag(cfg), AzureSearchRag)


def test_build_rag_ai_search_needs_service():
    cfg = Config()
    cfg.rag_backend = "ai_search"
    cfg.azure_search_service = ""
    assert build_rag(cfg) is None  # empty service => inert


def test_build_rag_qdrant_backend():
    cfg = Config()
    cfg.rag_backend = "qdrant"
    assert isinstance(build_rag(cfg), LocalQdrantRag)


def test_azure_row_drops_vector_and_keeps_text():
    # The embedding vector must NEVER be surfaced to the model; the text + score must be.
    hit = {
        "chunk": "Azure OpenAI is a managed service.",
        "title": "guia.pdf",
        "text_vector": [0.1, 0.2, 0.3],
        "@search.score": 0.87,
        "@search.reranker_score": 2.1,
    }
    row = AzureSearchRag._row(hit)
    assert "Azure OpenAI is a managed service." in row["text"]
    assert "0.1" not in row["text"] and "text_vector" not in row["text"]
    assert row["source"] == "guia.pdf"
    assert row["score"] == 0.87
