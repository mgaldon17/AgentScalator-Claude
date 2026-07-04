"""`_mem0_config` mapping tests — pure Config→mem0-schema translation (no mem0, no I/O).

This is the unit-testability the ``build_store`` split buys: the config mapping can be
asserted without mem0 installed or Qdrant running.
"""

from __future__ import annotations

from agentmem.config import Config
from agentmem.constants import EmbedderProvider
from agentmem.store import _mem0_config


def test_local_embedder_maps_to_minimal_config():
    cfg = Config()  # defaults: local huggingface embedder
    mem = _mem0_config(cfg)

    assert mem["vector_store"]["provider"] == "qdrant"
    assert mem["vector_store"]["config"]["collection_name"] == cfg.collection
    assert mem["vector_store"]["config"]["embedding_model_dims"] == cfg.embedder_dims
    assert mem["embedder"]["provider"] == EmbedderProvider.HUGGINGFACE
    # a local provider carries only the model name (no base_url / api_key keys)
    assert mem["embedder"]["config"] == {"model": cfg.embedder_model}


def test_remote_embedder_carries_base_url_and_key():
    cfg = Config()
    cfg.embedder_provider = EmbedderProvider.OPENAI
    cfg.embedder_base_url = "https://api.example.com/v1"
    cfg.embedder_api_key = "sk-test"

    embedder = _mem0_config(cfg)["embedder"]["config"]
    assert embedder["openai_base_url"] == "https://api.example.com/v1"
    assert embedder["api_key"] == "sk-test"


def test_llm_backend_claude_maps_to_anthropic_keyless():
    # Default backend = claude → mem0 provider "anthropic", the Claude model, and NO api_key
    # (mem0 reads ANTHROPIC_API_KEY from env). No top_p (Anthropic rejects it with temperature).
    cfg = Config()  # llm_backend defaults to "claude"
    llm = _mem0_config(cfg)["llm"]
    assert llm["provider"] == "anthropic"
    assert llm["config"]["model"] == cfg.llm_claude_model
    assert "api_key" not in llm["config"]
    assert "top_p" not in llm["config"]
    assert llm["config"]["temperature"] == cfg.llm_temperature


def test_llm_backend_local_maps_to_openai_lmstudio():
    cfg = Config()
    cfg.llm_backend = "local"
    llm = _mem0_config(cfg)["llm"]
    assert llm["provider"] == "openai"
    assert llm["config"]["model"] == cfg.llm_local_model
    assert llm["config"]["openai_base_url"] == cfg.llm_local_base_url
    assert llm["config"]["api_key"]  # some placeholder key for LM Studio


def test_vector_store_qdrant_is_default():
    cfg = Config()  # rag_backend defaults to "qdrant"
    vs = _mem0_config(cfg)["vector_store"]
    assert vs["provider"] == "qdrant"
    assert vs["config"]["collection_name"] == cfg.collection


def test_vector_store_ai_search_is_keyless():
    # rag.backend: ai_search → lessons stored in Azure AI Search directly, keyless.
    cfg = Config()
    cfg.rag_backend = "ai_search"
    cfg.azure_search_service = "mysvc"
    vs = _mem0_config(cfg)["vector_store"]
    assert vs["provider"] == "azure_ai_search"
    assert vs["config"]["service_name"] == "mysvc"
    assert vs["config"]["collection_name"] == cfg.azure_search_lessons_index
    assert "api_key" not in vs["config"]
    assert vs["config"]["embedding_model_dims"] == cfg.embedder_dims
