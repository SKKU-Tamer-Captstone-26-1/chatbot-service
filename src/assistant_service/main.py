"""ai-assistant-service skeleton entrypoint.

TODO:
- implement gRPC server from proto/assistant/v1/assistant.proto
- wire AuthClient, RecommendationClient, MapContextClient
- wire Guardrails, ContextBuilder, LLMAdapter, ResponseBuilder
"""
from assistant_service.config import load_config


def main() -> None:
    config = load_config()
    print(f"assistant-service skeleton configured on {config.service_addr}")


if __name__ == "__main__":
    main()
