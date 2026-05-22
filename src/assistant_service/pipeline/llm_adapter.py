"""Provider-neutral LLM adapter.

Do not put provider credentials here.
"""
from typing import Protocol


class LLMAdapter(Protocol):
    async def generate(self, system_prompt: str, context_json: str, user_message: str) -> str: ...


class NoopLLMAdapter:
    async def generate(self, system_prompt: str, context_json: str, user_message: str) -> str:
        return "현재 확인 가능한 추천 데이터 기준으로 답변을 준비했어요."
