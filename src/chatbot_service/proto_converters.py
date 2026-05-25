from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from google.protobuf import json_format

from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotCard, ChatbotRequest


def request_from_proto(request: Any, chatbot_pb2: Any) -> ChatbotRequest:
    return ChatbotRequest(
        conversation_id=request.conversation_id,
        message=request.message,
        lat=_optional_field(request, "lat"),
        lng=_optional_field(request, "lng"),
        radius_m=_optional_field(request, "radius_m"),
        budget_hint_krw=_optional_field(request, "budget_hint_krw"),
        screen_context=_enum_name(chatbot_pb2.ScreenContext, request.screen_context),
        selected_beverage_id=request.selected_beverage_id,
        category=request.category,
        beverage_limit=request.beverage_limit,
        venue_limit=request.venue_limit,
        budget_mode=_enum_name(chatbot_pb2.BudgetMode, request.budget_mode),
        client_context=struct_to_dict(request.client_context),
    )


def answer_to_proto(answer: ChatbotAnswer, chatbot_pb2: Any) -> Any:
    response = chatbot_pb2.AskChatbotResponse(
        conversation_id=answer.conversation_id,
        message_id=answer.message_id,
        intent=_enum_value(chatbot_pb2, _intent_name(answer.intent)),
        answer=answer.answer,
        confidence=answer.confidence,
        refused=answer.refused,
        refusal_reason=answer.refusal_reason,
        missing_facts=answer.missing_facts,
        follow_up_questions=answer.follow_up_questions,
        profile_status=_enum_value(chatbot_pb2, _profile_status_name(answer.profile_status)),
        status=_enum_value(chatbot_pb2, _response_status_name(answer.status.value)),
    )
    response.created_at.FromDatetime(datetime.now(UTC))
    response.used_sources.CopyFrom(used_sources_to_proto(answer.used_sources, chatbot_pb2))
    response.cards.extend([card_to_proto(card, chatbot_pb2) for card in answer.cards])
    return response


def conversation_message_to_proto(message: dict[str, Any], chatbot_pb2: Any) -> Any:
    metadata = dict(message.get("metadata") or message.get("metadata_json") or {})
    proto = chatbot_pb2.ChatbotConversationMessage(
        message_id=str(message.get("message_id", "")),
        role=_enum_value(chatbot_pb2, _role_name(str(message.get("role", "")))),
        content=str(message.get("content", "")),
        intent=_enum_value(
            chatbot_pb2,
            _intent_name(str(metadata.get("intent") or message.get("intent") or "")),
        ),
    )
    created_at = message.get("created_at")
    if isinstance(created_at, datetime):
        proto.created_at.FromDatetime(_to_aware_utc(created_at))
    cards = metadata.get("cards", [])
    if isinstance(cards, list):
        proto.cards.extend([card_to_proto(_dict_to_card(card), chatbot_pb2) for card in cards])
    used_sources = metadata.get("used_sources", {})
    if isinstance(used_sources, dict):
        proto.used_sources.CopyFrom(used_sources_to_proto(used_sources, chatbot_pb2))
    return proto


def card_to_proto(card: ChatbotCard, chatbot_pb2: Any) -> Any:
    proto = chatbot_pb2.ChatbotCard(
        card_type=_enum_value(chatbot_pb2, card.card_type),
        title=card.title,
        subtitle=card.subtitle,
        display_reason=card.display_reason,
        reason_codes=card.reason_codes,
    )
    dict_to_struct(card.metadata, proto.metadata)

    detail = card.detail or {}
    if "beverage_recommendation" in detail:
        json_format.ParseDict(
            detail["beverage_recommendation"],
            proto.beverage_recommendation,
            ignore_unknown_fields=True,
        )
    elif "venue_recommendation" in detail:
        json_format.ParseDict(
            detail["venue_recommendation"],
            proto.venue_recommendation,
            ignore_unknown_fields=True,
        )
    elif "purchase_option" in detail:
        json_format.ParseDict(
            detail["purchase_option"],
            proto.purchase_option,
            ignore_unknown_fields=True,
        )
    elif "comparison" in detail:
        json_format.ParseDict(detail["comparison"], proto.comparison, ignore_unknown_fields=True)
    elif "profile_status" in detail:
        json_format.ParseDict(
            detail["profile_status"],
            proto.profile_status,
            ignore_unknown_fields=True,
        )
    return proto


def used_sources_to_proto(used_sources: dict[str, Any], chatbot_pb2: Any) -> Any:
    proto = chatbot_pb2.UsedSources(
        recommendation_request_id=str(used_sources.get("recommendation_request_id", "")),
        profile_revision=int(used_sources.get("profile_revision", 0) or 0),
        beverage_ids=[str(item) for item in used_sources.get("beverage_ids", [])],
        place_ids=[str(item) for item in used_sources.get("place_ids", [])],
        menu_item_ids=[str(item) for item in used_sources.get("menu_item_ids", [])],
        inventory_item_ids=[str(item) for item in used_sources.get("inventory_item_ids", [])],
        price_offer_ids=[str(item) for item in used_sources.get("price_offer_ids", [])],
        reason_codes=[str(item) for item in used_sources.get("reason_codes", [])],
        beverage_recommendation_request_id=str(
            used_sources.get("beverage_recommendation_request_id", "")
        ),
        venue_recommendation_request_id=str(
            used_sources.get("venue_recommendation_request_id", "")
        ),
        beverage_result_ids=[str(item) for item in used_sources.get("beverage_result_ids", [])],
        venue_result_ids=[str(item) for item in used_sources.get("venue_result_ids", [])],
        profile_status=_enum_value(
            chatbot_pb2,
            _profile_status_name(str(used_sources.get("profile_status", ""))),
        ),
    )
    metadata = used_sources.get("metadata", {})
    if isinstance(metadata, dict):
        dict_to_struct(metadata, proto.metadata)
    return proto


def struct_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    return dict(json_format.MessageToDict(value, preserving_proto_field_name=True))


def dict_to_struct(value: dict[str, Any], target: Any) -> None:
    json_format.ParseDict(value or {}, target)


def _optional_field(message: Any, name: str) -> Any:
    try:
        return getattr(message, name) if message.HasField(name) else None
    except ValueError:
        value = getattr(message, name)
        return value if value not in {"", 0} else None


def _enum_name(enum_type: Any, value: int) -> str:
    try:
        return enum_type.Name(value)
    except ValueError:
        return ""


def _enum_value(module: Any, name: str) -> int:
    return int(getattr(module, name, 0))


def _intent_name(intent: ChatbotIntent | str) -> str:
    raw = intent.value if isinstance(intent, ChatbotIntent) else str(intent)
    if raw.startswith("CHATBOT_INTENT_"):
        return raw
    return f"CHATBOT_INTENT_{raw}" if raw else "CHATBOT_INTENT_UNSPECIFIED"


def _response_status_name(status: str) -> str:
    if status.startswith("CHATBOT_RESPONSE_STATUS_"):
        return status
    return f"CHATBOT_RESPONSE_STATUS_{status}" if status else "CHATBOT_RESPONSE_STATUS_UNSPECIFIED"


def _profile_status_name(status: str) -> str:
    if status.startswith("PROFILE_STATUS_"):
        return status
    return f"PROFILE_STATUS_{status}" if status else "PROFILE_STATUS_UNSPECIFIED"


def _role_name(role: str) -> str:
    normalized = role.upper()
    if normalized == "CHATBOT":
        normalized = "ASSISTANT"
    if normalized.startswith("CHATBOT_MESSAGE_ROLE_"):
        return normalized
    if not normalized:
        return "CHATBOT_MESSAGE_ROLE_UNSPECIFIED"
    return f"CHATBOT_MESSAGE_ROLE_{normalized}"


def _dict_to_card(value: dict[str, Any]) -> ChatbotCard:
    return ChatbotCard(
        card_type=str(value.get("card_type", "")),
        title=str(value.get("title", "")),
        subtitle=str(value.get("subtitle", "")),
        display_reason=str(value.get("display_reason", "")),
        score=value.get("score"),
        price_krw=value.get("price_krw"),
        distance_m=value.get("distance_m"),
        reason_codes=list(value.get("reason_codes", []) or []),
        metadata=dict(value.get("metadata", {}) or {}),
        detail=dict(value.get("detail", {}) or {}),
    )


def _to_aware_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)
