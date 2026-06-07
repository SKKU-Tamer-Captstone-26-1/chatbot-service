from __future__ import annotations

import asyncio
import copy
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Any

from chatbot_service.cache import Cache
from chatbot_service.clients.recommendation_client import RecommendationClient
from chatbot_service.metrics import MetricsRecorder

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class RecommendationCacheSettings:
    user_id_metadata_key: str = "x-user-id"
    profile_status_ttl_sec: int = 300
    beverage_recommendations_ttl_sec: int = 300
    venue_recommendations_ttl_sec: int = 120
    location_bucket_precision: int = 3


class CachingRecommendationClient:
    """Thin chatbot-side cache over recommendation-service API responses."""

    def __init__(
        self,
        inner: RecommendationClient,
        cache: Cache,
        settings: RecommendationCacheSettings,
        metrics: MetricsRecorder | None = None,
    ) -> None:
        self._inner = inner
        self._cache = cache
        self._settings = settings
        self._metrics = metrics or MetricsRecorder()
        self._locks: dict[str, asyncio.Lock] = {}

    async def get_profile_status(self, auth_metadata: dict[str, str]) -> Any:
        user_id = self._user_id(auth_metadata)
        if not user_id:
            self._metrics.increment(
                "recommendation.cache_bypass",
                operation="profile_status",
                reason="missing_user_id",
            )
            return await self._timed(
                "profile_status",
                self._inner.get_profile_status(auth_metadata),
            )

        cache_key = f"profile_status:{user_id}"
        cached = await self._cache_get(cache_key, "profile_status")
        if cached is not None:
            self._metrics.increment("recommendation.cache_hit", operation="profile_status")
            return copy.deepcopy(cached)

        self._metrics.increment("recommendation.cache_miss", operation="profile_status")
        return await self._get_or_fill_locked(
            cache_key=cache_key,
            operation="profile_status",
            ttl_sec=self._settings.profile_status_ttl_sec,
            fill=lambda: self._timed(
                "profile_status",
                self._inner.get_profile_status(auth_metadata),
            ),
        )

    async def get_beverage_recommendations(
        self,
        auth_metadata: dict[str, str],
        **filters: Any,
    ) -> Any:
        user_id = self._user_id(auth_metadata)
        profile_revision = int(filters.get("profile_revision") or 0)
        if not user_id or profile_revision <= 0:
            self._metrics.increment(
                "recommendation.cache_bypass",
                operation="beverage_recommendations",
                reason="missing_user_or_profile_revision",
            )
            return await self._timed(
                "beverage_recommendations",
                self._inner.get_beverage_recommendations(auth_metadata, **filters),
            )

        cache_key = _beverage_cache_key(user_id, profile_revision, filters)
        cached = await self._cache_get(cache_key, "beverage_recommendations")
        if cached is not None:
            self._metrics.increment(
                "recommendation.cache_hit",
                operation="beverage_recommendations",
            )
            return copy.deepcopy(cached)

        self._metrics.increment("recommendation.cache_miss", operation="beverage_recommendations")
        return await self._get_or_fill_locked(
            cache_key=cache_key,
            operation="beverage_recommendations",
            ttl_sec=self._settings.beverage_recommendations_ttl_sec,
            fill=lambda: self._timed(
                "beverage_recommendations",
                self._inner.get_beverage_recommendations(auth_metadata, **filters),
            ),
        )

    async def get_venue_recommendations(
        self,
        auth_metadata: dict[str, str],
        lat: float,
        lng: float,
        **filters: Any,
    ) -> Any:
        user_id = self._user_id(auth_metadata)
        profile_revision = int(filters.get("profile_revision") or 0)
        location_bucket = _location_bucket(lat, lng, self._settings.location_bucket_precision)
        if not user_id or profile_revision <= 0 or not location_bucket:
            self._metrics.increment(
                "recommendation.cache_bypass",
                operation="venue_recommendations",
                reason="missing_user_profile_or_location_bucket",
            )
            return await self._timed(
                "venue_recommendations",
                self._inner.get_venue_recommendations(auth_metadata, lat, lng, **filters),
            )

        cache_key = _venue_cache_key(user_id, profile_revision, location_bucket, filters)
        cached = await self._cache_get(cache_key, "venue_recommendations")
        if cached is not None:
            self._metrics.increment("recommendation.cache_hit", operation="venue_recommendations")
            return copy.deepcopy(cached)

        self._metrics.increment("recommendation.cache_miss", operation="venue_recommendations")
        return await self._get_or_fill_locked(
            cache_key=cache_key,
            operation="venue_recommendations",
            ttl_sec=self._settings.venue_recommendations_ttl_sec,
            fill=lambda: self._timed(
                "venue_recommendations",
                self._inner.get_venue_recommendations(auth_metadata, lat, lng, **filters),
            ),
            cacheable=_venue_response_cacheable,
        )

    async def record_recommendation_event(
        self,
        auth_metadata: dict[str, str],
        **event: Any,
    ) -> Any:
        return await self._timed(
            "record_recommendation_event",
            self._inner.record_recommendation_event(auth_metadata, **event),
        )

    async def close(self) -> None:
        close = getattr(self._inner, "close", None)
        if close is not None:
            await close()

    async def _timed(self, operation: str, awaitable: Any) -> Any:
        with self._metrics.timer("recommendation.call", operation=operation):
            return await awaitable

    def _user_id(self, auth_metadata: dict[str, str]) -> str:
        normalized = {str(key).lower(): str(value) for key, value in auth_metadata.items()}
        return normalized.get(self._settings.user_id_metadata_key.lower(), "").strip()

    async def _cache_get(self, key: str, operation: str) -> Any | None:
        try:
            return await self._cache.get(key)
        except Exception:
            self._metrics.increment("recommendation.cache_error", operation=operation, action="get")
            LOGGER.exception("recommendation cache get failed; operation=%s", operation)
            return None

    async def _cache_set(self, key: str, value: Any, ttl_sec: int, operation: str) -> None:
        try:
            await self._cache.set(key, value, ttl_sec)
        except Exception:
            self._metrics.increment("recommendation.cache_error", operation=operation, action="set")
            LOGGER.exception("recommendation cache set failed; operation=%s", operation)

    async def _get_or_fill_locked(
        self,
        *,
        cache_key: str,
        operation: str,
        ttl_sec: int,
        fill: Callable[[], Awaitable[Any]],
        cacheable: Callable[[Any], bool] | None = None,
    ) -> Any:
        lock = self._locks.setdefault(cache_key, asyncio.Lock())
        async with lock:
            cached = await self._cache_get(cache_key, operation)
            if cached is not None:
                self._metrics.increment("recommendation.cache_hit_after_lock", operation=operation)
                return copy.deepcopy(cached)
            response = await fill()
            if cacheable is not None and not cacheable(response):
                self._metrics.increment(
                    "recommendation.cache_bypass",
                    operation=operation,
                    reason="uncacheable_response",
                )
                return response
            await self._cache_set(cache_key, response, ttl_sec, operation)
            return response


def _beverage_cache_key(user_id: str, profile_revision: int, filters: dict[str, Any]) -> str:
    return ":".join(
        [
            "beverage_recs",
            user_id,
            str(profile_revision),
            str(filters.get("category", "")),
            str(filters.get("budget_mode", "BUDGET_MODE_UNSPECIFIED")),
            str(int(filters.get("limit") or 0)),
            _list_cache_segment(filters.get("exclude_beverage_ids")),
            _list_cache_segment(filters.get("exclude_result_ids")),
            str(filters.get("diversity_mode", "")),
            str(filters.get("session_context_id", "")),
        ]
    )


def _venue_cache_key(
    user_id: str,
    profile_revision: int,
    location_bucket: str,
    filters: dict[str, Any],
) -> str:
    return ":".join(
        [
            "venue_recs",
            user_id,
            str(profile_revision),
            str(filters.get("selected_beverage_id", "")),
            location_bucket,
            str(int(filters.get("radius_m") or 0)),
            str(filters.get("budget_mode", "BUDGET_MODE_UNSPECIFIED")),
            str(int(filters.get("limit") or 0)),
            _list_cache_segment(filters.get("exclude_beverage_ids")),
            _list_cache_segment(filters.get("exclude_result_ids")),
            str(filters.get("diversity_mode", "")),
            str(filters.get("session_context_id", "")),
        ]
    )


def _location_bucket(lat: float, lng: float, precision: int) -> str:
    if precision < 0:
        return ""
    lat_bucket = f"{round(float(lat), precision):.{precision}f}"
    lng_bucket = f"{round(float(lng), precision):.{precision}f}"
    return f"{lat_bucket},{lng_bucket}"


def _venue_response_cacheable(response: Any) -> bool:
    recommendations = response.get("recommendations", []) if isinstance(response, dict) else []
    if not recommendations:
        return False
    return all(_venue_recommendation_cacheable(item) for item in recommendations)


def _venue_recommendation_cacheable(item: Any) -> bool:
    if not isinstance(item, dict):
        return False
    freshness_status = str(item.get("freshness_status", "") or "")
    availability_status = str(item.get("availability_status", "") or "")
    if freshness_status != "VENUE_FRESHNESS_STATUS_FRESH":
        return False
    if availability_status in {"VENUE_AVAILABILITY_STATUS_UNAVAILABLE", "UNAVAILABLE"}:
        return False
    metadata = item.get("metadata", {})
    if isinstance(metadata, dict):
        for key in ("price_freshness_status", "inventory_freshness_status"):
            if str(metadata.get(key, "") or "") in {
                "STALE",
                "EXPIRED",
                "VENUE_FRESHNESS_STATUS_STALE",
                "VENUE_FRESHNESS_STATUS_EXPIRED",
            }:
                return False
    return True


def _list_cache_segment(values: Any) -> str:
    if values is None:
        return ""
    if isinstance(values, str):
        raw_items = values.split(",")
    elif isinstance(values, (list, tuple, set)):
        raw_items = list(values)
    else:
        return str(values)

    items = {
        item.strip()
        for item in (str(item).strip() for item in raw_items)
        if item.strip()
    }
    return ",".join(sorted(items))


__all__ = [
    "CachingRecommendationClient",
    "RecommendationCacheSettings",
    "_location_bucket",
]
