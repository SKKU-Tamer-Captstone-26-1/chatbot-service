"""Auth-service client interface.

The assistant should derive identity from Authorization metadata and may fetch
caller profile/coarse location through auth-service if available.
"""
from typing import Protocol, Any


class AuthClient(Protocol):
    async def validate_token(self, authorization: str) -> Any: ...
    async def get_me(self, authorization: str) -> Any: ...
