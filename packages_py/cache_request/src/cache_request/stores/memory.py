"""
Memory store implementations for cache_request.
"""
import asyncio
import time
from typing import Dict, Optional, TypeVar

from ..types import (
    CacheRequestStore,
    StoredResponse,
    SingleflightStore,
    InFlightRequest,
)

T = TypeVar("T")


class MemoryCacheStore(CacheRequestStore):
    """
    In-memory cache store for idempotency responses.
    """

    def __init__(self, cleanup_interval_seconds: float = 60.0) -> None:
        self._cache: Dict[str, StoredResponse] = {}
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._closed = False

    async def _start_cleanup(self) -> None:
        """Start the background cleanup task."""
        if self._cleanup_task is None and not self._closed:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Background cleanup loop."""
        while not self._closed:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup()
            except asyncio.CancelledError:
                break

    def _cleanup(self) -> None:
        """Remove expired entries."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items() if entry.expires_at <= now
        ]
        for key in expired_keys:
            del self._cache[key]

    async def get(self, key: str) -> Optional[StoredResponse]:
        """Get a stored response by idempotency key."""
        entry = self._cache.get(key)
        if entry is None:
            return None

        # Check if expired
        if entry.expires_at <= time.time():
            del self._cache[key]
            return None

        return entry

    async def set(self, key: str, response: StoredResponse) -> None:
        """Store a response with an idempotency key."""
        self._cache[key] = response
        # Ensure cleanup is running
        await self._start_cleanup()

    async def has(self, key: str) -> bool:
        """Check if a key exists."""
        entry = self._cache.get(key)
        if entry is None:
            return False

        # Check if expired
        if entry.expires_at <= time.time():
            del self._cache[key]
            return False

        return True

    async def delete(self, key: str) -> bool:
        """Delete a stored response."""
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def clear(self) -> None:
        """Clear all stored responses."""
        self._cache.clear()

    async def size(self) -> int:
        """Get current size of store."""
        # Clean up expired entries first
        self._cleanup()
        return len(self._cache)

    async def close(self) -> None:
        """Close the store and release resources."""
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        self._cache.clear()


class MemorySingleflightStore(SingleflightStore):
    """
    In-memory store for tracking in-flight requests (singleflight).
    """

    def __init__(self) -> None:
        self._in_flight: Dict[str, InFlightRequest] = {}

    def get(self, fingerprint: str) -> Optional[InFlightRequest]:
        """Get an in-flight request by fingerprint."""
        return self._in_flight.get(fingerprint)

    def set(self, fingerprint: str, request: InFlightRequest) -> None:
        """Register an in-flight request."""
        self._in_flight[fingerprint] = request

    def delete(self, fingerprint: str) -> bool:
        """Remove an in-flight request."""
        if fingerprint in self._in_flight:
            del self._in_flight[fingerprint]
            return True
        return False

    def has(self, fingerprint: str) -> bool:
        """Check if a request is in-flight."""
        return fingerprint in self._in_flight

    def size(self) -> int:
        """Get current number of in-flight requests."""
        return len(self._in_flight)

    def clear(self) -> None:
        """Clear all in-flight requests."""
        self._in_flight.clear()


def create_memory_cache_store(
    cleanup_interval_seconds: float = 60.0,
) -> MemoryCacheStore:
    """Create a memory cache store."""
    return MemoryCacheStore(cleanup_interval_seconds)


def create_memory_singleflight_store() -> MemorySingleflightStore:
    """Create a memory singleflight store."""
    return MemorySingleflightStore()
