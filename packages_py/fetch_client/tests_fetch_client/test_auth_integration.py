"""
Integration tests for Authentication Flow
Verifies the path: Application Layer (Client) -> Config -> Auth Strategy -> Encoding -> Request Call
"""
import pytest
import respx
from httpx import Response
from fetch_client.core.base_client import AsyncFetchClient
from fetch_client.config import ClientConfig, AuthConfig
from fetch_auth_encoding import encode_auth

import httpx
@pytest.mark.asyncio
async def test_auth_flow_integration_basic():
    """
    Verifies that a client configured with Basic auth correctly encodes credentials
    and sends them in the Authorization header.
    """
    # 1. Setup Configuration (Application Layer)
    username = "testuser"
    password = "testpassword"
    config = ClientConfig(
        base_url="https://api.example.com",
        auth=AuthConfig(
            type="basic",
            username=username,
            password=password
        )
    )

    # 2. Setup Network Mock via Router (Avoid auto-patching issues)
    router = respx.MockRouter()
    route = router.get("https://api.example.com/resource").mock(return_value=Response(200, json={"status": "ok"}))
    
    # Create explicit Transport and Client
    transport = httpx.MockTransport(router.async_handler)
    mock_httpx_client = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")

    # 3. Initialize Client with injected mock
    async with AsyncFetchClient(config, httpx_client=mock_httpx_client) as client:
        # 4. Execute Request
        response = await client.get("/resource")
        
        # Verify response
        assert response["status"] == 200
        assert response["data"] == {"status": "ok"}

    # 5. Verify Request Header (The Core Assertion)
    assert route.called
    last_request = route.calls.last.request

    # Calculate expected header using the encoding package directly
    expected_header = encode_auth(
        auth_type="basic",
        username=username,
        password=password
    )
    
    assert "Authorization" in last_request.headers
    assert last_request.headers["Authorization"] == expected_header["Authorization"]

@pytest.mark.asyncio
async def test_auth_flow_integration_bearer():
    """
    Verifies that a client configured with Bearer auth correctly sends the token.
    """
    token = "my-secret-token"
    config = ClientConfig(
        base_url="https://api.example.com",
        auth=AuthConfig(
            type="bearer",
            raw_api_key=token
        )
    )

    router = respx.MockRouter()
    route = router.get("https://api.example.com/resource").mock(return_value=Response(200))
    
    transport = httpx.MockTransport(router.async_handler)
    mock_httpx_client = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")

    async with AsyncFetchClient(config, httpx_client=mock_httpx_client) as client:
        await client.get("/resource")

    last_request = route.calls.last.request
    
    # Expected: "Bearer my-secret-token"
    assert "Authorization" in last_request.headers
    assert last_request.headers["Authorization"] == f"Bearer {token}"

@pytest.mark.asyncio
async def test_auth_flow_integration_custom():
    """
    Verifies that a client configured with Custom auth correctly sends a custom header.
    """
    api_key = "custom-key-value"
    header_name = "X-Custom-Auth"
    config = ClientConfig(
        base_url="https://api.example.com",
        auth=AuthConfig(
            type="custom",
            header_name=header_name,
            raw_api_key=api_key
        )
    )

    router = respx.MockRouter()
    route = router.get("https://api.example.com/resource").mock(return_value=Response(200))

    transport = httpx.MockTransport(router.async_handler)
    mock_httpx_client = httpx.AsyncClient(transport=transport, base_url="https://api.example.com")

    async with AsyncFetchClient(config, httpx_client=mock_httpx_client) as client:
        await client.get("/resource")
    
    last_request = route.calls.last.request
    
    assert header_name in last_request.headers
    assert last_request.headers[header_name] == api_key
