"""
FastAPI integration for fetch_client.

Provides lifespan management, dependency injection, and service patterns.
"""
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncGenerator, Callable, Optional, Union
from urllib.parse import urlparse
import logging

from ..config import ClientConfig, AuthConfig, TimeoutConfig, DefaultSerializer
from ..core.base_client import AsyncFetchClient
from ..dns_warmup import warmup_dns

logger = logging.getLogger(__name__)


@dataclass
class FetchClientService:
    """
    Service class for managing fetch clients in FastAPI applications.

    Provides application-scoped singleton clients via lifespan management.

    Example:
        service = FetchClientService()
        await service.register("gemini", ClientConfig(...))
        client = service.get("gemini")
    """

    clients: dict[str, AsyncFetchClient] = field(default_factory=dict)

    async def register(
        self,
        name: str,
        config: ClientConfig,
        warmup: bool = True,
    ) -> AsyncFetchClient:
        """
        Register a named client (application-scoped singleton).

        Args:
            name: Unique name for the client.
            config: Client configuration.
            warmup: Whether to perform DNS warmup on registration.

        Returns:
            The registered AsyncFetchClient.
        """
        if warmup and config.base_url:
            hostname = urlparse(config.base_url).hostname
            if hostname:
                try:
                    await warmup_dns(hostname)
                    logger.info(f"DNS warmup complete for {name} ({hostname})")
                except Exception as e:
                    logger.warning(f"DNS warmup failed for {name} ({hostname}): {e}")

        client = AsyncFetchClient(config)
        self.clients[name] = client
        logger.info(f"Registered fetch client: {name}")
        return client

    async def register_from_params(
        self,
        name: str,
        base_url: str,
        httpx_client: Optional[Any] = None,
        auth: Optional[AuthConfig] = None,
        timeout: Optional[Union[float, TimeoutConfig]] = None,
        default_headers: Optional[dict[str, str]] = None,
        content_type: str = "application/json",
        serializer: Optional[Any] = None,
        warmup: bool = True,
    ) -> AsyncFetchClient:
        """
        Register a named client from individual parameters.

        Args:
            name: Unique name for the client.
            base_url: Base URL for all requests.
            httpx_client: Pre-configured httpx.AsyncClient.
            auth: Authentication configuration.
            timeout: Request timeout.
            default_headers: Default headers for all requests.
            content_type: Default content type.
            serializer: Custom JSON serializer/deserializer.
            warmup: Whether to perform DNS warmup.

        Returns:
            The registered AsyncFetchClient.
        """
        config = ClientConfig(
            base_url=base_url,
            httpx_client=httpx_client,
            auth=auth,
            timeout=timeout,
            headers=default_headers or {},
            content_type=content_type,
        )
        return await self.register(name, config, warmup)

    def get(self, name: str) -> AsyncFetchClient:
        """
        Get a registered client by name.

        Args:
            name: Name of the registered client.

        Returns:
            The AsyncFetchClient instance.

        Raises:
            KeyError: If client is not registered.
        """
        client = self.clients.get(name)
        if not client:
            raise KeyError(f"Client '{name}' not registered")
        return client

    def has(self, name: str) -> bool:
        """
        Check if a client is registered.

        Args:
            name: Name to check.

        Returns:
            True if client exists.
        """
        return name in self.clients

    async def close(self, name: str) -> None:
        """
        Close and remove a specific client.

        Args:
            name: Name of the client to close.
        """
        client = self.clients.pop(name, None)
        if client:
            await client.close()
            logger.info(f"Closed fetch client: {name}")

    async def close_all(self) -> None:
        """Close all registered clients (called on shutdown)."""
        for name in list(self.clients.keys()):
            await self.close(name)
        logger.info("All fetch clients closed")


def create_lifespan(
    setup: Optional[Callable[[FetchClientService], Any]] = None,
) -> Callable[..., AsyncGenerator[None, None]]:
    """
    Factory to create FastAPI lifespan context manager.

    Args:
        setup: Async function to register clients during startup.
               Receives FetchClientService instance.

    Returns:
        Lifespan context manager for FastAPI app.

    Example:
        from fastapi import FastAPI
        from fetch_client.integrations.fastapi import create_lifespan, FetchClientService

        async def setup_clients(service: FetchClientService):
            await service.register("gemini", ClientConfig(
                base_url="https://generativelanguage.googleapis.com",
                auth=AuthConfig(type="x-api-key", api_key=os.environ.get("GEMINI_API_KEY")),
            ))
            await service.register("openai", ClientConfig(
                base_url="https://api.openai.com",
                auth=AuthConfig(type="bearer", api_key=os.environ.get("OPENAI_API_KEY")),
            ))

        app = FastAPI(lifespan=create_lifespan(setup_clients))

        @app.get("/chat")
        async def chat(request: Request):
            client = request.app.state.fetch_clients.get("gemini")
            return await client.get("/v1/models")
    """

    @asynccontextmanager
    async def lifespan(app: Any) -> AsyncGenerator[None, None]:
        # Startup: create service and register clients
        service = FetchClientService()

        if setup:
            await setup(service)

        # Store service on app.state (application-scoped)
        app.state.fetch_clients = service

        yield  # App is running

        # Shutdown: close all clients
        await service.close_all()

    return lifespan


def get_client(name: str) -> Callable[..., AsyncFetchClient]:
    """
    FastAPI dependency to get a named client.

    Args:
        name: Name of the registered client.

    Returns:
        Dependency function that returns AsyncFetchClient.

    Example:
        from fastapi import FastAPI, Depends
        from fetch_client import AsyncFetchClient
        from fetch_client.integrations.fastapi import get_client

        @app.get("/users")
        async def get_users(client: AsyncFetchClient = Depends(get_client("api"))):
            response = await client.get("/users")
            return response.json
    """

    def _get_client(request: Any) -> AsyncFetchClient:
        service: FetchClientService = request.app.state.fetch_clients
        return service.get(name)

    return _get_client


# Convenience dependency factories for common services
def gemini_client() -> Callable[..., AsyncFetchClient]:
    """Dependency for Gemini client."""
    return get_client("gemini")


def openai_client() -> Callable[..., AsyncFetchClient]:
    """Dependency for OpenAI client."""
    return get_client("openai")


def anthropic_client() -> Callable[..., AsyncFetchClient]:
    """Dependency for Anthropic client."""
    return get_client("anthropic")
