"""Recommendation-service client interface.

Implementation should call gRPC RecommendationService APIs:
- GetProfileStatus
- GetBeverageRecommendations
- GetVenueRecommendations
- RecordRecommendationEvent
"""
from __future__ import annotations

import sys
import time
import urllib.error
import urllib.parse
import urllib.request
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


class ServerlessAuthTokenProvider(Protocol):
    async def get_token(self) -> str: ...


class NoopServerlessAuthTokenProvider:
    async def get_token(self) -> str:
        return ""


class EnvServerlessAuthTokenProvider:
    def __init__(self, env_name: str) -> None:
        self._env_name = env_name

    async def get_token(self) -> str:
        import os

        token = os.getenv(self._env_name, "").strip()
        if not token:
            raise RecommendationClientError(
                f"{self._env_name} is required for recommendation serverless auth"
            )
        return token


class MetadataServerlessAuthTokenProvider:
    """Fetch a Google ID token from the Cloud Run/Compute metadata server."""

    def __init__(self, audience: str, *, timeout_ms: int = 1000, ttl_sec: int = 3000) -> None:
        if not audience:
            raise ValueError("RECOMMENDATION_SERVICE_SERVERLESS_AUDIENCE is required")
        self._audience = audience
        self._timeout_sec = timeout_ms / 1000
        self._ttl_sec = ttl_sec
        self._token = ""
        self._expires_at = 0.0

    async def get_token(self) -> str:
        import asyncio

        now = time.time()
        if self._token and now < self._expires_at:
            return self._token
        token = await asyncio.to_thread(self._fetch_token_sync)
        self._token = token
        self._expires_at = now + self._ttl_sec
        return token

    def _fetch_token_sync(self) -> str:
        query = urllib.parse.urlencode({"audience": self._audience, "format": "full"})
        request = urllib.request.Request(
            f"http://metadata/computeMetadata/v1/instance/service-accounts/default/identity?{query}",
            headers={"Metadata-Flavor": "Google"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(request, timeout=self._timeout_sec) as response:
                return response.read().decode("utf-8").strip()
        except (urllib.error.URLError, TimeoutError) as exc:
            raise RecommendationClientError(
                "failed to fetch recommendation-service Cloud Run ID token"
            ) from exc


class StaticServerlessAuthTokenProvider:
    def __init__(self, token: str) -> None:
        self._token = token

    async def get_token(self) -> str:
        return self._token


class GrpcRecommendationClient:
    def __init__(
        self,
        target: str,
        *,
        secure: bool | None = None,
        timeout_ms: int = 5000,
        serverless_auth_token_provider: ServerlessAuthTokenProvider | None = None,
        recommendation_pb2: Any | None = None,
        recommendation_pb2_grpc: Any | None = None,
    ) -> None:
        if not target:
            raise ValueError("RECOMMENDATION_SERVICE_GRPC_ADDR is required")
        self._target = _channel_target(target)
        self._secure = _target_uses_tls(target) if secure is None else secure
        self._timeout_sec = timeout_ms / 1000
        self._serverless_auth_token_provider = (
            serverless_auth_token_provider or NoopServerlessAuthTokenProvider()
        )
        self._recommendation_pb2 = recommendation_pb2
        self._recommendation_pb2_grpc = recommendation_pb2_grpc
        self._channel: Any | None = None
        self._stub: Any | None = None

    @classmethod
    def from_config(cls, config: ChatbotConfig) -> GrpcRecommendationClient:
        return cls(
            config.recommendation_service_url,
            secure=config.recommendation_service_grpc_tls,
            serverless_auth_token_provider=build_serverless_auth_token_provider(config),
        )

    async def close(self) -> None:
        if self._channel is not None:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def get_profile_status(self, auth_metadata: dict[str, str]) -> Any:
        pb2, stub = self._modules_and_stub()
        try:
            response = await stub.GetProfileStatus(
                pb2.GetProfileStatusRequest(),
                metadata=await self._metadata(auth_metadata),
                timeout=self._timeout_sec,
            )
        except Exception as exc:
            raise RecommendationClientError(
                "recommendation-service GetProfileStatus failed"
            ) from exc
        return _message_to_dict(response)

    async def get_beverage_recommendations(
        self,
        auth_metadata: dict[str, str],
        **filters: Any,
    ) -> Any:
        pb2, stub = self._modules_and_stub()
        try:
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
                metadata=await self._metadata(auth_metadata),
                timeout=self._timeout_sec,
            )
        except Exception as exc:
            raise RecommendationClientError(
                "recommendation-service GetBeverageRecommendations failed"
            ) from exc
        return _message_to_dict(response)

    async def get_venue_recommendations(
        self,
        auth_metadata: dict[str, str],
        lat: float,
        lng: float,
        **filters: Any,
    ) -> Any:
        pb2, stub = self._modules_and_stub()
        try:
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
                metadata=await self._metadata(auth_metadata),
                timeout=self._timeout_sec,
            )
        except Exception as exc:
            raise RecommendationClientError(
                "recommendation-service GetVenueRecommendations failed"
            ) from exc
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
        try:
            response = await stub.RecordRecommendationEvent(
                request,
                metadata=await self._metadata(auth_metadata),
                timeout=self._timeout_sec,
            )
        except Exception as exc:
            raise RecommendationClientError(
                "recommendation-service RecordRecommendationEvent failed"
            ) from exc
        return _message_to_dict(response)

    def _modules_and_stub(self) -> tuple[Any, Any]:
        if self._stub is not None:
            return self._recommendation_pb2, self._stub
        if self._recommendation_pb2 is None or self._recommendation_pb2_grpc is None:
            self._recommendation_pb2, self._recommendation_pb2_grpc = _load_generated_modules()
        self._channel = _build_channel(self._target, self._secure)
        self._stub = self._recommendation_pb2_grpc.RecommendationServiceStub(self._channel)
        return self._recommendation_pb2, self._stub

    async def _metadata(self, auth_metadata: dict[str, str]) -> list[tuple[str, str]]:
        metadata = _trusted_forward_metadata(auth_metadata)
        token = await self._serverless_auth_token_provider.get_token()
        if token:
            metadata["x-serverless-authorization"] = _bearer_token(token)
        return _metadata(metadata)


def build_serverless_auth_token_provider(config: ChatbotConfig) -> ServerlessAuthTokenProvider:
    mode = config.recommendation_service_serverless_auth_mode.strip().lower().replace("-", "_")
    if mode in {"", "none"}:
        return NoopServerlessAuthTokenProvider()
    if mode == "bearer_env":
        return EnvServerlessAuthTokenProvider(config.recommendation_service_serverless_token_env)
    if mode == "google_id_token":
        return MetadataServerlessAuthTokenProvider(
            config.recommendation_service_serverless_audience
        )
    raise ValueError(
        "unsupported RECOMMENDATION_SERVICE_SERVERLESS_AUTH_MODE: "
        f"{config.recommendation_service_serverless_auth_mode}"
    )


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


def _trusted_forward_metadata(auth_metadata: dict[str, str]) -> dict[str, str]:
    return {
        str(key).lower(): str(value)
        for key, value in auth_metadata.items()
        if str(key).lower() != "x-serverless-authorization"
    }


def _bearer_token(token: str) -> str:
    token = token.strip()
    if token.lower().startswith("bearer "):
        return token
    return f"Bearer {token}"


def _message_to_dict(message: Any) -> dict[str, Any]:
    return json_format.MessageToDict(
        message,
        preserving_proto_field_name=True,
        use_integers_for_enums=False,
    )


def _enum_value(module: Any, name: str, default: str) -> int:
    return int(getattr(module, name, getattr(module, default)))
