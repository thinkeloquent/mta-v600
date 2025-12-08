"""
Tests for cache request stores (Memory implementations).

Coverage includes:
- Statement coverage: All executable statements
- Decision coverage: All branches (true/false)
- Condition coverage: All boolean conditions
- Path coverage: Key execution paths
- Boundary testing: Edge cases and limits
- State transitions: Store lifecycle states
- Concurrent operations: Parallel access patterns
"""
import asyncio
import time
import pytest
from typing import Any

from cache_request import (
    MemoryCacheStore,
    MemorySingleflightStore,
    create_memory_cache_store,
    create_memory_singleflight_store,
    StoredResponse,
    InFlightRequest,
)


class TestMemoryCacheStore:
    """Tests for MemoryCacheStore."""

    @pytest.fixture
    def store(self) -> MemoryCacheStore:
        """Create a fresh store for each test."""
        return MemoryCacheStore(cleanup_interval_seconds=60.0)

    # === get() tests ===

    async def test_get_returns_none_for_nonexistent_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return None for non-existent key."""
        result = await store.get("nonexistent")
        assert result is None

    async def test_get_returns_stored_response(self, store: MemoryCacheStore) -> None:
        """Should return stored response for existing key."""
        response = StoredResponse(
            value="test-value",
            cached_at=time.time(),
            expires_at=time.time() + 10,
        )
        await store.set("key", response)

        result = await store.get("key")
        assert result is not None
        assert result.value == "test-value"

    async def test_get_returns_none_for_expired_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return None for expired key and remove it."""
        response = StoredResponse(
            value="test-value",
            cached_at=time.time(),
            expires_at=time.time() - 1,  # Already expired
        )
        await store.set("key", response)

        result = await store.get("key")
        assert result is None
        assert await store.has("key") is False

    async def test_get_with_generic_types(self, store: MemoryCacheStore) -> None:
        """Should handle generic types correctly."""
        data = {"id": 1, "name": "test"}
        response = StoredResponse(
            value=data,
            cached_at=time.time(),
            expires_at=time.time() + 10,
        )
        await store.set("typed-key", response)

        result = await store.get("typed-key")
        assert result is not None
        assert result.value["id"] == 1
        assert result.value["name"] == "test"

    # === set() tests ===

    async def test_set_stores_new_entry(self, store: MemoryCacheStore) -> None:
        """Should store a new entry."""
        response = StoredResponse(
            value="value",
            cached_at=time.time(),
            expires_at=time.time() + 10,
        )
        await store.set("key", response)

        assert await store.has("key") is True

    async def test_set_overwrites_existing_entry(
        self, store: MemoryCacheStore
    ) -> None:
        """Should overwrite existing entry."""
        response1 = StoredResponse(
            value="first",
            cached_at=time.time(),
            expires_at=time.time() + 10,
        )
        response2 = StoredResponse(
            value="second",
            cached_at=time.time(),
            expires_at=time.time() + 10,
        )

        await store.set("key", response1)
        await store.set("key", response2)

        result = await store.get("key")
        assert result is not None
        assert result.value == "second"

    async def test_set_handles_multiple_keys(self, store: MemoryCacheStore) -> None:
        """Should handle multiple keys independently."""
        await store.set(
            "key1",
            StoredResponse(value="value1", cached_at=time.time(), expires_at=time.time() + 10),
        )
        await store.set(
            "key2",
            StoredResponse(value="value2", cached_at=time.time(), expires_at=time.time() + 10),
        )

        result1 = await store.get("key1")
        result2 = await store.get("key2")
        assert result1 is not None and result1.value == "value1"
        assert result2 is not None and result2.value == "value2"

    # === has() tests ===

    async def test_has_returns_false_for_nonexistent_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return False for non-existent key."""
        assert await store.has("nonexistent") is False

    async def test_has_returns_true_for_existing_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return True for existing key."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.has("key") is True

    async def test_has_returns_false_for_expired_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return False for expired key and remove it."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() - 1),
        )

        assert await store.has("key") is False

    # === delete() tests ===

    async def test_delete_returns_true_for_existing_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return True when deleting existing key."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        result = await store.delete("key")
        assert result is True
        assert await store.has("key") is False

    async def test_delete_returns_false_for_nonexistent_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return False when deleting non-existent key."""
        result = await store.delete("nonexistent")
        assert result is False

    async def test_delete_only_affects_specified_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should only delete specified key."""
        await store.set(
            "key1",
            StoredResponse(value="value1", cached_at=time.time(), expires_at=time.time() + 10),
        )
        await store.set(
            "key2",
            StoredResponse(value="value2", cached_at=time.time(), expires_at=time.time() + 10),
        )

        await store.delete("key1")

        assert await store.has("key1") is False
        assert await store.has("key2") is True

    # === clear() tests ===

    async def test_clear_removes_all_entries(self, store: MemoryCacheStore) -> None:
        """Should remove all entries."""
        await store.set(
            "key1",
            StoredResponse(value="value1", cached_at=time.time(), expires_at=time.time() + 10),
        )
        await store.set(
            "key2",
            StoredResponse(value="value2", cached_at=time.time(), expires_at=time.time() + 10),
        )

        await store.clear()

        assert await store.size() == 0

    async def test_clear_safe_on_empty_store(self, store: MemoryCacheStore) -> None:
        """Should be safe to call on empty store."""
        await store.clear()
        assert await store.size() == 0

    # === size() tests ===

    async def test_size_returns_zero_for_empty_store(
        self, store: MemoryCacheStore
    ) -> None:
        """Should return 0 for empty store."""
        assert await store.size() == 0

    async def test_size_returns_correct_count(self, store: MemoryCacheStore) -> None:
        """Should return correct count."""
        await store.set(
            "key1",
            StoredResponse(value="value1", cached_at=time.time(), expires_at=time.time() + 10),
        )
        await store.set(
            "key2",
            StoredResponse(value="value2", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.size() == 2

    async def test_size_cleans_expired_before_counting(
        self, store: MemoryCacheStore
    ) -> None:
        """Should cleanup expired entries before returning size."""
        await store.set(
            "key1",
            StoredResponse(value="value1", cached_at=time.time(), expires_at=time.time() - 1),
        )
        await store.set(
            "key2",
            StoredResponse(value="value2", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.size() == 1

    # === close() tests ===

    async def test_close_clears_all_data(self, store: MemoryCacheStore) -> None:
        """Should clear all data."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        await store.close()

        assert await store.size() == 0

    async def test_close_safe_to_call_multiple_times(
        self, store: MemoryCacheStore
    ) -> None:
        """Should be safe to call multiple times."""
        await store.close()
        await store.close()
        await store.close()

    # === Boundary conditions ===

    async def test_boundary_empty_string_key(self, store: MemoryCacheStore) -> None:
        """Should handle empty string key."""
        await store.set(
            "",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.has("") is True

    async def test_boundary_special_characters_in_key(
        self, store: MemoryCacheStore
    ) -> None:
        """Should handle special characters in key."""
        special_key = "key:with/special@chars#and$symbols"
        await store.set(
            special_key,
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.has(special_key) is True

    async def test_boundary_very_long_key(self, store: MemoryCacheStore) -> None:
        """Should handle very long key."""
        long_key = "a" * 10000
        await store.set(
            long_key,
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        assert await store.has(long_key) is True

    async def test_boundary_immediate_expiration(
        self, store: MemoryCacheStore
    ) -> None:
        """Should handle immediate expiration."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time()),
        )

        await asyncio.sleep(0.001)

        assert await store.has("key") is False

    # === Concurrent operations ===

    async def test_concurrent_sets(self, store: MemoryCacheStore) -> None:
        """Should handle concurrent sets."""
        async def set_key(i: int) -> None:
            await store.set(
                f"key{i}",
                StoredResponse(
                    value=f"value{i}",
                    cached_at=time.time(),
                    expires_at=time.time() + 10,
                ),
            )

        await asyncio.gather(*[set_key(i) for i in range(100)])

        assert await store.size() == 100

    async def test_concurrent_gets(self, store: MemoryCacheStore) -> None:
        """Should handle concurrent gets."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        results = await asyncio.gather(*[store.get("key") for _ in range(100)])

        assert all(r is not None and r.value == "value" for r in results)

    async def test_concurrent_mixed_operations(
        self, store: MemoryCacheStore
    ) -> None:
        """Should handle mixed concurrent operations."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )

        operations = [
            store.get("key"),
            store.has("key"),
            store.size(),
        ]

        await asyncio.gather(*operations)

    # === State transitions ===

    async def test_state_transition_empty_to_stored_to_deleted(
        self, store: MemoryCacheStore
    ) -> None:
        """Should transition: empty -> stored -> deleted -> empty."""
        # Empty state
        assert await store.has("key") is False

        # Stored state
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 10),
        )
        assert await store.has("key") is True

        # Deleted state
        await store.delete("key")
        assert await store.has("key") is False

    async def test_state_transition_stored_to_expired(
        self, store: MemoryCacheStore
    ) -> None:
        """Should transition: stored -> expired -> empty."""
        await store.set(
            "key",
            StoredResponse(value="value", cached_at=time.time(), expires_at=time.time() + 0.001),
        )
        assert await store.has("key") is True

        await asyncio.sleep(0.002)

        assert await store.has("key") is False

    # === Factory function ===

    def test_factory_creates_store_with_default_options(self) -> None:
        """Should create store with default options."""
        store = create_memory_cache_store()
        assert isinstance(store, MemoryCacheStore)

    def test_factory_creates_store_with_custom_cleanup_interval(self) -> None:
        """Should create store with custom cleanup interval."""
        store = create_memory_cache_store(cleanup_interval_seconds=30.0)
        assert isinstance(store, MemoryCacheStore)


class TestMemorySingleflightStore:
    """Tests for MemorySingleflightStore."""

    @pytest.fixture
    def store(self) -> MemorySingleflightStore:
        """Create a fresh store for each test."""
        return MemorySingleflightStore()

    # === get() tests ===

    def test_get_returns_none_for_nonexistent_fingerprint(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return None for non-existent fingerprint."""
        result = store.get("nonexistent")
        assert result is None

    def test_get_returns_stored_request(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return stored request for existing fingerprint."""
        loop = asyncio.new_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        request = InFlightRequest(
            future=future,
            subscribers=1,
            started_at=time.time(),
        )
        store.set("fingerprint", request)

        result = store.get("fingerprint")
        assert result is not None
        assert result.subscribers == 1
        loop.close()

    # === set() tests ===

    def test_set_stores_new_request(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should store a new in-flight request."""
        loop = asyncio.new_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        request = InFlightRequest(
            future=future,
            subscribers=1,
            started_at=time.time(),
        )
        store.set("fingerprint", request)

        assert store.has("fingerprint") is True
        loop.close()

    def test_set_overwrites_existing_request(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should overwrite existing request."""
        loop = asyncio.new_event_loop()
        future1: asyncio.Future[str] = loop.create_future()
        future2: asyncio.Future[str] = loop.create_future()
        request1 = InFlightRequest(future=future1, subscribers=1, started_at=time.time())
        request2 = InFlightRequest(future=future2, subscribers=2, started_at=time.time())

        store.set("fingerprint", request1)
        store.set("fingerprint", request2)

        result = store.get("fingerprint")
        assert result is not None
        assert result.subscribers == 2
        loop.close()

    # === delete() tests ===

    def test_delete_returns_true_for_existing_request(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return True when deleting existing request."""
        loop = asyncio.new_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        store.set("fingerprint", InFlightRequest(future=future, subscribers=1, started_at=time.time()))

        result = store.delete("fingerprint")
        assert result is True
        assert store.has("fingerprint") is False
        loop.close()

    def test_delete_returns_false_for_nonexistent_request(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return False when deleting non-existent request."""
        result = store.delete("nonexistent")
        assert result is False

    # === has() tests ===

    def test_has_returns_false_for_nonexistent(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return False for non-existent fingerprint."""
        assert store.has("nonexistent") is False

    def test_has_returns_true_for_existing(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return True for existing fingerprint."""
        loop = asyncio.new_event_loop()
        future: asyncio.Future[str] = loop.create_future()
        store.set("fingerprint", InFlightRequest(future=future, subscribers=1, started_at=time.time()))

        assert store.has("fingerprint") is True
        loop.close()

    # === size() tests ===

    def test_size_returns_zero_for_empty_store(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return 0 for empty store."""
        assert store.size() == 0

    def test_size_returns_correct_count(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should return correct count."""
        loop = asyncio.new_event_loop()
        future1: asyncio.Future[str] = loop.create_future()
        future2: asyncio.Future[str] = loop.create_future()
        store.set("fp1", InFlightRequest(future=future1, subscribers=1, started_at=time.time()))
        store.set("fp2", InFlightRequest(future=future2, subscribers=1, started_at=time.time()))

        assert store.size() == 2
        loop.close()

    # === clear() tests ===

    def test_clear_removes_all_requests(
        self, store: MemorySingleflightStore
    ) -> None:
        """Should remove all in-flight requests."""
        loop = asyncio.new_event_loop()
        future1: asyncio.Future[str] = loop.create_future()
        future2: asyncio.Future[str] = loop.create_future()
        store.set("fp1", InFlightRequest(future=future1, subscribers=1, started_at=time.time()))
        store.set("fp2", InFlightRequest(future=future2, subscribers=1, started_at=time.time()))

        store.clear()

        assert store.size() == 0
        loop.close()

    # === Factory function ===

    def test_factory_creates_singleflight_store(self) -> None:
        """Should create a singleflight store."""
        store = create_memory_singleflight_store()
        assert isinstance(store, MemorySingleflightStore)
