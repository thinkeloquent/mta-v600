"""
Tests for cache response transport wrappers.
Following logic testing methodologies:
- Statement, Decision, Condition, Path Coverage
- Boundary Value Analysis
- State Transition Testing
- Error Handling
"""
import asyncio
from unittest.mock import MagicMock

import httpx
import pytest

from cache_response import (
    CacheResponseConfig,
    CacheFreshness,
)
from fetch_compose_cache_response import CacheResponseTransport, SyncCacheResponseTransport
from tests.conftest import (
    MockAsyncTransport,
    MockSyncTransport,
    CacheableMockAsyncTransport,
    CacheableMockSyncTransport,
    NonCacheableMockAsyncTransport,
    ErrorMockAsyncTransport,
    ErrorMockSyncTransport,
)


class TestCacheResponseTransport:
    """Tests for CacheResponseTransport."""

    class TestInitialization:
        """Test transport initialization."""

        @pytest.mark.asyncio
        async def test_create_with_defaults(self) -> None:
            """Test creating transport with default options."""
            inner = MockAsyncTransport()
            transport = CacheResponseTransport(inner)

            assert transport._inner is inner
            assert transport._cache is not None
            assert transport._enable_background_revalidation is True

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_custom_config(self) -> None:
            """Test creating transport with custom configuration."""
            inner = MockAsyncTransport()
            config = CacheResponseConfig(
                default_ttl_seconds=600,
                max_ttl_seconds=3600,
            )

            transport = CacheResponseTransport(inner, config=config)

            assert transport._cache is not None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_background_revalidation_disabled(self) -> None:
            """Test creating transport with background revalidation disabled."""
            inner = MockAsyncTransport()
            transport = CacheResponseTransport(
                inner,
                enable_background_revalidation=False,
            )

            assert transport._enable_background_revalidation is False

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_callbacks(self) -> None:
            """Test creating transport with callbacks."""
            inner = MockAsyncTransport()
            on_cache_hit = MagicMock()
            on_cache_miss = MagicMock()
            on_cache_store = MagicMock()
            on_revalidated = MagicMock()

            transport = CacheResponseTransport(
                inner,
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

    class TestCacheMiss:
        """Test cache miss scenarios."""

        @pytest.mark.asyncio
        async def test_cache_miss_on_first_request(self) -> None:
            """Test that first request results in cache miss."""
            inner = CacheableMockAsyncTransport(max_age=3600)
            on_cache_miss = MagicMock()

            transport = CacheResponseTransport(
                inner,
                on_cache_miss=on_cache_miss,
            )

            request = httpx.Request("GET", "http://localhost/api/data")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            on_cache_miss.assert_called_once()

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_response_is_cached_after_miss(self) -> None:
            """Test that response is cached after cache miss."""
            inner = CacheableMockAsyncTransport(max_age=3600)
            on_cache_store = MagicMock()

            transport = CacheResponseTransport(
                inner,
                on_cache_store=on_cache_store,
            )

            request = httpx.Request("GET", "http://localhost/api/data")
            await transport.handle_async_request(request)

            on_cache_store.assert_called_once()

            await transport.aclose()

    class TestCacheHit:
        """Test cache hit scenarios."""

        @pytest.mark.asyncio
        async def test_cache_hit_returns_cached_response(self) -> None:
            """Test that cache hit returns cached response."""
            inner = CacheableMockAsyncTransport(max_age=3600)
            on_cache_hit = MagicMock()

            transport = CacheResponseTransport(
                inner,
                on_cache_hit=on_cache_hit,
            )

            # First request - cache miss
            request1 = httpx.Request("GET", "http://localhost/api/data")
            response1 = await transport.handle_async_request(request1)
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request - cache hit
            request2 = httpx.Request("GET", "http://localhost/api/data")
            response2 = await transport.handle_async_request(request2)
            assert response2.status_code == 200
            # Inner transport should not be called
            assert len(inner.requests) == 1

            on_cache_hit.assert_called()

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_cache_hit_callback_receives_freshness(self) -> None:
            """Test that cache hit callback receives freshness status."""
            inner = CacheableMockAsyncTransport(max_age=3600)
            cache_hit_args = []

            def on_cache_hit(url: str, freshness: CacheFreshness) -> None:
                cache_hit_args.append((url, freshness))

            transport = CacheResponseTransport(
                inner,
                on_cache_hit=on_cache_hit,
            )

            # First request
            request1 = httpx.Request("GET", "http://localhost/api/data")
            await transport.handle_async_request(request1)

            # Second request
            request2 = httpx.Request("GET", "http://localhost/api/data")
            await transport.handle_async_request(request2)

            assert len(cache_hit_args) == 1
            assert cache_hit_args[0][1] == CacheFreshness.FRESH

            await transport.aclose()

    class TestConditionalRequests:
        """Test conditional request handling."""

        @pytest.mark.asyncio
        async def test_conditional_request_headers_are_added(self) -> None:
            """Test that conditional request headers are added when cache entry has validators."""
            inner = CacheableMockAsyncTransport(max_age=3600, etag='"abc123"')

            transport = CacheResponseTransport(inner)

            # First request - cache miss, stores entry with etag
            request1 = httpx.Request("GET", "http://localhost/api/data")
            response1 = await transport.handle_async_request(request1)
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request - cache hit (fresh), no additional request needed
            request2 = httpx.Request("GET", "http://localhost/api/data")
            response2 = await transport.handle_async_request(request2)
            assert response2.status_code == 200
            assert len(inner.requests) == 1  # Still only 1 request

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_304_response_uses_cached_body(self) -> None:
            """Test that 304 response uses cached body."""
            inner = CacheableMockAsyncTransport(
                max_age=0,
                etag='"abc123"',
                response_content=b'{"original": "data"}',
            )

            transport = CacheResponseTransport(
                inner,
                enable_background_revalidation=False,
            )

            # First request
            request1 = httpx.Request("GET", "http://localhost/api/data")
            response1 = await transport.handle_async_request(request1)
            content1 = response1.content
            assert content1 == b'{"original": "data"}'

            # Second request - gets 304, should use cached body
            request2 = httpx.Request("GET", "http://localhost/api/data")
            response2 = await transport.handle_async_request(request2)
            content2 = response2.content
            assert content2 == b'{"original": "data"}'

            await transport.aclose()

    class TestNonCacheableResponses:
        """Test non-cacheable response handling."""

        @pytest.mark.asyncio
        async def test_no_store_response_not_cached(self) -> None:
            """Test that no-store responses are not cached."""
            inner = NonCacheableMockAsyncTransport(cache_control="no-store")

            transport = CacheResponseTransport(inner)

            # First request
            request1 = httpx.Request("GET", "http://localhost/api/data")
            await transport.handle_async_request(request1)
            assert len(inner.requests) == 1

            # Second request - should not use cache
            request2 = httpx.Request("GET", "http://localhost/api/data")
            await transport.handle_async_request(request2)
            assert len(inner.requests) == 2

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_post_request_not_cached(self) -> None:
            """Test that POST requests are not cached."""
            inner = CacheableMockAsyncTransport(max_age=3600)

            transport = CacheResponseTransport(inner)

            # First POST request
            request1 = httpx.Request("POST", "http://localhost/api/data", content=b"{}")
            await transport.handle_async_request(request1)
            assert len(inner.requests) == 1

            # Second POST request - should not use cache
            request2 = httpx.Request("POST", "http://localhost/api/data", content=b"{}")
            await transport.handle_async_request(request2)
            assert len(inner.requests) == 2

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_put_request_not_cached(self) -> None:
            """Test that PUT requests are not cached."""
            inner = CacheableMockAsyncTransport(max_age=3600)

            transport = CacheResponseTransport(inner)

            request = httpx.Request("PUT", "http://localhost/api/data/1", content=b"{}")
            await transport.handle_async_request(request)
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_delete_request_not_cached(self) -> None:
            """Test that DELETE requests are not cached."""
            inner = MockAsyncTransport()

            transport = CacheResponseTransport(inner)

            request = httpx.Request("DELETE", "http://localhost/api/data/1")
            await transport.handle_async_request(request)
            assert len(inner.requests) == 1

            await transport.aclose()

    class TestErrorHandling:
        """Test error handling."""

        @pytest.mark.asyncio
        async def test_propagates_transport_errors(self) -> None:
            """Test that transport errors are propagated."""
            error = httpx.ConnectError("Connection refused")
            inner = ErrorMockAsyncTransport(error)

            transport = CacheResponseTransport(inner)

            request = httpx.Request("GET", "http://localhost/api/data")

            with pytest.raises(httpx.ConnectError):
                await transport.handle_async_request(request)

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_propagates_timeout_errors(self) -> None:
            """Test that timeout errors are propagated."""
            error = httpx.TimeoutException("Request timed out")
            inner = ErrorMockAsyncTransport(error)

            transport = CacheResponseTransport(inner)

            request = httpx.Request("GET", "http://localhost/api/data")

            with pytest.raises(httpx.TimeoutException):
                await transport.handle_async_request(request)

            await transport.aclose()

    class TestClose:
        """Test close functionality."""

        @pytest.mark.asyncio
        async def test_aclose_closes_inner_transport(self) -> None:
            """Test that aclose closes resources."""
            inner = MockAsyncTransport()
            transport = CacheResponseTransport(inner)

            await transport.aclose()
            # Should not raise


class TestSyncCacheResponseTransport:
    """Tests for SyncCacheResponseTransport."""

    class TestInitialization:
        """Test sync transport initialization."""

        def test_create_with_defaults(self) -> None:
            """Test creating sync transport with default options."""
            inner = MockSyncTransport()
            transport = SyncCacheResponseTransport(inner)

            assert transport._inner is inner
            assert transport._config is not None

            transport.close()

        def test_create_with_custom_config(self) -> None:
            """Test creating sync transport with custom configuration."""
            inner = MockSyncTransport()
            config = CacheResponseConfig(
                default_ttl_seconds=600,
                max_ttl_seconds=3600,
            )

            transport = SyncCacheResponseTransport(inner, config=config)

            assert transport._config == config

            transport.close()

        def test_create_with_callbacks(self) -> None:
            """Test creating sync transport with callbacks."""
            inner = MockSyncTransport()
            on_cache_hit = MagicMock()
            on_cache_miss = MagicMock()
            on_cache_store = MagicMock()

            transport = SyncCacheResponseTransport(
                inner,
                on_cache_hit=on_cache_hit,
                on_cache_miss=on_cache_miss,
                on_cache_store=on_cache_store,
            )

            assert transport._on_cache_hit is on_cache_hit
            assert transport._on_cache_miss is on_cache_miss
            assert transport._on_cache_store is on_cache_store

            transport.close()

    class TestCacheMiss:
        """Test sync cache miss scenarios."""

        def test_cache_miss_on_first_request(self) -> None:
            """Test that first request results in cache miss."""
            inner = CacheableMockSyncTransport(max_age=3600)
            on_cache_miss = MagicMock()

            transport = SyncCacheResponseTransport(
                inner,
                on_cache_miss=on_cache_miss,
            )

            request = httpx.Request("GET", "http://localhost/api/data")
            response = transport.handle_request(request)

            assert response.status_code == 200
            on_cache_miss.assert_called_once()

            transport.close()

        def test_response_is_cached_after_miss(self) -> None:
            """Test that response is cached after cache miss."""
            inner = CacheableMockSyncTransport(max_age=3600)
            on_cache_store = MagicMock()

            transport = SyncCacheResponseTransport(
                inner,
                on_cache_store=on_cache_store,
            )

            request = httpx.Request("GET", "http://localhost/api/data")
            transport.handle_request(request)

            on_cache_store.assert_called_once()

            transport.close()

    class TestCacheHit:
        """Test sync cache hit scenarios."""

        def test_cache_hit_returns_cached_response(self) -> None:
            """Test that cache hit returns cached response."""
            inner = CacheableMockSyncTransport(max_age=3600)
            on_cache_hit = MagicMock()

            transport = SyncCacheResponseTransport(
                inner,
                on_cache_hit=on_cache_hit,
            )

            # First request - cache miss
            request1 = httpx.Request("GET", "http://localhost/api/data")
            response1 = transport.handle_request(request1)
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request - cache hit
            request2 = httpx.Request("GET", "http://localhost/api/data")
            response2 = transport.handle_request(request2)
            assert response2.status_code == 200
            # Inner transport should not be called
            assert len(inner.requests) == 1

            on_cache_hit.assert_called()

            transport.close()

    class TestNonCacheableResponses:
        """Test sync non-cacheable response handling."""

        def test_post_request_not_cached(self) -> None:
            """Test that POST requests are not cached."""
            inner = CacheableMockSyncTransport(max_age=3600)

            transport = SyncCacheResponseTransport(inner)

            # First POST request
            request1 = httpx.Request("POST", "http://localhost/api/data", content=b"{}")
            transport.handle_request(request1)
            assert len(inner.requests) == 1

            # Second POST request - should not use cache
            request2 = httpx.Request("POST", "http://localhost/api/data", content=b"{}")
            transport.handle_request(request2)
            assert len(inner.requests) == 2

            transport.close()

    class TestErrorHandling:
        """Test sync error handling."""

        def test_propagates_transport_errors(self) -> None:
            """Test that transport errors are propagated."""
            error = httpx.ConnectError("Connection refused")
            inner = ErrorMockSyncTransport(error)

            transport = SyncCacheResponseTransport(inner)

            request = httpx.Request("GET", "http://localhost/api/data")

            with pytest.raises(httpx.ConnectError):
                transport.handle_request(request)

            transport.close()

    class TestClose:
        """Test sync close functionality."""

        def test_close_clears_cache(self) -> None:
            """Test that close clears the cache."""
            inner = MockSyncTransport()
            transport = SyncCacheResponseTransport(inner)

            transport.close()

            # Cache should be cleared
            assert len(transport._cache) == 0


class TestBoundaryConditions:
    """Test boundary conditions for both transport types."""

    @pytest.mark.asyncio
    async def test_empty_url(self) -> None:
        """Test handling of empty URL."""
        inner = CacheableMockAsyncTransport(max_age=3600)
        transport = CacheResponseTransport(inner)

        request = httpx.Request("GET", "http://localhost")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_url_with_query_params(self) -> None:
        """Test handling of URL with query parameters."""
        inner = CacheableMockAsyncTransport(max_age=3600)
        transport = CacheResponseTransport(inner)

        # First request
        request1 = httpx.Request("GET", "http://localhost/api?page=1&limit=10")
        await transport.handle_async_request(request1)
        assert len(inner.requests) == 1

        # Second request with same params - should hit cache
        request2 = httpx.Request("GET", "http://localhost/api?page=1&limit=10")
        await transport.handle_async_request(request2)
        assert len(inner.requests) == 1

        # Different query params - should miss cache
        request3 = httpx.Request("GET", "http://localhost/api?page=2&limit=10")
        await transport.handle_async_request(request3)
        assert len(inner.requests) == 2

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_different_methods_same_url(self) -> None:
        """Test that different methods have different cache entries."""
        inner = CacheableMockAsyncTransport(max_age=3600)
        transport = CacheResponseTransport(inner)

        # GET request
        get_request = httpx.Request("GET", "http://localhost/api/data")
        await transport.handle_async_request(get_request)
        assert len(inner.requests) == 1

        # HEAD request to same URL - should miss cache
        head_request = httpx.Request("HEAD", "http://localhost/api/data")
        await transport.handle_async_request(head_request)
        assert len(inner.requests) == 2

        await transport.aclose()


class TestStateTransitions:
    """Test state transitions."""

    @pytest.mark.asyncio
    async def test_fresh_to_stale_transition(self) -> None:
        """Test that cached responses transition from fresh to stale."""
        # Use very short max-age
        inner = CacheableMockAsyncTransport(max_age=0)
        transport = CacheResponseTransport(
            inner,
            enable_background_revalidation=False,
        )

        # First request - fresh
        request1 = httpx.Request("GET", "http://localhost/api/data")
        await transport.handle_async_request(request1)
        assert len(inner.requests) == 1

        # Wait a bit (cache entry should be immediately stale with max_age=0)
        await asyncio.sleep(0.1)

        # Second request - should revalidate (stale entry)
        request2 = httpx.Request("GET", "http://localhost/api/data")
        await transport.handle_async_request(request2)
        # Should have made another request for revalidation
        assert len(inner.requests) >= 2

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_sequential_requests_to_same_endpoint(self) -> None:
        """Test sequential requests to the same endpoint."""
        inner = CacheableMockAsyncTransport(max_age=3600)
        transport = CacheResponseTransport(inner)

        # Multiple sequential requests
        for i in range(5):
            request = httpx.Request("GET", "http://localhost/api/data")
            response = await transport.handle_async_request(request)
            assert response.status_code == 200

        # Only first request should hit the server
        assert len(inner.requests) == 1

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_requests_to_different_endpoints(self) -> None:
        """Test requests to different endpoints are cached separately."""
        inner = CacheableMockAsyncTransport(max_age=3600)
        transport = CacheResponseTransport(inner)

        endpoints = ["/api/users", "/api/posts", "/api/comments"]

        # Request each endpoint
        for endpoint in endpoints:
            request = httpx.Request("GET", f"http://localhost{endpoint}")
            await transport.handle_async_request(request)

        # All should hit the server
        assert len(inner.requests) == 3

        # Request again - all should hit cache
        for endpoint in endpoints:
            request = httpx.Request("GET", f"http://localhost{endpoint}")
            await transport.handle_async_request(request)

        # No additional server requests
        assert len(inner.requests) == 3

        await transport.aclose()
