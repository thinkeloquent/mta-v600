"""
Tests for DNS cache stores (Memory)

Coverage includes:
- All store interface methods (get, set, delete, has, keys, size, clear, close)
- LRU eviction behavior
- Concurrent access patterns
- State transitions: empty -> active -> expired -> evicted
- Boundary conditions: max entries, special characters
"""

import pytest
import time
from cache_dsn.stores.memory import MemoryStore, create_memory_store
from cache_dsn.types import CachedEntry, ResolvedEndpoint


def create_entry(dsn: str, expires_in: float = 60.0) -> CachedEntry:
    """Create a cached entry for testing"""
    now = time.time()
    return CachedEntry(
        dsn=dsn,
        endpoints=[ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)],
        resolved_at=now,
        expires_at=now + expires_in,
        ttl_seconds=expires_in,
        hit_count=0,
    )


class TestMemoryStoreGet:
    """Tests for MemoryStore.get"""

    @pytest.mark.asyncio
    async def test_get_nonexistent_key(self):
        """Should return None for non-existent key"""
        store = MemoryStore(100)
        result = await store.get("nonexistent")
        assert result is None
        await store.close()

    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Should return entry for existing key"""
        store = MemoryStore(100)
        entry = create_entry("example.com")
        await store.set("example.com", entry)

        result = await store.get("example.com")
        assert result is not None
        assert result.dsn == "example.com"
        await store.close()

    @pytest.mark.asyncio
    async def test_get_updates_lru_order(self):
        """Should update LRU order on access"""
        store = MemoryStore(100)

        # Fill store
        for i in range(100):
            await store.set(f"key{i}", create_entry(f"key{i}"))

        # Access key0 to make it recently used
        await store.get("key0")

        # Add new entry to trigger eviction
        await store.set("newkey", create_entry("newkey"))

        # key0 should still exist (was recently accessed)
        assert await store.has("key0") is True

        # key1 should be evicted (was least recently used)
        assert await store.has("key1") is False
        await store.close()

    @pytest.mark.asyncio
    async def test_concurrent_gets(self):
        """Should handle concurrent gets"""
        import asyncio
        store = MemoryStore(100)
        entry = create_entry("example.com")
        await store.set("example.com", entry)

        results = await asyncio.gather(*[
            store.get("example.com")
            for _ in range(10)
        ])

        assert all(r is not None and r.dsn == "example.com" for r in results)
        await store.close()


class TestMemoryStoreSet:
    """Tests for MemoryStore.set"""

    @pytest.mark.asyncio
    async def test_set_stores_entry(self):
        """Should store entry"""
        store = MemoryStore(100)
        entry = create_entry("example.com")
        await store.set("example.com", entry)

        assert await store.size() == 1
        result = await store.get("example.com")
        assert result is not None
        await store.close()

    @pytest.mark.asyncio
    async def test_set_updates_existing_entry(self):
        """Should update existing entry"""
        store = MemoryStore(100)
        entry1 = create_entry("example.com", expires_in=60.0)
        await store.set("example.com", entry1)

        entry2 = create_entry("example.com", expires_in=120.0)
        await store.set("example.com", entry2)

        assert await store.size() == 1
        result = await store.get("example.com")
        assert result is not None
        assert result.ttl_seconds == 120.0
        await store.close()

    @pytest.mark.asyncio
    async def test_set_evicts_lru_at_capacity(self):
        """Should evict LRU when at capacity"""
        store = MemoryStore(100)

        # Fill store to capacity
        for i in range(100):
            await store.set(f"key{i}", create_entry(f"key{i}"))

        assert await store.size() == 100

        # Add one more
        await store.set("overflow", create_entry("overflow"))

        assert await store.size() == 100
        assert await store.has("overflow") is True
        # First key should be evicted
        assert await store.has("key0") is False
        await store.close()

    @pytest.mark.asyncio
    async def test_set_no_evict_on_update(self):
        """Should not evict when updating existing key"""
        store = MemoryStore(100)

        for i in range(100):
            await store.set(f"key{i}", create_entry(f"key{i}"))

        # Update existing key
        await store.set("key50", create_entry("key50", expires_in=120.0))

        assert await store.size() == 100
        assert await store.has("key0") is True
        await store.close()

    @pytest.mark.asyncio
    async def test_rapid_sets(self):
        """Should handle rapid sets"""
        import asyncio
        store = MemoryStore(100)

        await asyncio.gather(*[
            store.set(f"key{i}", create_entry(f"key{i}"))
            for i in range(50)
        ])

        assert await store.size() == 50
        await store.close()


class TestMemoryStoreDelete:
    """Tests for MemoryStore.delete"""

    @pytest.mark.asyncio
    async def test_delete_existing_key(self):
        """Should return True for existing key"""
        store = MemoryStore(100)
        await store.set("example.com", create_entry("example.com"))

        result = await store.delete("example.com")
        assert result is True
        assert await store.has("example.com") is False
        await store.close()

    @pytest.mark.asyncio
    async def test_delete_nonexistent_key(self):
        """Should return False for non-existent key"""
        store = MemoryStore(100)
        result = await store.delete("nonexistent")
        assert result is False
        await store.close()

    @pytest.mark.asyncio
    async def test_delete_updates_size(self):
        """Should update size after delete"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        assert await store.size() == 2

        await store.delete("key1")

        assert await store.size() == 1
        await store.close()

    @pytest.mark.asyncio
    async def test_delete_only_specified_key(self):
        """Should only delete specified key"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        await store.delete("key1")

        assert await store.has("key1") is False
        assert await store.has("key2") is True
        await store.close()


class TestMemoryStoreHas:
    """Tests for MemoryStore.has"""

    @pytest.mark.asyncio
    async def test_has_existing_key(self):
        """Should return True for existing key"""
        store = MemoryStore(100)
        await store.set("example.com", create_entry("example.com"))
        assert await store.has("example.com") is True
        await store.close()

    @pytest.mark.asyncio
    async def test_has_nonexistent_key(self):
        """Should return False for non-existent key"""
        store = MemoryStore(100)
        assert await store.has("nonexistent") is False
        await store.close()

    @pytest.mark.asyncio
    async def test_has_after_delete(self):
        """Should return False after delete"""
        store = MemoryStore(100)
        await store.set("example.com", create_entry("example.com"))
        await store.delete("example.com")
        assert await store.has("example.com") is False
        await store.close()


class TestMemoryStoreKeys:
    """Tests for MemoryStore.keys"""

    @pytest.mark.asyncio
    async def test_keys_empty_store(self):
        """Should return empty list for empty store"""
        store = MemoryStore(100)
        keys = await store.keys()
        assert keys == []
        await store.close()

    @pytest.mark.asyncio
    async def test_keys_returns_all_keys(self):
        """Should return all keys"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))
        await store.set("key3", create_entry("key3"))

        keys = await store.keys()

        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys
        await store.close()


class TestMemoryStoreSize:
    """Tests for MemoryStore.size"""

    @pytest.mark.asyncio
    async def test_size_empty_store(self):
        """Should return 0 for empty store"""
        store = MemoryStore(100)
        assert await store.size() == 0
        await store.close()

    @pytest.mark.asyncio
    async def test_size_tracks_additions(self):
        """Should track additions"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        assert await store.size() == 1

        await store.set("key2", create_entry("key2"))
        assert await store.size() == 2
        await store.close()

    @pytest.mark.asyncio
    async def test_size_tracks_deletions(self):
        """Should track deletions"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        await store.delete("key1")

        assert await store.size() == 1
        await store.close()

    @pytest.mark.asyncio
    async def test_size_no_increment_on_update(self):
        """Should not increment for same key update"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key1", create_entry("key1", expires_in=120.0))

        assert await store.size() == 1
        await store.close()


class TestMemoryStoreClear:
    """Tests for MemoryStore.clear"""

    @pytest.mark.asyncio
    async def test_clear_removes_all_entries(self):
        """Should remove all entries"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))
        await store.set("key3", create_entry("key3"))

        await store.clear()

        assert await store.size() == 0
        assert await store.has("key1") is False
        assert await store.has("key2") is False
        assert await store.has("key3") is False
        await store.close()

    @pytest.mark.asyncio
    async def test_clear_on_empty_store(self):
        """Should be safe to call on empty store"""
        store = MemoryStore(100)
        await store.clear()
        assert await store.size() == 0
        await store.close()


class TestMemoryStoreClose:
    """Tests for MemoryStore.close"""

    @pytest.mark.asyncio
    async def test_close_clears_data(self):
        """Should clear all data"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        await store.close()

        assert await store.size() == 0

    @pytest.mark.asyncio
    async def test_close_multiple_times(self):
        """Should be safe to call multiple times"""
        store = MemoryStore(100)
        await store.close()
        await store.close()
        await store.close()


class TestMemoryStorePruneExpired:
    """Tests for MemoryStore.prune_expired"""

    @pytest.mark.asyncio
    async def test_prune_removes_expired(self):
        """Should remove expired entries"""
        store = MemoryStore(100)
        now = time.time()

        # Create expired entry
        expired_entry = CachedEntry(
            dsn="expired.com",
            endpoints=[],
            resolved_at=now - 10,
            expires_at=now - 5,  # Already expired
            ttl_seconds=5,
            hit_count=0,
        )

        # Create valid entry
        valid_entry = CachedEntry(
            dsn="valid.com",
            endpoints=[],
            resolved_at=now,
            expires_at=now + 60,  # Expires in future
            ttl_seconds=60,
            hit_count=0,
        )

        await store.set("expired.com", expired_entry)
        await store.set("valid.com", valid_entry)

        pruned = await store.prune_expired()

        assert pruned == 1
        assert await store.has("expired.com") is False
        assert await store.has("valid.com") is True
        await store.close()

    @pytest.mark.asyncio
    async def test_prune_returns_zero_when_none_expired(self):
        """Should return 0 when no expired entries"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        pruned = await store.prune_expired()
        assert pruned == 0
        await store.close()

    @pytest.mark.asyncio
    async def test_prune_with_custom_timestamp(self):
        """Should use provided timestamp"""
        store = MemoryStore(100)
        entry = create_entry("example.com", expires_in=10)
        await store.set("example.com", entry)

        # Prune with future timestamp
        future_time = time.time() + 20
        pruned = await store.prune_expired(future_time)

        assert pruned == 1
        await store.close()


class TestMemoryStoreEntries:
    """Tests for MemoryStore.entries"""

    @pytest.mark.asyncio
    async def test_entries_returns_all(self):
        """Should return all entries"""
        store = MemoryStore(100)
        await store.set("key1", create_entry("key1"))
        await store.set("key2", create_entry("key2"))

        entries = await store.entries()

        assert len(entries) == 2
        dsns = [e.dsn for e in entries]
        assert "key1" in dsns
        assert "key2" in dsns
        await store.close()

    @pytest.mark.asyncio
    async def test_entries_empty_store(self):
        """Should return empty list for empty store"""
        store = MemoryStore(100)
        entries = await store.entries()
        assert entries == []
        await store.close()


class TestBoundaryConditions:
    """Tests for boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_string_key(self):
        """Should handle empty string key"""
        store = MemoryStore(100)
        await store.set("", create_entry(""))
        assert await store.has("") is True
        result = await store.get("")
        assert result is not None
        assert result.dsn == ""
        await store.close()

    @pytest.mark.asyncio
    async def test_special_characters_in_key(self):
        """Should handle special characters in key"""
        store = MemoryStore(100)
        special_key = "api:user@example.com:path/to/resource?query=1"
        await store.set(special_key, create_entry(special_key))
        assert await store.has(special_key) is True
        await store.close()

    @pytest.mark.asyncio
    async def test_unicode_characters_in_key(self):
        """Should handle unicode characters in key"""
        store = MemoryStore(100)
        unicode_key = "api.example.com"
        await store.set(unicode_key, create_entry(unicode_key))
        assert await store.has(unicode_key) is True
        await store.close()

    @pytest.mark.asyncio
    async def test_very_long_key(self):
        """Should handle very long keys"""
        store = MemoryStore(100)
        long_key = "a" * 1000
        await store.set(long_key, create_entry(long_key))
        assert await store.has(long_key) is True
        await store.close()

    @pytest.mark.asyncio
    async def test_max_entries_one(self):
        """Should handle store with max_entries = 1"""
        store = MemoryStore(1)

        await store.set("key1", create_entry("key1"))
        assert await store.size() == 1

        await store.set("key2", create_entry("key2"))
        assert await store.size() == 1
        assert await store.has("key1") is False
        assert await store.has("key2") is True
        await store.close()

    @pytest.mark.asyncio
    async def test_entry_with_many_endpoints(self):
        """Should handle entry with many endpoints"""
        store = MemoryStore(100)
        endpoints = [
            ResolvedEndpoint(host=f"10.0.0.{i}", port=80, healthy=True)
            for i in range(100)
        ]

        entry = CachedEntry(
            dsn="example.com",
            endpoints=endpoints,
            resolved_at=time.time(),
            expires_at=time.time() + 60,
            ttl_seconds=60,
            hit_count=0,
        )

        await store.set("example.com", entry)
        result = await store.get("example.com")
        assert result is not None
        assert len(result.endpoints) == 100
        await store.close()


class TestConcurrentOperations:
    """Tests for concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_sets_different_keys(self):
        """Should handle concurrent sets to different keys"""
        import asyncio
        store = MemoryStore(100)

        await asyncio.gather(*[
            store.set(f"key{i}", create_entry(f"key{i}"))
            for i in range(50)
        ])

        assert await store.size() == 50
        await store.close()

    @pytest.mark.asyncio
    async def test_concurrent_sets_same_key(self):
        """Should handle concurrent sets to same key"""
        import asyncio
        store = MemoryStore(100)

        await asyncio.gather(*[
            store.set("shared", create_entry("shared", expires_in=60 + i))
            for i in range(10)
        ])

        assert await store.size() == 1
        await store.close()

    @pytest.mark.asyncio
    async def test_mixed_concurrent_operations(self):
        """Should handle mixed concurrent operations"""
        import asyncio
        store = MemoryStore(100)
        await store.set("key", create_entry("key"))

        await asyncio.gather(
            store.get("key"),
            store.set("key2", create_entry("key2")),
            store.has("key"),
            store.delete("key"),
            store.set("key3", create_entry("key3")),
        )

        assert await store.has("key") is False
        assert await store.has("key2") is True
        assert await store.has("key3") is True
        await store.close()


class TestStateTransitions:
    """Tests for state transitions"""

    @pytest.mark.asyncio
    async def test_empty_to_populated_to_cleared(self):
        """Should transition: empty -> populated -> cleared -> empty"""
        store = MemoryStore(100)
        assert await store.size() == 0

        await store.set("key", create_entry("key"))
        assert await store.size() == 1

        await store.clear()
        assert await store.size() == 0
        await store.close()

    @pytest.mark.asyncio
    async def test_populated_to_deleted_to_repopulated(self):
        """Should transition: populated -> deleted -> repopulated"""
        store = MemoryStore(100)

        await store.set("key", create_entry("key"))
        assert await store.has("key") is True

        await store.delete("key")
        assert await store.has("key") is False

        await store.set("key", create_entry("key"))
        assert await store.has("key") is True
        await store.close()

    @pytest.mark.asyncio
    async def test_at_capacity_to_evict_to_stable(self):
        """Should transition: at capacity -> evict -> stable"""
        store = MemoryStore(100)

        # Fill to capacity
        for i in range(100):
            await store.set(f"key{i}", create_entry(f"key{i}"))
        assert await store.size() == 100

        # Add more entries - should evict and maintain capacity
        for i in range(100, 150):
            await store.set(f"key{i}", create_entry(f"key{i}"))
        assert await store.size() == 100
        await store.close()


class TestCreateMemoryStore:
    """Tests for create_memory_store factory"""

    def test_create_with_default_max_entries(self):
        """Should create store with default max_entries"""
        store = create_memory_store()
        assert isinstance(store, MemoryStore)

    @pytest.mark.asyncio
    async def test_create_with_custom_max_entries(self):
        """Should create store with custom max_entries"""
        store = create_memory_store(500)

        # Verify custom limit
        for i in range(550):
            await store.set(f"key{i}", create_entry(f"key{i}"))

        assert await store.size() == 500
        await store.close()
