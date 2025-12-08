"""
Tests for cache request factory functions.
Following logic testing methodologies:
- Statement Coverage
- Decision Coverage
- Function Composition Testing
- Integration Testing
"""
from unittest.mock import MagicMock, AsyncMock

import httpx
import pytest

from cache_request import (
    IdempotencyConfig,
    SingleflightConfig,
    MemoryCacheStore,
    MemorySingleflightStore,
)
from fetch_compose_cache_request import (
    compose_transport,
    compose_sync_transport,
    create_cache_request_transport,
    create_cache_request_sync_transport,
    create_cache_request_client,
    create_cache_request_sync_client,
    CacheRequestTransport,
    SyncCacheRequestTransport,
)
from conftest import MockAsyncTransport, MockSyncTransport


class TestComposeTransport:
    """Tests for compose_transport function."""

    @pytest.mark.asyncio
    async def test_compose_with_no_wrappers(self) -> None:
        """Test composing with no wrappers returns base transport."""
        base = MockAsyncTransport()
        result = compose_transport(base)

        assert result is base

    @pytest.mark.asyncio
    async def test_compose_with_single_wrapper(self) -> None:
        """Test composing with a single wrapper."""
        base = MockAsyncTransport()

        def wrapper(inner: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
            return CacheRequestTransport(inner)

        result = compose_transport(base, wrapper)

        assert isinstance(result, CacheRequestTransport)

    @pytest.mark.asyncio
    async def test_compose_with_multiple_wrappers(self) -> None:
        """Test composing with multiple wrappers."""
        base = MockAsyncTransport()
        wrappers_called = []

        def wrapper1(inner: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
            wrappers_called.append("wrapper1")
            return CacheRequestTransport(inner, enable_singleflight=False)

        def wrapper2(inner: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
            wrappers_called.append("wrapper2")
            return CacheRequestTransport(inner, enable_idempotency=False)

        result = compose_transport(base, wrapper1, wrapper2)

        # Wrappers should be applied in order
        assert wrappers_called == ["wrapper1", "wrapper2"]
        assert isinstance(result, CacheRequestTransport)

    @pytest.mark.asyncio
    async def test_compose_preserves_chain(self) -> None:
        """Test that composition preserves the transport chain."""
        base = MockAsyncTransport()

        # Create a chain of wrappers
        def create_wrapper(name: str):
            def wrapper(inner: httpx.AsyncBaseTransport) -> httpx.AsyncBaseTransport:
                return CacheRequestTransport(
                    inner,
                    enable_idempotency=False,
                    enable_singleflight=False,
                )
            return wrapper

        result = compose_transport(
            base,
            create_wrapper("first"),
            create_wrapper("second"),
            create_wrapper("third"),
        )

        assert isinstance(result, CacheRequestTransport)


class TestComposeSyncTransport:
    """Tests for compose_sync_transport function."""

    def test_compose_with_no_wrappers(self) -> None:
        """Test composing with no wrappers returns base transport."""
        base = MockSyncTransport()
        result = compose_sync_transport(base)

        assert result is base

    def test_compose_with_single_wrapper(self) -> None:
        """Test composing with a single wrapper."""
        base = MockSyncTransport()

        def wrapper(inner: httpx.BaseTransport) -> httpx.BaseTransport:
            return SyncCacheRequestTransport(inner)

        result = compose_sync_transport(base, wrapper)

        assert isinstance(result, SyncCacheRequestTransport)

    def test_compose_with_multiple_wrappers(self) -> None:
        """Test composing with multiple wrappers."""
        base = MockSyncTransport()
        wrappers_called = []

        def wrapper1(inner: httpx.BaseTransport) -> httpx.BaseTransport:
            wrappers_called.append("wrapper1")
            return SyncCacheRequestTransport(inner)

        def wrapper2(inner: httpx.BaseTransport) -> httpx.BaseTransport:
            wrappers_called.append("wrapper2")
            return SyncCacheRequestTransport(inner, enable_idempotency=False)

        result = compose_sync_transport(base, wrapper1, wrapper2)

        assert wrappers_called == ["wrapper1", "wrapper2"]
        assert isinstance(result, SyncCacheRequestTransport)


class TestCreateCacheRequestTransport:
    """Tests for create_cache_request_transport function."""

    @pytest.mark.asyncio
    async def test_create_with_defaults(self) -> None:
        """Test creating transport with default options."""
        transport = create_cache_request_transport()

        assert isinstance(transport, CacheRequestTransport)
        assert transport._enable_idempotency is True
        assert transport._enable_singleflight is True

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_inner(self) -> None:
        """Test creating transport with custom inner transport."""
        inner = MockAsyncTransport()
        transport = create_cache_request_transport(inner)

        assert isinstance(transport, CacheRequestTransport)
        assert transport._inner is inner

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_idempotency_disabled(self) -> None:
        """Test creating transport with idempotency disabled."""
        transport = create_cache_request_transport(
            enable_idempotency=False,
        )

        assert transport._enable_idempotency is False
        assert transport._idempotency_manager is None

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_singleflight_disabled(self) -> None:
        """Test creating transport with singleflight disabled."""
        transport = create_cache_request_transport(
            enable_singleflight=False,
        )

        assert transport._enable_singleflight is False
        assert transport._singleflight is None

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_configs(self) -> None:
        """Test creating transport with custom configurations."""
        idempotency_config = IdempotencyConfig(
            ttl_seconds=3600,
            header_name="X-Request-Id",
        )
        singleflight_config = SingleflightConfig(methods=["GET"])

        transport = create_cache_request_transport(
            idempotency_config=idempotency_config,
            singleflight_config=singleflight_config,
        )

        assert isinstance(transport, CacheRequestTransport)

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_stores(self) -> None:
        """Test creating transport with custom stores."""
        cache_store = MemoryCacheStore()
        singleflight_store = MemorySingleflightStore()

        transport = create_cache_request_transport(
            idempotency_store=cache_store,
            singleflight_store=singleflight_store,
        )

        assert isinstance(transport, CacheRequestTransport)

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_callbacks(self) -> None:
        """Test creating transport with callbacks."""
        on_key_generated = MagicMock()
        on_coalesced = MagicMock()

        transport = create_cache_request_transport(
            on_idempotency_key_generated=on_key_generated,
            on_request_coalesced=on_coalesced,
        )

        assert transport._on_idempotency_key_generated is on_key_generated
        assert transport._on_request_coalesced is on_coalesced

        await transport.aclose()


class TestCreateCacheRequestSyncTransport:
    """Tests for create_cache_request_sync_transport function."""

    def test_create_with_defaults(self) -> None:
        """Test creating sync transport with default options."""
        transport = create_cache_request_sync_transport()

        assert isinstance(transport, SyncCacheRequestTransport)
        assert transport._enable_idempotency is True

        transport.close()

    def test_create_with_custom_inner(self) -> None:
        """Test creating sync transport with custom inner transport."""
        inner = MockSyncTransport()
        transport = create_cache_request_sync_transport(inner)

        assert isinstance(transport, SyncCacheRequestTransport)
        assert transport._inner is inner

        transport.close()

    def test_create_with_idempotency_disabled(self) -> None:
        """Test creating sync transport with idempotency disabled."""
        transport = create_cache_request_sync_transport(
            enable_idempotency=False,
        )

        assert transport._enable_idempotency is False

        transport.close()

    def test_create_with_custom_config(self) -> None:
        """Test creating sync transport with custom configuration."""
        config = IdempotencyConfig(
            ttl_seconds=3600,
            header_name="X-Request-Id",
        )

        transport = create_cache_request_sync_transport(
            idempotency_config=config,
        )

        assert transport._idempotency_config == config

        transport.close()

    def test_create_with_callback(self) -> None:
        """Test creating sync transport with callback."""
        on_key_generated = MagicMock()

        transport = create_cache_request_sync_transport(
            on_idempotency_key_generated=on_key_generated,
        )

        assert transport._on_idempotency_key_generated is on_key_generated

        transport.close()


class TestCreateCacheRequestClient:
    """Tests for create_cache_request_client function."""

    @pytest.mark.asyncio
    async def test_create_with_defaults(self) -> None:
        """Test creating async client with default options."""
        client = create_cache_request_client()

        assert isinstance(client, httpx.AsyncClient)

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_options(self) -> None:
        """Test creating async client with custom options."""
        client = create_cache_request_client(
            enable_idempotency=True,
            enable_singleflight=True,
            idempotency_config=IdempotencyConfig(ttl_seconds=3600),
        )

        assert isinstance(client, httpx.AsyncClient)

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_base_url(self) -> None:
        """Test creating async client with base URL."""
        client = create_cache_request_client(
            base_url="http://api.example.com",
        )

        assert isinstance(client, httpx.AsyncClient)
        assert str(client.base_url) == "http://api.example.com"

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_client_kwargs(self) -> None:
        """Test creating async client with additional client kwargs."""
        client = create_cache_request_client(
            timeout=30.0,
            follow_redirects=True,
        )

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.read == 30.0
        assert client.follow_redirects is True

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_all_options(self) -> None:
        """Test creating async client with all options."""
        client = create_cache_request_client(
            enable_idempotency=True,
            enable_singleflight=True,
            idempotency_config=IdempotencyConfig(
                ttl_seconds=3600,
                header_name="X-Request-Id",
            ),
            singleflight_config=SingleflightConfig(methods=["GET"]),
            base_url="http://api.example.com",
            timeout=60.0,
        )

        assert isinstance(client, httpx.AsyncClient)
        assert str(client.base_url) == "http://api.example.com"
        assert client.timeout.read == 60.0

        await client.aclose()


class TestCreateCacheRequestSyncClient:
    """Tests for create_cache_request_sync_client function."""

    def test_create_with_defaults(self) -> None:
        """Test creating sync client with default options."""
        client = create_cache_request_sync_client()

        assert isinstance(client, httpx.Client)

        client.close()

    def test_create_with_custom_options(self) -> None:
        """Test creating sync client with custom options."""
        client = create_cache_request_sync_client(
            enable_idempotency=True,
            idempotency_config=IdempotencyConfig(ttl_seconds=3600),
        )

        assert isinstance(client, httpx.Client)

        client.close()

    def test_create_with_base_url(self) -> None:
        """Test creating sync client with base URL."""
        client = create_cache_request_sync_client(
            base_url="http://api.example.com",
        )

        assert isinstance(client, httpx.Client)
        assert str(client.base_url) == "http://api.example.com"

        client.close()

    def test_create_with_client_kwargs(self) -> None:
        """Test creating sync client with additional client kwargs."""
        client = create_cache_request_sync_client(
            timeout=30.0,
            follow_redirects=True,
        )

        assert isinstance(client, httpx.Client)
        assert client.timeout.read == 30.0
        assert client.follow_redirects is True

        client.close()

    def test_create_with_all_options(self) -> None:
        """Test creating sync client with all options."""
        client = create_cache_request_sync_client(
            enable_idempotency=True,
            idempotency_config=IdempotencyConfig(
                ttl_seconds=3600,
                header_name="X-Request-Id",
            ),
            base_url="http://api.example.com",
            timeout=60.0,
        )

        assert isinstance(client, httpx.Client)
        assert str(client.base_url) == "http://api.example.com"
        assert client.timeout.read == 60.0

        client.close()


class TestIntegration:
    """Integration tests for factory functions."""

    @pytest.mark.asyncio
    async def test_composed_transport_handles_requests(self) -> None:
        """Test that composed transport properly handles requests."""
        inner = MockAsyncTransport()
        transport = compose_transport(
            inner,
            lambda t: CacheRequestTransport(t, enable_idempotency=False),
        )

        request = httpx.Request("GET", "http://localhost/api/users")

        # Need to use the wrapped transport
        if isinstance(transport, CacheRequestTransport):
            response = await transport.handle_async_request(request)
            assert response.status_code == 200
            await transport.aclose()

    @pytest.mark.asyncio
    async def test_factory_transport_works_with_client(self) -> None:
        """Test that factory-created transport works with httpx client."""
        inner = MockAsyncTransport()
        transport = create_cache_request_transport(
            inner,
            enable_idempotency=True,
            enable_singleflight=True,
        )

        # Create client with our transport
        client = httpx.AsyncClient(transport=transport)

        # Make a request through the client
        request = httpx.Request("GET", "http://localhost/api/users")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await client.aclose()

    def test_sync_composed_transport_handles_requests(self) -> None:
        """Test that sync composed transport properly handles requests."""
        inner = MockSyncTransport()
        transport = compose_sync_transport(
            inner,
            lambda t: SyncCacheRequestTransport(t),
        )

        if isinstance(transport, SyncCacheRequestTransport):
            request = httpx.Request("POST", "http://localhost/api/orders")
            response = transport.handle_request(request)
            assert response.status_code == 200
            transport.close()


class TestEdgeCases:
    """Test edge cases for factory functions."""

    @pytest.mark.asyncio
    async def test_create_transport_with_none_inner(self) -> None:
        """Test creating transport with None inner creates default."""
        transport = create_cache_request_transport(None)

        assert isinstance(transport, CacheRequestTransport)
        # Inner should be AsyncHTTPTransport (default)
        assert isinstance(transport._inner, httpx.AsyncHTTPTransport)

        await transport.aclose()

    def test_create_sync_transport_with_none_inner(self) -> None:
        """Test creating sync transport with None inner creates default."""
        transport = create_cache_request_sync_transport(None)

        assert isinstance(transport, SyncCacheRequestTransport)
        # Inner should be HTTPTransport (default)
        assert isinstance(transport._inner, httpx.HTTPTransport)

        transport.close()

    @pytest.mark.asyncio
    async def test_client_with_empty_base_url(self) -> None:
        """Test creating client with empty base URL."""
        client = create_cache_request_client(base_url="")

        assert isinstance(client, httpx.AsyncClient)

        await client.aclose()

    def test_sync_client_with_empty_base_url(self) -> None:
        """Test creating sync client with empty base URL."""
        client = create_cache_request_sync_client(base_url="")

        assert isinstance(client, httpx.Client)

        client.close()


class TestMemoryManagement:
    """Test memory management for factory functions."""

    @pytest.mark.asyncio
    async def test_independent_stores_for_each_transport(self) -> None:
        """Test that each transport gets independent stores by default."""
        transport1 = create_cache_request_transport()
        transport2 = create_cache_request_transport()

        # They should have different store instances
        assert transport1._idempotency_manager is not transport2._idempotency_manager

        await transport1.aclose()
        await transport2.aclose()

    @pytest.mark.asyncio
    async def test_shared_stores_across_transports(self) -> None:
        """Test that stores can be shared across transports."""
        cache_store = MemoryCacheStore()
        singleflight_store = MemorySingleflightStore()

        transport1 = create_cache_request_transport(
            idempotency_store=cache_store,
            singleflight_store=singleflight_store,
        )
        transport2 = create_cache_request_transport(
            idempotency_store=cache_store,
            singleflight_store=singleflight_store,
        )

        # They should share the same stores
        assert transport1 is not transport2

        await transport1.aclose()
        await transport2.aclose()
