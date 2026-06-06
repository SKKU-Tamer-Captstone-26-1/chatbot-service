"""Provider-neutral LLM adapter.

Do not put provider credentials here.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import urllib.error
import urllib.parse
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
    auth_mode: str
    api_key_env: str
    timeout_ms: int
    temperature: float
    max_tokens: int
    serverless_auth_mode: str = "none"
    serverless_audience: str = ""
    serverless_token_env: str = "GOOGLE_ID_TOKEN"


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
                auth_mode=config.llm_auth_mode,
                api_key_env=config.llm_api_key_env,
                timeout_ms=config.llm_timeout_ms,
                temperature=config.llm_temperature,
                max_tokens=config.llm_max_tokens,
                serverless_auth_mode=config.llm_serverless_auth_mode,
                serverless_audience=config.llm_serverless_audience,
                serverless_token_env=config.llm_serverless_token_env,
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
        auth_mode = self._config.auth_mode.strip().lower().replace("-", "_")
        if auth_mode == "bearer_env":
            api_key = os.getenv(self._config.api_key_env, "")
            if not api_key:
                raise LLMGenerationError(
                    f"{self._config.api_key_env} is required when CHATBOT_LLM_AUTH_MODE=bearer_env"
                )
            headers["Authorization"] = f"Bearer {api_key}"
        elif auth_mode not in {"", "none"}:
            raise LLMGenerationError(f"Unsupported CHATBOT_LLM_AUTH_MODE: {self._config.auth_mode}")

        serverless_auth_mode = self._config.serverless_auth_mode.strip().lower().replace("-", "_")
        if serverless_auth_mode == "env":
            token = os.getenv(self._config.serverless_token_env, "").strip()
            if not token:
                raise LLMGenerationError(
                    f"{self._config.serverless_token_env} is required for LLM serverless auth"
                )
            headers["X-Serverless-Authorization"] = f"Bearer {token}"
        elif serverless_auth_mode == "google_id_token":
            token = _fetch_google_id_token(self._config.serverless_audience)
            headers["X-Serverless-Authorization"] = f"Bearer {token}"
        elif serverless_auth_mode not in {"", "none"}:
            raise LLMGenerationError(
                "Unsupported CHATBOT_LLM_SERVERLESS_AUTH_MODE: "
                f"{self._config.serverless_auth_mode}"
            )

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


_TOKEN_CACHE: dict[str, tuple[str, float]] = {}


def _fetch_google_id_token(audience: str, *, timeout_sec: float = 1.0) -> str:
    if not audience:
        raise LLMGenerationError("CHATBOT_LLM_SERVERLESS_AUDIENCE is required")
    now = time.time()
    cached = _TOKEN_CACHE.get(audience)
    if cached is not None and now < cached[1]:
        return cached[0]

    query = urllib.parse.urlencode({"audience": audience, "format": "full"})
    request = urllib.request.Request(
        f"http://metadata/computeMetadata/v1/instance/service-accounts/default/identity?{query}",
        headers={"Metadata-Flavor": "Google"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout_sec) as response:
            token = response.read().decode("utf-8").strip()
    except (urllib.error.URLError, TimeoutError) as exc:
        raise LLMGenerationError("failed to fetch LLM Cloud Run ID token") from exc
    if not token:
        raise LLMGenerationError("metadata server returned empty LLM Cloud Run ID token")
    _TOKEN_CACHE[audience] = (token, now + 3000)
    return token
