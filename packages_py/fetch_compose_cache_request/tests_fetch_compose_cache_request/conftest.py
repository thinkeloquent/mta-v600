"""Pytest configuration and fixtures for fetch_compose_cache_request tests."""
import asyncio
from typing import AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from cache_request import (
    IdempotencyConfig,
    SingleflightConfig,
    MemoryCacheStore,
    MemorySingleflightStore,
)
from fetch_compose_cache_request import (
    CacheRequestTransport,
    SyncCacheRequestTransport,
)


class MockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport for testing."""

    def __init__(
        self,
        response_status: int = 200,
        response_content: bytes = b'{"success": true}',
        response_headers: dict | None = None,
    ) -> None:
        self.response_status = response_status
        self.response_content = response_content
        self.response_headers = response_headers or {"content-type": "application/json"}
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the async request and return a mock response."""
        self.requests.append(request)
        return httpx.Response(
            status_code=self.response_status,
            headers=self.response_headers,
            content=self.response_content,
        )

    async def aclose(self) -> None:
        """Close the transport."""
        pass


class MockSyncTransport(httpx.BaseTransport):
    """Mock sync transport for testing."""

    def __init__(
        self,
        response_status: int = 200,
        response_content: bytes = b'{"success": true}',
        response_headers: dict | None = None,
    ) -> None:
        self.response_status = response_status
        self.response_content = response_content
        self.response_headers = response_headers or {"content-type": "application/json"}
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the sync request and return a mock response."""
        self.requests.append(request)
        return httpx.Response(
            status_code=self.response_status,
            headers=self.response_headers,
            content=self.response_content,
        )

    def close(self) -> None:
        """Close the transport."""
        pass


class DelayedMockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport with configurable delay for testing singleflight."""

    def __init__(
        self,
        delay: float = 0.1,
        response_status: int = 200,
        response_content: bytes = b'{"success": true}',
    ) -> None:
        self.delay = delay
        self.response_status = response_status
        self.response_content = response_content
        self.request_count = 0
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the async request with delay."""
        self.request_count += 1
        self.requests.append(request)
        await asyncio.sleep(self.delay)
        return httpx.Response(
            status_code=self.response_status,
            headers={"content-type": "application/json"},
            content=self.response_content,
        )

    async def aclose(self) -> None:
        """Close the transport."""
        pass


class ErrorMockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport that raises errors."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Raise the configured error."""
        raise self.error

    async def aclose(self) -> None:
        """Close the transport."""
        pass


class ErrorMockSyncTransport(httpx.BaseTransport):
    """Mock sync transport that raises errors."""

    def __init__(self, error: Exception) -> None:
        self.error = error

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Raise the configured error."""
        raise self.error

    def close(self) -> None:
        """Close the transport."""
        pass


@pytest.fixture
def mock_async_transport() -> MockAsyncTransport:
    """Create a mock async transport for testing."""
    return MockAsyncTransport()


@pytest.fixture
def mock_sync_transport() -> MockSyncTransport:
    """Create a mock sync transport for testing."""
    return MockSyncTransport()


@pytest.fixture
def delayed_async_transport() -> DelayedMockAsyncTransport:
    """Create a delayed mock async transport for singleflight testing."""
    return DelayedMockAsyncTransport(delay=0.1)


@pytest.fixture
def memory_cache_store() -> MemoryCacheStore:
    """Create a memory cache store for testing."""
    return MemoryCacheStore(cleanup_interval_seconds=60.0)


@pytest.fixture
def memory_singleflight_store() -> MemorySingleflightStore:
    """Create a memory singleflight store for testing."""
    return MemorySingleflightStore()


@pytest.fixture
async def cache_request_transport(
    mock_async_transport: MockAsyncTransport,
) -> AsyncGenerator[CacheRequestTransport, None]:
    """Create a cache request transport for testing."""
    transport = CacheRequestTransport(
        mock_async_transport,
        enable_idempotency=True,
        enable_singleflight=True,
    )
    yield transport
    await transport.aclose()


@pytest.fixture
def sync_cache_request_transport(
    mock_sync_transport: MockSyncTransport,
) -> Generator[SyncCacheRequestTransport, None, None]:
    """Create a sync cache request transport for testing."""
    transport = SyncCacheRequestTransport(
        mock_sync_transport,
        enable_idempotency=True,
    )
    yield transport
    transport.close()
