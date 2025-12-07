"""
Tests for factory.py
Logic testing: Decision/Branch, Path coverage
"""
import pytest
from unittest.mock import MagicMock, AsyncMock

import httpx

from fetch_client.factory import (
    create_client,
    create_async_client,
    create_sync_client,
    create_rest_adapter,
)
from fetch_client.core.base_client import AsyncFetchClient, SyncFetchClient
from fetch_client.adapters.rest_adapter import AsyncRestAdapter, SyncRestAdapter
from fetch_client.config import AuthConfig, TimeoutConfig


class TestCreateClient:
    """Tests for create_client function."""

    # Decision: default (no httpx_client) creates async client
    def test_create_client_default(self):
        client = create_client(base_url="https://api.example.com")

        assert isinstance(client, AsyncFetchClient)

    # Decision: with AsyncClient creates async client
    def test_create_client_async(self):
        httpx_client = AsyncMock(spec=httpx.AsyncClient)
        client = create_client(
            base_url="https://api.example.com", httpx_client=httpx_client
        )

        assert isinstance(client, AsyncFetchClient)

    # Decision: with Client creates sync client
    def test_create_client_sync(self):
        httpx_client = MagicMock(spec=httpx.Client)
        client = create_client(
            base_url="https://api.example.com", httpx_client=httpx_client
        )

        assert isinstance(client, SyncFetchClient)

    # Path: with auth config
    def test_create_client_with_auth(self):
        auth = AuthConfig(type="bearer", api_key="test-key")
        client = create_client(base_url="https://api.example.com", auth=auth)

        assert isinstance(client, AsyncFetchClient)

    # Path: with timeout
    def test_create_client_with_timeout(self):
        client = create_client(base_url="https://api.example.com", timeout=60.0)

        assert isinstance(client, AsyncFetchClient)

    # Path: with TimeoutConfig
    def test_create_client_with_timeout_config(self):
        timeout = TimeoutConfig(connect=5.0, read=30.0, write=10.0)
        client = create_client(base_url="https://api.example.com", timeout=timeout)

        assert isinstance(client, AsyncFetchClient)

    # Path: with headers
    def test_create_client_with_headers(self):
        client = create_client(
            base_url="https://api.example.com",
            default_headers={"User-Agent": "TestClient/1.0"},
        )

        assert isinstance(client, AsyncFetchClient)

    # Error Path: invalid base_url
    def test_create_client_invalid_url(self):
        with pytest.raises(ValueError, match="base_url is required"):
            create_client(base_url="")


class TestCreateAsyncClient:
    """Tests for create_async_client function."""

    # Path: always creates AsyncFetchClient
    def test_create_async_client(self):
        client = create_async_client(base_url="https://api.example.com")

        assert isinstance(client, AsyncFetchClient)

    # Path: with httpx AsyncClient
    def test_create_async_client_with_httpx(self):
        httpx_client = AsyncMock(spec=httpx.AsyncClient)
        client = create_async_client(
            base_url="https://api.example.com", httpx_client=httpx_client
        )

        assert isinstance(client, AsyncFetchClient)

    # Path: with all options
    def test_create_async_client_all_options(self):
        client = create_async_client(
            base_url="https://api.example.com",
            auth=AuthConfig(type="bearer", api_key="key"),
            timeout=30.0,
            default_headers={"Accept": "application/json"},
            content_type="application/json",
        )

        assert isinstance(client, AsyncFetchClient)


class TestCreateSyncClient:
    """Tests for create_sync_client function."""

    # Path: always creates SyncFetchClient
    def test_create_sync_client(self):
        client = create_sync_client(base_url="https://api.example.com")

        assert isinstance(client, SyncFetchClient)

    # Path: with httpx Client
    def test_create_sync_client_with_httpx(self):
        httpx_client = MagicMock(spec=httpx.Client)
        client = create_sync_client(
            base_url="https://api.example.com", httpx_client=httpx_client
        )

        assert isinstance(client, SyncFetchClient)

    # Path: with all options
    def test_create_sync_client_all_options(self):
        client = create_sync_client(
            base_url="https://api.example.com",
            auth=AuthConfig(type="x-api-key", api_key="key"),
            timeout=TimeoutConfig(connect=5.0, read=60.0, write=10.0),
            default_headers={"User-Agent": "SyncClient"},
        )

        assert isinstance(client, SyncFetchClient)


class TestCreateRestAdapter:
    """Tests for create_rest_adapter function."""

    # Decision: AsyncFetchClient -> AsyncRestAdapter
    def test_create_rest_adapter_async(self):
        client = create_async_client(base_url="https://api.example.com")
        adapter = create_rest_adapter(client)

        assert isinstance(adapter, AsyncRestAdapter)

    # Decision: SyncFetchClient -> SyncRestAdapter
    def test_create_rest_adapter_sync(self):
        client = create_sync_client(base_url="https://api.example.com")
        adapter = create_rest_adapter(client)

        assert isinstance(adapter, SyncRestAdapter)
