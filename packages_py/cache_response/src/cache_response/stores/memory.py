"""
In-memory cache store for RFC 7234 HTTP response caching.
"""
import asyncio
import json
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

from ..types import CacheResponseStore, CachedResponse


@dataclass
class LruEntry:
    """LRU cache entry."""

    response: CachedResponse
    size: int


@dataclass
class MemoryCacheStats:
    """Memory cache statistics."""

    entries: int
    size_bytes: int
    max_size_bytes: int
    max_entries: int
    utilization_percent: float


class MemoryCacheStore(CacheResponseStore):
    """
    In-memory cache store with LRU eviction.
    """

    def __init__(
        self,
        max_size: int = 100 * 1024 * 1024,  # 100MB default
        max_entries: int = 1000,
        max_entry_size: int = 5 * 1024 * 1024,  # 5MB default
        cleanup_interval_seconds: float = 60.0,
    ) -> None:
        self._cache: Dict[str, LruEntry] = {}
        self._current_size: int = 0
        self._max_size = max_size
        self._max_entries = max_entries
        self._max_entry_size = max_entry_size
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
            key
            for key, entry in self._cache.items()
            if entry.response.metadata.expires_at <= now
        ]
        for key in expired_keys:
            self._delete_entry(key)

    def _delete_entry(self, key: str) -> bool:
        """Delete an entry and update size tracking."""
        entry = self._cache.get(key)
        if entry:
            self._current_size -= entry.size
            del self._cache[key]
            return True
        return False

    def _calculate_entry_size(self, response: CachedResponse) -> int:
        """Calculate the size of a cache entry in bytes."""
        size = 0

        # Body size
        if response.body:
            size += len(response.body)

        # Metadata size (rough estimate)
        metadata_dict = {
            "url": response.metadata.url,
            "method": response.metadata.method,
            "status_code": response.metadata.status_code,
            "headers": response.metadata.headers,
            "cached_at": response.metadata.cached_at,
            "expires_at": response.metadata.expires_at,
            "etag": response.metadata.etag,
            "last_modified": response.metadata.last_modified,
            "cache_control": response.metadata.cache_control,
            "vary": response.metadata.vary,
        }
        size += len(json.dumps(metadata_dict, default=str))

        return size

    def _evict_if_needed(self, required_size: int) -> None:
        """Evict entries if needed to make room."""
        # Evict by size
        while self._current_size + required_size > self._max_size and self._cache:
            oldest_key = next(iter(self._cache))
            self._delete_entry(oldest_key)

        # Evict by entry count
        while len(self._cache) >= self._max_entries:
            oldest_key = next(iter(self._cache))
            self._delete_entry(oldest_key)

    def _move_to_end(self, key: str) -> None:
        """Move an entry to the end of the LRU queue."""
        if key in self._cache:
            entry = self._cache.pop(key)
            self._cache[key] = entry

    async def get(self, key: str) -> Optional[CachedResponse]:
        """Get a cached response by key."""
        entry = self._cache.get(key)
        if not entry:
            return None

        # Check if expired
        if entry.response.metadata.expires_at <= time.time():
            self._delete_entry(key)
            return None

        # Move to end for LRU
        self._move_to_end(key)

        return entry.response

    async def set(self, key: str, response: CachedResponse) -> None:
        """Store a response."""
        size = self._calculate_entry_size(response)

        # Don't cache if entry is too large
        if size > self._max_entry_size:
            return

        # Remove existing entry if present
        if key in self._cache:
            self._delete_entry(key)

        # Evict entries if needed
        self._evict_if_needed(size)

        # Store new entry
        self._cache[key] = LruEntry(response=response, size=size)
        self._current_size += size

        # Ensure cleanup is running
        await self._start_cleanup()

    async def has(self, key: str) -> bool:
        """Check if a key exists."""
        entry = self._cache.get(key)
        if not entry:
            return False

        # Check if expired
        if entry.response.metadata.expires_at <= time.time():
            self._delete_entry(key)
            return False

        return True

    async def delete(self, key: str) -> bool:
        """Delete a cached response."""
        return self._delete_entry(key)

    async def clear(self) -> None:
        """Clear all cached responses."""
        self._cache.clear()
        self._current_size = 0

    async def size(self) -> int:
        """Get current size of store."""
        self._cleanup()
        return len(self._cache)

    async def keys(self) -> List[str]:
        """Get all keys."""
        self._cleanup()
        return list(self._cache.keys())

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
        self._current_size = 0

    def get_stats(self) -> MemoryCacheStats:
        """Get cache statistics."""
        return MemoryCacheStats(
            entries=len(self._cache),
            size_bytes=self._current_size,
            max_size_bytes=self._max_size,
            max_entries=self._max_entries,
            utilization_percent=(self._current_size / self._max_size) * 100
            if self._max_size > 0
            else 0,
        )


def create_memory_cache_store(
    max_size: int = 100 * 1024 * 1024,
    max_entries: int = 1000,
    max_entry_size: int = 5 * 1024 * 1024,
    cleanup_interval_seconds: float = 60.0,
) -> MemoryCacheStore:
    """Create a memory cache store."""
    return MemoryCacheStore(
        max_size=max_size,
        max_entries=max_entries,
        max_entry_size=max_entry_size,
        cleanup_interval_seconds=cleanup_interval_seconds,
    )
