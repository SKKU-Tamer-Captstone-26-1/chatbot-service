"""Build grounded RAG context from service outputs.

This module should not directly read survey DB or map DB.
"""
from dataclasses import dataclass, field
from typing import Any

from chatbot_service.clients.recommendation_client import RecommendationClient
from chatbot_service.domain.intents import ChatbotIntent
from chatbot_service.domain.schemas import CallerContext, ChatbotRequest


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
        profile = await self._recommendation_client.get_profile_status(auth_metadata)
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
        response = await self._recommendation_client.get_beverage_recommendations(
            auth_metadata,
            category=request.category,
            limit=request.beverage_limit,
            budget_mode=request.budget_mode,
            profile_revision=profile_revision,
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
        return GroundedContext(
            intent=ChatbotIntent.RECOMMEND_BEVERAGE.value,
            facts={
                "profile_status": profile_status,
                "profile_revision": profile_revision,
                "beverage_recommendations": [_to_plain_dict(item) for item in recommendations],
                "grounded_recommendation_context": _build_beverage_grounded_context(
                    profile_status,
                    recommendations,
                ),
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
        recommendations = _read_repeated(response, "recommendations")
        recommendations = [item for item in recommendations if _venue_item_is_usable(item)]
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
) -> dict[str, Any]:
    return {
        "user_profile_status": _user_visible_profile_status(profile_status),
        "recommendations": [_beverage_grounded_item(item) for item in recommendations],
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
    return {
        "recommendation_id": str(plain.get("result_id") or plain.get("recommendation_id") or ""),
        "beverage_id": str(plain.get("beverage_id", "")),
        "name": str(plain.get("name_ko") or plain.get("name_en") or plain.get("name") or ""),
        "category": str(plain.get("category", "")),
        "description": str(plain.get("description") or metadata.get("description") or ""),
        "flavor_tags": list(plain.get("flavor_tags") or metadata.get("flavor_tags") or []),
        "reason": str(plain.get("explanation") or plain.get("reason") or ""),
        "reason_codes": list(plain.get("reason_codes", []) or []),
        "price_range": str(plain.get("price_range") or metadata.get("price_range") or ""),
        "store": None,
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


def _venue_item_is_usable(item: Any) -> bool:
    freshness_status = str(_read_field(item, "freshness_status", "") or "")
    availability_status = str(_read_field(item, "availability_status", "") or "")
    metadata = _read_field(item, "metadata", {}) or {}
    if freshness_status in {
        "VENUE_FRESHNESS_STATUS_STALE",
        "VENUE_FRESHNESS_STATUS_EXPIRED",
        "STALE",
        "EXPIRED",
    }:
        return False
    if availability_status in {"VENUE_AVAILABILITY_STATUS_UNAVAILABLE", "UNAVAILABLE"}:
        return False
    if isinstance(metadata, dict):
        for key in ("price_freshness_status", "inventory_freshness_status"):
            value = str(metadata.get(key, "") or "")
            if value in {
                "STALE",
                "EXPIRED",
                "VENUE_FRESHNESS_STATUS_STALE",
                "VENUE_FRESHNESS_STATUS_EXPIRED",
            }:
                return False
    return True


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
