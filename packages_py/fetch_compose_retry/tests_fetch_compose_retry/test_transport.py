"""
Tests for fetch_compose_retry transport wrappers.

Test coverage includes:
- Statement coverage: All executable statements
- Decision/Branch coverage: All boolean decisions (if/else)
- Path coverage: Success paths, retry paths, failure paths
- State transition testing: Attempt states and transitions
"""

import pytest
import time
from unittest.mock import MagicMock, patch, AsyncMock
import httpx

from fetch_compose_retry.transport import RetryTransport, SyncRetryTransport
from fetch_retry import RetryConfig


class MockResponse:
    """Mock httpx.Response for testing."""

    def __init__(self, status_code: int, headers: dict = None):
        self.status_code = status_code
        self.headers = httpx.Headers(headers or {})


class TestRetryTransport:
    """Tests for async RetryTransport class."""

    class TestConstructor:
        """Tests for constructor."""

        def test_creates_transport_with_default_config(self):
            """Should create transport with default config."""
            inner = MagicMock(spec=httpx.AsyncHTTPTransport)
            transport = RetryTransport(inner)
            assert transport._config.max_retries == 3

        def test_creates_transport_with_custom_max_retries(self):
            """Should create transport with custom max_retries."""
            inner = MagicMock(spec=httpx.AsyncHTTPTransport)
            transport = RetryTransport(inner, max_retries=5)
            assert transport._config.max_retries == 5

        def test_creates_transport_with_custom_config(self):
            """Should create transport with custom config."""
            inner = MagicMock(spec=httpx.AsyncHTTPTransport)
            config = RetryConfig(max_retries=10, base_delay_seconds=2.0)
            transport = RetryTransport(inner, config=config)
            assert transport._config.max_retries == 10
            assert transport._config.base_delay_seconds == 2.0

        def test_stores_callbacks(self):
            """Should store callbacks."""
            inner = MagicMock(spec=httpx.AsyncHTTPTransport)
            on_retry = MagicMock()
            on_success = MagicMock()
            transport = RetryTransport(inner, on_retry=on_retry, on_success=on_success)
            assert transport._on_retry == on_retry
            assert transport._on_success == on_success

    class TestHandleAsyncRequest:
        """Tests for handle_async_request method."""

        @pytest.mark.asyncio
        async def test_passes_through_non_retryable_methods(self):
            """Should pass through non-retryable methods immediately."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.return_value = MockResponse(200)
            transport = RetryTransport(inner)

            request = httpx.Request("POST", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert inner.handle_async_request.call_count == 1

        @pytest.mark.asyncio
        async def test_returns_response_on_success(self):
            """Should return response on immediate success."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.return_value = MockResponse(200)
            transport = RetryTransport(inner)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

        @pytest.mark.asyncio
        async def test_retries_on_retryable_status(self):
            """Should retry on retryable status codes."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(503),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert inner.handle_async_request.call_count == 2

        @pytest.mark.asyncio
        async def test_retries_on_429_with_retry_after_header(self):
            """Should retry on 429 and respect Retry-After header."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(429, headers={"retry-after": "1"}),
                MockResponse(200),
            ]
            transport = RetryTransport(inner, max_retries=3, respect_retry_after=True)

            request = httpx.Request("GET", "https://example.com/test")
            start = time.monotonic()
            response = await transport.handle_async_request(request)
            elapsed = time.monotonic() - start

            assert response.status_code == 200
            assert elapsed >= 1.0

        @pytest.mark.asyncio
        async def test_retries_on_500_status(self):
            """Should retry on 500 Internal Server Error."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(500),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200
            assert inner.handle_async_request.call_count == 2

        @pytest.mark.asyncio
        async def test_retries_on_502_status(self):
            """Should retry on 502 Bad Gateway."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(502),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

        @pytest.mark.asyncio
        async def test_retries_on_504_status(self):
            """Should retry on 504 Gateway Timeout."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(504),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

        @pytest.mark.asyncio
        async def test_does_not_retry_on_4xx_errors(self):
            """Should not retry on 4xx client errors."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.return_value = MockResponse(400)
            transport = RetryTransport(inner, max_retries=3)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 400
            assert inner.handle_async_request.call_count == 1

        @pytest.mark.asyncio
        async def test_retries_on_network_error(self):
            """Should retry on network errors."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                ConnectionError("connection refused"),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

        @pytest.mark.asyncio
        async def test_retries_on_timeout_error(self):
            """Should retry on timeout errors."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                TimeoutError("request timed out"),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = await transport.handle_async_request(request)

            assert response.status_code == 200

        @pytest.mark.asyncio
        async def test_raises_after_max_retries_exhausted(self):
            """Should raise after max retries exhausted."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = ConnectionError("network error")
            config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")

            with pytest.raises(ConnectionError):
                await transport.handle_async_request(request)

            assert inner.handle_async_request.call_count == 3  # initial + 2 retries

        @pytest.mark.asyncio
        async def test_raises_immediately_for_non_retryable_errors(self):
            """Should raise immediately for non-retryable errors."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = ValueError("validation error")
            transport = RetryTransport(inner, max_retries=3)

            request = httpx.Request("GET", "https://example.com/test")

            with pytest.raises(ValueError):
                await transport.handle_async_request(request)

            assert inner.handle_async_request.call_count == 1

        @pytest.mark.asyncio
        async def test_calls_on_retry_callback(self):
            """Should call on_retry callback before each retry."""
            on_retry = MagicMock()
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.side_effect = [
                MockResponse(503),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = RetryTransport(inner, config=config, on_retry=on_retry)

            request = httpx.Request("GET", "https://example.com/test")
            await transport.handle_async_request(request)

            assert on_retry.call_count == 1
            on_retry.assert_called_with(
                expect.any(Exception), 1, expect.any(float)
            )

        @pytest.mark.asyncio
        async def test_calls_on_success_callback(self):
            """Should call on_success callback on success."""
            on_success = MagicMock()
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            inner.handle_async_request.return_value = MockResponse(200)
            transport = RetryTransport(inner, on_success=on_success)

            request = httpx.Request("GET", "https://example.com/test")
            await transport.handle_async_request(request)

            on_success.assert_called_once()

    class TestAclose:
        """Tests for aclose method."""

        @pytest.mark.asyncio
        async def test_closes_inner_transport(self):
            """Should close inner transport."""
            inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
            transport = RetryTransport(inner)

            await transport.aclose()

            inner.aclose.assert_called_once()


class TestSyncRetryTransport:
    """Tests for sync SyncRetryTransport class."""

    class TestConstructor:
        """Tests for constructor."""

        def test_creates_transport_with_default_config(self):
            """Should create transport with default config."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            transport = SyncRetryTransport(inner)
            assert transport._config.max_retries == 3

        def test_creates_transport_with_custom_config(self):
            """Should create transport with custom config."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            config = RetryConfig(max_retries=10)
            transport = SyncRetryTransport(inner, config=config)
            assert transport._config.max_retries == 10

    class TestHandleRequest:
        """Tests for handle_request method."""

        def test_passes_through_non_retryable_methods(self):
            """Should pass through non-retryable methods immediately."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.return_value = MockResponse(200)
            transport = SyncRetryTransport(inner)

            request = httpx.Request("POST", "https://example.com/test")
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert inner.handle_request.call_count == 1

        def test_returns_response_on_success(self):
            """Should return response on immediate success."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.return_value = MockResponse(200)
            transport = SyncRetryTransport(inner)

            request = httpx.Request("GET", "https://example.com/test")
            response = transport.handle_request(request)

            assert response.status_code == 200

        def test_retries_on_retryable_status(self):
            """Should retry on retryable status codes."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.side_effect = [
                MockResponse(503),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = SyncRetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = transport.handle_request(request)

            assert response.status_code == 200
            assert inner.handle_request.call_count == 2

        def test_retries_on_network_error(self):
            """Should retry on network errors."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.side_effect = [
                ConnectionError("connection refused"),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = SyncRetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")
            response = transport.handle_request(request)

            assert response.status_code == 200

        def test_raises_after_max_retries_exhausted(self):
            """Should raise after max retries exhausted."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.side_effect = ConnectionError("network error")
            config = RetryConfig(max_retries=2, base_delay_seconds=0.01, jitter_factor=0)
            transport = SyncRetryTransport(inner, config=config)

            request = httpx.Request("GET", "https://example.com/test")

            with pytest.raises(ConnectionError):
                transport.handle_request(request)

            assert inner.handle_request.call_count == 3

        def test_calls_on_retry_callback(self):
            """Should call on_retry callback before each retry."""
            on_retry = MagicMock()
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.side_effect = [
                MockResponse(503),
                MockResponse(200),
            ]
            config = RetryConfig(max_retries=3, base_delay_seconds=0.01, jitter_factor=0)
            transport = SyncRetryTransport(inner, config=config, on_retry=on_retry)

            request = httpx.Request("GET", "https://example.com/test")
            transport.handle_request(request)

            assert on_retry.call_count == 1

        def test_calls_on_success_callback(self):
            """Should call on_success callback on success."""
            on_success = MagicMock()
            inner = MagicMock(spec=httpx.HTTPTransport)
            inner.handle_request.return_value = MockResponse(200)
            transport = SyncRetryTransport(inner, on_success=on_success)

            request = httpx.Request("GET", "https://example.com/test")
            transport.handle_request(request)

            on_success.assert_called_once()

    class TestClose:
        """Tests for close method."""

        def test_closes_inner_transport(self):
            """Should close inner transport."""
            inner = MagicMock(spec=httpx.HTTPTransport)
            transport = SyncRetryTransport(inner)

            transport.close()

            inner.close.assert_called_once()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    @pytest.mark.asyncio
    async def test_zero_max_retries_async(self):
        """Should not retry when max_retries is 0."""
        inner = AsyncMock(spec=httpx.AsyncHTTPTransport)
        inner.handle_async_request.side_effect = ConnectionError("error")
        config = RetryConfig(max_retries=0)
        transport = RetryTransport(inner, config=config)

        request = httpx.Request("GET", "https://example.com/test")

        with pytest.raises(ConnectionError):
            await transport.handle_async_request(request)

        assert inner.handle_async_request.call_count == 1

    def test_zero_max_retries_sync(self):
        """Should not retry when max_retries is 0."""
        inner = MagicMock(spec=httpx.HTTPTransport)
        inner.handle_request.side_effect = ConnectionError("error")
        config = RetryConfig(max_retries=0)
        transport = SyncRetryTransport(inner, config=config)

        request = httpx.Request("GET", "https://example.com/test")

        with pytest.raises(ConnectionError):
            transport.handle_request(request)

        assert inner.handle_request.call_count == 1


class expect:
    """Helper for flexible assertions."""

    @staticmethod
    def any(type_):
        class AnyMatcher:
            def __eq__(self, other):
                return isinstance(other, type_)

            def __repr__(self):
                return f"<any {type_.__name__}>"

        return AnyMatcher()
