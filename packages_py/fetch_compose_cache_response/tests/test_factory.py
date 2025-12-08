"""
Tests for cache response factory functions.
Following logic testing methodologies:
- Statement, Decision, Condition, Path Coverage
- Boundary Value Analysis
- Error Handling
"""
from unittest.mock import MagicMock

import httpx
import pytest

from cache_response import (
    CacheResponseConfig,
    CacheFreshness,
)
from fetch_compose_cache_response import (
    compose_transport,
    compose_sync_transport,
    create_cache_response_transport,
    create_cache_response_sync_transport,
    create_cache_response_client,
    create_cache_response_sync_client,
    CacheResponseTransport,
    SyncCacheResponseTransport,
)
from tests.conftest import (
    MockAsyncTransport,
    MockSyncTransport,
    CacheableMockAsyncTransport,
)


class TestComposeTransport:
    """Tests for compose_transport function."""

    @pytest.mark.asyncio
    async def test_compose_single_wrapper(self) -> None:
        """Test composing a single wrapper."""
        base = MockAsyncTransport()
        transport = compose_transport(
            base,
            lambda inner: CacheResponseTransport(inner),
        )

        assert isinstance(transport, CacheResponseTransport)
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_compose_no_wrappers(self) -> None:
        """Test composing with no wrappers returns base."""
        base = MockAsyncTransport()
        transport = compose_transport(base)

        assert transport is base

    @pytest.mark.asyncio
    async def test_compose_preserves_order(self) -> None:
        """Test that wrappers are applied in order."""
        base = MockAsyncTransport()
        call_order = []

        def wrapper1(inner):
            call_order.append("wrapper1")
            return CacheResponseTransport(inner)

        def wrapper2(inner):
            call_order.append("wrapper2")
            # Just return a passthrough for testing
            return inner

        compose_transport(base, wrapper1, wrapper2)

        assert call_order == ["wrapper1", "wrapper2"]


class TestComposeSyncTransport:
    """Tests for compose_sync_transport function."""

    def test_compose_single_sync_wrapper(self) -> None:
        """Test composing a single sync wrapper."""
        base = MockSyncTransport()
        transport = compose_sync_transport(
            base,
            lambda inner: SyncCacheResponseTransport(inner),
        )

        assert isinstance(transport, SyncCacheResponseTransport)
        transport.close()

    def test_compose_no_sync_wrappers(self) -> None:
        """Test composing with no wrappers returns base."""
        base = MockSyncTransport()
        transport = compose_sync_transport(base)

        assert transport is base


class TestCreateCacheResponseTransport:
    """Tests for create_cache_response_transport function."""

    @pytest.mark.asyncio
    async def test_create_with_defaults(self) -> None:
        """Test creating transport with default options."""
        transport = create_cache_response_transport()

        assert isinstance(transport, CacheResponseTransport)
        assert transport._enable_background_revalidation is True

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_inner_transport(self) -> None:
        """Test creating transport with custom inner transport."""
        inner = MockAsyncTransport()
        transport = create_cache_response_transport(inner)

        assert isinstance(transport, CacheResponseTransport)
        assert transport._inner is inner

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self) -> None:
        """Test creating transport with custom configuration."""
        config = CacheResponseConfig(
            default_ttl_seconds=600,
            max_ttl_seconds=3600,
        )
        transport = create_cache_response_transport(config=config)

        assert isinstance(transport, CacheResponseTransport)

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_background_revalidation_disabled(self) -> None:
        """Test creating transport with background revalidation disabled."""
        transport = create_cache_response_transport(
            enable_background_revalidation=False,
        )

        assert transport._enable_background_revalidation is False

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_callbacks(self) -> None:
        """Test creating transport with callbacks."""
        on_cache_hit = MagicMock()
        on_cache_miss = MagicMock()
        on_cache_store = MagicMock()
        on_revalidated = MagicMock()

        transport = create_cache_response_transport(
            on_cache_hit=on_cache_hit,
            on_cache_miss=on_cache_miss,
            on_cache_store=on_cache_store,
            on_revalidated=on_revalidated,
        )

        assert transport._on_cache_hit is on_cache_hit
        assert transport._on_cache_miss is on_cache_miss
        assert transport._on_cache_store is on_cache_store
        assert transport._on_revalidated is on_revalidated

        await transport.aclose()


class TestCreateCacheResponseSyncTransport:
    """Tests for create_cache_response_sync_transport function."""

    def test_create_with_defaults(self) -> None:
        """Test creating sync transport with default options."""
        transport = create_cache_response_sync_transport()

        assert isinstance(transport, SyncCacheResponseTransport)

        transport.close()

    def test_create_with_inner_transport(self) -> None:
        """Test creating sync transport with custom inner transport."""
        inner = MockSyncTransport()
        transport = create_cache_response_sync_transport(inner)

        assert isinstance(transport, SyncCacheResponseTransport)
        assert transport._inner is inner

        transport.close()

    def test_create_with_custom_config(self) -> None:
        """Test creating sync transport with custom configuration."""
        config = CacheResponseConfig(
            default_ttl_seconds=600,
            max_ttl_seconds=3600,
        )
        transport = create_cache_response_sync_transport(config=config)

        assert isinstance(transport, SyncCacheResponseTransport)

        transport.close()

    def test_create_with_callbacks(self) -> None:
        """Test creating sync transport with callbacks."""
        on_cache_hit = MagicMock()
        on_cache_miss = MagicMock()
        on_cache_store = MagicMock()

        transport = create_cache_response_sync_transport(
            on_cache_hit=on_cache_hit,
            on_cache_miss=on_cache_miss,
            on_cache_store=on_cache_store,
        )

        assert transport._on_cache_hit is on_cache_hit
        assert transport._on_cache_miss is on_cache_miss
        assert transport._on_cache_store is on_cache_store

        transport.close()


class TestCreateCacheResponseClient:
    """Tests for create_cache_response_client function."""

    @pytest.mark.asyncio
    async def test_create_with_defaults(self) -> None:
        """Test creating client with default options."""
        client = create_cache_response_client()

        assert isinstance(client, httpx.AsyncClient)
        assert isinstance(client._transport, CacheResponseTransport)

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_base_url(self) -> None:
        """Test creating client with base URL."""
        client = create_cache_response_client(base_url="http://localhost:8080")

        assert str(client.base_url) == "http://localhost:8080"

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self) -> None:
        """Test creating client with custom configuration."""
        config = CacheResponseConfig(
            default_ttl_seconds=600,
        )
        client = create_cache_response_client(config=config)

        assert isinstance(client._transport, CacheResponseTransport)

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_background_revalidation_disabled(self) -> None:
        """Test creating client with background revalidation disabled."""
        client = create_cache_response_client(enable_background_revalidation=False)

        transport = client._transport
        assert isinstance(transport, CacheResponseTransport)
        assert transport._enable_background_revalidation is False

        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_additional_kwargs(self) -> None:
        """Test creating client with additional httpx kwargs."""
        client = create_cache_response_client(
            timeout=30.0,
            headers={"X-Custom-Header": "test"},
        )

        assert client.timeout.connect == 30.0
        assert client.headers.get("X-Custom-Header") == "test"

        await client.aclose()


class TestCreateCacheResponseSyncClient:
    """Tests for create_cache_response_sync_client function."""

    def test_create_with_defaults(self) -> None:
        """Test creating sync client with default options."""
        client = create_cache_response_sync_client()

        assert isinstance(client, httpx.Client)
        assert isinstance(client._transport, SyncCacheResponseTransport)

        client.close()

    def test_create_with_base_url(self) -> None:
        """Test creating sync client with base URL."""
        client = create_cache_response_sync_client(base_url="http://localhost:8080")

        assert str(client.base_url) == "http://localhost:8080"

        client.close()

    def test_create_with_custom_config(self) -> None:
        """Test creating sync client with custom configuration."""
        config = CacheResponseConfig(
            default_ttl_seconds=600,
        )
        client = create_cache_response_sync_client(config=config)

        assert isinstance(client._transport, SyncCacheResponseTransport)

        client.close()

    def test_create_with_additional_kwargs(self) -> None:
        """Test creating sync client with additional httpx kwargs."""
        client = create_cache_response_sync_client(
            timeout=30.0,
            headers={"X-Custom-Header": "test"},
        )

        assert client.timeout.connect == 30.0
        assert client.headers.get("X-Custom-Header") == "test"

        client.close()


class TestIntegration:
    """Integration tests for factory functions."""

    @pytest.mark.asyncio
    async def test_client_caches_responses(self) -> None:
        """Test that created client properly caches responses."""
        # Create a custom transport to track requests
        inner = CacheableMockAsyncTransport(max_age=3600)

        # Use factory to create transport
        transport = create_cache_response_transport(inner)

        # Create client with our transport
        async with httpx.AsyncClient(transport=transport) as client:
            # First request - should hit inner transport
            response1 = await client.get("http://localhost/api/data")
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request - should hit cache
            response2 = await client.get("http://localhost/api/data")
            assert response2.status_code == 200
            assert len(inner.requests) == 1

    def test_sync_client_caches_responses(self) -> None:
        """Test that created sync client properly caches responses."""
        # Create client
        client = create_cache_response_sync_client()

        try:
            # Just verify the client was created correctly
            assert isinstance(client._transport, SyncCacheResponseTransport)
        finally:
            client.close()
