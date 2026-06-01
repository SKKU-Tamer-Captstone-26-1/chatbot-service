from chatbot_service.config import load_config


def test_load_config_defaults(monkeypatch):
    for name in (
        "CHATBOT_SERVICE_ADDR",
        "PORT",
        "CHATBOT_AUTH_MODE",
        "CHATBOT_LLM_PROVIDER",
        "RECOMMENDATION_SERVICE_GRPC_ADDR",
        "RECOMMENDATION_SERVICE_URL",
        "RECOMMENDATION_SERVICE_GRPC_TLS",
        "CHATBOT_LLM_AUTH_MODE",
        "CHATBOT_REQUIRE_GROUNDED_FACTS",
        "CHATBOT_CACHE_BACKEND",
        "CHATBOT_CACHE_PROFILE_STATUS_TTL_SEC",
        "CHATBOT_CACHE_BEVERAGE_RECOMMENDATIONS_TTL_SEC",
        "CHATBOT_CACHE_VENUE_RECOMMENDATIONS_TTL_SEC",
        "CHATBOT_CACHE_PROMPT_CONTEXT_TTL_SEC",
        "CHATBOT_CACHE_LOCATION_BUCKET_PRECISION",
        "CHATBOT_STORE_CONVERSATIONS",
        "CHATBOT_ASYNC_CONVERSATION_PERSISTENCE",
        "CHATBOT_PERSISTENCE_QUEUE_MAX_SIZE",
        "CHATBOT_PERSISTENCE_RETRY_ATTEMPTS",
        "CHATBOT_METRICS_SNAPSHOT_PATH",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.service_addr == ":9100"
    assert config.auth_mode == "validate_token"
    assert config.auth_user_id_metadata_key == "x-user-id"
    assert config.auth_authorization_metadata_key == "authorization"
    assert config.recommendation_service_url == ""
    assert config.recommendation_service_grpc_tls is False
    assert config.llm_provider == "none"
    assert config.llm_auth_mode == "none"
    assert config.llm_api_key_env == "HF_TOKEN"
    assert config.llm_max_tokens == 512
    assert config.default_language == "ko"
    assert config.require_grounded_facts is True
    assert config.cache_backend == "memory"
    assert config.cache_profile_status_ttl_sec == 300
    assert config.cache_beverage_recommendations_ttl_sec == 300
    assert config.cache_venue_recommendations_ttl_sec == 120
    assert config.cache_prompt_context_ttl_sec == 120
    assert config.cache_location_bucket_precision == 3
    assert config.store_conversations is True
    assert config.storage_retention_days == 365
    assert config.async_conversation_persistence is True
    assert config.persistence_queue_max_size == 1000
    assert config.persistence_retry_attempts == 3
    assert config.metrics_snapshot_path == ""


def test_load_config_uses_cloud_run_port_when_service_addr_is_unset(monkeypatch):
    monkeypatch.delenv("CHATBOT_SERVICE_ADDR", raising=False)
    monkeypatch.setenv("PORT", "8080")

    config = load_config()

    assert config.service_addr == ":8080"


def test_boolean_config_accepts_false(monkeypatch):
    monkeypatch.setenv("CHATBOT_REQUIRE_GROUNDED_FACTS", "false")
    monkeypatch.setenv("CHATBOT_STORE_CONVERSATIONS", "0")
    monkeypatch.setenv("CHATBOT_ASYNC_CONVERSATION_PERSISTENCE", "off")

    config = load_config()

    assert config.require_grounded_facts is False
    assert config.store_conversations is False
    assert config.async_conversation_persistence is False


def test_recommendation_grpc_addr_and_tls_override_legacy_url(monkeypatch):
    monkeypatch.setenv("RECOMMENDATION_SERVICE_URL", "https://legacy.example.com:443")
    monkeypatch.setenv("RECOMMENDATION_SERVICE_GRPC_ADDR", "recommendation.example.com:443")
    monkeypatch.setenv("RECOMMENDATION_SERVICE_GRPC_TLS", "true")

    config = load_config()

    assert config.recommendation_service_url == "recommendation.example.com:443"
    assert config.recommendation_service_grpc_tls is True


def test_llm_provider_defaults_to_openai_compatible_adapter_when_endpoint_is_set(monkeypatch):
    monkeypatch.delenv("CHATBOT_LLM_PROVIDER", raising=False)
    monkeypatch.setenv("CHATBOT_LLM_ENDPOINT_URL", "https://llm.example.com/v1/chat/completions")
    monkeypatch.setenv("CHATBOT_LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct")

    config = load_config()

    assert config.llm_provider == "huggingface_tgi"
    assert config.llm_auth_mode == "none"
