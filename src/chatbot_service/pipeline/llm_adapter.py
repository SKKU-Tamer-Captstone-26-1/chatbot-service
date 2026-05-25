"""Provider-neutral LLM adapter.

Do not put provider credentials here.
"""
from __future__ import annotations

import asyncio
import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

from chatbot_service.config import ChatbotConfig


class LLMAdapter(Protocol):
    async def generate(self, system_prompt: str, context_json: str, user_message: str) -> str: ...


class NoopLLMAdapter:
    async def generate(self, system_prompt: str, context_json: str, user_message: str) -> str:
        return "현재 확인 가능한 추천 데이터 기준으로 답변을 준비했어요."


class LLMGenerationError(RuntimeError):
    """Raised when the configured LLM endpoint cannot produce text."""


@dataclass(frozen=True)
class HuggingFaceTGIConfig:
    endpoint_url: str
    model: str
    api_key_env: str
    timeout_ms: int
    temperature: float
    max_tokens: int


class HuggingFaceTGIAdapter:
    """Call a Hugging Face TGI/OpenAI-compatible chat completions endpoint."""

    def __init__(self, config: HuggingFaceTGIConfig) -> None:
        self._config = config

    @classmethod
    def from_chatbot_config(cls, config: ChatbotConfig) -> HuggingFaceTGIAdapter:
        return cls(
            HuggingFaceTGIConfig(
                endpoint_url=config.llm_endpoint_url,
                model=config.llm_model,
                api_key_env=config.llm_api_key_env,
                timeout_ms=config.llm_timeout_ms,
                temperature=config.llm_temperature,
                max_tokens=config.llm_max_tokens,
            )
        )

    async def generate(self, system_prompt: str, context_json: str, user_message: str) -> str:
        return await asyncio.to_thread(
            self._generate_sync,
            system_prompt,
            context_json,
            user_message,
        )

    def _generate_sync(self, system_prompt: str, context_json: str, user_message: str) -> str:
        if not self._config.endpoint_url:
            raise LLMGenerationError("CHATBOT_LLM_ENDPOINT_URL is required for huggingface_tgi")

        payload = {
            "model": self._config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Grounded context JSON:\n{context_json}\n\n"
                        f"User message:\n{user_message}"
                    ),
                },
            ],
            "temperature": self._config.temperature,
            "max_tokens": self._config.max_tokens,
        }
        body = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        api_key = os.getenv(self._config.api_key_env, "")
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        request = urllib.request.Request(
            self._config.endpoint_url,
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=self._config.timeout_ms / 1000,
            ) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise LLMGenerationError(f"LLM endpoint returned HTTP {exc.code}: {detail}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise LLMGenerationError(f"LLM endpoint request failed: {exc}") from exc

        text = _extract_chat_completion_text(response_payload)
        if not text:
            raise LLMGenerationError("LLM endpoint returned no assistant content")
        return text


def build_llm_adapter(config: ChatbotConfig) -> LLMAdapter:
    if config.llm_provider == "huggingface_tgi":
        return HuggingFaceTGIAdapter.from_chatbot_config(config)
    return NoopLLMAdapter()


def _extract_chat_completion_text(payload: dict[str, object]) -> str:
    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content.strip()
    text = first.get("text")
    if isinstance(text, str):
        return text.strip()
    return ""
