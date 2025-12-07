"""
Tests for DNS cache factory functions

Coverage includes:
- compose_transport function
- compose_sync_transport function
- create_dns_cached_client factory
- create_dns_cached_sync_client factory
- create_api_dns_cache factory
- create_from_preset function
- Preset configurations
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import httpx

from fetch_compose_cache_dsn.factory import (
    compose_transport,
    compose_sync_transport,
    create_dns_cached_client,
    create_dns_cached_sync_client,
    create_api_dns_cache,
    create_from_preset,
    AGGRESSIVE_DNS_CACHE,
    CONSERVATIVE_DNS_CACHE,
    HIGH_AVAILABILITY_DNS_CACHE,
)
from fetch_compose_cache_dsn.transport import DnsCacheTransport, SyncDnsCacheTransport


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


class TestCreateDnsCachedClient:
    """Tests for create_dns_cached_client factory"""

    def test_create_with_base_url(self):
        """Should create client with base URL"""
        client = create_dns_cached_client(base_url="https://api.example.com")
        assert isinstance(client, httpx.AsyncClient)

    def test_create_with_custom_ttl_and_base_url(self):
        """Should create client with custom TTL"""
        client = create_dns_cached_client(
            default_ttl_seconds=120.0,
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)

    def test_create_with_load_balance_strategy_and_base_url(self):
        """Should create client with custom strategy"""
        client = create_dns_cached_client(
            load_balance_strategy="power-of-two",
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)

    def test_create_with_host_filters_and_base_url(self):
        """Should create client with host filters"""
        client = create_dns_cached_client(
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)

    def test_create_with_client_kwargs(self):
        """Should pass kwargs to client"""
        client = create_dns_cached_client(
            timeout=30.0,
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.AsyncClient)


class TestCreateDnsCachedSyncClient:
    """Tests for create_dns_cached_sync_client factory"""

    def test_create_with_base_url(self):
        """Should create sync client with base URL"""
        client = create_dns_cached_sync_client(base_url="https://api.example.com")
        assert isinstance(client, httpx.Client)

    def test_create_with_custom_ttl_and_base_url(self):
        """Should create sync client with custom TTL"""
        client = create_dns_cached_sync_client(
            default_ttl_seconds=120.0,
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.Client)

    def test_create_with_host_filters_and_base_url(self):
        """Should create sync client with host filters"""
        client = create_dns_cached_sync_client(
            hosts=["api.example.com"],
            exclude_hosts=["internal.example.com"],
            base_url="https://api.example.com",
        )
        assert isinstance(client, httpx.Client)


class TestCreateApiDnsCache:
    """Tests for create_api_dns_cache factory"""

    def test_create_wrapper(self):
        """Should create transport wrapper function"""
        wrapper = create_api_dns_cache("my-api")
        assert callable(wrapper)

    def test_wrapper_creates_transport(self):
        """Wrapper should create DnsCacheTransport"""
        wrapper = create_api_dns_cache("my-api", ttl_seconds=120.0)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_wrapper_uses_api_id(self):
        """Wrapper should use API ID in config"""
        wrapper = create_api_dns_cache("github-api")
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert transport.resolver._config.id == "github-api"

    def test_wrapper_uses_custom_ttl(self):
        """Wrapper should use custom TTL"""
        wrapper = create_api_dns_cache("my-api", ttl_seconds=300.0)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert transport.resolver._config.default_ttl_seconds == 300.0

    def test_wrapper_uses_custom_strategy(self):
        """Wrapper should use custom strategy"""
        wrapper = create_api_dns_cache(
            "my-api",
            load_balance_strategy="least-connections",
        )
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert transport.resolver._config.load_balance_strategy == "least-connections"


class TestPresets:
    """Tests for preset configurations"""

    def test_aggressive_preset(self):
        """Aggressive preset should have long TTL"""
        assert AGGRESSIVE_DNS_CACHE["default_ttl_seconds"] == 300.0
        assert AGGRESSIVE_DNS_CACHE["load_balance_strategy"] == "power-of-two"

    def test_conservative_preset(self):
        """Conservative preset should have short TTL"""
        assert CONSERVATIVE_DNS_CACHE["default_ttl_seconds"] == 10.0
        assert CONSERVATIVE_DNS_CACHE["load_balance_strategy"] == "round-robin"

    def test_high_availability_preset(self):
        """High availability preset should have moderate TTL"""
        assert HIGH_AVAILABILITY_DNS_CACHE["default_ttl_seconds"] == 30.0
        assert HIGH_AVAILABILITY_DNS_CACHE["load_balance_strategy"] == "least-connections"

    def test_preset_ttl_ordering(self):
        """Conservative < HA < Aggressive TTL"""
        assert (
            CONSERVATIVE_DNS_CACHE["default_ttl_seconds"]
            < HIGH_AVAILABILITY_DNS_CACHE["default_ttl_seconds"]
        )
        assert (
            HIGH_AVAILABILITY_DNS_CACHE["default_ttl_seconds"]
            < AGGRESSIVE_DNS_CACHE["default_ttl_seconds"]
        )


class TestCreateFromPreset:
    """Tests for create_from_preset function"""

    def test_create_from_aggressive_preset(self):
        """Should create transport from aggressive preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(AGGRESSIVE_DNS_CACHE, inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_create_from_conservative_preset(self):
        """Should create transport from conservative preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(CONSERVATIVE_DNS_CACHE, inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_create_from_ha_preset(self):
        """Should create transport from HA preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(HIGH_AVAILABILITY_DNS_CACHE, inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_create_with_overrides(self):
        """Should apply overrides to preset"""
        inner = MockAsyncTransport()
        transport = create_from_preset(
            AGGRESSIVE_DNS_CACHE,
            inner,
            default_ttl_seconds=60.0,  # Override
        )
        assert isinstance(transport, DnsCacheTransport)


class TestIntegration:
    """Integration tests for factory functions"""

    def test_compose_with_dns_cache(self):
        """Should compose transport with DNS cache wrapper"""
        base = MockAsyncTransport()
        transport = compose_transport(
            base,
            create_api_dns_cache("api1", ttl_seconds=60),
        )
        assert isinstance(transport, DnsCacheTransport)

    def test_compose_multiple_api_caches(self):
        """Should compose multiple API caches"""
        base = MockAsyncTransport()
        transport = compose_transport(
            base,
            create_api_dns_cache("api1", ttl_seconds=60),
            create_api_dns_cache("api2", ttl_seconds=120),
        )
        # Outer wrapper should be api2
        assert isinstance(transport, DnsCacheTransport)
        assert transport.resolver._config.id == "api2"


class TestBoundaryConditions:
    """Tests for boundary conditions"""

    def test_empty_api_id(self):
        """Should handle empty API ID"""
        wrapper = create_api_dns_cache("")
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_very_long_api_id(self):
        """Should handle very long API ID"""
        wrapper = create_api_dns_cache("a" * 1000)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_zero_ttl(self):
        """Should handle zero TTL (will be clamped)"""
        wrapper = create_api_dns_cache("api", ttl_seconds=0.0)
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, DnsCacheTransport)

    def test_very_large_ttl(self):
        """Should handle very large TTL"""
        wrapper = create_api_dns_cache("api", ttl_seconds=86400.0)  # 24 hours
        inner = MockAsyncTransport()
        transport = wrapper(inner)
        assert isinstance(transport, DnsCacheTransport)
