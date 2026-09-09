import os


class Settings:
    app_name = os.getenv('APP_NAME', 'Sovereign Agent Orchestrator')
    api_host = os.getenv('API_HOST', '0.0.0.0')
    api_port = int(os.getenv('API_PORT', '8080'))
    database_url = os.getenv('DATABASE_URL', 'sqlite:///./orchestrator.db')
    workspace_root = os.getenv('WORKSPACE_ROOT', './workspace')

    # Model serving. MODEL_MODE selects the adapter:
    #   fake      - deterministic stub, no server required (default, used in tests)
    #   llamaswap - OpenAI-compatible endpoint (llama-swap in front of llama.cpp,
    #               or any /v1 server such as vLLM)
    model_mode = os.getenv('MODEL_MODE', 'fake')
    llm_base_url = os.getenv('LLM_BASE_URL', 'http://localhost:8080/v1')
    llm_api_key = os.getenv('LLM_API_KEY', '')
    model_registry_path = os.getenv('MODEL_REGISTRY_PATH', 'config/model_registry.yaml')

    # Qwen3.5/3.6 are thinking models. Thinking is off by default so the model
    # returns the answer rather than spending the token budget on reasoning
    # (which leaves `content` empty). Set LLM_ENABLE_THINKING=true for higher
    # reasoning quality, and raise LLM_MAX_TOKENS to match.
    llm_enable_thinking = os.getenv('LLM_ENABLE_THINKING', 'false').lower() == 'true'
    llm_max_tokens = int(os.getenv('LLM_MAX_TOKENS', '2048'))

    # Aliases the RAG layer requests from the OpenAI-compatible endpoint. These
    # must match a `model_alias` in the model registry and llama-swap config.
    embedding_model_alias = os.getenv('EMBEDDING_MODEL_ALIAS', 'embedder')
    vision_model_alias = os.getenv('VISION_MODEL_ALIAS', 'vision')

    rag_url = os.getenv('RAG_URL', '')
    max_iterations = int(os.getenv('MAX_ITERATIONS', '3'))
    max_tool_calls = int(os.getenv('MAX_TOOL_CALLS', '12'))
    job_timeout_seconds = int(os.getenv('JOB_TIMEOUT_SECONDS', '120'))
    tool_timeout_seconds = int(os.getenv('TOOL_TIMEOUT_SECONDS', '30'))


settings = Settings()
