"""
Tests for rest_adapter.py
Logic testing: Path coverage for delegation pattern
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

from fetch_client.adapters.rest_adapter import AsyncRestAdapter, SyncRestAdapter
from fetch_client.core.base_client import AsyncFetchClient, SyncFetchClient
from fetch_client.types import FetchResponse


class TestAsyncRestAdapter:
    """Tests for AsyncRestAdapter class."""

    @pytest.fixture
    def mock_async_client(self):
        """Create mock AsyncFetchClient."""
        mock = AsyncMock(spec=AsyncFetchClient)
        mock.close = AsyncMock()
        return mock

    @pytest.fixture
    def mock_response(self):
        """Create mock response."""
        return FetchResponse(
            status=200,
            status_text="OK",
            headers={},
            data={"success": True},
            ok=True,
        )

    # Path: constructor wraps client
    def test_constructor(self, mock_async_client):
        adapter = AsyncRestAdapter(mock_async_client)
        assert adapter._client is mock_async_client

    # Path: get delegates to client
    @pytest.mark.asyncio
    async def test_get_delegates(self, mock_async_client, mock_response):
        mock_async_client.get = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        result = await adapter.get("/users")

        mock_async_client.get.assert_called_once_with("/users")
        assert result == mock_response

    # Path: post delegates to client
    @pytest.mark.asyncio
    async def test_post_delegates(self, mock_async_client, mock_response):
        mock_async_client.post = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        result = await adapter.post("/users", json={"name": "test"})

        mock_async_client.post.assert_called_once_with("/users", json={"name": "test"})
        assert result == mock_response

    # Path: put delegates to client
    @pytest.mark.asyncio
    async def test_put_delegates(self, mock_async_client, mock_response):
        mock_async_client.put = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        await adapter.put("/users/1", json={"name": "updated"})

        mock_async_client.put.assert_called_once_with(
            "/users/1", json={"name": "updated"}
        )

    # Path: patch delegates to client
    @pytest.mark.asyncio
    async def test_patch_delegates(self, mock_async_client, mock_response):
        mock_async_client.patch = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        await adapter.patch("/users/1", json={"name": "patched"})

        mock_async_client.patch.assert_called_once_with(
            "/users/1", json={"name": "patched"}
        )

    # Path: delete delegates to client
    @pytest.mark.asyncio
    async def test_delete_delegates(self, mock_async_client, mock_response):
        mock_async_client.delete = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        await adapter.delete("/users/1")

        mock_async_client.delete.assert_called_once_with("/users/1")

    # Path: request delegates to client
    @pytest.mark.asyncio
    async def test_request_delegates(self, mock_async_client, mock_response):
        mock_async_client.request = AsyncMock(return_value=mock_response)
        adapter = AsyncRestAdapter(mock_async_client)

        await adapter.request(method="GET", path="/users")

        mock_async_client.request.assert_called_once_with(method="GET", path="/users")

    # Path: close delegates to client
    @pytest.mark.asyncio
    async def test_close_delegates(self, mock_async_client):
        adapter = AsyncRestAdapter(mock_async_client)

        await adapter.close()

        mock_async_client.close.assert_called_once()


class TestSyncRestAdapter:
    """Tests for SyncRestAdapter class."""

    @pytest.fixture
    def mock_sync_client(self):
        """Create mock SyncFetchClient."""
        mock = MagicMock(spec=SyncFetchClient)
        return mock

    @pytest.fixture
    def mock_response(self):
        """Create mock response."""
        return FetchResponse(
            status=200,
            status_text="OK",
            headers={},
            data={"success": True},
            ok=True,
        )

    # Path: constructor wraps client
    def test_constructor(self, mock_sync_client):
        adapter = SyncRestAdapter(mock_sync_client)
        assert adapter._client is mock_sync_client

    # Path: get delegates to client
    def test_get_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.get = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        result = adapter.get("/users")

        mock_sync_client.get.assert_called_once_with("/users")
        assert result == mock_response

    # Path: post delegates to client
    def test_post_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.post = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        result = adapter.post("/users", json={"name": "test"})

        mock_sync_client.post.assert_called_once_with("/users", json={"name": "test"})
        assert result == mock_response

    # Path: put delegates to client
    def test_put_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.put = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        adapter.put("/users/1", json={"name": "updated"})

        mock_sync_client.put.assert_called_once()

    # Path: patch delegates to client
    def test_patch_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.patch = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        adapter.patch("/users/1", json={"name": "patched"})

        mock_sync_client.patch.assert_called_once()

    # Path: delete delegates to client
    def test_delete_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.delete = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        adapter.delete("/users/1")

        mock_sync_client.delete.assert_called_once_with("/users/1")

    # Path: request delegates to client
    def test_request_delegates(self, mock_sync_client, mock_response):
        mock_sync_client.request = MagicMock(return_value=mock_response)
        adapter = SyncRestAdapter(mock_sync_client)

        adapter.request(method="GET", path="/users")

        mock_sync_client.request.assert_called_once()

    # Path: close delegates to client
    def test_close_delegates(self, mock_sync_client):
        adapter = SyncRestAdapter(mock_sync_client)

        adapter.close()

        mock_sync_client.close.assert_called_once()
