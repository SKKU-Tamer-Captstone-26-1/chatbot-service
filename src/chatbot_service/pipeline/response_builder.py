from typing import Any

from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import ChatbotAnswer, ChatbotCard, ChatbotResponseStatus
from chatbot_service.pipeline.context_builder import GroundedContext


class ResponseBuilder:
    def build_from_grounded_text(
        self,
        intent: ChatbotIntent,
        answer: str,
        context: GroundedContext,
    ) -> ChatbotAnswer:
        cards = self._build_cards(context)
        return ChatbotAnswer(
            intent=intent,
            answer=answer,
            confidence=context.confidence,
            status=ChatbotResponseStatus.ANSWERED,
            profile_status=str(context.facts.get("profile_status", "PROFILE_STATUS_UNSPECIFIED")),
            cards=cards,
            used_sources=context.facts.get("used_sources", {}),
            missing_facts=context.missing_facts,
        )

    def _build_cards(self, context: GroundedContext) -> list[ChatbotCard]:
        cards: list[ChatbotCard] = []
        for item in context.facts.get("beverage_recommendations", []):
            cards.append(_beverage_card(item))
        for item in context.facts.get("venue_recommendations", []):
            cards.append(_venue_card(item))
        if context.facts.get("profile_status") and not cards:
            cards.append(
                ChatbotCard(
                    card_type="CHATBOT_CARD_TYPE_PROFILE_STATUS",
                    title=str(context.facts["profile_status"]),
                    display_reason=str(context.facts.get("stale_reason", "")),
                    detail={
                        "profile_status": {
                            "status": context.facts["profile_status"],
                            "profile_revision": context.facts.get("profile_revision", 0),
                        }
                    },
                )
            )
        return cards


def _beverage_card(item: dict[str, Any]) -> ChatbotCard:
    title = str(item.get("name_ko") or item.get("name_en") or item.get("beverage_id") or "")
    return ChatbotCard(
        card_type="CHATBOT_CARD_TYPE_BEVERAGE_RECOMMENDATION",
        title=title,
        subtitle=str(item.get("category", "")),
        display_reason=str(item.get("explanation", "")),
        score=float(item.get("score", 0.0) or 0.0),
        reason_codes=list(item.get("reason_codes", []) or []),
        metadata=dict(item.get("metadata", {}) or {}),
        detail={"beverage_recommendation": item},
    )


def _venue_card(item: dict[str, Any]) -> ChatbotCard:
    return ChatbotCard(
        card_type="CHATBOT_CARD_TYPE_VENUE_RECOMMENDATION",
        title=str(item.get("name") or item.get("place_id") or ""),
        subtitle=str(item.get("place_type", "")),
        display_reason=str(item.get("explanation", "")),
        score=float(item.get("score", 0.0) or 0.0),
        price_krw=item.get("price_krw"),
        distance_m=_distance_to_int(item.get("distance_m")),
        reason_codes=list(item.get("reason_codes", []) or []),
        metadata=dict(item.get("metadata", {}) or {}),
        detail={"venue_recommendation": item},
    )


def _distance_to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(float(value))
