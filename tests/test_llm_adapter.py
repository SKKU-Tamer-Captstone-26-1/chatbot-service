import json

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


def test_huggingface_tgi_auth_none_calls_openai_compatible_endpoint(monkeypatch):
    captured = {}

    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def read(self):
            return json.dumps(
                {"choices": [{"message": {"content": "추천 결과 기준 답변"}}]}
            ).encode("utf-8")

    def fake_urlopen(request, timeout):
        captured["request"] = request
        captured["timeout"] = timeout
        return FakeResponse()

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
    adapter = HuggingFaceTGIAdapter(
        HuggingFaceTGIConfig(
            endpoint_url="https://llm.example.com/v1/chat/completions",
            model="Qwen/Qwen2.5-7B-Instruct",
            auth_mode="none",
            api_key_env="HF_TOKEN",
            timeout_ms=8000,
            temperature=0.2,
            max_tokens=512,
        )
    )

    answer = adapter._generate_sync("system", '{"grounded_context": {}}', "추천해줘")

    body = json.loads(captured["request"].data.decode("utf-8"))
    headers = dict(captured["request"].header_items())
    assert answer == "추천 결과 기준 답변"
    assert captured["request"].full_url == "https://llm.example.com/v1/chat/completions"
    assert body["model"] == "Qwen/Qwen2.5-7B-Instruct"
    assert body["messages"][0]["role"] == "system"
    assert "Authorization" not in headers
    assert captured["timeout"] == 8.0
