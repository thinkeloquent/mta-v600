"""
Tests for FastAPI integration (integrations/fastapi.py)
Logic testing: Decision/Branch, State, Path coverage
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from fetch_client.integrations.fastapi import (
    FetchClientService,
    create_lifespan,
    get_client,
)
from fetch_client.config import ClientConfig, AuthConfig
from fetch_client.core.base_client import AsyncFetchClient


class TestFetchClientService:
    """Tests for FetchClientService class."""

    @pytest.fixture
    def service(self):
        return FetchClientService()

    @pytest.fixture
    def sample_config(self):
        return ClientConfig(base_url="https://api.example.com")

    # Happy Path: register client
    @pytest.mark.asyncio
    async def test_register_client(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            client = await service.register("api", sample_config)

        assert isinstance(client, AsyncFetchClient)
        assert "api" in service.clients

    # Decision: register with warmup
    @pytest.mark.asyncio
    async def test_register_with_warmup(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]) as mock_dns:
            await service.register("api", sample_config, warmup=True)

        mock_dns.assert_called()

    # Decision: register without warmup
    @pytest.mark.asyncio
    async def test_register_without_warmup(self, service, sample_config):
        with patch("socket.getaddrinfo") as mock_dns:
            await service.register("api", sample_config, warmup=False)

        mock_dns.assert_not_called()

    # Error Path: warmup failure logs warning
    @pytest.mark.asyncio
    async def test_register_warmup_failure(self, service, sample_config):
        with patch("socket.getaddrinfo", side_effect=Exception("DNS error")):
            # Should not raise, just log warning
            client = await service.register("api", sample_config, warmup=True)

        assert client is not None

    # Path: get existing client
    @pytest.mark.asyncio
    async def test_get_existing(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            await service.register("api", sample_config)

        client = service.get("api")
        assert isinstance(client, AsyncFetchClient)

    # Error Path: get missing client
    def test_get_missing(self, service):
        with pytest.raises(KeyError, match="Client 'missing' not registered"):
            service.get("missing")

    # Path: has returns True for existing
    @pytest.mark.asyncio
    async def test_has_true(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            await service.register("api", sample_config)

        assert service.has("api") is True

    # Path: has returns False for missing
    def test_has_false(self, service):
        assert service.has("missing") is False

    # State: close removes and closes client
    @pytest.mark.asyncio
    async def test_close(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            client = await service.register("api", sample_config)

        # Mock the close method
        client._closed = False

        await service.close("api")

        assert "api" not in service.clients

    # State: close_all closes all clients
    @pytest.mark.asyncio
    async def test_close_all(self, service, sample_config):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            await service.register("api1", sample_config)
            await service.register("api2", sample_config)

        await service.close_all()

        assert len(service.clients) == 0

    # Path: register_from_params
    @pytest.mark.asyncio
    async def test_register_from_params(self, service):
        with patch("socket.getaddrinfo", return_value=[(2, 1, 6, "", ("1.1.1.1", 443))]):
            client = await service.register_from_params(
                name="api",
                base_url="https://api.example.com",
                auth=AuthConfig(type="bearer", api_key="key"),
                warmup=False,
            )

        assert isinstance(client, AsyncFetchClient)


class TestCreateLifespan:
    """Tests for create_lifespan function."""

    @pytest.fixture
    def mock_app(self):
        """Create mock FastAPI app."""
        app = MagicMock()
        app.state = MagicMock()
        return app

    # Path: lifespan creates service
    @pytest.mark.asyncio
    async def test_lifespan_creates_service(self, mock_app):
        lifespan = create_lifespan()

        async with lifespan(mock_app):
            assert hasattr(mock_app.state, "fetch_clients")
            assert isinstance(mock_app.state.fetch_clients, FetchClientService)

    # Path: setup function invoked
    @pytest.mark.asyncio
    async def test_lifespan_setup_called(self, mock_app):
        setup_called = []

        async def setup(service):
            setup_called.append(True)

        lifespan = create_lifespan(setup)

        async with lifespan(mock_app):
            pass

        assert len(setup_called) == 1

    # State: clients closed on shutdown
    @pytest.mark.asyncio
    async def test_lifespan_shutdown(self, mock_app):
        close_called = []

        async def setup(service):
            # Register mock client
            mock_client = AsyncMock()
            mock_client.close = AsyncMock(side_effect=lambda: close_called.append(True))
            service.clients["test"] = mock_client

        lifespan = create_lifespan(setup)

        async with lifespan(mock_app):
            pass  # Shutdown happens on exit

        assert len(close_called) == 1


class TestGetClient:
    """Tests for get_client dependency function."""

    @pytest.fixture
    def mock_request(self):
        """Create mock request with app state."""
        request = MagicMock()
        request.app = MagicMock()
        request.app.state = MagicMock()
        request.app.state.fetch_clients = FetchClientService()
        return request

    # Path: returns client from service
    @pytest.mark.asyncio
    async def test_get_client_dependency(self, mock_request):
        # Register a client
        mock_client = AsyncMock(spec=AsyncFetchClient)
        mock_request.app.state.fetch_clients.clients["api"] = mock_client

        dependency = get_client("api")
        result = dependency(mock_request)

        assert result is mock_client

    # Error Path: raises KeyError for missing client
    def test_get_client_missing(self, mock_request):
        dependency = get_client("missing")

        with pytest.raises(KeyError):
            dependency(mock_request)
