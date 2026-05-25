from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

from chatbot_service.server import load_generated_chatbot_grpc
from chatbot_service.validation.config import ValidationConfig
from chatbot_service.validation.summary import ValidationRunSummary, summarize_run


@dataclass(frozen=True)
class SmokeResult:
    health_ok: bool
    ask_ok: bool
    conversation_ok: bool
    feedback_ok: bool
    conversation_id: str
    message_id: str
    errors: list[str]

    @property
    def passed(self) -> bool:
        return self.health_ok and self.ask_ok and self.conversation_ok and self.feedback_ok


async def run_smoke_validation(config: ValidationConfig) -> SmokeResult:
    import grpc

    channel = _build_channel(config)
    generated = load_generated_chatbot_grpc()
    stub = generated.chatbot_pb2_grpc.ChatbotServiceStub(channel)
    errors: list[str] = []
    health_ok = await _check_health(channel, config, errors)

    conversation_id = ""
    message_id = ""
    ask_ok = False
    conversation_ok = False
    feedback_ok = False
    try:
        ask_response = await stub.AskChatbot(
            _beverage_request(generated.chatbot_pb2, config),
            metadata=config.metadata,
            timeout=config.timeout_sec,
        )
        _assert_grounded_response(ask_response, generated.chatbot_pb2)
        ask_ok = bool(ask_response.answer)
        conversation_id = ask_response.conversation_id
        message_id = ask_response.message_id
        if not ask_ok:
            errors.append("AskChatbot returned no answer")
    except grpc.RpcError as exc:
        errors.append(f"AskChatbot failed: {exc.details() or exc.code().name}")

    if conversation_id:
        try:
            conversation = await stub.GetConversation(
                generated.chatbot_pb2.GetConversationRequest(
                    conversation_id=conversation_id,
                    page_size=10,
                ),
                metadata=config.metadata,
                timeout=config.timeout_sec,
            )
            conversation_ok = bool(conversation.messages)
            if not conversation_ok:
                errors.append("GetConversation returned no messages")
        except grpc.RpcError as exc:
            errors.append(f"GetConversation failed: {exc.details() or exc.code().name}")
    else:
        errors.append("AskChatbot returned no conversation_id")

    if message_id:
        try:
            feedback = await stub.RecordChatbotFeedback(
                generated.chatbot_pb2.RecordChatbotFeedbackRequest(
                    message_id=message_id,
                    event_type=generated.chatbot_pb2.CHATBOT_FEEDBACK_EVENT_TYPE_HELPFUL,
                    idempotency_key=f"validation-{int(time.time() * 1000)}",
                ),
                metadata=config.metadata,
                timeout=config.timeout_sec,
            )
            feedback_ok = bool(feedback.recorded)
            if not feedback_ok:
                errors.append("RecordChatbotFeedback did not record feedback")
        except grpc.RpcError as exc:
            errors.append(f"RecordChatbotFeedback failed: {exc.details() or exc.code().name}")
    else:
        errors.append("AskChatbot returned no message_id")

    await channel.close()
    return SmokeResult(
        health_ok=health_ok,
        ask_ok=ask_ok,
        conversation_ok=conversation_ok,
        feedback_ok=feedback_ok,
        conversation_id=conversation_id,
        message_id=message_id,
        errors=errors,
    )


async def run_load_validation(config: ValidationConfig, *, name: str) -> ValidationRunSummary:
    channel = _build_channel(config)
    generated = load_generated_chatbot_grpc()
    stub = generated.chatbot_pb2_grpc.ChatbotServiceStub(channel)
    semaphore = asyncio.Semaphore(max(1, config.concurrency))
    latencies: list[float] = []
    errors: list[str] = []

    async def run_one(index: int) -> None:
        async with semaphore:
            request = _load_request(generated.chatbot_pb2, config, index)
            started_at = time.perf_counter()
            try:
                response = await stub.AskChatbot(
                    request,
                    metadata=config.metadata,
                    timeout=config.timeout_sec,
                )
                _assert_grounded_response(response, generated.chatbot_pb2)
                latencies.append((time.perf_counter() - started_at) * 1000)
            except Exception as exc:
                errors.append(_error_name(exc))

    await asyncio.gather(*(run_one(index) for index in range(max(1, config.requests))))
    await channel.close()
    return summarize_run(name, latencies, errors)


def _build_channel(config: ValidationConfig) -> Any:
    import grpc

    if config.secure:
        return grpc.aio.secure_channel(config.target, grpc.ssl_channel_credentials())
    return grpc.aio.insecure_channel(config.target)


async def _check_health(channel: Any, config: ValidationConfig, errors: list[str]) -> bool:
    try:
        from grpc_health.v1 import health_pb2, health_pb2_grpc

        generated = load_generated_chatbot_grpc()
        service_name = generated.chatbot_pb2.DESCRIPTOR.services_by_name[
            "ChatbotService"
        ].full_name
        stub = health_pb2_grpc.HealthStub(channel)
        response = await stub.Check(
            health_pb2.HealthCheckRequest(service=service_name),
            timeout=config.timeout_sec,
        )
        if response.status != health_pb2.HealthCheckResponse.SERVING:
            errors.append(f"health status is not SERVING: {response.status}")
            return False
        return True
    except Exception as exc:
        errors.append(f"health check failed: {_error_name(exc)}")
        return False


def _beverage_request(chatbot_pb2: Any, config: ValidationConfig) -> Any:
    return chatbot_pb2.AskChatbotRequest(
        message=config.beverage_message,
        screen_context=chatbot_pb2.SCREEN_CONTEXT_HOME,
        category=config.category,
        beverage_limit=config.beverage_limit,
        budget_mode=_enum_value(chatbot_pb2, config.budget_mode, "BUDGET_MODE_SOFT"),
    )


def _venue_request(chatbot_pb2: Any, config: ValidationConfig, index: int) -> Any:
    offset = (index % 5) * 0.001
    return chatbot_pb2.AskChatbotRequest(
        message=config.venue_message,
        screen_context=chatbot_pb2.SCREEN_CONTEXT_MAP,
        selected_beverage_id=config.selected_beverage_id,
        lat=config.lat + offset,
        lng=config.lng + offset,
        radius_m=config.radius_m,
        venue_limit=config.venue_limit,
        budget_mode=_enum_value(chatbot_pb2, config.budget_mode, "BUDGET_MODE_SOFT"),
    )


def _load_request(chatbot_pb2: Any, config: ValidationConfig, index: int) -> Any:
    if index % 3 == 0:
        return _venue_request(chatbot_pb2, config, index)
    return _beverage_request(chatbot_pb2, config)


def _assert_grounded_response(response: Any, chatbot_pb2: Any) -> None:
    if response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_ANSWERED:
        if not response.cards:
            raise ValueError("answered response had no cards")
        _assert_answered_cards_grounded(response, chatbot_pb2)
    elif response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_INSUFFICIENT_DATA:
        if not response.missing_facts:
            raise ValueError("insufficient-data response had no missing_facts")
    elif response.status == chatbot_pb2.CHATBOT_RESPONSE_STATUS_REFUSED:
        if not response.refused:
            raise ValueError("refused response did not set refused=true")
    else:
        raise ValueError("response status was unspecified")


def _assert_answered_cards_grounded(response: Any, chatbot_pb2: Any) -> None:
    beverage_result_ids = set(response.used_sources.beverage_result_ids)
    venue_result_ids = set(response.used_sources.venue_result_ids)
    beverage_ranks: list[int] = []
    venue_ranks: list[int] = []
    for card in response.cards:
        if card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION:
            if card.WhichOneof("detail") != "beverage_recommendation":
                raise ValueError("beverage card had no beverage_recommendation detail")
            detail = card.beverage_recommendation
            _assert_result_id("beverage", detail.result_id, beverage_result_ids)
            beverage_ranks.append(detail.rank)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION:
            if card.WhichOneof("detail") != "venue_recommendation":
                raise ValueError("venue card had no venue_recommendation detail")
            detail = card.venue_recommendation
            _assert_result_id("venue", detail.result_id, venue_result_ids)
            venue_ranks.append(detail.rank)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_PURCHASE_OPTION:
            if card.WhichOneof("detail") != "purchase_option":
                raise ValueError("purchase card had no purchase_option detail")
            detail = card.purchase_option
            _assert_result_id("purchase", detail.result_id, venue_result_ids)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_COMPARISON:
            if card.WhichOneof("detail") != "comparison":
                raise ValueError("comparison card had no comparison detail")
            for option in card.comparison.options:
                _assert_result_id("comparison purchase", option.result_id, venue_result_ids)
        elif card.card_type == chatbot_pb2.CHATBOT_CARD_TYPE_PROFILE_STATUS:
            if card.WhichOneof("detail") != "profile_status":
                raise ValueError("profile card had no profile_status detail")
        else:
            raise ValueError("answered response used unsupported card type")
    if beverage_ranks and beverage_ranks != sorted(beverage_ranks):
        raise ValueError("beverage recommendation card ranks were not ordered")
    if venue_ranks and venue_ranks != sorted(venue_ranks):
        raise ValueError("recommendation card ranks were not ordered")


def _assert_result_id(kind: str, result_id: str, used_result_ids: set[str]) -> None:
    if not result_id:
        raise ValueError(f"{kind} card had no result_id")
    if not used_result_ids:
        raise ValueError(f"{kind} card had no used_sources result IDs")
    if result_id not in used_result_ids:
        raise ValueError(f"{kind} card result_id was not present in used_sources")


def _enum_value(module: Any, name: str, default: str) -> int:
    return int(getattr(module, name, getattr(module, default)))


def _error_name(exc: Exception) -> str:
    code = getattr(exc, "code", None)
    if callable(code):
        try:
            return code().name
        except Exception:
            pass
    return type(exc).__name__
