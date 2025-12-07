"""
Shared fixtures for fetch_client tests.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock

import httpx

from fetch_client.config import AuthConfig, ClientConfig, TimeoutConfig
from fetch_client.types import RequestContext


@pytest.fixture
def sample_auth_config():
    """Sample AuthConfig for testing."""
    return AuthConfig(type="bearer", api_key="test-key")


@pytest.fixture
def sample_client_config(sample_auth_config):
    """Sample ClientConfig for testing."""
    return ClientConfig(
        base_url="https://api.example.com",
        auth=sample_auth_config,
    )


@pytest.fixture
def sample_request_context():
    """Sample RequestContext for testing."""
    return RequestContext(
        method="GET",
        path="/users",
        headers={"X-Custom": "value"},
    )


@pytest.fixture
def mock_httpx_async_client():
    """Mock httpx.AsyncClient for testing."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


@pytest.fixture
def mock_httpx_sync_client():
    """Mock httpx.Client for testing."""
    client = MagicMock(spec=httpx.Client)
    client.close = MagicMock()
    return client


@pytest.fixture
def mock_response():
    """Mock httpx.Response for testing."""
    response = MagicMock()
    response.status_code = 200
    response.reason_phrase = "OK"
    response.headers = {"content-type": "application/json"}
    response.text = '{"success": true}'
    return response


@pytest.fixture
def mock_async_response():
    """Mock async httpx.Response for testing."""
    response = AsyncMock()
    response.status_code = 200
    response.reason_phrase = "OK"
    response.headers = {"content-type": "application/json"}
    response.text = '{"success": true}'
    return response
