"""
Tests for base_client.py (both async and sync clients)
Logic testing: Decision/Branch, State Transition, Path coverage
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

import httpx

from fetch_client.core.base_client import AsyncFetchClient, SyncFetchClient
from fetch_client.config import ClientConfig, AuthConfig


class TestAsyncFetchClient:
    """Tests for AsyncFetchClient class."""

    @pytest.fixture
    def client_config(self):
        return ClientConfig(base_url="https://api.example.com")

    @pytest.fixture
    def mock_async_client(self):
        """Create mock httpx.AsyncClient."""
        mock = AsyncMock(spec=httpx.AsyncClient)
        mock.aclose = AsyncMock()
        return mock

    # Path: constructor config resolution
    def test_init_config_resolution(self, client_config):
        client = AsyncFetchClient(client_config)
        assert client._config.base_url == "https://api.example.com"
        assert client._closed is False

    # Error Path: invalid config
    def test_init_invalid_config(self):
        with pytest.raises(ValueError, match="base_url is required"):
            AsyncFetchClient(ClientConfig(base_url=""))

    # Happy Path: GET request success
    @pytest.mark.asyncio
    async def test_request_get_success(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"name": "test"}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        result = await client.request(method="GET", path="/users")

        assert result["status"] == 200
        assert result["ok"] is True
        assert result["data"] == {"name": "test"}

    # Path: POST with json body
    @pytest.mark.asyncio
    async def test_request_post_json(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.reason_phrase = "Created"
        mock_response.headers = {}
        mock_response.text = '{"id": 1}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        result = await client.request(method="POST", path="/users", json={"name": "test"})

        assert result["status"] == 201
        mock_async_client.request.assert_called_once()

    # State: request on closed client
    @pytest.mark.asyncio
    async def test_request_closed_client(self, client_config, mock_async_client):
        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.close()

        with pytest.raises(RuntimeError, match="Client has been closed"):
            await client.request(method="GET", path="/users")

    # Decision: 404 response
    @pytest.mark.asyncio
    async def test_request_404(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.headers = {}
        mock_response.text = '{"error": "Not found"}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        result = await client.request(method="GET", path="/users/999")

        assert result["status"] == 404
        assert result["ok"] is False

    # Decision: 500 response
    @pytest.mark.asyncio
    async def test_request_500(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.reason_phrase = "Server Error"
        mock_response.headers = {}
        mock_response.text = '{"error": "Server error"}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        result = await client.request(method="GET", path="/users")

        assert result["status"] == 500
        assert result["ok"] is False

    # Error Path: JSON parse failure falls back to text
    @pytest.mark.asyncio
    async def test_request_json_parse_failure(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}
        mock_response.text = "plain text response"
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        result = await client.request(method="GET", path="/text")

        assert result["data"] == "plain text response"

    # Path: get method delegation
    @pytest.mark.asyncio
    async def test_get_delegation(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.get("/users")

        mock_async_client.request.assert_called_once()
        call_kwargs = mock_async_client.request.call_args
        assert call_kwargs.kwargs["method"] == "GET"

    # Path: post method delegation
    @pytest.mark.asyncio
    async def test_post_delegation(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.reason_phrase = "Created"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.post("/users", json={"name": "test"})

        call_kwargs = mock_async_client.request.call_args
        assert call_kwargs.kwargs["method"] == "POST"

    # Path: put method delegation
    @pytest.mark.asyncio
    async def test_put_delegation(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.put("/users/1", json={"name": "updated"})

        call_kwargs = mock_async_client.request.call_args
        assert call_kwargs.kwargs["method"] == "PUT"

    # Path: patch method delegation
    @pytest.mark.asyncio
    async def test_patch_delegation(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.patch("/users/1", json={"name": "patched"})

        call_kwargs = mock_async_client.request.call_args
        assert call_kwargs.kwargs["method"] == "PATCH"

    # Path: delete method delegation
    @pytest.mark.asyncio
    async def test_delete_delegation(self, client_config, mock_async_client):
        mock_response = MagicMock()
        mock_response.status_code = 204
        mock_response.reason_phrase = "No Content"
        mock_response.headers = {}
        mock_response.text = ''
        mock_async_client.request = AsyncMock(return_value=mock_response)

        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)
        await client.delete("/users/1")

        call_kwargs = mock_async_client.request.call_args
        assert call_kwargs.kwargs["method"] == "DELETE"

    # State: close sets flag
    @pytest.mark.asyncio
    async def test_close_sets_flag(self, client_config, mock_async_client):
        client = AsyncFetchClient(client_config, httpx_client=mock_async_client)

        await client.close()

        assert client._closed is True
        mock_async_client.aclose.assert_called_once()


class TestSyncFetchClient:
    """Tests for SyncFetchClient class."""

    @pytest.fixture
    def client_config(self):
        return ClientConfig(base_url="https://api.example.com")

    @pytest.fixture
    def mock_sync_client(self):
        """Create mock httpx.Client."""
        mock = MagicMock(spec=httpx.Client)
        mock.close = MagicMock()
        return mock

    # Path: constructor config resolution
    def test_init_config_resolution(self, client_config):
        client = SyncFetchClient(client_config)
        assert client._config.base_url == "https://api.example.com"
        assert client._closed is False

    # Happy Path: GET request success
    def test_request_get_success(self, client_config, mock_sync_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.text = '{"name": "test"}'
        mock_sync_client.request = MagicMock(return_value=mock_response)

        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)
        result = client.request(method="GET", path="/users")

        assert result["status"] == 200
        assert result["ok"] is True
        assert result["data"] == {"name": "test"}

    # State: request on closed client
    def test_request_closed_client(self, client_config, mock_sync_client):
        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)
        client.close()

        with pytest.raises(RuntimeError, match="Client has been closed"):
            client.request(method="GET", path="/users")

    # Decision: 404 response
    def test_request_404(self, client_config, mock_sync_client):
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_response.reason_phrase = "Not Found"
        mock_response.headers = {}
        mock_response.text = '{"error": "Not found"}'
        mock_sync_client.request = MagicMock(return_value=mock_response)

        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)
        result = client.request(method="GET", path="/users/999")

        assert result["status"] == 404
        assert result["ok"] is False

    # Path: get method delegation
    def test_get_delegation(self, client_config, mock_sync_client):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.reason_phrase = "OK"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_sync_client.request = MagicMock(return_value=mock_response)

        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)
        client.get("/users")

        mock_sync_client.request.assert_called_once()
        call_kwargs = mock_sync_client.request.call_args
        assert call_kwargs.kwargs["method"] == "GET"

    # Path: post method delegation
    def test_post_delegation(self, client_config, mock_sync_client):
        mock_response = MagicMock()
        mock_response.status_code = 201
        mock_response.reason_phrase = "Created"
        mock_response.headers = {}
        mock_response.text = '{}'
        mock_sync_client.request = MagicMock(return_value=mock_response)

        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)
        client.post("/users", json={"name": "test"})

        call_kwargs = mock_sync_client.request.call_args
        assert call_kwargs.kwargs["method"] == "POST"

    # State: close sets flag
    def test_close_sets_flag(self, client_config, mock_sync_client):
        client = SyncFetchClient(client_config, httpx_client=mock_sync_client)

        client.close()

        assert client._closed is True
        mock_sync_client.close.assert_called_once()
