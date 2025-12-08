"""
Tests for rate limit transport wrappers

Coverage includes:
- RateLimitTransport creation and configuration
- SyncRateLimitTransport creation and configuration
- Retry-After header parsing
- Method filtering
- Rate limiting behavior
"""

import pytest
import time
from unittest.mock import Mock, AsyncMock, MagicMock, patch
import httpx

from fetch_compose_rate_limiter.transport import (
    RateLimitTransport,
    SyncRateLimitTransport,
)
from fetch_rate_limiter import (
    RateLimiterConfig,
    StaticRateLimitConfig,
    RateLimitStore,
)
from fetch_rate_limiter.stores.memory import MemoryStore


class TestRateLimitTransport:
    """Tests for async RateLimitTransport."""

    @pytest.fixture
    def mock_inner_transport(self):
        """Create a mock async transport."""
        transport = AsyncMock(spec=httpx.AsyncBaseTransport)
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.headers = {}
        transport.handle_async_request.return_value = response
        return transport

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = Mock(spec=httpx.Request)
        request.method = "GET"
        request.url = httpx.URL("https://api.example.com/test")
        return request

    class TestConstructor:
        """Tests for constructor."""

        @pytest.mark.asyncio
        async def test_create_with_max_per_second(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)
            assert transport is not None
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_custom_config(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            config = RateLimiterConfig(
                id="test",
                static=StaticRateLimitConfig(max_requests=100, interval_seconds=60.0),
            )
            transport = RateLimitTransport(inner, config=config)
            assert transport is not None
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_custom_store(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            store = MemoryStore()
            transport = RateLimitTransport(inner, max_per_second=10, store=store)
            assert transport is not None
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_default_config(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner)
            assert transport is not None
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_methods_filter(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(
                inner, max_per_second=10, methods=["GET", "POST"]
            )
            assert transport is not None
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_create_with_respect_retry_after(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(
                inner, max_per_second=10, respect_retry_after=False
            )
            assert transport is not None
            await transport.aclose()

    class TestHandleAsyncRequest:
        """Tests for handle_async_request method."""

        @pytest.mark.asyncio
        async def test_pass_request_to_inner_transport(
            self, mock_inner_transport, mock_request
        ):
            transport = RateLimitTransport(mock_inner_transport, max_per_second=100)

            await transport.handle_async_request(mock_request)

            mock_inner_transport.handle_async_request.assert_called_once_with(
                mock_request
            )
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_bypass_rate_limiting_for_unspecified_methods(
            self, mock_inner_transport, mock_request
        ):
            mock_request.method = "DELETE"
            transport = RateLimitTransport(
                mock_inner_transport, max_per_second=100, methods=["GET", "POST"]
            )

            await transport.handle_async_request(mock_request)

            mock_inner_transport.handle_async_request.assert_called_once()
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_rate_limit_specified_methods(
            self, mock_inner_transport, mock_request
        ):
            mock_request.method = "GET"
            transport = RateLimitTransport(
                mock_inner_transport, max_per_second=100, methods=["GET"]
            )

            await transport.handle_async_request(mock_request)

            mock_inner_transport.handle_async_request.assert_called_once()
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_handle_429_with_retry_after_seconds(
            self, mock_inner_transport, mock_request
        ):
            response = Mock(spec=httpx.Response)
            response.status_code = 429
            response.headers = {"retry-after": "5"}
            mock_inner_transport.handle_async_request.return_value = response

            transport = RateLimitTransport(
                mock_inner_transport, max_per_second=100, respect_retry_after=True
            )

            result = await transport.handle_async_request(mock_request)

            assert result.status_code == 429
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_handle_429_with_retry_after_date(
            self, mock_inner_transport, mock_request
        ):
            from email.utils import formatdate

            future_date = formatdate(time.time() + 5, usegmt=True)
            response = Mock(spec=httpx.Response)
            response.status_code = 429
            response.headers = {"retry-after": future_date}
            mock_inner_transport.handle_async_request.return_value = response

            transport = RateLimitTransport(
                mock_inner_transport, max_per_second=100, respect_retry_after=True
            )

            result = await transport.handle_async_request(mock_request)

            assert result.status_code == 429
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_ignore_retry_after_when_disabled(
            self, mock_inner_transport, mock_request
        ):
            response = Mock(spec=httpx.Response)
            response.status_code = 429
            response.headers = {"retry-after": "5"}
            mock_inner_transport.handle_async_request.return_value = response

            transport = RateLimitTransport(
                mock_inner_transport, max_per_second=100, respect_retry_after=False
            )

            result = await transport.handle_async_request(mock_request)

            assert result.status_code == 429
            await transport.aclose()

    class TestParseRetryAfter:
        """Tests for _parse_retry_after method."""

        @pytest.mark.asyncio
        async def test_parse_integer_seconds(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            result = transport._parse_retry_after("60")
            assert result == 60.0
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_parse_float_seconds(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            result = transport._parse_retry_after("1.5")
            assert result == 1.5
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_parse_http_date(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            from email.utils import formatdate

            future_date = formatdate(time.time() + 60, usegmt=True)
            result = transport._parse_retry_after(future_date)
            assert 55 <= result <= 65  # Allow some timing variance
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_return_0_for_invalid_value(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            result = transport._parse_retry_after("invalid")
            assert result == 0
            await transport.aclose()

        @pytest.mark.asyncio
        async def test_return_0_for_past_date(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            from email.utils import formatdate

            past_date = formatdate(time.time() - 60, usegmt=True)
            result = transport._parse_retry_after(past_date)
            assert result == 0
            await transport.aclose()

    class TestAclose:
        """Tests for aclose method."""

        @pytest.mark.asyncio
        async def test_close_limiter_and_inner_transport(self):
            inner = AsyncMock(spec=httpx.AsyncBaseTransport)
            transport = RateLimitTransport(inner, max_per_second=10)

            await transport.aclose()

            inner.aclose.assert_called_once()


class TestSyncRateLimitTransport:
    """Tests for sync SyncRateLimitTransport."""

    @pytest.fixture
    def mock_inner_transport(self):
        """Create a mock sync transport."""
        transport = Mock(spec=httpx.BaseTransport)
        response = Mock(spec=httpx.Response)
        response.status_code = 200
        response.headers = {}
        transport.handle_request.return_value = response
        return transport

    @pytest.fixture
    def mock_request(self):
        """Create a mock request."""
        request = Mock(spec=httpx.Request)
        request.method = "GET"
        request.url = httpx.URL("https://api.example.com/test")
        return request

    class TestConstructor:
        """Tests for constructor."""

        def test_create_with_max_per_second(self):
            inner = Mock(spec=httpx.BaseTransport)
            transport = SyncRateLimitTransport(inner, max_per_second=10)
            assert transport is not None

        def test_create_with_default_config(self):
            inner = Mock(spec=httpx.BaseTransport)
            transport = SyncRateLimitTransport(inner)
            assert transport is not None

        def test_create_with_methods_filter(self):
            inner = Mock(spec=httpx.BaseTransport)
            transport = SyncRateLimitTransport(
                inner, max_per_second=10, methods=["GET", "POST"]
            )
            assert transport is not None

        def test_create_with_respect_retry_after(self):
            inner = Mock(spec=httpx.BaseTransport)
            transport = SyncRateLimitTransport(
                inner, max_per_second=10, respect_retry_after=False
            )
            assert transport is not None

    class TestHandleRequest:
        """Tests for handle_request method."""

        def test_pass_request_to_inner_transport(
            self, mock_inner_transport, mock_request
        ):
            transport = SyncRateLimitTransport(mock_inner_transport, max_per_second=100)

            transport.handle_request(mock_request)

            mock_inner_transport.handle_request.assert_called_once_with(mock_request)

        def test_bypass_rate_limiting_for_unspecified_methods(
            self, mock_inner_transport, mock_request
        ):
            mock_request.method = "DELETE"
            transport = SyncRateLimitTransport(
                mock_inner_transport, max_per_second=100, methods=["GET", "POST"]
            )

            transport.handle_request(mock_request)

            mock_inner_transport.handle_request.assert_called_once()

        def test_rate_limit_specified_methods(
            self, mock_inner_transport, mock_request
        ):
            mock_request.method = "GET"
            transport = SyncRateLimitTransport(
                mock_inner_transport, max_per_second=100, methods=["GET"]
            )

            transport.handle_request(mock_request)

            mock_inner_transport.handle_request.assert_called_once()

        def test_handle_429_with_retry_after(self, mock_inner_transport, mock_request):
            response = Mock(spec=httpx.Response)
            response.status_code = 429
            response.headers = {"retry-after": "1"}
            mock_inner_transport.handle_request.return_value = response

            transport = SyncRateLimitTransport(
                mock_inner_transport, max_per_second=100, respect_retry_after=True
            )

            result = transport.handle_request(mock_request)

            assert result.status_code == 429

        def test_enforce_rate_limit(self, mock_inner_transport, mock_request):
            transport = SyncRateLimitTransport(
                mock_inner_transport, max_per_second=2
            )

            start = time.time()
            for _ in range(3):
                transport.handle_request(mock_request)
            elapsed = time.time() - start

            # Should take at least 0.5 seconds (2 requests per second)
            assert elapsed >= 0.4

    class TestClose:
        """Tests for close method."""

        def test_close_inner_transport(self):
            inner = Mock(spec=httpx.BaseTransport)
            transport = SyncRateLimitTransport(inner, max_per_second=10)

            transport.close()

            inner.close.assert_called_once()


class TestRetryAfterParsing:
    """Additional tests for Retry-After parsing edge cases."""

    @pytest.mark.asyncio
    async def test_parse_zero_seconds(self):
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RateLimitTransport(inner, max_per_second=10)

        result = transport._parse_retry_after("0")
        assert result == 0.0
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_parse_very_large_seconds(self):
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RateLimitTransport(inner, max_per_second=10)

        result = transport._parse_retry_after("3600")
        assert result == 3600.0
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_parse_negative_value(self):
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RateLimitTransport(inner, max_per_second=10)

        result = transport._parse_retry_after("-5")
        assert result == -5.0
        await transport.aclose()

    @pytest.mark.asyncio
    async def test_parse_empty_string(self):
        inner = AsyncMock(spec=httpx.AsyncBaseTransport)
        transport = RateLimitTransport(inner, max_per_second=10)

        result = transport._parse_retry_after("")
        assert result == 0
        await transport.aclose()
