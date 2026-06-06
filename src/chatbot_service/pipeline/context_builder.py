"""Build grounded RAG context from service outputs.

This module should not directly read survey DB or map DB.
"""
from dataclasses import dataclass, field
from typing import Any

from chatbot_service.clients.recommendation_client import (
    RecommendationClient,
    RecommendationClientError,
)
from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import CallerContext, ChatbotRequest

PRICE_EXPERIENCE_WARNING = (
    "이 추천은 검증된 가격 관측값과 사람들의 경험적 의견을 바탕으로 만든 참고용 추천입니다. "
    "실제 매장 가격, 재고, 판매 여부는 달라질 수 있습니다."
)


@dataclass
class GroundedContext:
    intent: str
    facts: dict[str, Any] = field(default_factory=dict)
    missing_facts: list[str] = field(default_factory=list)
    confidence: float = 0.0

    @property
    def has_evidence(self) -> bool:
        return bool(self.facts)


def _read_field(value: Any, name: str, default: Any = None) -> Any:
    if isinstance(value, dict):
        return value.get(name, default)
    return getattr(value, name, default)


def _read_repeated(value: Any, name: str) -> list[Any]:
    repeated = _read_field(value, name, [])
    return list(repeated or [])


def _status_name(value: Any) -> str:
    if value is None:
        return "PROFILE_STATUS_UNSPECIFIED"
    if isinstance(value, str):
        return value
    name = getattr(value, "name", "")
    if name:
        return name
    return str(value)


class RecommendationContextBuilder:
    """Build grounded context from recommendation-service outputs only."""

    def __init__(self, recommendation_client: RecommendationClient) -> None:
        self._recommendation_client = recommendation_client

    async def build(
        self,
        intent: ChatbotIntent,
        request: ChatbotRequest,
        caller: CallerContext,
    ) -> GroundedContext:
        if intent in {ChatbotIntent.OUT_OF_SCOPE, ChatbotIntent.INSUFFICIENT_DATA}:
            return GroundedContext(intent=intent.value)

        auth_metadata = caller.metadata
        try:
            profile = await self._recommendation_client.get_profile_status(auth_metadata)
        except RecommendationClientError:
            return GroundedContext(
                intent=intent.value,
                missing_facts=["recommendation_service_unavailable"],
            )
        profile_status = _status_name(_read_field(profile, "status"))
        profile_revision = int(_read_field(profile, "profile_revision", 0) or 0)

        if profile_status not in {"PROFILE_STATUS_ACTIVE", "ACTIVE"}:
            return GroundedContext(
                intent=ChatbotIntent.PROFILE_STATUS.value,
                facts={
                    "profile_status": profile_status,
                    "profile_revision": profile_revision,
                    "profile": _to_plain_dict(profile),
                    "used_sources": {
                        "profile_status": profile_status,
                        "profile_revision": profile_revision,
                    },
                },
                missing_facts=["active_recommendation_profile"],
                confidence=1.0,
            )

        if intent == ChatbotIntent.RECOMMEND_BEVERAGE:
            return await self._build_beverage_context(
                request,
                auth_metadata,
                profile_status,
                profile_revision,
            )

        if intent in {
            ChatbotIntent.FIND_NEARBY_VENUE,
            ChatbotIntent.COMPARE_PURCHASE_OPTIONS,
        }:
            return await self._build_venue_context(
                intent,
                request,
                auth_metadata,
                profile_status,
                profile_revision,
            )

        return GroundedContext(
            intent=intent.value,
            missing_facts=["supported_recommendation_intent"],
        )

    async def _build_beverage_context(
        self,
        request: ChatbotRequest,
        auth_metadata: dict[str, str],
        profile_status: str,
        profile_revision: int,
    ) -> GroundedContext:
        try:
            response = await self._recommendation_client.get_beverage_recommendations(
                auth_metadata,
                category=request.category,
                limit=request.beverage_limit,
                budget_mode=request.budget_mode,
                profile_revision=profile_revision,
            )
        except RecommendationClientError:
            return GroundedContext(
                intent=ChatbotIntent.RECOMMEND_BEVERAGE.value,
                missing_facts=["recommendation_service_unavailable"],
            )
        recommendations = _read_repeated(response, "recommendations")
        if not recommendations:
            return GroundedContext(
                intent=ChatbotIntent.RECOMMEND_BEVERAGE.value,
                missing_facts=["beverage_recommendation_candidates"],
            )

        request_id = str(_read_field(response, "request_id", ""))
        used_sources = _build_used_sources(
            profile_status=profile_status,
            profile_revision=profile_revision,
            beverage_request_id=request_id,
            beverage_recommendations=recommendations,
        )
        required_warnings = _required_warnings(recommendations)
        return GroundedContext(
            intent=ChatbotIntent.RECOMMEND_BEVERAGE.value,
            facts={
                "profile_status": profile_status,
                "profile_revision": profile_revision,
                "beverage_recommendations": [_to_plain_dict(item) for item in recommendations],
                "grounded_recommendation_context": _build_beverage_grounded_context(
                    profile_status,
                    recommendations,
                    required_warnings,
                ),
                "required_warnings": required_warnings,
                "used_sources": used_sources,
            },
            confidence=_max_score(recommendations),
        )

    async def _build_venue_context(
        self,
        intent: ChatbotIntent,
        request: ChatbotRequest,
        auth_metadata: dict[str, str],
        profile_status: str,
        profile_revision: int,
    ) -> GroundedContext:
        missing: list[str] = []
        if request.lat is None or request.lng is None:
            missing.append("detailed_location")
        if not request.selected_beverage_id:
            missing.append("selected_beverage_id")
        if missing:
            return GroundedContext(intent=intent.value, missing_facts=missing)

        try:
            response = await self._recommendation_client.get_venue_recommendations(
                auth_metadata,
                selected_beverage_id=request.selected_beverage_id,
                lat=request.lat,
                lng=request.lng,
                radius_m=request.radius_m,
                limit=request.venue_limit,
                budget_mode=request.budget_mode,
                profile_revision=profile_revision,
            )
        except RecommendationClientError:
            return GroundedContext(
                intent=intent.value,
                missing_facts=["recommendation_service_unavailable"],
            )
        recommendations = _read_repeated(response, "recommendations")
        if not recommendations:
            return GroundedContext(
                intent=intent.value,
                missing_facts=["fresh_venue_recommendation_candidates"],
            )

        request_id = str(_read_field(response, "request_id", ""))
        used_sources = _build_used_sources(
            profile_status=profile_status,
            profile_revision=profile_revision,
            venue_request_id=request_id,
            venue_recommendations=recommendations,
        )
        return GroundedContext(
            intent=intent.value,
            facts={
                "profile_status": profile_status,
                "profile_revision": profile_revision,
                "venue_recommendations": [_to_plain_dict(item) for item in recommendations],
                "grounded_recommendation_context": _build_venue_grounded_context(
                    profile_status,
                    recommendations,
                ),
                "used_sources": used_sources,
            },
            confidence=_max_score(recommendations),
        )


def _to_plain_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    result: dict[str, Any] = {}
    for name in dir(value):
        if name.startswith("_"):
            continue
        attr = getattr(value, name)
        if callable(attr):
            continue
        result[name] = attr
    return result


def _build_beverage_grounded_context(
    profile_status: str,
    recommendations: list[Any],
    required_warnings: list[str],
) -> dict[str, Any]:
    return {
        "user_profile_status": _user_visible_profile_status(profile_status),
        "recommendations": [_beverage_grounded_item(item) for item in recommendations],
        "required_warnings": required_warnings,
    }


def _build_venue_grounded_context(
    profile_status: str,
    recommendations: list[Any],
) -> dict[str, Any]:
    return {
        "user_profile_status": _user_visible_profile_status(profile_status),
        "recommendations": [_venue_grounded_item(item) for item in recommendations],
    }


def _beverage_grounded_item(item: Any) -> dict[str, Any]:
    plain = _to_plain_dict(item)
    metadata = plain.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    source = _source_metadata(metadata)
    price_min_krw = _optional_int(source.get("price_min_krw"))
    price_max_krw = _optional_int(source.get("price_max_krw"))
    return {
        "recommendation_id": str(plain.get("result_id") or plain.get("recommendation_id") or ""),
        "rank": _optional_int(plain.get("rank")),
        "beverage_id": str(plain.get("beverage_id", "")),
        "name_ko": str(plain.get("name_ko", "")),
        "name_en": str(plain.get("name_en", "")),
        "name": str(plain.get("name_ko") or plain.get("name_en") or plain.get("name") or ""),
        "category": str(plain.get("category", "")),
        "score": _optional_float(plain.get("score")),
        "score_user_visible": False,
        "description": str(plain.get("description") or metadata.get("description") or ""),
        "flavor_tags": list(plain.get("flavor_tags") or metadata.get("flavor_tags") or []),
        "reason": str(plain.get("explanation") or plain.get("reason") or ""),
        "reason_codes": list(plain.get("reason_codes", []) or []),
        "price_range": _price_range(price_min_krw, price_max_krw, metadata),
        "store": None,
        "source": {
            "catalog_key": str(source.get("catalog_key", "")),
            "price_min_krw": price_min_krw,
            "price_max_krw": price_max_krw,
            "price_observation_summary": source.get("price_observation_summary", ""),
            "price_policy": str(source.get("price_policy", "")),
        },
    }


def _venue_grounded_item(item: Any) -> dict[str, Any]:
    plain = _to_plain_dict(item)
    metadata = plain.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    store = {
        "place_id": str(plain.get("place_id", "")),
        "name": str(plain.get("name", "")),
        "place_type": str(plain.get("place_type", "")),
        "address": str(plain.get("address", "")),
        "distance_m": plain.get("distance_m"),
        "price_krw": plain.get("price_krw"),
        "availability_status": str(plain.get("availability_status", "")),
        "freshness_status": str(plain.get("freshness_status", "")),
    }
    return {
        "recommendation_id": str(plain.get("result_id") or plain.get("recommendation_id") or ""),
        "beverage_id": str(plain.get("beverage_id", "")),
        "name": str(plain.get("beverage_name") or plain.get("name") or ""),
        "category": str(plain.get("category") or metadata.get("category") or ""),
        "description": str(plain.get("description") or metadata.get("description") or ""),
        "flavor_tags": list(plain.get("flavor_tags") or metadata.get("flavor_tags") or []),
        "reason": str(plain.get("explanation") or plain.get("reason") or ""),
        "reason_codes": list(plain.get("reason_codes", []) or []),
        "price_range": str(plain.get("price_range") or metadata.get("price_range") or ""),
        "store": store,
    }


def _user_visible_profile_status(profile_status: str) -> str:
    if profile_status.startswith("PROFILE_STATUS_"):
        return profile_status.removeprefix("PROFILE_STATUS_")
    return profile_status


def _max_score(items: list[Any]) -> float:
    scores = [float(_read_field(item, "score", 0.0) or 0.0) for item in items]
    return max(scores, default=0.0)


def _source_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    source = metadata.get("source", {})
    if isinstance(source, dict):
        return dict(source)
    return {}


def _required_warnings(recommendations: list[Any]) -> list[str]:
    if any(_requires_price_or_experience_warning(item) for item in recommendations):
        return [PRICE_EXPERIENCE_WARNING]
    return []


def _requires_price_or_experience_warning(item: Any) -> bool:
    plain = _to_plain_dict(item)
    metadata = plain.get("metadata", {})
    if not isinstance(metadata, dict):
        metadata = {}
    source = _source_metadata(metadata)
    if str(source.get("price_policy", "")) == "verified_krw_observations_not_live_truth":
        return True
    if source.get("price_min_krw") is not None or source.get("price_max_krw") is not None:
        return True
    reason_codes = [str(code).upper() for code in plain.get("reason_codes", []) or []]
    return any("EXPERIENCE" in code or "OPINION" in code for code in reason_codes)


def _price_range(
    price_min_krw: int | None,
    price_max_krw: int | None,
    metadata: dict[str, Any],
) -> str:
    if price_min_krw is not None and price_max_krw is not None:
        if price_min_krw == price_max_krw:
            return f"{price_min_krw} KRW"
        return f"{price_min_krw}-{price_max_krw} KRW"
    if price_min_krw is not None:
        return f"{price_min_krw} KRW+"
    if price_max_krw is not None:
        return f"up to {price_max_krw} KRW"
    return str(metadata.get("price_range", ""))


def _optional_int(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _optional_float(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _build_used_sources(
    *,
    profile_status: str,
    profile_revision: int,
    beverage_request_id: str = "",
    venue_request_id: str = "",
    beverage_recommendations: list[Any] | None = None,
    venue_recommendations: list[Any] | None = None,
) -> dict[str, Any]:
    beverages = beverage_recommendations or []
    venues = venue_recommendations or []
    beverage_ids = [
        str(_read_field(item, "beverage_id", ""))
        for item in beverages
        if _read_field(item, "beverage_id", "")
    ]
    place_ids = [
        str(_read_field(item, "place_id", ""))
        for item in venues
        if _read_field(item, "place_id", "")
    ]
    beverage_result_ids = [
        str(_read_field(item, "result_id", ""))
        for item in beverages
        if _read_field(item, "result_id", "")
    ]
    venue_result_ids = [
        str(_read_field(item, "result_id", ""))
        for item in venues
        if _read_field(item, "result_id", "")
    ]
    return {
        "profile_status": profile_status,
        "profile_revision": profile_revision,
        "recommendation_request_id": beverage_request_id or venue_request_id,
        "beverage_recommendation_request_id": beverage_request_id,
        "venue_recommendation_request_id": venue_request_id,
        "beverage_ids": beverage_ids,
        "place_ids": place_ids,
        "beverage_result_ids": beverage_result_ids,
        "venue_result_ids": venue_result_ids,
        "reason_codes": sorted(
            {
                str(code)
                for item in [*beverages, *venues]
                for code in (_read_field(item, "reason_codes", []) or [])
            }
        ),
    }
