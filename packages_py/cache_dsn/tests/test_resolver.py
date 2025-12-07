"""
Tests for DNS Cache Resolver

Coverage includes:
- resolve() cache hit/miss/stale paths
- Custom resolver registration
- Health management (mark_healthy/mark_unhealthy)
- Connection tracking (increment/decrement)
- Cache invalidation
- Statistics tracking
- Event emission
- Concurrent operations
"""

import pytest
import time
import asyncio
from typing import List

from cache_dsn.resolver import DnsCacheResolver, create_dns_cache_resolver
from cache_dsn.types import (
    DnsCacheConfig,
    ResolvedEndpoint,
    DnsCacheEvent,
)
from cache_dsn.stores.memory import MemoryStore


def create_test_config(**overrides) -> DnsCacheConfig:
    """Create a test config with defaults"""
    defaults = {
        "id": "test-resolver",
        "default_ttl_seconds": 60.0,
        "min_ttl_seconds": 1.0,
        "max_ttl_seconds": 300.0,
        "load_balance_strategy": "round-robin",
        "stale_while_revalidate": True,
        "stale_grace_period_seconds": 5.0,
        "negative_ttl_seconds": 30.0,
    }
    defaults.update(overrides)
    return DnsCacheConfig(**defaults)


class TestResolve:
    """Tests for DnsCacheResolver.resolve"""

    @pytest.mark.asyncio
    async def test_cache_miss_fresh_resolve(self):
        """Should perform fresh resolution on cache miss"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        # Register custom resolver
        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        result = await resolver.resolve("test.example.com")

        assert result.from_cache is False
        assert len(result.endpoints) == 1
        assert result.endpoints[0].host == "10.0.0.1"
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_cache_hit(self):
        """Should return cached result on cache hit"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        # Register custom resolver
        call_count = 0

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            nonlocal call_count
            call_count += 1
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        # First call - cache miss
        await resolver.resolve("test.example.com")
        assert call_count == 1

        # Second call - cache hit
        result = await resolver.resolve("test.example.com")
        assert result.from_cache is True
        assert call_count == 1  # Resolver not called again
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_force_refresh(self):
        """Should bypass cache when force_refresh is True"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        call_count = 0

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            nonlocal call_count
            call_count += 1
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        await resolver.resolve("test.example.com")
        assert call_count == 1

        result = await resolver.resolve("test.example.com", force_refresh=True)
        assert result.from_cache is False
        assert call_count == 2
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_custom_ttl(self):
        """Should use custom TTL when provided"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        result = await resolver.resolve("test.example.com", ttl_seconds=120.0)

        assert result.ttl_remaining_seconds <= 120.0
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_ttl_clamping(self):
        """Should clamp TTL to configured bounds"""
        config = create_test_config(min_ttl_seconds=10.0, max_ttl_seconds=60.0)
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        # Try to set TTL below minimum
        result = await resolver.resolve("test.example.com", ttl_seconds=1.0)
        assert result.ttl_remaining_seconds >= 9.0  # Allow for some resolution time

        await resolver.destroy()


class TestStaleWhileRevalidate:
    """Tests for stale-while-revalidate behavior"""

    @pytest.mark.asyncio
    async def test_stale_hit_within_grace_period(self):
        """Should return stale data within grace period"""
        config = create_test_config(
            default_ttl_seconds=0.05,  # Very short TTL (50ms)
            min_ttl_seconds=0.01,  # Allow very short TTL
            stale_while_revalidate=True,
            stale_grace_period_seconds=5.0,
        )
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        # First call
        await resolver.resolve("test.example.com")

        # Wait for entry to expire
        await asyncio.sleep(0.1)

        # Should get stale data
        result = await resolver.resolve("test.example.com")
        assert result.from_cache is True
        # When stale, ttl_remaining_seconds should be 0
        assert result.ttl_remaining_seconds == 0
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_stale_while_revalidate_disabled(self):
        """Should not serve stale when disabled"""
        config = create_test_config(
            default_ttl_seconds=0.05,  # 50ms TTL
            min_ttl_seconds=0.01,  # Allow very short TTL
            stale_while_revalidate=False,
            stale_grace_period_seconds=0.0,  # No grace period
        )
        resolver = DnsCacheResolver(config)

        call_count = 0

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            nonlocal call_count
            call_count += 1
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        await resolver.resolve("test.example.com")
        await asyncio.sleep(0.1)  # Wait for expiry

        # Should do fresh resolve (cache expired, stale not enabled)
        result = await resolver.resolve("test.example.com")
        assert result.from_cache is False
        assert call_count == 2
        await resolver.destroy()


class TestResolveOne:
    """Tests for DnsCacheResolver.resolve_one"""

    @pytest.mark.asyncio
    async def test_resolve_one_selects_endpoint(self):
        """Should resolve and select a single endpoint"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [
                ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True),
                ResolvedEndpoint(host="10.0.0.2", port=80, healthy=True),
            ]

        resolver.register_resolver("test.example.com", custom_resolver)

        endpoint = await resolver.resolve_one("test.example.com")

        assert endpoint is not None
        assert endpoint.host in ["10.0.0.1", "10.0.0.2"]
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_resolve_one_empty_endpoints(self):
        """Should return None for empty endpoints"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return []

        resolver.register_resolver("test.example.com", custom_resolver)

        endpoint = await resolver.resolve_one("test.example.com")
        assert endpoint is None
        await resolver.destroy()


class TestSelectEndpoint:
    """Tests for DnsCacheResolver.select_endpoint"""

    @pytest.mark.asyncio
    async def test_select_endpoint_from_cache(self):
        """Should select endpoint from cached entry"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [
                ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True),
                ResolvedEndpoint(host="10.0.0.2", port=80, healthy=True),
            ]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        endpoint = await resolver.select_endpoint("test.example.com")
        assert endpoint is not None
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_select_endpoint_not_cached(self):
        """Should return None when not cached"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        endpoint = await resolver.select_endpoint("not.cached.com")
        assert endpoint is None
        await resolver.destroy()


class TestCustomResolvers:
    """Tests for custom resolver registration"""

    @pytest.mark.asyncio
    async def test_register_resolver(self):
        """Should use registered resolver"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="custom.host", port=9000, healthy=True)]

        resolver.register_resolver("custom.example.com", custom_resolver)

        result = await resolver.resolve("custom.example.com")
        assert result.endpoints[0].host == "custom.host"
        assert result.endpoints[0].port == 9000
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_unregister_resolver(self):
        """Should unregister resolver"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="custom.host", port=9000, healthy=True)]

        resolver.register_resolver("custom.example.com", custom_resolver)
        result = resolver.unregister_resolver("custom.example.com")

        assert result is True
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_unregister_nonexistent_resolver(self):
        """Should return False for non-existent resolver"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        result = resolver.unregister_resolver("nonexistent")
        assert result is False
        await resolver.destroy()


class TestHealthManagement:
    """Tests for health management"""

    @pytest.mark.asyncio
    async def test_mark_unhealthy(self):
        """Should mark endpoint as unhealthy"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)
        await resolver.mark_unhealthy("test.example.com", endpoint)

        # Verify endpoint is now unhealthy
        result = await resolver.resolve("test.example.com")
        assert result.endpoints[0].healthy is False
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_mark_healthy(self):
        """Should mark endpoint as healthy"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=False)]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=False)
        await resolver.mark_healthy("test.example.com", endpoint)

        result = await resolver.resolve("test.example.com")
        assert result.endpoints[0].healthy is True
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_mark_unhealthy_not_cached(self):
        """Should handle marking non-cached entry"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)
        await resolver.mark_unhealthy("not.cached.com", endpoint)
        # Should not raise
        await resolver.destroy()


class TestConnectionTracking:
    """Tests for connection tracking"""

    @pytest.mark.asyncio
    async def test_increment_connections(self):
        """Should increment connection count"""
        config = create_test_config(load_balance_strategy="least-connections")
        resolver = DnsCacheResolver(config)

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)
        resolver.increment_connections(endpoint)

        # Internal state check
        key = "10.0.0.1:80"
        assert resolver._load_balance_state.active_connections.get(key) == 1
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_decrement_connections(self):
        """Should decrement connection count"""
        config = create_test_config(load_balance_strategy="least-connections")
        resolver = DnsCacheResolver(config)

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)
        resolver.increment_connections(endpoint)
        resolver.increment_connections(endpoint)
        resolver.decrement_connections(endpoint)

        key = "10.0.0.1:80"
        assert resolver._load_balance_state.active_connections.get(key) == 1
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_decrement_below_zero(self):
        """Should not go below zero"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)
        resolver.decrement_connections(endpoint)

        key = "10.0.0.1:80"
        assert resolver._load_balance_state.active_connections.get(key) == 0
        await resolver.destroy()


class TestCacheOperations:
    """Tests for cache operations"""

    @pytest.mark.asyncio
    async def test_invalidate(self):
        """Should invalidate cached entry"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        result = await resolver.invalidate("test.example.com")
        assert result is True

        # Cache miss after invalidation
        stats = await resolver.get_stats()
        # Next resolve would be a cache miss
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_invalidate_not_cached(self):
        """Should return False for non-cached entry"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        result = await resolver.invalidate("not.cached.com")
        assert result is False
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_clear(self):
        """Should clear all entries"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test1.example.com", custom_resolver)
        resolver.register_resolver("test2.example.com", custom_resolver)

        await resolver.resolve("test1.example.com")
        await resolver.resolve("test2.example.com")

        await resolver.clear()

        stats = await resolver.get_stats()
        assert stats.total_entries == 0
        await resolver.destroy()


class TestStatistics:
    """Tests for statistics tracking"""

    @pytest.mark.asyncio
    async def test_cache_hits_tracked(self):
        """Should track cache hits"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        await resolver.resolve("test.example.com")  # Miss
        await resolver.resolve("test.example.com")  # Hit
        await resolver.resolve("test.example.com")  # Hit

        stats = await resolver.get_stats()
        assert stats.cache_hits == 2
        assert stats.cache_misses == 1
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_hit_ratio(self):
        """Should calculate hit ratio correctly"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        await resolver.resolve("test.example.com")  # Miss
        await resolver.resolve("test.example.com")  # Hit
        await resolver.resolve("test.example.com")  # Hit
        await resolver.resolve("test.example.com")  # Hit

        stats = await resolver.get_stats()
        assert stats.hit_ratio == 0.75  # 3 hits / 4 total
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_healthy_unhealthy_counts(self):
        """Should count healthy/unhealthy endpoints"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [
                ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True),
                ResolvedEndpoint(host="10.0.0.2", port=80, healthy=False),
            ]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        stats = await resolver.get_stats()
        assert stats.healthy_endpoints == 1
        assert stats.unhealthy_endpoints == 1
        await resolver.destroy()


class TestEvents:
    """Tests for event emission"""

    @pytest.mark.asyncio
    async def test_cache_miss_event(self):
        """Should emit cache:miss event"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        events: List[DnsCacheEvent] = []

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        resolver.on(lambda e: events.append(e))

        await resolver.resolve("test.example.com")

        event_types = [e.type for e in events]
        assert "cache:miss" in event_types
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_cache_hit_event(self):
        """Should emit cache:hit event"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        events: List[DnsCacheEvent] = []

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        await resolver.resolve("test.example.com")

        resolver.on(lambda e: events.append(e))
        await resolver.resolve("test.example.com")

        event_types = [e.type for e in events]
        assert "cache:hit" in event_types
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_resolve_success_event(self):
        """Should emit resolve:success event"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        events: List[DnsCacheEvent] = []

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        resolver.on(lambda e: events.append(e))

        await resolver.resolve("test.example.com")

        event_types = [e.type for e in events]
        assert "resolve:success" in event_types
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_unsubscribe_event(self):
        """Should unsubscribe from events"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        events: List[DnsCacheEvent] = []

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        def listener(e: DnsCacheEvent):
            events.append(e)

        unsubscribe = resolver.on(listener)
        await resolver.resolve("test.example.com")

        unsubscribe()
        events.clear()

        await resolver.resolve("test.example.com", force_refresh=True)
        assert len(events) == 0
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_off_method(self):
        """Should unsubscribe via off method"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        events: List[DnsCacheEvent] = []

        def listener(e: DnsCacheEvent):
            events.append(e)

        resolver.on(listener)
        resolver.off(listener)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        await resolver.resolve("test.example.com")

        assert len(events) == 0
        await resolver.destroy()


class TestConcurrentOperations:
    """Tests for concurrent operations"""

    @pytest.mark.asyncio
    async def test_concurrent_resolves_same_dsn(self):
        """Should handle concurrent resolves to same DSN"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)
        call_count = 0

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            nonlocal call_count
            call_count += 1
            await asyncio.sleep(0.01)  # Simulate some latency
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)

        results = await asyncio.gather(*[
            resolver.resolve("test.example.com")
            for _ in range(10)
        ])

        assert all(r.endpoints[0].host == "10.0.0.1" for r in results)
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_concurrent_resolves_different_dsns(self):
        """Should handle concurrent resolves to different DSNs"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host=f"host-{dsn}", port=80, healthy=True)]

        for i in range(5):
            resolver.register_resolver(f"test{i}.example.com", custom_resolver)

        results = await asyncio.gather(*[
            resolver.resolve(f"test{i}.example.com")
            for i in range(5)
        ])

        assert len(results) == 5
        await resolver.destroy()


class TestErrorHandling:
    """Tests for error handling"""

    @pytest.mark.asyncio
    async def test_resolve_error_propagates(self):
        """Should propagate resolution errors"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def failing_resolver(dsn: str) -> List[ResolvedEndpoint]:
            raise ValueError("Resolution failed")

        resolver.register_resolver("test.example.com", failing_resolver)

        with pytest.raises(ValueError, match="Resolution failed"):
            await resolver.resolve("test.example.com")
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_resolve_error_caches_negative(self):
        """Should cache negative result on error"""
        config = create_test_config(negative_ttl_seconds=30.0)
        resolver = DnsCacheResolver(config)

        call_count = 0

        async def failing_resolver(dsn: str) -> List[ResolvedEndpoint]:
            nonlocal call_count
            call_count += 1
            raise ValueError("Resolution failed")

        resolver.register_resolver("test.example.com", failing_resolver)

        try:
            await resolver.resolve("test.example.com")
        except ValueError:
            pass

        # Second call should use negative cache
        result = await resolver.resolve("test.example.com")
        assert result.from_cache is True
        assert len(result.endpoints) == 0
        assert call_count == 1  # Only called once
        await resolver.destroy()


class TestDestroy:
    """Tests for destroy method"""

    @pytest.mark.asyncio
    async def test_destroy_clears_resources(self):
        """Should clear all resources"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        async def custom_resolver(dsn: str) -> List[ResolvedEndpoint]:
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        resolver.register_resolver("test.example.com", custom_resolver)
        resolver.on(lambda e: None)
        await resolver.resolve("test.example.com")

        await resolver.destroy()

        # Verify cleanup
        assert len(resolver._listeners) == 0
        assert len(resolver._custom_resolvers) == 0

    @pytest.mark.asyncio
    async def test_destroy_multiple_times(self):
        """Should be safe to call multiple times"""
        config = create_test_config()
        resolver = DnsCacheResolver(config)

        await resolver.destroy()
        await resolver.destroy()
        await resolver.destroy()


class TestCreateDnsCacheResolver:
    """Tests for create_dns_cache_resolver factory"""

    @pytest.mark.asyncio
    async def test_create_with_config(self):
        """Should create resolver with config"""
        config = create_test_config()
        resolver = create_dns_cache_resolver(config)

        assert isinstance(resolver, DnsCacheResolver)
        await resolver.destroy()

    @pytest.mark.asyncio
    async def test_create_with_custom_store(self):
        """Should create resolver with custom store"""
        config = create_test_config()
        store = MemoryStore(500)
        resolver = create_dns_cache_resolver(config, store)

        assert isinstance(resolver, DnsCacheResolver)
        await resolver.destroy()
