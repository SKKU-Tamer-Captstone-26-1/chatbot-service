"""Internal schemas for chatbot pipeline.

These are intentionally lightweight placeholders. Generate final DTOs from proto
when implementation begins.
"""
from dataclasses import dataclass, field
from typing import Any

from .intents import ChatbotIntent


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


@dataclass
class ChatbotAnswer:
    intent: ChatbotIntent
    answer: str
    confidence: float
    refused: bool = False
    refusal_reason: str = ""
    cards: list[ChatbotCard] = field(default_factory=list)
    used_sources: dict[str, Any] = field(default_factory=dict)
    missing_facts: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
