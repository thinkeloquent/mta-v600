"""
Redis rate limit store implementation
Suitable for distributed applications
"""
from typing import Any, Protocol
from ..types import RateLimitStore


class RedisClientProtocol(Protocol):
    """Protocol for Redis client (compatible with redis-py async)"""

    async def incr(self, name: str) -> int:
        ...

    async def pexpire(self, name: str, time: int) -> bool:
        ...

    async def get(self, name: str) -> Any:
        ...

    async def pttl(self, name: str) -> int:
        ...

    async def delete(self, *names: str) -> int:
        ...

    async def close(self) -> None:
        ...


class RedisStore(RateLimitStore):
    """
    Redis implementation of RateLimitStore.
    Uses Redis for distributed rate limiting across multiple processes/servers.
    """

    def __init__(
        self, client: RedisClientProtocol, key_prefix: str = "ratelimit:"
    ) -> None:
        """
        Create a new RedisStore.

        Args:
            client: Redis client (async redis-py instance)
            key_prefix: Prefix for all keys. Default: 'ratelimit:'
        """
        self._client = client
        self._key_prefix = key_prefix

    def _get_key(self, key: str) -> str:
        """Get the full key with prefix"""
        return f"{self._key_prefix}{key}"

    async def get_count(self, key: str) -> int:
        """Get the current count for a key"""
        value = await self._client.get(self._get_key(key))
        return int(value) if value else 0

    async def increment(self, key: str, ttl_seconds: float) -> int:
        """
        Increment the count for a key.
        Uses INCR + PEXPIRE in sequence (not atomic, but sufficient for rate limiting)
        """
        full_key = self._get_key(key)
        count = await self._client.incr(full_key)

        # Set expiry only on first increment (when count is 1)
        if count == 1:
            await self._client.pexpire(full_key, int(ttl_seconds * 1000))

        return count

    async def get_ttl(self, key: str) -> float:
        """Get the TTL remaining for a key"""
        ttl_ms = await self._client.pttl(self._get_key(key))
        # PTTL returns -2 if key doesn't exist, -1 if no expiry
        return ttl_ms / 1000 if ttl_ms > 0 else 0

    async def reset(self, key: str) -> None:
        """Reset the count for a key"""
        await self._client.delete(self._get_key(key))

    async def close(self) -> None:
        """Close the store and cleanup resources"""
        await self._client.close()


def create_redis_store(
    client: RedisClientProtocol, key_prefix: str = "ratelimit:"
) -> RedisStore:
    """
    Create a new RedisStore instance.

    Args:
        client: Redis client (async redis-py instance)
        key_prefix: Prefix for all keys

    Returns:
        RedisStore instance
    """
    return RedisStore(client, key_prefix)
