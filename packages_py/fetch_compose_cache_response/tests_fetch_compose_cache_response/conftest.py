"""Pytest configuration and fixtures for fetch_compose_cache_response tests."""
import asyncio
from typing import AsyncGenerator, Generator

import httpx
import pytest

from cache_response import (
    CacheResponseConfig,
    MemoryCacheStore,
    create_memory_cache_store,
)
from fetch_compose_cache_response import (
    CacheResponseTransport,
    SyncCacheResponseTransport,
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


class CacheableMockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport that returns cacheable responses."""

    def __init__(
        self,
        response_status: int = 200,
        response_content: bytes = b'{"data": "cached"}',
        max_age: int = 3600,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        self.response_status = response_status
        self.response_content = response_content
        self.max_age = max_age
        self.etag = etag
        self.last_modified = last_modified
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the async request and return a cacheable response."""
        self.requests.append(request)

        # Check for conditional request
        if_none_match = request.headers.get("if-none-match")
        if_modified_since = request.headers.get("if-modified-since")

        # Return 304 if conditional headers match
        if self.etag and if_none_match == self.etag:
            return httpx.Response(
                status_code=304,
                headers={"etag": self.etag, "cache-control": f"max-age={self.max_age}"},
                content=b"",
            )

        if self.last_modified and if_modified_since == self.last_modified:
            return httpx.Response(
                status_code=304,
                headers={
                    "last-modified": self.last_modified,
                    "cache-control": f"max-age={self.max_age}",
                },
                content=b"",
            )

        headers = {
            "content-type": "application/json",
            "cache-control": f"max-age={self.max_age}",
        }
        if self.etag:
            headers["etag"] = self.etag
        if self.last_modified:
            headers["last-modified"] = self.last_modified

        return httpx.Response(
            status_code=self.response_status,
            headers=headers,
            content=self.response_content,
        )

    async def aclose(self) -> None:
        """Close the transport."""
        pass


class CacheableMockSyncTransport(httpx.BaseTransport):
    """Mock sync transport that returns cacheable responses."""

    def __init__(
        self,
        response_status: int = 200,
        response_content: bytes = b'{"data": "cached"}',
        max_age: int = 3600,
        etag: str | None = None,
        last_modified: str | None = None,
    ) -> None:
        self.response_status = response_status
        self.response_content = response_content
        self.max_age = max_age
        self.etag = etag
        self.last_modified = last_modified
        self.requests: list[httpx.Request] = []

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the sync request and return a cacheable response."""
        self.requests.append(request)

        # Check for conditional request
        if_none_match = request.headers.get("if-none-match")
        if_modified_since = request.headers.get("if-modified-since")

        # Return 304 if conditional headers match
        if self.etag and if_none_match == self.etag:
            return httpx.Response(
                status_code=304,
                headers={"etag": self.etag, "cache-control": f"max-age={self.max_age}"},
                content=b"",
            )

        if self.last_modified and if_modified_since == self.last_modified:
            return httpx.Response(
                status_code=304,
                headers={
                    "last-modified": self.last_modified,
                    "cache-control": f"max-age={self.max_age}",
                },
                content=b"",
            )

        headers = {
            "content-type": "application/json",
            "cache-control": f"max-age={self.max_age}",
        }
        if self.etag:
            headers["etag"] = self.etag
        if self.last_modified:
            headers["last-modified"] = self.last_modified

        return httpx.Response(
            status_code=self.response_status,
            headers=headers,
            content=self.response_content,
        )

    def close(self) -> None:
        """Close the transport."""
        pass


class NonCacheableMockAsyncTransport(httpx.AsyncBaseTransport):
    """Mock async transport that returns non-cacheable responses."""

    def __init__(
        self,
        response_status: int = 200,
        response_content: bytes = b'{"data": "not cached"}',
        cache_control: str = "no-store",
    ) -> None:
        self.response_status = response_status
        self.response_content = response_content
        self.cache_control = cache_control
        self.requests: list[httpx.Request] = []

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle the async request and return a non-cacheable response."""
        self.requests.append(request)
        return httpx.Response(
            status_code=self.response_status,
            headers={
                "content-type": "application/json",
                "cache-control": self.cache_control,
            },
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
def cacheable_async_transport() -> CacheableMockAsyncTransport:
    """Create a cacheable mock async transport for testing."""
    return CacheableMockAsyncTransport()


@pytest.fixture
def cacheable_sync_transport() -> CacheableMockSyncTransport:
    """Create a cacheable mock sync transport for testing."""
    return CacheableMockSyncTransport()


@pytest.fixture
def memory_cache_store() -> MemoryCacheStore:
    """Create a memory cache store for testing."""
    return create_memory_cache_store()


@pytest.fixture
async def cache_response_transport(
    cacheable_async_transport: CacheableMockAsyncTransport,
    memory_cache_store: MemoryCacheStore,
) -> AsyncGenerator[CacheResponseTransport, None]:
    """Create a cache response transport for testing."""
    transport = CacheResponseTransport(
        cacheable_async_transport,
        store=memory_cache_store,
    )
    yield transport
    await transport.aclose()


@pytest.fixture
def sync_cache_response_transport(
    cacheable_sync_transport: CacheableMockSyncTransport,
) -> Generator[SyncCacheResponseTransport, None, None]:
    """Create a sync cache response transport for testing."""
    transport = SyncCacheResponseTransport(cacheable_sync_transport)
    yield transport
    transport.close()
