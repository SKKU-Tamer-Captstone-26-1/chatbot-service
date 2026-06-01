"""Recommendation-service client interface.

Implementation should call gRPC RecommendationService APIs:
- GetProfileStatus
- GetBeverageRecommendations
- GetVenueRecommendations
- RecordRecommendationEvent
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Protocol

from google.protobuf import json_format

from chatbot_service.config import ChatbotConfig


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


class RecommendationClientError(RuntimeError):
    """Raised when recommendation-service cannot be called."""


class GrpcRecommendationClient:
    def __init__(
        self,
        target: str,
        *,
        secure: bool | None = None,
        timeout_ms: int = 5000,
        recommendation_pb2: Any | None = None,
        recommendation_pb2_grpc: Any | None = None,
    ) -> None:
        if not target:
            raise ValueError("RECOMMENDATION_SERVICE_GRPC_ADDR is required")
        self._target = _channel_target(target)
        self._secure = _target_uses_tls(target) if secure is None else secure
        self._timeout_sec = timeout_ms / 1000
        self._recommendation_pb2 = recommendation_pb2
        self._recommendation_pb2_grpc = recommendation_pb2_grpc
        self._channel: Any | None = None
        self._stub: Any | None = None

    @classmethod
    def from_config(cls, config: ChatbotConfig) -> GrpcRecommendationClient:
        return cls(
            config.recommendation_service_url,
            secure=config.recommendation_service_grpc_tls,
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def get_profile_status(self, auth_metadata: dict[str, str]) -> Any:
        pb2, stub = self._modules_and_stub()
        response = await stub.GetProfileStatus(
            pb2.GetProfileStatusRequest(),
            metadata=_metadata(auth_metadata),
            timeout=self._timeout_sec,
        )
        return _message_to_dict(response)

    async def get_beverage_recommendations(
        self,
        auth_metadata: dict[str, str],
        **filters: Any,
    ) -> Any:
        pb2, stub = self._modules_and_stub()
        response = await stub.GetBeverageRecommendations(
            pb2.GetBeverageRecommendationsRequest(
                category=str(filters.get("category", "")),
                limit=int(filters.get("limit") or 0),
                budget_mode=_enum_value(
                    pb2,
                    str(filters.get("budget_mode", "BUDGET_MODE_UNSPECIFIED")),
                    "BUDGET_MODE_UNSPECIFIED",
                ),
            ),
            metadata=_metadata(auth_metadata),
            timeout=self._timeout_sec,
        )
        return _message_to_dict(response)

    async def get_venue_recommendations(
        self,
        auth_metadata: dict[str, str],
        lat: float,
        lng: float,
        **filters: Any,
    ) -> Any:
        pb2, stub = self._modules_and_stub()
        response = await stub.GetVenueRecommendations(
            pb2.GetVenueRecommendationsRequest(
                selected_beverage_id=str(filters.get("selected_beverage_id", "")),
                lat=float(lat),
                lng=float(lng),
                radius_m=int(filters.get("radius_m") or 0),
                limit=int(filters.get("limit") or 0),
                budget_mode=_enum_value(
                    pb2,
                    str(filters.get("budget_mode", "BUDGET_MODE_UNSPECIFIED")),
                    "BUDGET_MODE_UNSPECIFIED",
                ),
            ),
            metadata=_metadata(auth_metadata),
            timeout=self._timeout_sec,
        )
        return _message_to_dict(response)

    async def record_recommendation_event(
        self,
        auth_metadata: dict[str, str],
        **event: Any,
    ) -> Any:
        pb2, stub = self._modules_and_stub()
        request = pb2.RecordRecommendationEventRequest(
            request_id=str(event.get("request_id", "")),
            result_id=str(event.get("result_id", "")),
            event_type=_enum_value(
                pb2,
                str(event.get("event_type", "RECOMMENDATION_EVENT_TYPE_UNSPECIFIED")),
                "RECOMMENDATION_EVENT_TYPE_UNSPECIFIED",
            ),
            idempotency_key=str(event.get("idempotency_key", "")),
        )
        metadata = event.get("metadata", {})
        if isinstance(metadata, dict):
            json_format.ParseDict(metadata, request.metadata)
        response = await stub.RecordRecommendationEvent(
            request,
            metadata=_metadata(auth_metadata),
            timeout=self._timeout_sec,
        )
        return _message_to_dict(response)

    def _modules_and_stub(self) -> tuple[Any, Any]:
        if self._stub is not None:
            return self._recommendation_pb2, self._stub
        if self._recommendation_pb2 is None or self._recommendation_pb2_grpc is None:
            self._recommendation_pb2, self._recommendation_pb2_grpc = _load_generated_modules()
        self._channel = _build_channel(self._target, self._secure)
        self._stub = self._recommendation_pb2_grpc.RecommendationServiceStub(self._channel)
        return self._recommendation_pb2, self._stub


def _load_generated_modules() -> tuple[Any, Any]:
    generated_root = Path(__file__).resolve().parents[1] / "generated"
    if str(generated_root) not in sys.path:
        sys.path.insert(0, str(generated_root))
    try:
        from chatbot.v1 import recommendation_pb2, recommendation_pb2_grpc
    except (ImportError, ModuleNotFoundError) as exc:
        raise RecommendationClientError(
            "Generated recommendation gRPC modules are missing. Run scripts/generate_proto.sh."
        ) from exc
    return recommendation_pb2, recommendation_pb2_grpc


def _build_channel(target: str, secure: bool) -> Any:
    import grpc

    if secure:
        return grpc.aio.secure_channel(target, grpc.ssl_channel_credentials())
    return grpc.aio.insecure_channel(target)


def _channel_target(raw: str) -> str:
    if raw.startswith("https://"):
        return raw.removeprefix("https://")
    if raw.startswith("http://"):
        return raw.removeprefix("http://")
    return raw


def _target_uses_tls(raw: str) -> bool:
    return raw.startswith("https://") or raw.endswith(":443")


def _metadata(auth_metadata: dict[str, str]) -> list[tuple[str, str]]:
    return [(str(key), str(value)) for key, value in auth_metadata.items()]


def _message_to_dict(message: Any) -> dict[str, Any]:
    return json_format.MessageToDict(
        message,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )


def _enum_value(module: Any, name: str, default: str) -> int:
    return int(getattr(module, name, getattr(module, default)))
