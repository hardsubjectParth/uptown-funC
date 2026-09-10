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

    # When true, a job whose answer is not backed by retrieved evidence fails
    # verification. Off by default: some task types have no corpus to ground
    # against. The `evidence_grounded` check is reported either way.
    require_evidence = os.getenv('REQUIRE_EVIDENCE', 'false').lower() == 'true'

    # Use the `router` model to classify tasks instead of regex. Falls back to
    # regex when the model is unavailable or returns an unknown label.
    use_model_router = os.getenv('USE_MODEL_ROUTER', 'false').lower() == 'true'
    router_model_alias = os.getenv('ROUTER_MODEL_ALIAS', 'router')

    # Retrieved document text is untrusted input. Detected prompt-injection
    # attempts are always recorded on the job and emitted as an event; when this
    # is true the offending chunks are dropped instead of merely fenced off.
    block_on_injection = os.getenv('BLOCK_ON_INJECTION', 'false').lower() == 'true'

    # Outbound email. Without SMTP_HOST, send_email writes a real .eml artifact
    # and delivers nothing -- the correct default for an air-gapped deployment.
    # The policy engine routes send_email through human approval either way.
    smtp = {
        'host': os.getenv('SMTP_HOST', ''),
        'port': os.getenv('SMTP_PORT', '587'),
        'user': os.getenv('SMTP_USER', ''),
        'password': os.getenv('SMTP_PASSWORD', ''),
        'from': os.getenv('SMTP_FROM', ''),
        'use_tls': os.getenv('SMTP_USE_TLS', 'true').lower() == 'true',
    }

    # Aliases the RAG layer requests from the OpenAI-compatible endpoint. These
    # must match a `model_alias` in the model registry and llama-swap config.
    embedding_model_alias = os.getenv('EMBEDDING_MODEL_ALIAS', 'embedder')
    vision_model_alias = os.getenv('VISION_MODEL_ALIAS', 'vision')

    # Second-stage retrieval scoring: retrieval overfetches by RERANK_OVERFETCH
    # and rescores with a cross-encoder, which measurably beats embedding cosine
    # alone. Set to empty to disable. Requires the `reranker` model to be served.
    rerank_model_alias = os.getenv('RERANK_MODEL_ALIAS', 'reranker')
    rerank_overfetch = int(os.getenv('RERANK_OVERFETCH', '4'))

    rag_url = os.getenv('RAG_URL', '')
    max_iterations = int(os.getenv('MAX_ITERATIONS', '3'))
    max_tool_calls = int(os.getenv('MAX_TOOL_CALLS', '12'))
    job_timeout_seconds = int(os.getenv('JOB_TIMEOUT_SECONDS', '120'))
    tool_timeout_seconds = int(os.getenv('TOOL_TIMEOUT_SECONDS', '30'))


settings = Settings()
