"""
Tests for rate limit stores (Memory and Redis)

Coverage includes:
- All store interface methods
- TTL expiration behavior
- Concurrent access patterns
- Cleanup mechanisms
"""

import pytest
import asyncio
import time
from fetch_rate_limiter.stores.memory import MemoryStore, create_memory_store


class TestMemoryStore:
    """Tests for MemoryStore."""

    @pytest.fixture
    def store(self):
        """Create a fresh store for each test."""
        return MemoryStore(cleanup_interval_seconds=60.0)

    @pytest.fixture
    async def async_store(self):
        """Create and yield a store, closing it after test."""
        store = MemoryStore(cleanup_interval_seconds=60.0)
        yield store
        await store.close()

    class TestGetCount:
        """Tests for get_count method."""

        @pytest.mark.asyncio
        async def test_return_0_for_nonexistent_key(self):
            store = MemoryStore()
            count = await store.get_count("nonexistent")
            assert count == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_return_current_count_for_existing_key(self):
            store = MemoryStore()
            await store.increment("key", 10.0)
            await store.increment("key", 10.0)

            count = await store.get_count("key")
            assert count == 2
            await store.close()

        @pytest.mark.asyncio
        async def test_return_0_for_expired_key(self):
            store = MemoryStore()
            await store.increment("key", 0.001)

            await asyncio.sleep(0.01)

            count = await store.get_count("key")
            assert count == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_multiple_keys_independently(self):
            store = MemoryStore()
            await store.increment("key1", 10.0)
            await store.increment("key1", 10.0)
            await store.increment("key2", 10.0)

            assert await store.get_count("key1") == 2
            assert await store.get_count("key2") == 1
            await store.close()

    class TestIncrement:
        """Tests for increment method."""

        @pytest.mark.asyncio
        async def test_create_new_entry_with_count_1(self):
            store = MemoryStore()
            count = await store.increment("key", 10.0)
            assert count == 1
            await store.close()

        @pytest.mark.asyncio
        async def test_increment_existing_entry(self):
            store = MemoryStore()
            await store.increment("key", 10.0)
            count = await store.increment("key", 10.0)
            assert count == 2
            await store.close()

        @pytest.mark.asyncio
        async def test_reset_count_when_ttl_expires(self):
            store = MemoryStore()
            await store.increment("key", 0.001)
            await store.increment("key", 0.001)

            await asyncio.sleep(0.01)

            count = await store.increment("key", 10.0)
            assert count == 1
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_rapid_increments(self):
            store = MemoryStore()

            async def increment():
                return await store.increment("key", 10.0)

            results = await asyncio.gather(*[increment() for _ in range(100)])
            count = await store.get_count("key")

            assert count == 100
            assert 100 in results
            await store.close()

        @pytest.mark.asyncio
        async def test_use_correct_ttl_for_new_entries(self):
            store = MemoryStore()
            await store.increment("key", 0.1)

            await asyncio.sleep(0.05)
            assert await store.get_count("key") == 1

            await asyncio.sleep(0.06)
            assert await store.get_count("key") == 0
            await store.close()

    class TestGetTTL:
        """Tests for get_ttl method."""

        @pytest.mark.asyncio
        async def test_return_0_for_nonexistent_key(self):
            store = MemoryStore()
            ttl = await store.get_ttl("nonexistent")
            assert ttl == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_return_remaining_ttl(self):
            store = MemoryStore()
            await store.increment("key", 1.0)

            await asyncio.sleep(0.1)

            ttl = await store.get_ttl("key")
            assert 0.8 <= ttl <= 1.0
            await store.close()

        @pytest.mark.asyncio
        async def test_return_0_when_ttl_expired(self):
            store = MemoryStore()
            await store.increment("key", 0.001)

            await asyncio.sleep(0.01)

            ttl = await store.get_ttl("key")
            assert ttl == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_never_return_negative_ttl(self):
            store = MemoryStore()
            await store.increment("key", 0.001)

            await asyncio.sleep(0.1)

            ttl = await store.get_ttl("key")
            assert ttl == 0
            await store.close()

    class TestReset:
        """Tests for reset method."""

        @pytest.mark.asyncio
        async def test_remove_existing_key(self):
            store = MemoryStore()
            await store.increment("key", 10.0)
            await store.reset("key")

            count = await store.get_count("key")
            assert count == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_reset_of_nonexistent_key(self):
            store = MemoryStore()
            await store.reset("nonexistent")
            assert await store.get_count("nonexistent") == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_only_affect_specified_key(self):
            store = MemoryStore()
            await store.increment("key1", 10.0)
            await store.increment("key2", 10.0)

            await store.reset("key1")

            assert await store.get_count("key1") == 0
            assert await store.get_count("key2") == 1
            await store.close()

    class TestClose:
        """Tests for close method."""

        @pytest.mark.asyncio
        async def test_clear_all_data(self):
            store = MemoryStore()
            await store.increment("key1", 10.0)
            await store.increment("key2", 10.0)

            await store.close()

            assert store.size == 0

        @pytest.mark.asyncio
        async def test_safe_to_call_multiple_times(self):
            store = MemoryStore()
            await store.close()
            await store.close()
            await store.close()

    class TestSize:
        """Tests for size property."""

        @pytest.mark.asyncio
        async def test_zero_for_new_store(self):
            store = MemoryStore()
            assert store.size == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_track_additions(self):
            store = MemoryStore()
            await store.increment("key1", 10.0)
            assert store.size == 1

            await store.increment("key2", 10.0)
            assert store.size == 2
            await store.close()

        @pytest.mark.asyncio
        async def test_not_change_for_same_key_increments(self):
            store = MemoryStore()
            await store.increment("key", 10.0)
            await store.increment("key", 10.0)

            assert store.size == 1
            await store.close()

    class TestBoundaryConditions:
        """Tests for boundary conditions."""

        @pytest.mark.asyncio
        async def test_handle_very_short_ttl(self):
            store = MemoryStore()
            await store.increment("key", 0.0001)

            await asyncio.sleep(0.001)

            assert await store.get_count("key") == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_very_long_ttl(self):
            store = MemoryStore()
            await store.increment("key", 86400.0)

            assert await store.get_count("key") == 1
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_zero_ttl(self):
            store = MemoryStore()
            count = await store.increment("key", 0.0)
            assert count == 1

            await asyncio.sleep(0.001)
            assert await store.get_count("key") == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_empty_string_key(self):
            store = MemoryStore()
            await store.increment("", 10.0)
            assert await store.get_count("") == 1
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_special_characters_in_key(self):
            store = MemoryStore()
            special_key = "limiter:api:user@domain.com:path/to/resource"
            await store.increment(special_key, 10.0)
            assert await store.get_count(special_key) == 1
            await store.close()

    class TestConcurrentOperations:
        """Tests for concurrent operations."""

        @pytest.mark.asyncio
        async def test_handle_concurrent_increments_correctly(self):
            store = MemoryStore()

            async def increment_key(i: int):
                return await store.increment(f"key{i % 5}", 10.0)

            await asyncio.gather(*[increment_key(i) for i in range(50)])

            total = 0
            for i in range(5):
                total += await store.get_count(f"key{i}")

            assert total == 50
            await store.close()

        @pytest.mark.asyncio
        async def test_handle_mixed_operations(self):
            store = MemoryStore()

            async def op1():
                return await store.increment("key", 10.0)

            async def op2():
                return await store.get_count("key")

            async def op3():
                return await store.get_ttl("key")

            await asyncio.gather(op1(), op2(), op1(), op3(), op1())

            assert await store.get_count("key") == 3
            await store.close()

    class TestStateTransitions:
        """Tests for state transitions."""

        @pytest.mark.asyncio
        async def test_transition_empty_to_active_to_expired_to_empty(self):
            store = MemoryStore()

            assert await store.get_count("key") == 0

            await store.increment("key", 0.01)
            assert await store.get_count("key") == 1

            await asyncio.sleep(0.02)
            assert await store.get_count("key") == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_transition_active_to_reset_to_empty(self):
            store = MemoryStore()

            await store.increment("key", 10.0)
            assert await store.get_count("key") == 1

            await store.reset("key")
            assert await store.get_count("key") == 0
            await store.close()

        @pytest.mark.asyncio
        async def test_transition_active_to_close_to_cleared(self):
            store = MemoryStore()

            await store.increment("key", 10.0)
            assert store.size == 1

            await store.close()
            assert store.size == 0


class TestCreateMemoryStore:
    """Tests for create_memory_store factory."""

    @pytest.mark.asyncio
    async def test_create_store_with_default_cleanup_interval(self):
        store = create_memory_store()
        assert isinstance(store, MemoryStore)
        await store.close()

    @pytest.mark.asyncio
    async def test_create_store_with_custom_cleanup_interval(self):
        store = create_memory_store(30.0)
        assert isinstance(store, MemoryStore)
        await store.close()
