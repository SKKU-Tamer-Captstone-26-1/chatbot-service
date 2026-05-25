"""Internal schemas for chatbot pipeline.

These are intentionally lightweight placeholders. Generate final DTOs from proto
when implementation begins.
"""
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from .intents import ChatbotIntent


class ChatbotResponseStatus(StrEnum):
    ANSWERED = "ANSWERED"
    REFUSED = "REFUSED"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass
class ChatbotCard:
    card_type: str
    title: str
    subtitle: str = ""
    display_reason: str = ""
    score: float | None = None
    price_krw: int | None = None
    distance_m: int | None = None
    reason_codes: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class ChatbotAnswer:
    intent: ChatbotIntent
    answer: str
    confidence: float
    conversation_id: str = ""
    message_id: str = ""
    prompt_context_hash: str = ""
    status: ChatbotResponseStatus = ChatbotResponseStatus.ANSWERED
    profile_status: str = "PROFILE_STATUS_UNSPECIFIED"
    refused: bool = False
    refusal_reason: str = ""
    cards: list[ChatbotCard] = field(default_factory=list)
    used_sources: dict[str, Any] = field(default_factory=dict)
    missing_facts: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class CallerContext:
    user_id: str
    authorization: str = ""
    metadata: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class ChatbotRequest:
    message: str
    conversation_id: str = ""
    screen_context: str = "SCREEN_CONTEXT_UNSPECIFIED"
    lat: float | None = None
    lng: float | None = None
    radius_m: int | None = None
    budget_hint_krw: int | None = None
    selected_beverage_id: str = ""
    category: str = ""
    beverage_limit: int = 0
    venue_limit: int = 0
    budget_mode: str = "BUDGET_MODE_UNSPECIFIED"
    client_context: dict[str, Any] = field(default_factory=dict)
