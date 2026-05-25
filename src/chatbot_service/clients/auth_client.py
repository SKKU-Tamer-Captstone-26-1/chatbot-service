"""Auth-service client interface.

The chatbot should derive identity from Authorization metadata and may fetch
caller profile/coarse location through auth-service if available.
"""
from typing import Any, Protocol

from chatbot_service.config import ChatbotConfig
from chatbot_service.domain.schemas import CallerContext


class AuthClient(Protocol):
    async def validate_token(self, authorization: str) -> Any: ...
    async def get_me(self, authorization: str) -> Any: ...


class AuthMetadataError(ValueError):
    """Raised when authenticated caller metadata is unavailable."""


class AuthMetadataResolver:
    """Resolve caller context from trusted gateway/auth metadata.

    This class intentionally does not look at chatbot request bodies.
    """

    def __init__(self, config: ChatbotConfig) -> None:
        self._user_id_key = config.auth_user_id_metadata_key.lower()
        self._authorization_key = config.auth_authorization_metadata_key.lower()

    def resolve(self, metadata: dict[str, str] | list[tuple[str, str]]) -> CallerContext:
        normalized = _normalize_metadata(metadata)
        user_id = normalized.get(self._user_id_key, "").strip()
        authorization = normalized.get(self._authorization_key, "").strip()
        if not user_id:
            raise AuthMetadataError(
                f"Missing authenticated user metadata: {self._user_id_key}"
            )
        return CallerContext(
            user_id=user_id,
            authorization=authorization,
            metadata=normalized,
        )


def _normalize_metadata(metadata: dict[str, str] | list[tuple[str, str]]) -> dict[str, str]:
    if isinstance(metadata, dict):
        items = metadata.items()
    else:
        items = metadata
    return {str(key).lower(): str(value) for key, value in items}
