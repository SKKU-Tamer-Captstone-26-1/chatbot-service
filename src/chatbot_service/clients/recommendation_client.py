"""Recommendation-service client interface.

Implementation should call gRPC RecommendationService APIs:
- GetProfileStatus
- GetBeverageRecommendations
- GetVenueRecommendations
- RecordRecommendationEvent
"""
from typing import Any, Protocol


class RecommendationClient(Protocol):
    async def get_profile_status(self, auth_metadata: dict[str, str]) -> Any: ...

    async def get_beverage_recommendations(
        self,
        auth_metadata: dict[str, str],
        **filters: Any,
    ) -> Any: ...

    async def get_venue_recommendations(
        self,
        auth_metadata: dict[str, str],
        lat: float,
        lng: float,
        **filters: Any,
    ) -> Any: ...

    async def record_recommendation_event(
        self,
        auth_metadata: dict[str, str],
        **event: Any,
    ) -> Any: ...
