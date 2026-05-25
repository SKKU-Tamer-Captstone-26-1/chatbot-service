from __future__ import annotations

import copy
import json
import time
from dataclasses import dataclass
from typing import Any, Protocol

from chatbot_service.config import ChatbotConfig


class Cache(Protocol):
    async def get(self, key: str) -> Any | None: ...
    async def set(self, key: str, value: Any, ttl_sec: int) -> None: ...


class NullCache:
    async def get(self, key: str) -> Any | None:
        return None

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        return None


@dataclass
class _CacheEntry:
    value: Any
    expires_at: float


class InMemoryCache:
    """Process-local TTL cache used for tests and single-process development."""

    def __init__(self, clock=time.monotonic) -> None:
        self._clock = clock
        self._items: dict[str, _CacheEntry] = {}

    async def get(self, key: str) -> Any | None:
        entry = self._items.get(key)
        if entry is None:
            return None
        if entry.expires_at <= self._clock():
            self._items.pop(key, None)
            return None
        return copy.deepcopy(entry.value)

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        if ttl_sec <= 0:
            return
        self._items[key] = _CacheEntry(
            value=copy.deepcopy(value),
            expires_at=self._clock() + ttl_sec,
        )


class RedisCache:
    """Redis/Memorystore cache backend.

    The redis dependency is loaded only when this backend is configured so local
    tests can run without a Redis server or credentials.
    """

    def __init__(self, url: str, *, key_prefix: str = "chatbot") -> None:
        if not url:
            raise ValueError("CHATBOT_CACHE_REDIS_URL is required for redis cache backend")
        try:
            from redis import asyncio as redis_asyncio
        except ModuleNotFoundError as exc:
            raise RuntimeError("redis package is required for CHATBOT_CACHE_BACKEND=redis") from exc
        self._client = redis_asyncio.from_url(url, encoding="utf-8", decode_responses=True)
        self._key_prefix = key_prefix.rstrip(":")

    async def get(self, key: str) -> Any | None:
        raw = await self._client.get(self._namespaced(key))
        if raw is None:
            return None
        return json.loads(raw)["value"]

    async def set(self, key: str, value: Any, ttl_sec: int) -> None:
        if ttl_sec <= 0:
            return
        await self._client.set(
            self._namespaced(key),
            json.dumps({"value": value}, ensure_ascii=False, sort_keys=True),
            ex=ttl_sec,
        )

    async def close(self) -> None:
        await self._client.aclose()

    def _namespaced(self, key: str) -> str:
        return f"{self._key_prefix}:{key}"


def build_cache(config: ChatbotConfig) -> Cache:
    backend = config.cache_backend.strip().lower()
    if backend in {"", "none", "disabled"}:
        return NullCache()
    if backend == "memory":
        return InMemoryCache()
    if backend == "redis":
        return RedisCache(config.cache_redis_url)
    raise ValueError(f"Unsupported CHATBOT_CACHE_BACKEND: {config.cache_backend}")


__all__ = ["Cache", "InMemoryCache", "NullCache", "RedisCache", "build_cache"]
