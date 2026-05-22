from chatbot_service.config import load_config


def test_load_config_defaults(monkeypatch):
    for name in (
        "CHATBOT_SERVICE_ADDR",
        "CHATBOT_AUTH_MODE",
        "CHATBOT_LLM_PROVIDER",
        "CHATBOT_REQUIRE_GROUNDED_FACTS",
        "CHATBOT_STORE_CONVERSATIONS",
    ):
        monkeypatch.delenv(name, raising=False)

    config = load_config()

    assert config.service_addr == ":9100"
    assert config.auth_mode == "validate_token"
    assert config.llm_provider == "none"
    assert config.default_language == "ko"
    assert config.require_grounded_facts is True
    assert config.store_conversations is True


def test_boolean_config_accepts_false(monkeypatch):
    monkeypatch.setenv("CHATBOT_REQUIRE_GROUNDED_FACTS", "false")
    monkeypatch.setenv("CHATBOT_STORE_CONVERSATIONS", "0")

    config = load_config()

    assert config.require_grounded_facts is False
    assert config.store_conversations is False
