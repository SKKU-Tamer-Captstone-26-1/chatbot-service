import pytest

from chatbot_service.clients.auth_client import AuthMetadataError, AuthMetadataResolver
from chatbot_service.config import load_config


def test_auth_metadata_resolver_uses_metadata_only(monkeypatch):
    monkeypatch.setenv("CHATBOT_AUTH_USER_ID_METADATA_KEY", "x-auth-user")
    config = load_config()

    caller = AuthMetadataResolver(config).resolve(
        [
            ("X-Auth-User", "user_123"),
            ("Authorization", "Bearer token"),
        ]
    )

    assert caller.user_id == "user_123"
    assert caller.authorization == "Bearer token"
    assert caller.metadata["x-auth-user"] == "user_123"


def test_auth_metadata_resolver_rejects_missing_user_id(monkeypatch):
    config = load_config()

    with pytest.raises(AuthMetadataError):
        AuthMetadataResolver(config).resolve({"authorization": "Bearer token"})
