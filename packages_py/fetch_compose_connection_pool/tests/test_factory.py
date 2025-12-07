"""
Tests for connection pool factory functions

Coverage includes:
- Preset configuration testing
- Factory function testing
- Composition pattern testing
- Shared pool testing
"""

import pytest
from unittest.mock import MagicMock, AsyncMock
import httpx

from fetch_compose_connection_pool.factory import (
    compose_transport,
    compose_sync_transport,
    create_pooled_client,
    create_pooled_sync_client,
    create_api_connection_pool,
    create_from_preset,
    create_shared_connection_pool,
    HIGH_CONCURRENCY_POOL,
    LOW_LATENCY_POOL,
    MINIMAL_POOL,
)
from fetch_compose_connection_pool.transport import (
    ConnectionPoolTransport,
    SyncConnectionPoolTransport,
)
from connection_pool import ConnectionPoolConfig


class MockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport for testing"""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, content=b"OK")


class MockSyncTransport(httpx.BaseTransport):
    """Mock sync transport for testing"""

    def __init__(self, name: str = "mock"):
        self.name = name
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return httpx.Response(200, content=b"OK")


class TestPresets:
    """Tests for preset configurations"""

    def test_high_concurrency_preset(self):
        """High concurrency preset should have high limits"""
        assert HIGH_CONCURRENCY_POOL["max_connections"] == 200
        assert HIGH_CONCURRENCY_POOL["max_connections_per_host"] == 20
        assert HIGH_CONCURRENCY_POOL["max_idle_connections"] == 50
        assert HIGH_CONCURRENCY_POOL["max_queue_size"] == 2000

    def test_low_latency_preset(self):
        """Low latency preset should have longer timeouts"""
        assert LOW_LATENCY_POOL["max_connections"] == 100
        assert LOW_LATENCY_POOL["max_connections_per_host"] == 10
        assert LOW_LATENCY_POOL["idle_timeout_seconds"] == 120.0
        assert LOW_LATENCY_POOL["keep_alive_timeout_seconds"] == 60.0

    def test_minimal_preset(self):
        """Minimal preset should have low limits"""
        assert MINIMAL_POOL["max_connections"] == 20
        assert MINIMAL_POOL["max_connections_per_host"] == 5
        assert MINIMAL_POOL["max_idle_connections"] == 5
        assert MINIMAL_POOL["max_queue_size"] == 100

    def test_preset_ordering(self):
        """Presets should have ascending connection limits"""
        assert MINIMAL_POOL["max_connections"] < LOW_LATENCY_POOL["max_connections"]
        assert LOW_LATENCY_POOL["max_connections"] < HIGH_CONCURRENCY_POOL["max_connections"]


class TestComposeTransport:
    """Tests for compose_transport function"""

    def test_compose_single_wrapper(self):
        """Should compose single wrapper"""
        base = MockAsyncTransport("base")

        def wrapper(inner):
            mock = MockAsyncTransport("wrapper")
            mock._inner = inner
            return mock

        transport = compose_transport(base, wrapper)
        assert hasattr(transport, "_inner")

    def test_compose_multiple_wrappers(self):
        """Should compose multiple wrappers"""
        base = MockAsyncTransport("base")

        def wrapper1(inner):
            mock = MockAsyncTransport("wrapper1")
            mock._inner = inner
            return mock

        def wrapper2(inner):
            mock = MockAsyncTransport("wrapper2")
            mock._inner = inner
            return mock

        transport = compose_transport(base, wrapper1, wrapper2)
        assert transport.name == "wrapper2"
        assert transport._inner.name == "wrapper1"
        assert transport._inner._inner.name == "base"

    def test_compose_no_wrappers(self):
        """Should return base when no wrappers"""
        base = MockAsyncTransport("base")
        transport = compose_transport(base)
        assert transport is base


class TestComposeSyncTransport:
    """Tests for compose_sync_transport function"""

    def test_compose_single_wrapper(self):
        """Should compose single sync wrapper"""
        base = MockSyncTransport("base")

        def wrapper(inner):
            mock = MockSyncTransport("wrapper")
            mock._inner = inner
            return mock

        transport = compose_sync_transport(base, wrapper)
        assert hasattr(transport, "_inner")

    def test_compose_no_wrappers(self):
        """Should return base when no wrappers"""
        base = MockSyncTransport("base")
        transport = compose_sync_transport(base)
        assert transport is base


class TestCreatePooledClient:
    """Tests for create_pooled_client factory"""

    @pytest.mark.asyncio
    async def test_create_with_base_url(self):
        """Should create client with base URL"""
        client = create_pooled_client(base_url="https://api.example.com")
        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_limits(self):
        """Should create client with custom limits"""
        client = create_pooled_client(
            max_connections=50,
            max_connections_per_host=5,
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_host_filters(self):
        """Should create client with host filters"""
        client = create_pooled_client(
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()


class TestCreatePooledSyncClient:
    """Tests for create_pooled_sync_client factory"""

    def test_create_with_base_url(self):
        """Should create sync client with base URL"""
        client = create_pooled_sync_client(base_url="https://api.example.com")
        assert isinstance(client, httpx.Client)
        client.close()

    def test_create_with_custom_limits(self):
        """Should create sync client with custom limits"""
        client = create_pooled_sync_client(
            max_connections=50,
            max_connections_per_host=5,
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.Client)
        client.close()

    def test_create_with_host_filters(self):
        """Should create sync client with host filters"""
        client = create_pooled_sync_client(
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.Client)
        client.close()


class TestCreateApiConnectionPool:
    """Tests for create_api_connection_pool factory"""

    def test_create_wrapper(self):
        """Should create transport wrapper function"""
        wrapper = create_api_connection_pool("my-api")
        assert callable(wrapper)

    @pytest.mark.asyncio
    async def test_wrapper_creates_transport(self):
        """Wrapper should create ConnectionPoolTransport"""
        wrapper = create_api_connection_pool("my-api", max_connections_per_host=5)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_wrapper_uses_api_id(self):
        """Wrapper should use API ID in config"""
        wrapper = create_api_connection_pool("github-api")
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert transport.pool.id == "github-api"
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_wrapper_uses_custom_limits(self):
        """Wrapper should use custom limits"""
        wrapper = create_api_connection_pool(
            "my-api",
            max_connections_per_host=5,
            max_idle_connections=10,
        )
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()


class TestCreateFromPreset:
    """Tests for create_from_preset function"""

    @pytest.mark.asyncio
    async def test_create_from_high_concurrency_preset(self):
        """Should create transport from high concurrency preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(HIGH_CONCURRENCY_POOL, inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_from_low_latency_preset(self):
        """Should create transport from low latency preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(LOW_LATENCY_POOL, inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_from_minimal_preset(self):
        """Should create transport from minimal preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(MINIMAL_POOL, inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_overrides(self):
        """Should apply overrides to preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(
            HIGH_CONCURRENCY_POOL,
            inner,
            max_connections=50,  # Override
        )
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()


class TestCreateSharedConnectionPool:
    """Tests for create_shared_connection_pool function"""

    @pytest.mark.asyncio
    async def test_returns_pool_and_wrapper_factory(self):
        """Should return pool and wrapper factory"""
        config = ConnectionPoolConfig(id="shared-pool", max_connections=100)
        pool, create_wrapper = create_shared_connection_pool(config)

        assert pool is not None
        assert callable(create_wrapper)

        await pool.close()

    @pytest.mark.asyncio
    async def test_pool_has_correct_id(self):
        """Should create pool with correct ID"""
        config = ConnectionPoolConfig(id="test-shared-pool", max_connections=100)
        pool, _ = create_shared_connection_pool(config)

        assert pool.id == "test-shared-pool"

        await pool.close()

    @pytest.mark.asyncio
    async def test_wrapper_factory_creates_transports(self):
        """Wrapper factory should create transports"""
        config = ConnectionPoolConfig(id="shared-pool", max_connections=100)
        pool, create_wrapper = create_shared_connection_pool(config)

        wrapper = create_wrapper()
        inner = MockAsyncTransport()
        transport = wrapper(inner)

        assert isinstance(transport, ConnectionPoolTransport)

        await pool.close()

    @pytest.mark.asyncio
    async def test_wrapper_factory_accepts_host_filters(self):
        """Wrapper factory should accept host filters"""
        config = ConnectionPoolConfig(id="shared-pool", max_connections=100)
        pool, create_wrapper = create_shared_connection_pool(config)

        wrapper = create_wrapper(
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
        )
        inner = MockAsyncTransport()
        transport = wrapper(inner)

        assert isinstance(transport, ConnectionPoolTransport)

        await pool.close()


class TestIntegration:
    """Integration tests for factory functions"""

    @pytest.mark.asyncio
    async def test_compose_with_connection_pool(self):
        """Should compose transport with connection pool wrapper"""
        base = MockAsyncTransport()
        transport = compose_transport(
            base,
            create_api_connection_pool("api1", max_connections_per_host=5),
        )
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_compose_multiple_pools(self):
        """Should compose multiple API pools"""
        base = MockAsyncTransport()
        transport = compose_transport(
            base,
            create_api_connection_pool("api1", max_connections_per_host=5),
            create_api_connection_pool("api2", max_connections_per_host=10),
        )
        # Outer wrapper should be api2
        assert isinstance(transport, ConnectionPoolTransport)
        assert transport.pool.id == "api2"
        await transport.aclose()
        # Also close inner transport (api1)
        if hasattr(transport._inner, "aclose"):
            await transport._inner.aclose()


class TestBoundaryConditions:
    """Tests for boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_api_id(self):
        """Should handle empty API ID"""
        wrapper = create_api_connection_pool("")
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_very_long_api_id(self):
        """Should handle very long API ID"""
        wrapper = create_api_connection_pool("a" * 1000)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_zero_limits(self):
        """Should handle zero limits"""
        wrapper = create_api_connection_pool(
            "api",
            max_connections_per_host=1,
            max_idle_connections=0,
        )
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_very_large_limits(self):
        """Should handle very large limits"""
        wrapper = create_api_connection_pool(
            "api",
            max_connections_per_host=10000,
            max_idle_connections=5000,
        )
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, ConnectionPoolTransport)
        await transport.aclose()
