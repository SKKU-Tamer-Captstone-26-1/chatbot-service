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

    def build_generation_fallback(
        self,
        intent: ChatbotIntent,
        context: GroundedContext,
        *,
        reason: str,
    ) -> ChatbotAnswer:
        return ChatbotAnswer(
            intent=intent,
            answer=_fallback_answer(intent, context),
            confidence=context.confidence,
            status=ChatbotResponseStatus.ANSWERED,
            profile_status=str(context.facts.get("profile_status", "PROFILE_STATUS_UNSPECIFIED")),
            cards=self._build_cards(context),
            used_sources=context.facts.get("used_sources", {}),
            missing_facts=[],
        )

    def _build_cards(self, context: GroundedContext) -> list[ChatbotCard]:
        cards: list[ChatbotCard] = []
        for item in context.facts.get("beverage_recommendations", []):
            cards.append(_beverage_card(item))
        if context.intent == ChatbotIntent.COMPARE_PURCHASE_OPTIONS.value:
            for item in context.facts.get("venue_recommendations", []):
                cards.append(_purchase_option_card(item))
            return cards
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


def _fallback_answer(intent: ChatbotIntent, context: GroundedContext) -> str:
    if intent == ChatbotIntent.RECOMMEND_BEVERAGE:
        names = [
            _beverage_title(item)
            for item in context.facts.get("beverage_recommendations", [])
        ]
        names = [name for name in names if name]
        if names:
            return (
                f"추천 서비스 결과 기준으로는 {names[0]}을 먼저 확인해 보세요. "
                "아래 후보는 추천 서비스가 반환한 순서대로 보여드릴게요."
            )
    if intent in {ChatbotIntent.FIND_NEARBY_VENUE, ChatbotIntent.COMPARE_PURCHASE_OPTIONS}:
        names = [
            str(item.get("name") or item.get("place_id") or "")
            for item in context.facts.get("venue_recommendations", [])
        ]
        names = [name for name in names if name]
        if names:
            return (
                f"추천 서비스 결과 기준으로는 {names[0]}을 먼저 확인해 보세요. "
                "아래 장소 정보는 추천 서비스가 반환한 데이터만 사용했어요."
            )
    return (
        "추천 서비스 결과는 확인했지만, 지금은 자연어 답변을 생성하지 못했어요. "
        "아래 카드의 추천 결과를 확인해 주세요."
    )


def _beverage_title(item: dict[str, Any]) -> str:
    return str(item.get("name_ko") or item.get("name_en") or item.get("beverage_id") or "")


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


def _purchase_option_card(item: dict[str, Any]) -> ChatbotCard:
    place_name = str(item.get("name") or item.get("place_id") or "")
    detail = {
        "option_type": item.get("option_type", "VENUE_OPTION_TYPE_UNSPECIFIED"),
        "result_id": item.get("result_id", ""),
        "beverage_id": item.get("beverage_id", ""),
        "beverage_name": item.get("beverage_name", ""),
        "place_id": item.get("place_id", ""),
        "place_name": place_name,
        "place_type": item.get("place_type", ""),
        "address": item.get("address", ""),
        "distance_m": item.get("distance_m", 0.0),
        "availability_status": item.get(
            "availability_status",
            "VENUE_AVAILABILITY_STATUS_UNSPECIFIED",
        ),
        "freshness_status": item.get(
            "freshness_status",
            "VENUE_FRESHNESS_STATUS_UNSPECIFIED",
        ),
        "score": item.get("score", 0.0),
        "reason_codes": list(item.get("reason_codes", []) or []),
        "explanation": item.get("explanation", ""),
        "metadata": dict(item.get("metadata", {}) or {}),
    }
    if item.get("price_krw") is not None:
        detail["price_krw"] = item["price_krw"]
    if item.get("estimated_travel_time_sec") is not None:
        detail["estimated_travel_time_sec"] = item["estimated_travel_time_sec"]
    return ChatbotCard(
        card_type="CHATBOT_CARD_TYPE_PURCHASE_OPTION",
        title=place_name,
        subtitle=str(item.get("place_type", "")),
        display_reason=str(item.get("explanation", "")),
        score=float(item.get("score", 0.0) or 0.0),
        price_krw=item.get("price_krw"),
        distance_m=_distance_to_int(item.get("distance_m")),
        reason_codes=list(item.get("reason_codes", []) or []),
        metadata=dict(item.get("metadata", {}) or {}),
        detail={"purchase_option": detail},
    )


def _distance_to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(float(value))
