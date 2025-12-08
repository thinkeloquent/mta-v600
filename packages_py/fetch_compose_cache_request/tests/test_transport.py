"""
Tests for cache request transport wrappers.
Following logic testing methodologies:
- Statement, Decision, Condition, Path Coverage
- Boundary Value Analysis
- State Transition Testing
- Error Handling
"""
import asyncio
import time
from unittest.mock import MagicMock
import uuid

import httpx
import pytest

from cache_request import (
    IdempotencyConfig,
    SingleflightConfig,
    MemoryCacheStore,
    MemorySingleflightStore,
)
from fetch_compose_cache_request import CacheRequestTransport, SyncCacheRequestTransport
from conftest import (
    MockAsyncTransport,
    MockSyncTransport,
    DelayedMockAsyncTransport,
    ErrorMockAsyncTransport,
    ErrorMockSyncTransport,
)


class TestCacheRequestTransport:
    """Tests for CacheRequestTransport."""

    class TestInitialization:
        """Test transport initialization."""

        @pytest.mark.asyncio
        async def test_create_with_defaults(self) -> None:
            """Test creating transport with default options."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(inner)

            assert transport._enable_idempotency is True
            assert transport._enable_singleflight is True
            assert transport._idempotency_manager is not None
            assert transport._singleflight is not None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_idempotency_only(self) -> None:
            """Test creating transport with idempotency only."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
            )

            assert transport._idempotency_manager is not None
            assert transport._singleflight is None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_singleflight_only(self) -> None:
            """Test creating transport with singleflight only."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
            )

            assert transport._idempotency_manager is None
            assert transport._singleflight is not None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_both_disabled(self) -> None:
            """Test creating transport with both features disabled."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=False,
            )

            assert transport._idempotency_manager is None
            assert transport._singleflight is None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_custom_configs(self) -> None:
            """Test creating transport with custom configurations."""
            inner = MockAsyncTransport()
            idempotency_config = IdempotencyConfig(
                ttl_seconds=3600,
                header_name="X-Request-Id",
            )
            singleflight_config = SingleflightConfig(methods=["GET"])

            transport = CacheRequestTransport(
                inner,
                idempotency_config=idempotency_config,
                singleflight_config=singleflight_config,
            )

            assert transport._idempotency_manager is not None
            assert transport._singleflight is not None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_custom_stores(self) -> None:
            """Test creating transport with custom stores."""
            inner = MockAsyncTransport()
            cache_store = MemoryCacheStore()
            singleflight_store = MemorySingleflightStore()

            transport = CacheRequestTransport(
                inner,
                idempotency_store=cache_store,
                singleflight_store=singleflight_store,
            )

            assert transport._idempotency_manager is not None
            assert transport._singleflight is not None

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_callbacks(self) -> None:
            """Test creating transport with callbacks."""
            inner = MockAsyncTransport()
            on_key_generated = MagicMock()
            on_coalesced = MagicMock()

            transport = CacheRequestTransport(
                inner,
                on_idempotency_key_generated=on_key_generated,
                on_request_coalesced=on_coalesced,
            )

            assert transport._on_idempotency_key_generated is on_key_generated
            assert transport._on_request_coalesced is on_coalesced

            await transport.aclose()

    class TestIdempotency:
        """Test idempotency handling."""

        @pytest.mark.asyncio
        async def test_post_request_generates_idempotency_key(self) -> None:
            """Test that POST requests generate idempotency key."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_existing_idempotency_key_is_used(self) -> None:
            """Test that existing idempotency key is used."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
            )

            existing_key = "my-custom-key-123"
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": existing_key},
            )
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1
            assert inner.requests[0].headers.get("Idempotency-Key") == existing_key

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_callback_called_on_key_generation(self) -> None:
            """Test callback is called when key is generated."""
            inner = MockAsyncTransport()
            on_key_generated = MagicMock()

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                on_idempotency_key_generated=on_key_generated,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")
            await transport.handle_async_request(request)

            on_key_generated.assert_called_once()
            call_args = on_key_generated.call_args[0]
            assert isinstance(call_args[0], str)  # key
            assert call_args[1] == "POST"  # method
            assert "http://localhost/api/orders" in call_args[2]  # url

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_callback_not_called_when_key_exists(self) -> None:
            """Test callback is not called when key already exists."""
            inner = MockAsyncTransport()
            on_key_generated = MagicMock()

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                on_idempotency_key_generated=on_key_generated,
            )

            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": "existing-key"},
            )
            await transport.handle_async_request(request)

            on_key_generated.assert_not_called()

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_caches_successful_responses(self) -> None:
            """Test that successful responses are cached."""
            inner = MockAsyncTransport()
            cache_store = MemoryCacheStore()

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                idempotency_store=cache_store,
            )

            idempotency_key = str(uuid.uuid4())
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test"}',
            )

            # First request
            response1 = await transport.handle_async_request(request)
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request with same key should return cached response
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test"}',
            )
            response2 = await transport.handle_async_request(request2)
            assert response2.status_code == 200
            # Inner transport should not be called again
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_does_not_cache_error_responses(self) -> None:
            """Test that error responses are not cached."""
            inner = MockAsyncTransport(response_status=500)
            cache_store = MemoryCacheStore()

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                idempotency_store=cache_store,
            )

            idempotency_key = str(uuid.uuid4())
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )

            response = await transport.handle_async_request(request)
            assert response.status_code == 500
            assert len(inner.requests) == 1

            # Second request should not use cache
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )
            response2 = await transport.handle_async_request(request2)
            assert response2.status_code == 500
            assert len(inner.requests) == 2

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_put_request_with_idempotency(self) -> None:
            """Test PUT request with idempotency."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                idempotency_config=IdempotencyConfig(methods=["POST", "PUT"]),
            )

            request = httpx.Request("PUT", "http://localhost/api/orders/1")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_patch_request_with_idempotency(self) -> None:
            """Test PATCH request with idempotency."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=False,
                idempotency_config=IdempotencyConfig(methods=["POST", "PATCH"]),
            )

            request = httpx.Request("PATCH", "http://localhost/api/orders/1")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

    class TestSingleflight:
        """Test singleflight handling."""

        @pytest.mark.asyncio
        async def test_get_request_with_singleflight(self) -> None:
            """Test GET request with singleflight."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
            )

            request = httpx.Request("GET", "http://localhost/api/users")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_concurrent_requests_are_coalesced(self) -> None:
            """Test that concurrent identical requests are coalesced."""
            inner = DelayedMockAsyncTransport(delay=0.1)
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
            )

            async def make_request():
                request = httpx.Request("GET", "http://localhost/api/users")
                return await transport.handle_async_request(request)

            # Fire concurrent requests
            responses = await asyncio.gather(
                make_request(),
                make_request(),
                make_request(),
            )

            # All responses should be successful
            for response in responses:
                assert response.status_code == 200

            # Only one actual request should have been made
            assert inner.request_count == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_callback_called_on_coalescing(self) -> None:
            """Test callback is called when requests are coalesced."""
            inner = DelayedMockAsyncTransport(delay=0.1)
            on_coalesced = MagicMock()

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
                on_request_coalesced=on_coalesced,
            )

            async def make_request():
                request = httpx.Request("GET", "http://localhost/api/users")
                return await transport.handle_async_request(request)

            await asyncio.gather(
                make_request(),
                make_request(),
            )

            # Callback should have been called for shared requests
            assert on_coalesced.call_count >= 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_head_request_with_singleflight(self) -> None:
            """Test HEAD request with singleflight."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
                singleflight_config=SingleflightConfig(methods=["GET", "HEAD"]),
            )

            request = httpx.Request("HEAD", "http://localhost/api/health")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

            await transport.aclose()

    class TestPassthrough:
        """Test passthrough behavior."""

        @pytest.mark.asyncio
        async def test_delete_request_passes_through(self) -> None:
            """Test DELETE request passes through without caching."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=True,
            )

            request = httpx.Request("DELETE", "http://localhost/api/users/1")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_options_request_passes_through(self) -> None:
            """Test OPTIONS request passes through."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=False,
            )

            request = httpx.Request("OPTIONS", "http://localhost/api/users")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_all_disabled_passes_through(self) -> None:
            """Test that requests pass through when both features are disabled."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=False,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            await transport.aclose()

    class TestErrorHandling:
        """Test error handling."""

        @pytest.mark.asyncio
        async def test_propagates_transport_errors(self) -> None:
            """Test that transport errors are propagated."""
            error = httpx.ConnectError("Connection refused")
            inner = ErrorMockAsyncTransport(error)

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=True,
                enable_singleflight=True,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")

            with pytest.raises(httpx.ConnectError):
                await transport.handle_async_request(request)

            await transport.aclose()

        @pytest.mark.asyncio
        async def test_propagates_timeout_errors(self) -> None:
            """Test that timeout errors are propagated."""
            error = httpx.TimeoutException("Request timed out")
            inner = ErrorMockAsyncTransport(error)

            transport = CacheRequestTransport(
                inner,
                enable_idempotency=False,
                enable_singleflight=True,
            )

            request = httpx.Request("GET", "http://localhost/api/users")

            with pytest.raises(httpx.TimeoutException):
                await transport.handle_async_request(request)

            await transport.aclose()

    class TestClose:
        """Test close functionality."""

        @pytest.mark.asyncio
        async def test_aclose_closes_inner_transport(self) -> None:
            """Test that aclose closes the inner transport."""
            inner = MockAsyncTransport()
            transport = CacheRequestTransport(inner)

            await transport.aclose()
            # Should not raise


class TestSyncCacheRequestTransport:
    """Tests for SyncCacheRequestTransport."""

    class TestInitialization:
        """Test sync transport initialization."""

        def test_create_with_defaults(self) -> None:
            """Test creating sync transport with default options."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            assert transport._enable_idempotency is True

            transport.close()

        def test_create_with_idempotency_disabled(self) -> None:
            """Test creating sync transport with idempotency disabled."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(
                inner,
                enable_idempotency=False,
            )

            assert transport._enable_idempotency is False

            transport.close()

        def test_create_with_custom_config(self) -> None:
            """Test creating sync transport with custom configuration."""
            inner = MockSyncTransport()
            config = IdempotencyConfig(
                ttl_seconds=3600,
                header_name="X-Request-Id",
            )

            transport = SyncCacheRequestTransport(
                inner,
                idempotency_config=config,
            )

            assert transport._idempotency_config == config

            transport.close()

        def test_create_with_callback(self) -> None:
            """Test creating sync transport with callback."""
            inner = MockSyncTransport()
            on_key_generated = MagicMock()

            transport = SyncCacheRequestTransport(
                inner,
                on_idempotency_key_generated=on_key_generated,
            )

            assert transport._on_idempotency_key_generated is on_key_generated

            transport.close()

    class TestIdempotency:
        """Test sync idempotency handling."""

        def test_post_request_generates_idempotency_key(self) -> None:
            """Test that POST requests generate idempotency key."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            request = httpx.Request("POST", "http://localhost/api/orders")
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            transport.close()

        def test_existing_idempotency_key_is_used(self) -> None:
            """Test that existing idempotency key is used."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            existing_key = "my-custom-key-123"
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": existing_key},
            )
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1
            assert inner.requests[0].headers.get("Idempotency-Key") == existing_key

            transport.close()

        def test_callback_called_on_key_generation(self) -> None:
            """Test callback is called when key is generated."""
            inner = MockSyncTransport()
            on_key_generated = MagicMock()

            transport = SyncCacheRequestTransport(
                inner,
                on_idempotency_key_generated=on_key_generated,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")
            transport.handle_request(request)

            on_key_generated.assert_called_once()

            transport.close()

        def test_caches_successful_responses(self) -> None:
            """Test that successful responses are cached."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            idempotency_key = str(uuid.uuid4())
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test"}',
            )

            # First request
            response1 = transport.handle_request(request)
            assert response1.status_code == 200
            assert len(inner.requests) == 1

            # Second request with same key
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test"}',
            )
            response2 = transport.handle_request(request2)
            assert response2.status_code == 200
            # Should use cached response
            assert len(inner.requests) == 1

            transport.close()

        def test_does_not_cache_error_responses(self) -> None:
            """Test that error responses are not cached."""
            inner = MockSyncTransport(response_status=500)
            transport = SyncCacheRequestTransport(inner)

            idempotency_key = str(uuid.uuid4())
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )

            response = transport.handle_request(request)
            assert response.status_code == 500
            assert len(inner.requests) == 1

            # Second request should not use cache
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )
            response2 = transport.handle_request(request2)
            assert response2.status_code == 500
            assert len(inner.requests) == 2

            transport.close()

        def test_cache_expiration(self) -> None:
            """Test that cached responses expire."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(
                inner,
                idempotency_config=IdempotencyConfig(ttl_seconds=0.1),
            )

            idempotency_key = str(uuid.uuid4())
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )

            # First request
            transport.handle_request(request)
            assert len(inner.requests) == 1

            # Wait for expiration
            time.sleep(0.2)

            # Second request should not use cache
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
            )
            transport.handle_request(request2)
            assert len(inner.requests) == 2

            transport.close()

        def test_fingerprint_validation(self) -> None:
            """Test that fingerprint is validated."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            idempotency_key = str(uuid.uuid4())

            # First request
            request1 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test1"}',
            )
            transport.handle_request(request1)
            assert len(inner.requests) == 1

            # Second request with different body (different fingerprint)
            request2 = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": idempotency_key},
                content=b'{"item": "test2"}',
            )
            transport.handle_request(request2)
            # Different fingerprint, so cache not used
            assert len(inner.requests) == 2

            transport.close()

    class TestPassthrough:
        """Test sync passthrough behavior."""

        def test_get_request_passes_through(self) -> None:
            """Test GET request passes through."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            request = httpx.Request("GET", "http://localhost/api/users")
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            transport.close()

        def test_idempotency_disabled_passes_through(self) -> None:
            """Test that POST passes through when idempotency is disabled."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(
                inner,
                enable_idempotency=False,
            )

            request = httpx.Request("POST", "http://localhost/api/orders")
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert len(inner.requests) == 1

            transport.close()

    class TestErrorHandling:
        """Test sync error handling."""

        def test_propagates_transport_errors(self) -> None:
            """Test that transport errors are propagated."""
            error = httpx.ConnectError("Connection refused")
            inner = ErrorMockSyncTransport(error)

            transport = SyncCacheRequestTransport(inner)

            request = httpx.Request("POST", "http://localhost/api/orders")

            with pytest.raises(httpx.ConnectError):
                transport.handle_request(request)

            transport.close()

    class TestClose:
        """Test sync close functionality."""

        def test_close_clears_cache(self) -> None:
            """Test that close clears the cache."""
            inner = MockSyncTransport()
            transport = SyncCacheRequestTransport(inner)

            # Add something to cache
            request = httpx.Request(
                "POST",
                "http://localhost/api/orders",
                headers={"Idempotency-Key": "test-key"},
            )
            transport.handle_request(request)

            transport.close()

            # Cache should be cleared
            assert len(transport._cache) == 0


class TestBoundaryConditions:
    """Test boundary conditions for both transport types."""

    @pytest.mark.asyncio
    async def test_empty_url(self) -> None:
        """Test handling of empty URL."""
        inner = MockAsyncTransport()
        transport = CacheRequestTransport(
            inner,
            enable_idempotency=False,
            enable_singleflight=True,
        )

        request = httpx.Request("GET", "http://localhost")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_url_with_query_params(self) -> None:
        """Test handling of URL with query parameters."""
        inner = MockAsyncTransport()
        transport = CacheRequestTransport(
            inner,
            enable_idempotency=False,
            enable_singleflight=True,
        )

        request = httpx.Request("GET", "http://localhost/api?page=1&limit=10")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_large_request_body(self) -> None:
        """Test handling of large request body."""
        inner = MockAsyncTransport()
        transport = CacheRequestTransport(
            inner,
            enable_idempotency=True,
            enable_singleflight=False,
        )

        large_body = b'{"data": "' + b"x" * 100000 + b'"}'
        request = httpx.Request(
            "POST",
            "http://localhost/api/upload",
            content=large_body,
        )
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_empty_request_body(self) -> None:
        """Test handling of empty request body."""
        inner = MockAsyncTransport()
        transport = CacheRequestTransport(
            inner,
            enable_idempotency=True,
            enable_singleflight=False,
        )

        request = httpx.Request("POST", "http://localhost/api/orders", content=b"")
        response = await transport.handle_async_request(request)

        assert response.status_code == 200

        await transport.aclose()


class TestStateTransitions:
    """Test state transitions."""

    @pytest.mark.asyncio
    async def test_sequential_requests_to_same_endpoint(self) -> None:
        """Test sequential requests to the same endpoint."""
        inner = MockAsyncTransport()
        transport = CacheRequestTransport(
            inner,
            enable_idempotency=False,
            enable_singleflight=True,
        )

        # First request
        request1 = httpx.Request("GET", "http://localhost/api/data")
        response1 = await transport.handle_async_request(request1)
        assert response1.status_code == 200

        # Second request (after first completes)
        request2 = httpx.Request("GET", "http://localhost/api/data")
        response2 = await transport.handle_async_request(request2)
        assert response2.status_code == 200

        # Both should have hit the inner transport
        assert len(inner.requests) == 2

        await transport.aclose()
