"""gRPC server bootstrap for ai-chatbot-service."""

from __future__ import annotations

import asyncio
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from chatbot_service.app import build_chatbot_pipeline, build_conversation_repository
from chatbot_service.cache import build_cache
from chatbot_service.clients.recommendation_client import GrpcRecommendationClient
from chatbot_service.config import ChatbotConfig, load_config
from chatbot_service.grpc_service import build_chatbot_servicer
from chatbot_service.metrics import MetricsRecorder

LOGGER = logging.getLogger(__name__)


class GeneratedGrpcMissingError(RuntimeError):
    """Raised when generated protobuf modules have not been created yet."""


@dataclass(frozen=True)
class GeneratedChatbotGrpc:
    chatbot_pb2: Any
    chatbot_pb2_grpc: Any


def normalize_grpc_addr(addr: str) -> str:
    """Convert ':9100' style config into a gRPC listen address."""

    if addr.startswith(":"):
        return f"[::]{addr}"
    return addr


def load_generated_chatbot_grpc() -> GeneratedChatbotGrpc:
    """Load generated chatbot protobuf modules.

    Generate them with:
    python -m grpc_tools.protoc -I proto \
      --python_out=src/chatbot_service/generated \
      --grpc_python_out=src/chatbot_service/generated \
      proto/chatbot/v1/chatbot.proto
    """

    generated_root = Path(__file__).resolve().parent / "generated"
    if str(generated_root) not in sys.path:
        sys.path.insert(0, str(generated_root))

    try:
        from chatbot.v1 import chatbot_pb2, chatbot_pb2_grpc
    except (ImportError, ModuleNotFoundError) as exc:
        raise GeneratedGrpcMissingError(
            "Generated chatbot gRPC modules are missing. "
            "Run the proto generation command documented in scripts/README.md."
        ) from exc
    return GeneratedChatbotGrpc(
        chatbot_pb2=chatbot_pb2,
        chatbot_pb2_grpc=chatbot_pb2_grpc,
    )


def register_health_service(server: Any, service_name: str) -> None:
    """Register standard gRPC health if grpcio-health-checking is installed."""

    try:
        from grpc_health.v1 import health, health_pb2, health_pb2_grpc
    except ModuleNotFoundError:
        LOGGER.warning("grpcio-health-checking is not installed; health service disabled")
        return

    health_servicer = health.HealthServicer()
    health_servicer.set(service_name, health_pb2.HealthCheckResponse.SERVING)
    health_pb2_grpc.add_HealthServicer_to_server(health_servicer, server)


async def serve(config: ChatbotConfig | None = None) -> None:
    """Start the async gRPC server.

    RPC handlers resolve auth metadata, call recommendation-service, generate a
    grounded answer, and use chatbot-owned storage when configured.
    """

    try:
        import grpc
    except ModuleNotFoundError as exc:
        raise RuntimeError("grpcio is required to start ai-chatbot-service.") from exc

    config = config or load_config()
    generated = load_generated_chatbot_grpc()
    service_name = generated.chatbot_pb2.DESCRIPTOR.services_by_name["ChatbotService"].full_name

    metrics = MetricsRecorder(snapshot_path=config.metrics_snapshot_path or None)
    cache = build_cache(config)
    recommendation_client = GrpcRecommendationClient.from_config(config)
    conversation_repository = build_conversation_repository(config, metrics=metrics)
    pipeline = build_chatbot_pipeline(
        config,
        recommendation_client,
        conversation_repository=conversation_repository,
        cache=cache,
        metrics=metrics,
    )

    server = grpc.aio.server()
    servicer = build_chatbot_servicer(
        generated.chatbot_pb2_grpc.ChatbotServiceServicer,
        config,
        generated.chatbot_pb2,
        pipeline,
        conversation_repository,
    )
    generated.chatbot_pb2_grpc.add_ChatbotServiceServicer_to_server(servicer, server)
    register_health_service(server, service_name)

    listen_addr = normalize_grpc_addr(config.service_addr)
    server.add_insecure_port(listen_addr)
    await server.start()
    LOGGER.info("ai-chatbot-service gRPC skeleton listening on %s", listen_addr)

    try:
        await server.wait_for_termination()
    except asyncio.CancelledError:
        await server.stop(grace=5)
        raise
    finally:
        await _close_if_available(conversation_repository)
        await _close_if_available(recommendation_client)
        await _close_if_available(cache)


async def _close_if_available(value: Any) -> None:
    close = getattr(value, "close", None)
    if close is not None:
        await close()


__all__ = [
    "GeneratedChatbotGrpc",
    "GeneratedGrpcMissingError",
    "load_generated_chatbot_grpc",
    "normalize_grpc_addr",
    "register_health_service",
    "serve",
]
