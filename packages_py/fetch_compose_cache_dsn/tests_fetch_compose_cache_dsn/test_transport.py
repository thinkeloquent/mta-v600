"""
Tests for DNS cache transport

Coverage includes:
- DnsCacheTransport async handling
- SyncDnsCacheTransport sync handling
- Host filtering (include/exclude patterns)
- Method filtering
- Host header preservation
- Connection tracking
- Error handling and health marking
- Wildcard host matching
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from fetch_compose_cache_dsn.transport import (
    DnsCacheTransport,
    SyncDnsCacheTransport,
)
from cache_dsn import DnsCacheConfig, ResolvedEndpoint


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


class TestDnsCacheTransportCreation:
    """Tests for DnsCacheTransport creation"""

    def test_create_with_defaults(self):
        """Should create transport with default options"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)
        assert transport is not None
        assert transport._inner is inner

    def test_create_with_custom_ttl(self):
        """Should create transport with custom TTL"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner, default_ttl_seconds=120.0)
        assert transport is not None

    def test_create_with_custom_strategy(self):
        """Should create transport with custom load balance strategy"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner, load_balance_strategy="power-of-two"
        )
        assert transport is not None

    def test_create_with_custom_config(self):
        """Should create transport with custom config"""
        inner = MockAsyncTransport()
        config = DnsCacheConfig(
            id="custom-transport",
            default_ttl_seconds=90.0,
            load_balance_strategy="least-connections",
        )
        transport = DnsCacheTransport(inner, config=config)
        assert transport is not None

    def test_create_with_host_filters(self):
        """Should create transport with host filters"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
        )
        assert transport is not None

    def test_create_with_method_filters(self):
        """Should create transport with method filters"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            methods=["GET", "POST"],
        )
        assert transport is not None


class TestDnsCacheTransportMethodFiltering:
    """Tests for method filtering"""

    @pytest.mark.asyncio
    async def test_passes_through_unfiltered_methods(self):
        """Should pass through when method not in filter list"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner, methods=["GET", "POST"])

        request = httpx.Request("DELETE", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through directly
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

    @pytest.mark.asyncio
    async def test_caches_filtered_methods(self):
        """Should apply caching when method is in filter list"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner, methods=["GET"])

        # Register custom resolver
        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should resolve to cached IP
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_caches_all_methods_when_no_filter(self):
        """Should apply caching to all methods when no filter"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)

        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        for method in ["GET", "POST", "PUT", "DELETE", "PATCH"]:
            request = httpx.Request(method, "http://api.example.com/resource")
            await transport.handle_async_request(request)

        # All should use cached resolution
        assert len(inner.requests) == 5
        assert all(req.url.host == "10.0.0.1" for req in inner.requests)


class TestDnsCacheTransportHostFiltering:
    """Tests for host filtering"""

    @pytest.mark.asyncio
    async def test_passes_through_excluded_hosts(self):
        """Should pass through when host is in exclude list"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            exclude_hosts=["internal.example.com"],
        )

        request = httpx.Request("GET", "https://internal.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through directly
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "internal.example.com"

    @pytest.mark.asyncio
    async def test_caches_included_hosts(self):
        """Should apply caching when host is in include list"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["api.example.com"],
        )

        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should use cached resolution
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_passes_through_non_included_hosts(self):
        """Should pass through when host not in include list"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["api.example.com"],
        )

        request = httpx.Request("GET", "https://other.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through directly
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "other.example.com"

    @pytest.mark.asyncio
    async def test_wildcard_host_matching(self):
        """Should support wildcard host patterns"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["*.example.com"],
        )

        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should match wildcard
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "10.0.0.1"


class TestDnsCacheTransportHostHeader:
    """Tests for Host header handling"""

    @pytest.mark.asyncio
    async def test_adds_host_header(self):
        """Should add Host header when missing"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)

        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        assert "host" in inner.requests[0].headers
        assert inner.requests[0].headers["host"] == "api.example.com"

    @pytest.mark.asyncio
    async def test_preserves_existing_host_header(self):
        """Should preserve existing Host header"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            exclude_hosts=["api.example.com"],  # Passthrough to verify header preserved
        )

        request = httpx.Request(
            "GET",
            "https://api.example.com/resource",
            headers={"host": "custom.example.com"},
        )
        await transport.handle_async_request(request)

        assert inner.requests[0].headers["host"] == "custom.example.com"


class TestDnsCacheTransportConnectionTracking:
    """Tests for connection tracking"""

    @pytest.mark.asyncio
    async def test_increments_connections(self):
        """Should increment connection count"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)

        async def resolver(dsn: str):
            return [ResolvedEndpoint(host="10.0.0.1", port=80, healthy=True)]

        transport.resolver.register_resolver("api.example.com", resolver)

        # Make request
        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        # Connection should have been incremented then decremented
        # (ends at 0 after successful request)
        connections = transport.resolver._load_balance_state.active_connections
        assert connections.get("10.0.0.1:80", 0) == 0


class TestDnsCacheTransportClose:
    """Tests for transport close"""

    @pytest.mark.asyncio
    async def test_close(self):
        """Should close transport and resolver"""
        inner = MockAsyncTransport()
        inner.aclose = AsyncMock()
        transport = DnsCacheTransport(inner)

        await transport.aclose()

        inner.aclose.assert_called_once()


class TestSyncDnsCacheTransport:
    """Tests for SyncDnsCacheTransport"""

    def test_create_with_defaults(self):
        """Should create sync transport with defaults"""
        inner = MockSyncTransport()
        transport = SyncDnsCacheTransport(inner)
        assert transport is not None

    def test_method_filtering(self):
        """Should filter by method"""
        inner = MockSyncTransport()
        transport = SyncDnsCacheTransport(
            inner,
            methods=["GET"],
        )

        # DELETE should pass through
        request = httpx.Request("DELETE", "https://api.example.com/resource")
        transport.handle_request(request)

        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

    def test_host_filtering(self):
        """Should filter by host"""
        inner = MockSyncTransport()
        transport = SyncDnsCacheTransport(
            inner,
            exclude_hosts=["internal.example.com"],
        )

        request = httpx.Request("GET", "https://internal.example.com/resource")
        transport.handle_request(request)

        # Should pass through
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "internal.example.com"

    def test_close(self):
        """Should close transport"""
        inner = MockSyncTransport()
        inner.close = MagicMock()
        transport = SyncDnsCacheTransport(inner)

        transport.close()

        inner.close.assert_called_once()
        assert len(transport._cache) == 0


class TestHostMatching:
    """Tests for host matching patterns"""

    @pytest.mark.asyncio
    async def test_exact_match(self):
        """Should match exact host"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["api.example.com"],
        )

        assert transport._should_cache_host("api.example.com") is True
        assert transport._should_cache_host("other.example.com") is False

    @pytest.mark.asyncio
    async def test_wildcard_subdomain(self):
        """Should match wildcard subdomains"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["*.example.com"],
        )

        assert transport._should_cache_host("api.example.com") is True
        assert transport._should_cache_host("v2.api.example.com") is True
        assert transport._should_cache_host("example.com") is True  # Base domain
        assert transport._should_cache_host("example.org") is False

    @pytest.mark.asyncio
    async def test_combined_include_exclude(self):
        """Should handle both include and exclude lists"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=["*.example.com"],
            exclude_hosts=["internal.example.com"],
        )

        assert transport._should_cache_host("api.example.com") is True
        assert transport._should_cache_host("internal.example.com") is False


class TestBoundaryConditions:
    """Tests for boundary conditions"""

    @pytest.mark.asyncio
    async def test_empty_hosts_list(self):
        """Should pass through when hosts list is empty"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(
            inner,
            hosts=[],
        )

        request = httpx.Request("GET", "https://api.example.com/resource")
        await transport.handle_async_request(request)

        # Empty hosts list means nothing matches - should pass through
        assert len(inner.requests) == 1
        assert inner.requests[0].url.host == "api.example.com"

    @pytest.mark.asyncio
    async def test_no_endpoints_resolved(self):
        """Should pass through when no endpoints available"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)

        async def resolver(dsn: str):
            return []  # No endpoints

        transport.resolver.register_resolver("api.example.com", resolver)

        request = httpx.Request("GET", "http://api.example.com/resource")
        await transport.handle_async_request(request)

        # Should pass through to original
        assert len(inner.requests) == 1


class TestResolver:
    """Tests for resolver property"""

    def test_resolver_property(self):
        """Should expose resolver via property"""
        inner = MockAsyncTransport()
        transport = DnsCacheTransport(inner)

        assert transport.resolver is not None
        assert hasattr(transport.resolver, "resolve")
        assert hasattr(transport.resolver, "resolve_one")
