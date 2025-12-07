"""
In-memory rate limit store implementation
Suitable for single-process applications
"""
import asyncio
import time
from typing import Optional
from ..types import RateLimitStore


class StoreEntry:
    """Internal storage entry"""

    def __init__(self, count: int, expires_at: float) -> None:
        self.count = count
        self.expires_at = expires_at


class MemoryStore(RateLimitStore):
    """
    In-memory implementation of RateLimitStore.
    Uses a dict with automatic cleanup of expired entries.
    """

    def __init__(self, cleanup_interval_seconds: float = 60.0) -> None:
        """
        Create a new MemoryStore.

        Args:
            cleanup_interval_seconds: How often to run cleanup (seconds). Default: 60
        """
        self._store: dict[str, StoreEntry] = {}
        self._cleanup_interval = cleanup_interval_seconds
        self._cleanup_task: Optional[asyncio.Task] = None
        self._closed = False

    async def _start_cleanup(self) -> None:
        """Start the cleanup task"""
        if self._cleanup_task is None and not self._closed:
            self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def _cleanup_loop(self) -> None:
        """Run cleanup periodically"""
        while not self._closed:
            try:
                await asyncio.sleep(self._cleanup_interval)
                self._cleanup()
            except asyncio.CancelledError:
                break
            except Exception:
                pass

    def _cleanup(self) -> None:
        """Remove expired entries"""
        now = time.time()
        expired = [key for key, entry in self._store.items() if entry.expires_at <= now]
        for key in expired:
            del self._store[key]

    async def get_count(self, key: str) -> int:
        """Get the current count for a key"""
        entry = self._store.get(key)
        if entry is None:
            return 0

        if entry.expires_at <= time.time():
            del self._store[key]
            return 0

        return entry.count

    async def increment(self, key: str, ttl_seconds: float) -> int:
        """Increment the count for a key"""
        await self._start_cleanup()

        now = time.time()
        entry = self._store.get(key)

        if entry is None or entry.expires_at <= now:
            # Create new entry
            self._store[key] = StoreEntry(count=1, expires_at=now + ttl_seconds)
            return 1

        # Increment existing entry
        entry.count += 1
        return entry.count

    async def get_ttl(self, key: str) -> float:
        """Get the TTL remaining for a key"""
        entry = self._store.get(key)
        if entry is None:
            return 0

        remaining = entry.expires_at - time.time()
        return max(0, remaining)

    async def reset(self, key: str) -> None:
        """Reset the count for a key"""
        self._store.pop(key, None)

    async def close(self) -> None:
        """Close the store and cleanup resources"""
        self._closed = True
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        self._store.clear()

    @property
    def size(self) -> int:
        """Get the current size of the store (for debugging)"""
        return len(self._store)


def create_memory_store(cleanup_interval_seconds: float = 60.0) -> MemoryStore:
    """Create a new MemoryStore instance"""
    return MemoryStore(cleanup_interval_seconds)
