"""
REST adapter for fetch_client.

Provides REST-style HTTP methods on top of the base client.
"""
from typing import Any, AsyncGenerator, Dict, Generator, Optional, Union

from ..types import FetchResponse, HttpMethod, SSEEvent
from ..core.base_client import AsyncFetchClient, SyncFetchClient


class AsyncRestAdapter:
    """Async REST adapter wrapping a fetch client."""

    def __init__(self, client: AsyncFetchClient):
        self._client = client

    async def get(self, path: str, **kwargs: Any) -> FetchResponse:
        """GET request."""
        return await self._client.get(path, **kwargs)

    async def post(self, path: str, **kwargs: Any) -> FetchResponse:
        """POST request."""
        return await self._client.post(path, **kwargs)

    async def put(self, path: str, **kwargs: Any) -> FetchResponse:
        """PUT request."""
        return await self._client.put(path, **kwargs)

    async def patch(self, path: str, **kwargs: Any) -> FetchResponse:
        """PATCH request."""
        return await self._client.patch(path, **kwargs)

    async def delete(self, path: str, **kwargs: Any) -> FetchResponse:
        """DELETE request."""
        return await self._client.delete(path, **kwargs)

    async def request(self, **kwargs: Any) -> FetchResponse:
        """Generic request."""
        return await self._client.request(**kwargs)

    async def stream(
        self, path: str, **kwargs: Any
    ) -> AsyncGenerator[SSEEvent, None]:
        """Stream SSE response."""
        async for event in self._client.stream(path, **kwargs):
            yield event

    async def stream_ndjson(
        self, path: str, **kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        """Stream NDJSON response."""
        async for item in self._client.stream_ndjson(path, **kwargs):
            yield item

    async def close(self) -> None:
        """Close the client."""
        await self._client.close()


class SyncRestAdapter:
    """Sync REST adapter wrapping a fetch client."""

    def __init__(self, client: SyncFetchClient):
        self._client = client

    def get(self, path: str, **kwargs: Any) -> FetchResponse:
        """GET request."""
        return self._client.get(path, **kwargs)

    def post(self, path: str, **kwargs: Any) -> FetchResponse:
        """POST request."""
        return self._client.post(path, **kwargs)

    def put(self, path: str, **kwargs: Any) -> FetchResponse:
        """PUT request."""
        return self._client.put(path, **kwargs)

    def patch(self, path: str, **kwargs: Any) -> FetchResponse:
        """PATCH request."""
        return self._client.patch(path, **kwargs)

    def delete(self, path: str, **kwargs: Any) -> FetchResponse:
        """DELETE request."""
        return self._client.delete(path, **kwargs)

    def request(self, **kwargs: Any) -> FetchResponse:
        """Generic request."""
        return self._client.request(**kwargs)

    def stream(
        self, path: str, **kwargs: Any
    ) -> Generator[SSEEvent, None, None]:
        """Stream SSE response."""
        yield from self._client.stream(path, **kwargs)

    def stream_ndjson(
        self, path: str, **kwargs: Any
    ) -> Generator[Any, None, None]:
        """Stream NDJSON response."""
        yield from self._client.stream_ndjson(path, **kwargs)

    def close(self) -> None:
        """Close the client."""
        self._client.close()
