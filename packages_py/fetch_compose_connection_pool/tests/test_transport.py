"""
Tests for connection pool transport

Coverage includes:
- Decision/Branch Coverage: Host and method filtering
- State Transition Testing: Connection lifecycle
- Error handling paths
- Integration with HTTPX transport pattern
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from fetch_compose_connection_pool.transport import (
    ConnectionPoolTransport,
    SyncConnectionPoolTransport,
)
from connection_pool import ConnectionPoolConfig


class MockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport for testing"""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.response_factory = None

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.response_factory:
            return self.response_factory(request)
        return httpx.Response(200, content=b"OK")


class MockSyncTransport(httpx.BaseTransport):
    """Mock sync transport for testing"""

    def __init__(self):
        self.requests: list[httpx.Request] = []
        self.response_factory = None

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self.response_factory:
            return self.response_factory(request)
        return httpx.Response(200, content=b"OK")


class TestConnectionPoolTransportCreation:
    """Tests for ConnectionPoolTransport creation"""

    @pytest.mark.asyncio
    async def test_create_with_defaults(self):
        """Should create transport with default options"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner)
        assert transport is not None
        assert transport._inner is inner
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_limits(self):
        """Should create transport with custom limits"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            max_connections=50,
            max_connections_per_host=5,
            max_idle_connections=10,
        )
        assert transport is not None
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self):
        """Should create transport with custom config"""
        inner = MockAsyncTransport()
        config = ConnectionPoolConfig(
            id="custom-transport",
            max_connections=100,
            max_connections_per_host=10,
        )
        transport = ConnectionPoolTransport(inner, config=config)
        assert transport is not None
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_host_filters(self):
        """Should create transport with host filters"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
        )
        assert transport is not None
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_create_with_method_filters(self):
        """Should create transport with method filters"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            methods=["GET", "POST"],
        )
        assert transport is not None
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_exposes_pool_property(self):
        """Should expose pool via property"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner)
        assert transport.pool is not None
        assert hasattr(transport.pool, "acquire")
        await transport.aclose()


class TestConnectionPoolTransportMethodFiltering:
    """Tests for method filtering"""

    @pytest.mark.asyncio
    async def test_passes_through_unfiltered_methods(self):
        """Should pass through when method not in filter list"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner, methods=["GET", "POST"])

        request = httpx.Request("DELETE", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through directly
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_uses_pool_for_filtered_methods(self):
        """Should use pool when method is in filter list"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner, methods=["GET"])

        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should go through pool (still dispatched to inner)
        assert len(inner.requests) == 1

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_pools_all_methods_when_no_filter(self):
        """Should pool all methods when no filter"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner)

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            request = httpx.Request(method, "https://api.example.com/resource")
            await transport.handle_async_request(request)

        # All should be processed
        assert len(inner.requests) == 5

        await transport.aclose()


class TestConnectionPoolTransportHostFiltering:
    """Tests for host filtering"""

    @pytest.mark.asyncio
    async def test_passes_through_excluded_hosts(self):
        """Should pass through when host is in exclude list"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            exclude_hosts=["internal.example.com"],
        )

        request = httpx.Request("GET", "https://internal.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through directly
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "internal.example.com"

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_pools_included_hosts(self):
        """Should use pool when host is in include list"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["api.example.com"],
        )

        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        assert len(inner.requests) == 1

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_passes_through_non_included_hosts(self):
        """Should pass through when host not in include list"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["api.example.com"],
        )

        request = httpx.Request("GET", "https://other.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "other.example.com"

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_wildcard_host_matching(self):
        """Should support wildcard host patterns"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["*.example.com"],
        )

        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should match wildcard
        assert len(inner.requests) == 1

        await transport.aclose()


class TestConnectionPoolTransportClose:
    """Tests for transport close"""

    @pytest.mark.asyncio
    async def test_closes_pool_and_inner(self):
        """Should close pool and inner transport"""
        inner = MockAsyncTransport()
        inner.aclose = AsyncMock()
        transport = ConnectionPoolTransport(inner)

        await transport.aclose()

        inner.aclose.assert_called_once()


class TestSyncConnectionPoolTransport:
    """Tests for SyncConnectionPoolTransport"""

    def test_create_with_defaults(self):
        """Should create sync transport with defaults"""
        inner = MockSyncTransport()
        transport = SyncConnectionPoolTransport(inner)
        assert transport is not None

    def test_method_filtering(self):
        """Should filter by method"""
        inner = MockSyncTransport()
        transport = SyncConnectionPoolTransport(
            inner,
            methods=["GET"],
        )

        # DELETE should pass through
        request = httpx.Request("DELETE", "https://api.example.com/resource")
        transport.handle_request(request)

        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

        transport.close()

    def test_host_filtering(self):
        """Should filter by host"""
        inner = MockSyncTransport()
        transport = SyncConnectionPoolTransport(
            inner,
            exclude_hosts=["internal.example.com"],
        )

        request = httpx.Request("GET", "https://internal.example.com/resource")
        transport.handle_request(request)

        # Should pass through
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "internal.example.com"

        transport.close()

    def test_close(self):
        """Should close transport"""
        inner = MockSyncTransport()
        inner.close = MagicMock()
        transport = SyncConnectionPoolTransport(inner)

        transport.close()

        inner.close.assert_called_once()


class TestHostMatching:
    """Tests for host matching patterns"""

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """Should match exact host"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["api.example.com"],
        )

        assert transport._should_pool_host("api.example.com") is True
        assert transport._should_pool_host("other.example.com") is False

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_wildcard_subdomain(self):
        """Should match wildcard subdomains"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["*.example.com"],
        )

        assert transport._should_pool_host("api.example.com") is True
        assert transport._should_pool_host("v2.api.example.com") is True
        assert transport._should_pool_host("example.com") is True  # Base domain
        assert transport._should_pool_host("example.org") is False

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_combined_include_exclude(self):
        """Should handle both include and exclude lists"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=["*.example.com"],
            exclude_hosts=["internal.example.com"],
        )

        assert transport._should_pool_host("api.example.com") is True
        assert transport._should_pool_host("internal.example.com") is False

        await transport.aclose()


class TestBoundaryConditions:
    """Tests for boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_hosts_list(self):
        """Should not pool when hosts list is empty"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(
            inner,
            hosts=[],
        )

        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Empty hosts list means nothing matches - should pass through
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_missing_host(self):
        """Should handle missing host gracefully"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner)

        # Request with empty host
        request = httpx.Request("GET", "http:///resource")
        await transport.handle_async_request(request)

        # Should still be processed
        assert len(inner.requests) == 1

        await transport.aclose()


class TestPoolProperty:
    """Tests for pool property access"""

    @pytest.mark.asyncio
    async def test_pool_stats(self):
        """Should be able to get pool stats"""
        inner = MockAsyncTransport()
        transport = ConnectionPoolTransport(inner)

        # Make a request
        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        stats = await transport.pool.get_stats()
        assert stats.total_requests >= 1

        await transport.aclose()

    @pytest.mark.asyncio
    async def test_pool_has_correct_config(self):
        """Should configure pool correctly"""
        inner = MockAsyncTransport()
        config = ConnectionPoolConfig(
            id="test-pool",
            max_connections=50,
            max_connections_per_host=5,
        )
        transport = ConnectionPoolTransport(inner, config=config)

        assert transport.pool.id == "test-pool"

        await transport.aclose()
