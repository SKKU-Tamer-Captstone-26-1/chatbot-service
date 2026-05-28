import pytest

from chatbot_service.pipeline.llm_adapter import (
    HuggingFaceTGIAdapter,
    HuggingFaceTGIConfig,
    LLMGenerationError,
    _extract_chat_completion_text,
)


def test_extract_chat_completion_text_from_openai_compatible_payload():
    payload = {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "추천 결과 기준으로 답변드릴게요.",
                }
            }
        ]
    }

    assert _extract_chat_completion_text(payload) == "추천 결과 기준으로 답변드릴게요."


def test_huggingface_tgi_requires_api_key_for_bearer_env(monkeypatch):
    monkeypatch.delenv("HF_TOKEN", raising=False)
    adapter = HuggingFaceTGIAdapter(
        HuggingFaceTGIConfig(
            endpoint_url="https://llm.example.com/v1/chat/completions",
            model="chatbot",
            auth_mode="bearer_env",
            api_key_env="HF_TOKEN",
            timeout_ms=8000,
            temperature=0.2,
            max_tokens=512,
        )
    )

    with pytest.raises(LLMGenerationError, match="HF_TOKEN"):
        adapter._generate_sync("system", "{}", "message")
