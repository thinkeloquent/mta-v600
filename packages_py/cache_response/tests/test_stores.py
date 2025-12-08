"""Tests for cache stores."""
import asyncio
import json
import time
import pytest

from cache_response import (
    MemoryCacheStore,
    create_memory_cache_store,
    CachedResponse,
    CacheEntryMetadata,
)


def create_response(key: str, expires_in_seconds: float = 60) -> CachedResponse:
    """Create a test response."""
    now = time.time()
    return CachedResponse(
        metadata=CacheEntryMetadata(
            url=f"https://example.com/{key}",
            method="GET",
            status_code=200,
            headers={"content-type": "application/json"},
            cached_at=now,
            expires_at=now + expires_in_seconds,
        ),
        body=json.dumps({"key": key}).encode(),
    )


@pytest.fixture
async def store():
    """Create a MemoryCacheStore for testing."""
    s = MemoryCacheStore(
        max_size=1024 * 1024,  # 1MB
        max_entries=100,
        max_entry_size=100 * 1024,  # 100KB
        cleanup_interval_seconds=1.0,
    )
    yield s
    await s.close()


class TestGetSet:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, store):
        response = create_response("test")
        await store.set("key1", response)

        retrieved = await store.get("key1")
        assert retrieved is not None
        assert retrieved.metadata.url == "https://example.com/test"
        assert retrieved.body == json.dumps({"key": "test"}).encode()

    @pytest.mark.asyncio
    async def test_return_none_for_nonexistent(self, store):
        result = await store.get("non-existent")
        assert result is None

    @pytest.mark.asyncio
    async def test_overwrite_existing_key(self, store):
        await store.set("key1", create_response("first"))
        await store.set("key1", create_response("second"))

        retrieved = await store.get("key1")
        assert retrieved.body == json.dumps({"key": "second"}).encode()


class TestHas:
    @pytest.mark.asyncio
    async def test_true_for_existing(self, store):
        await store.set("key1", create_response("test"))
        assert await store.has("key1") is True

    @pytest.mark.asyncio
    async def test_false_for_nonexistent(self, store):
        assert await store.has("non-existent") is False


class TestDelete:
    @pytest.mark.asyncio
    async def test_delete_existing(self, store):
        await store.set("key1", create_response("test"))
        assert await store.delete("key1") is True
        assert await store.has("key1") is False

    @pytest.mark.asyncio
    async def test_delete_nonexistent(self, store):
        assert await store.delete("non-existent") is False


class TestClear:
    @pytest.mark.asyncio
    async def test_remove_all_entries(self, store):
        await store.set("key1", create_response("test1"))
        await store.set("key2", create_response("test2"))
        await store.set("key3", create_response("test3"))

        await store.clear()

        assert await store.size() == 0


class TestSize:
    @pytest.mark.asyncio
    async def test_correct_count(self, store):
        assert await store.size() == 0

        await store.set("key1", create_response("test1"))
        assert await store.size() == 1

        await store.set("key2", create_response("test2"))
        assert await store.size() == 2

        await store.delete("key1")
        assert await store.size() == 1


class TestKeys:
    @pytest.mark.asyncio
    async def test_return_all_keys(self, store):
        await store.set("key1", create_response("test1"))
        await store.set("key2", create_response("test2"))
        await store.set("key3", create_response("test3"))

        keys = await store.keys()
        assert len(keys) == 3
        assert "key1" in keys
        assert "key2" in keys
        assert "key3" in keys


class TestExpiration:
    @pytest.mark.asyncio
    async def test_return_none_for_expired(self, store):
        response = create_response("test", expires_in_seconds=-1)  # Already expired
        await store.set("expired", response)

        result = await store.get("expired")
        assert result is None

    @pytest.mark.asyncio
    async def test_remove_expired_on_has(self, store):
        response = create_response("test", expires_in_seconds=-1)
        await store.set("expired", response)

        assert await store.has("expired") is False

    @pytest.mark.asyncio
    async def test_cleanup_expired_entries(self):
        fast_store = MemoryCacheStore(cleanup_interval_seconds=0.1)

        response = create_response("test", expires_in_seconds=0.05)
        await fast_store.set("key1", response)

        assert await fast_store.has("key1") is True

        # Wait for expiration and cleanup
        await asyncio.sleep(0.2)

        assert await fast_store.size() == 0

        await fast_store.close()


class TestLruEviction:
    @pytest.mark.asyncio
    async def test_evict_oldest_when_max_entries_exceeded(self):
        small_store = MemoryCacheStore(max_entries=3)

        await small_store.set("key1", create_response("test1"))
        await small_store.set("key2", create_response("test2"))
        await small_store.set("key3", create_response("test3"))
        await small_store.set("key4", create_response("test4"))

        assert await small_store.size() == 3
        assert await small_store.has("key1") is False  # Evicted
        assert await small_store.has("key4") is True  # Most recent

        await small_store.close()

    @pytest.mark.asyncio
    async def test_no_store_large_entries(self):
        small_store = MemoryCacheStore(max_entry_size=10)  # Very small

        # This response is larger than 10 bytes
        await small_store.set("key1", create_response("test"))

        assert await small_store.size() == 0

        await small_store.close()

    @pytest.mark.asyncio
    async def test_move_accessed_to_end(self):
        small_store = MemoryCacheStore(max_entries=3)

        await small_store.set("key1", create_response("test1"))
        await small_store.set("key2", create_response("test2"))
        await small_store.set("key3", create_response("test3"))

        # Access key1 to move it to end
        await small_store.get("key1")

        # Add new entry, should evict key2 (now oldest)
        await small_store.set("key4", create_response("test4"))

        assert await small_store.has("key1") is True  # Still there
        assert await small_store.has("key2") is False  # Evicted

        await small_store.close()


class TestGetStats:
    @pytest.mark.asyncio
    async def test_return_statistics(self, store):
        await store.set("key1", create_response("test1"))
        await store.set("key2", create_response("test2"))

        stats = store.get_stats()
        assert stats.entries == 2
        assert stats.size_bytes > 0
        assert stats.max_size_bytes == 1024 * 1024
        assert stats.max_entries == 100
        assert stats.utilization_percent > 0


class TestCreateMemoryCacheStore:
    def test_create_with_defaults(self):
        store = create_memory_cache_store()
        assert isinstance(store, MemoryCacheStore)

    def test_create_with_custom_options(self):
        store = create_memory_cache_store(
            max_size=50 * 1024 * 1024,
            max_entries=500,
        )
        stats = store.get_stats()
        assert stats.max_size_bytes == 50 * 1024 * 1024
        assert stats.max_entries == 500
