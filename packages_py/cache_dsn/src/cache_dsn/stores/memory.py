"""
In-memory DNS cache store implementation
"""
import time
from typing import Optional

from ..types import CachedEntry, DnsCacheStore


class MemoryStore(DnsCacheStore):
    """
    In-memory DNS cache store with LRU eviction

    Example:
        store = MemoryStore(max_entries=1000)
        await store.set("example.com", cached_entry)
        entry = await store.get("example.com")
    """

    def __init__(self, max_entries: int = 1000) -> None:
        self._cache: dict[str, CachedEntry] = {}
        self._max_entries = max_entries
        self._lru_order: dict[str, float] = {}
        self._access_counter = 0.0

    async def get(self, key: str) -> Optional[CachedEntry]:
        """Get a cached entry"""
        entry = self._cache.get(key)
        if entry:
            # Update LRU access time
            self._access_counter += 1
            self._lru_order[key] = self._access_counter
        return entry

    async def set(self, key: str, entry: CachedEntry) -> None:
        """Set a cached entry"""
        # Evict if at capacity
        if key not in self._cache and len(self._cache) >= self._max_entries:
            await self._evict_lru()

        self._cache[key] = entry
        self._access_counter += 1
        self._lru_order[key] = self._access_counter

    async def delete(self, key: str) -> bool:
        """Delete a cached entry"""
        self._lru_order.pop(key, None)
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    async def has(self, key: str) -> bool:
        """Check if an entry exists"""
        return key in self._cache

    async def keys(self) -> list[str]:
        """Get all cached keys"""
        return list(self._cache.keys())

    async def size(self) -> int:
        """Get the number of cached entries"""
        return len(self._cache)

    async def clear(self) -> None:
        """Clear all cached entries"""
        self._cache.clear()
        self._lru_order.clear()
        self._access_counter = 0

    async def close(self) -> None:
        """Close the store"""
        await self.clear()

    async def _evict_lru(self) -> None:
        """Evict the least recently used entry"""
        if not self._lru_order:
            return

        oldest_key = min(self._lru_order, key=self._lru_order.get)  # type: ignore
        await self.delete(oldest_key)

    async def prune_expired(self, now: Optional[float] = None) -> int:
        """Remove all expired entries"""
        if now is None:
            now = time.time()

        pruned = 0
        keys_to_delete = [
            key for key, entry in self._cache.items()
            if now >= entry.expires_at
        ]

        for key in keys_to_delete:
            await self.delete(key)
            pruned += 1

        return pruned

    async def entries(self) -> list[CachedEntry]:
        """Get all entries (for debugging/stats)"""
        return list(self._cache.values())


def create_memory_store(max_entries: int = 1000) -> MemoryStore:
    """Create a memory store instance"""
    return MemoryStore(max_entries)
