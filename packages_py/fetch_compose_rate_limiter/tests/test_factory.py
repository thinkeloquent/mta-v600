"""
Tests for factory functions

Coverage includes:
- compose_transport function
- compose_sync_transport function
- create_rate_limited_client function
- create_rate_limited_sync_client function
- create_api_rate_limiter function
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
import httpx

from fetch_compose_rate_limiter.factory import (
    compose_transport,
    compose_sync_transport,
    create_rate_limited_client,
    create_rate_limited_sync_client,
    create_api_rate_limiter,
)
from fetch_compose_rate_limiter.transport import (
    RateLimitTransport,
    SyncRateLimitTransport,
)
from fetch_rate_limiter import (
    RateLimiterConfig,
    StaticRateLimitConfig,
)
from fetch_rate_limiter.stores.memory import MemoryStore


class TestComposeTransport:
    """Tests for compose_transport function."""

    @pytest.mark.asyncio
    async def test_return_base_when_no_wrappers(self):
        base = AsyncMock(spec=httpx.AsyncBaseTransport)

        result = compose_transport(base)

        assert result is base

    @pytest.mark.asyncio
    async def test_apply_single_wrapper(self):
        base = AsyncMock(spec=httpx.AsyncBaseTransport)
        wrapped = AsyncMock(spec=httpx.AsyncBaseTransport)

        def wrapper(inner):
            assert inner is base
            return wrapped

        result = compose_transport(base, wrapper)

        assert result is wrapped

    @pytest.mark.asyncio
    async def test_apply_multiple_wrappers_in_order(self):
        base = AsyncMock(spec=httpx.AsyncBaseTransport)
        order = []

        def wrapper1(inner):
            order.append(1)
            return Mock(spec=httpx.AsyncBaseTransport, inner=inner)

        def wrapper2(inner):
            order.append(2)
            return Mock(spec=httpx.AsyncBaseTransport, inner=inner)

        def wrapper3(inner):
            order.append(3)
            return Mock(spec=httpx.AsyncBaseTransport, inner=inner)

        compose_transport(base, wrapper1, wrapper2, wrapper3)

        assert order == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_compose_with_rate_limiter(self):
        base = httpx.AsyncHTTPTransport()

        def rate_limit_wrapper(inner):
            return RateLimitTransport(inner, max_per_second=10)

        result = compose_transport(base, rate_limit_wrapper)

        assert isinstance(result, RateLimitTransport)


class TestComposeSyncTransport:
    """Tests for compose_sync_transport function."""

    def test_return_base_when_no_wrappers(self):
        base = Mock(spec=httpx.BaseTransport)

        result = compose_sync_transport(base)

        assert result is base

    def test_apply_single_wrapper(self):
        base = Mock(spec=httpx.BaseTransport)
        wrapped = Mock(spec=httpx.BaseTransport)

        def wrapper(inner):
            assert inner is base
            return wrapped

        result = compose_sync_transport(base, wrapper)

        assert result is wrapped

    def test_apply_multiple_wrappers_in_order(self):
        base = Mock(spec=httpx.BaseTransport)
        order = []

        def wrapper1(inner):
            order.append(1)
            return Mock(spec=httpx.BaseTransport, inner=inner)

        def wrapper2(inner):
            order.append(2)
            return Mock(spec=httpx.BaseTransport, inner=inner)

        compose_sync_transport(base, wrapper1, wrapper2)

        assert order == [1, 2]

    def test_compose_with_sync_rate_limiter(self):
        base = httpx.HTTPTransport()

        def rate_limit_wrapper(inner):
            return SyncRateLimitTransport(inner, max_per_second=10)

        result = compose_sync_transport(base, rate_limit_wrapper)

        assert isinstance(result, SyncRateLimitTransport)


class TestCreateRateLimitedClient:
    """Tests for create_rate_limited_client function."""

    @pytest.mark.asyncio
    async def test_create_with_max_per_second(self):
        client = create_rate_limited_client(max_per_second=10)

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_config(self):
        config = RateLimiterConfig(
            id="test",
            static=StaticRateLimitConfig(max_requests=100, interval_seconds=60.0),
        )
        client = create_rate_limited_client(config=config)

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_store(self):
        store = MemoryStore()
        client = create_rate_limited_client(max_per_second=10, store=store)

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_base_url(self):
        client = create_rate_limited_client(
            max_per_second=10, base_url="https://api.example.com"
        )

        assert isinstance(client, httpx.AsyncClient)
        assert str(client.base_url) == "https://api.example.com"
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_proxy(self):
        client = create_rate_limited_client(
            max_per_second=10, proxy="http://proxy:8080"
        )

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_custom_timeout(self):
        client = create_rate_limited_client(max_per_second=10, timeout=30.0)

        assert isinstance(client, httpx.AsyncClient)
        assert client.timeout.connect == 30.0
        await client.aclose()

    @pytest.mark.asyncio
    async def test_create_with_additional_kwargs(self):
        client = create_rate_limited_client(
            max_per_second=10,
            headers={"X-Custom-Header": "value"},
        )

        assert isinstance(client, httpx.AsyncClient)
        assert client.headers.get("X-Custom-Header") == "value"
        await client.aclose()


class TestCreateRateLimitedSyncClient:
    """Tests for create_rate_limited_sync_client function."""

    def test_create_with_max_per_second(self):
        client = create_rate_limited_sync_client(max_per_second=10)

        assert isinstance(client, httpx.Client)
        client.close()

    def test_create_with_base_url(self):
        client = create_rate_limited_sync_client(
            max_per_second=10, base_url="https://api.example.com"
        )

        assert isinstance(client, httpx.Client)
        assert str(client.base_url) == "https://api.example.com"
        client.close()

    def test_create_with_proxy(self):
        client = create_rate_limited_sync_client(max_per_second=10, proxy="http://proxy:8080")

        assert isinstance(client, httpx.Client)
        client.close()

    def test_create_with_custom_timeout(self):
        client = create_rate_limited_sync_client(max_per_second=10, timeout=30.0)

        assert isinstance(client, httpx.Client)
        assert client.timeout.connect == 30.0
        client.close()

    def test_create_with_additional_kwargs(self):
        client = create_rate_limited_sync_client(
            max_per_second=10,
            headers={"X-Custom-Header": "value"},
        )

        assert isinstance(client, httpx.Client)
        assert client.headers.get("X-Custom-Header") == "value"
        client.close()


class TestCreateApiRateLimiter:
    """Tests for create_api_rate_limiter function."""

    @pytest.mark.asyncio
    async def test_create_with_api_id_and_rate(self):
        wrapper = create_api_rate_limiter("github", 5000 / 3600)

        assert callable(wrapper)

    @pytest.mark.asyncio
    async def test_create_with_integer_rate(self):
        wrapper = create_api_rate_limiter("openai", 60)

        assert callable(wrapper)

    @pytest.mark.asyncio
    async def test_create_with_custom_store(self):
        store = MemoryStore()
        wrapper = create_api_rate_limiter("api", 10, store)

        assert callable(wrapper)

    @pytest.mark.asyncio
    async def test_wrapper_returns_rate_limit_transport(self):
        wrapper = create_api_rate_limiter("api", 10)
        inner = httpx.AsyncHTTPTransport()

        result = wrapper(inner)

        assert isinstance(result, RateLimitTransport)

    @pytest.mark.asyncio
    async def test_multiple_api_limiters(self):
        github_limiter = create_api_rate_limiter("github", 5000 / 3600)
        openai_limiter = create_api_rate_limiter("openai", 60)

        inner1 = httpx.AsyncHTTPTransport()
        inner2 = httpx.AsyncHTTPTransport()

        transport1 = github_limiter(inner1)
        transport2 = openai_limiter(inner2)

        assert isinstance(transport1, RateLimitTransport)
        assert isinstance(transport2, RateLimitTransport)


class TestIntegrationScenarios:
    """Integration tests for various scenarios."""

    @pytest.mark.asyncio
    async def test_compose_multiple_rate_limiters(self):
        base = httpx.AsyncHTTPTransport()

        def limiter1(inner):
            return RateLimitTransport(inner, max_per_second=100)

        def limiter2(inner):
            return RateLimitTransport(inner, max_per_second=50)

        result = compose_transport(base, limiter1, limiter2)

        assert isinstance(result, RateLimitTransport)

    @pytest.mark.asyncio
    async def test_shared_store_across_clients(self):
        store = MemoryStore()

        client1 = create_rate_limited_client(max_per_second=10, store=store)
        client2 = create_rate_limited_client(max_per_second=10, store=store)

        assert isinstance(client1, httpx.AsyncClient)
        assert isinstance(client2, httpx.AsyncClient)

        await client1.aclose()
        await client2.aclose()

    @pytest.mark.asyncio
    async def test_create_client_without_options(self):
        client = create_rate_limited_client()

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()


class TestEdgeCases:
    """Tests for edge cases."""

    @pytest.mark.asyncio
    async def test_very_low_rate_limit(self):
        client = create_rate_limited_client(max_per_second=0.1)

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_very_high_rate_limit(self):
        client = create_rate_limited_client(max_per_second=10000)

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    def test_sync_client_without_options(self):
        client = create_rate_limited_sync_client()

        assert isinstance(client, httpx.Client)
        client.close()

    @pytest.mark.asyncio
    async def test_empty_base_url(self):
        client = create_rate_limited_client(max_per_second=10, base_url="")

        assert isinstance(client, httpx.AsyncClient)
        await client.aclose()

    @pytest.mark.asyncio
    async def test_api_limiter_with_special_characters_in_id(self):
        wrapper = create_api_rate_limiter("api:v2/endpoint", 10)

        assert callable(wrapper)
