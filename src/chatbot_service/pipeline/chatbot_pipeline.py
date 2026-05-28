from __future__ import annotations

import hashlib
import json
import logging
import time

from chatbot_service.cache import Cache
from chatbot_service.domain.schemas import CallerContext, ChatbotAnswer, ChatbotRequest
from chatbot_service.metrics import MetricsRecorder
from chatbot_service.pipeline.context_builder import RecommendationContextBuilder
from chatbot_service.pipeline.guardrails import Guardrails
from chatbot_service.pipeline.intent_classifier import IntentClassifier
from chatbot_service.pipeline.llm_adapter import LLMAdapter
from chatbot_service.pipeline.prompt_builder import PromptBuilder
from chatbot_service.pipeline.response_builder import ResponseBuilder
from chatbot_service.pipeline.response_verifier import ResponseVerificationError, ResponseVerifier
from chatbot_service.storage.conversation_repository import ConversationRepository

LOGGER = logging.getLogger(__name__)


class ChatbotPipeline:
    def __init__(
        self,
        *,
        intent_classifier: IntentClassifier,
        context_builder: RecommendationContextBuilder,
        guardrails: Guardrails,
        prompt_builder: PromptBuilder,
        llm_adapter: LLMAdapter,
        response_verifier: ResponseVerifier,
        response_builder: ResponseBuilder,
        conversation_repository: ConversationRepository | None = None,
        metrics: MetricsRecorder | None = None,
        prompt_context_cache: Cache | None = None,
        prompt_context_cache_ttl_sec: int = 0,
    ) -> None:
        self._intent_classifier = intent_classifier
        self._context_builder = context_builder
        self._guardrails = guardrails
        self._prompt_builder = prompt_builder
        self._llm_adapter = llm_adapter
        self._response_verifier = response_verifier
        self._response_builder = response_builder
        self._conversation_repository = conversation_repository
        self._metrics = metrics or MetricsRecorder()
        self._prompt_context_cache = prompt_context_cache
        self._prompt_context_cache_ttl_sec = prompt_context_cache_ttl_sec

    async def ask(self, request: ChatbotRequest, caller: CallerContext) -> ChatbotAnswer:
        started_at = time.perf_counter()
        status = "error"
        try:
            intent = self._intent_classifier.classify(request.message)
            context = await self._context_builder.build(intent, request, caller)

            guarded = self._guardrails.enforce(intent, context)
            if guarded is not None:
                status = guarded.status.value
                await self._persist_if_configured(request, caller, guarded)
                return guarded

            system_prompt = self._prompt_builder.build_system_prompt()
            context_json, context_hash = await self._build_context_json(context)
            with self._metrics.timer("llm.call"):
                generated = await self._llm_adapter.generate(
                    system_prompt,
                    context_json,
                    request.message,
                )
            try:
                verified = self._response_verifier.verify(generated, context)
            except ResponseVerificationError:
                fallback = self._guardrails.enforce(intent, context)
                if fallback is not None:
                    fallback.prompt_context_hash = context_hash
                    status = fallback.status.value
                    await self._persist_if_configured(request, caller, fallback)
                    return fallback
                raise

            answer = self._response_builder.build_from_grounded_text(intent, verified, context)
            answer.prompt_context_hash = context_hash
            status = answer.status.value
            await self._persist_if_configured(request, caller, answer)
            return answer
        finally:
            self._metrics.observe("chatbot.ask", time.perf_counter() - started_at, status=status)

    async def _build_context_json(self, context: object) -> tuple[str, str]:
        context_hash = _context_hash(context)
        cache_key = f"prompt_context:{getattr(context, 'intent', '')}:{context_hash}"
        if self._is_prompt_context_cacheable(context):
            cached = await self._prompt_context_cache_get(cache_key)
            if isinstance(cached, str):
                self._metrics.increment("prompt_context.cache_hit")
                return cached, context_hash
            self._metrics.increment("prompt_context.cache_miss")

        context_json = self._prompt_builder.build_context_json(context)
        if self._is_prompt_context_cacheable(context) and self._prompt_context_cache is not None:
            await self._prompt_context_cache_set(
                cache_key,
                context_json,
                self._prompt_context_cache_ttl_sec,
            )
        return context_json, context_hash

    def _is_prompt_context_cacheable(self, context: object) -> bool:
        if self._prompt_context_cache is None or self._prompt_context_cache_ttl_sec <= 0:
            return False
        facts = getattr(context, "facts", {})
        missing_facts = getattr(context, "missing_facts", [])
        confidence = float(getattr(context, "confidence", 0.0) or 0.0)
        profile_status = str(facts.get("profile_status", "")) if isinstance(facts, dict) else ""
        if not facts or missing_facts or confidence <= 0:
            return False
        return profile_status in {"", "PROFILE_STATUS_ACTIVE", "ACTIVE"}

    async def _prompt_context_cache_get(self, key: str) -> object | None:
        if self._prompt_context_cache is None:
            return None
        try:
            return await self._prompt_context_cache.get(key)
        except Exception:
            self._metrics.increment("prompt_context.cache_error", action="get")
            LOGGER.exception("prompt context cache get failed")
            return None

    async def _prompt_context_cache_set(self, key: str, value: str, ttl_sec: int) -> None:
        if self._prompt_context_cache is None:
            return
        try:
            await self._prompt_context_cache.set(key, value, ttl_sec)
        except Exception:
            self._metrics.increment("prompt_context.cache_error", action="set")
            LOGGER.exception("prompt context cache set failed")

    async def _persist_if_configured(
        self,
        request: ChatbotRequest,
        caller: CallerContext,
        answer: ChatbotAnswer,
    ) -> None:
        if self._conversation_repository is None:
            return
        conversation_id = await self._conversation_repository.create_or_get_conversation(
            user_id=caller.user_id,
            conversation_id=request.conversation_id or None,
            screen_context=request.screen_context,
            metadata={"client_context": request.client_context},
        )
        answer.conversation_id = conversation_id
        await self._conversation_repository.append_message(
            conversation_id=conversation_id,
            role="USER",
            content=request.message,
            metadata={"screen_context": request.screen_context},
        )
        assistant_message_id = await self._conversation_repository.append_message(
            conversation_id=conversation_id,
            role="ASSISTANT",
            content=answer.answer,
            metadata={
                "intent": answer.intent.value,
                "confidence": answer.confidence,
                "status": answer.status.value,
                "refused": answer.refused,
                "refusal_reason": answer.refusal_reason,
                "cards": [card.__dict__ for card in answer.cards],
                "used_sources": answer.used_sources,
                "missing_facts": answer.missing_facts,
                "profile_status": answer.profile_status,
                "prompt_context_hash": answer.prompt_context_hash,
            },
        )
        answer.message_id = assistant_message_id
        await self._conversation_repository.store_retrieval_trace(
            message_id=assistant_message_id,
            trace={
                "used_sources": answer.used_sources,
                "missing_facts": answer.missing_facts,
                "profile_status": answer.profile_status,
                "prompt_context_hash": answer.prompt_context_hash,
            },
        )


def _context_hash(context: object) -> str:
    payload = {
        "intent": getattr(context, "intent", ""),
        "facts": getattr(context, "facts", {}),
        "missing_facts": getattr(context, "missing_facts", []),
        "confidence": getattr(context, "confidence", 0.0),
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
