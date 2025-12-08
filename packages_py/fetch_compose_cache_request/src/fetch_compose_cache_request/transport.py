"""
Cache request transport wrapper for httpx.
"""
import asyncio
import time
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Optional

import httpx

from cache_request import (
    IdempotencyManager,
    Singleflight,
    IdempotencyConfig,
    SingleflightConfig,
    CacheRequestStore,
    SingleflightStore,
    RequestFingerprint,
    create_memory_cache_store,
    create_memory_singleflight_store,
)


@dataclass
class CachedResponseData:
    """Data structure for cached responses."""

    status_code: int
    headers: httpx.Headers
    content: bytes
    http_version: str = "HTTP/1.1"


class CacheRequestTransport(httpx.AsyncBaseTransport):
    """
    Cache request transport wrapper for httpx.

    Wraps another transport and provides idempotency key management
    and request coalescing (singleflight) capabilities.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = CacheRequestTransport(base)
        client = httpx.AsyncClient(transport=transport)
    """

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        enable_idempotency: bool = True,
        enable_singleflight: bool = True,
        idempotency_config: Optional[IdempotencyConfig] = None,
        singleflight_config: Optional[SingleflightConfig] = None,
        idempotency_store: Optional[CacheRequestStore] = None,
        singleflight_store: Optional[SingleflightStore] = None,
        on_idempotency_key_generated: Optional[Callable[[str, str, str], None]] = None,
        on_request_coalesced: Optional[Callable[[str, int], None]] = None,
    ) -> None:
        """
        Create a new CacheRequestTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            enable_idempotency: Enable idempotency key management. Default: True
            enable_singleflight: Enable request coalescing. Default: True
            idempotency_config: Idempotency configuration
            singleflight_config: Singleflight configuration
            idempotency_store: Custom store for idempotency
            singleflight_store: Custom store for singleflight
            on_idempotency_key_generated: Callback when idempotency key is generated
            on_request_coalesced: Callback when request is coalesced
        """
        self._inner = inner
        self._enable_idempotency = enable_idempotency
        self._enable_singleflight = enable_singleflight
        self._on_idempotency_key_generated = on_idempotency_key_generated
        self._on_request_coalesced = on_request_coalesced

        # Create managers
        self._idempotency_manager: Optional[IdempotencyManager] = None
        if enable_idempotency:
            self._idempotency_manager = IdempotencyManager(
                idempotency_config, idempotency_store or create_memory_cache_store()
            )

        self._singleflight: Optional[Singleflight] = None
        if enable_singleflight:
            self._singleflight = Singleflight(
                singleflight_config, singleflight_store or create_memory_singleflight_store()
            )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with cache request capabilities."""
        method = request.method
        url = str(request.url)

        # Build request fingerprint
        fingerprint = RequestFingerprint(
            method=method,
            url=url,
            headers=dict(request.headers),
            body=request.content if request.content else None,
        )

        # Handle idempotency for mutating methods
        if self._idempotency_manager and self._idempotency_manager.requires_idempotency(method):
            return await self._handle_idempotent_request(request, fingerprint)

        # Handle singleflight for safe methods
        if self._singleflight and self._singleflight.supports_coalescing(method):
            return await self._handle_singleflight_request(request, fingerprint)

        # Pass through for other methods
        return await self._inner.handle_async_request(request)

    async def _handle_idempotent_request(
        self, request: httpx.Request, fingerprint: RequestFingerprint
    ) -> httpx.Response:
        """Handle idempotent request with key management."""
        manager = self._idempotency_manager
        header_name = manager.get_header_name()

        # Check if idempotency key already exists in headers
        existing_key = request.headers.get(header_name)

        # Generate or use existing key
        idempotency_key = existing_key or manager.generate_key()

        if not existing_key and self._on_idempotency_key_generated:
            self._on_idempotency_key_generated(
                idempotency_key, request.method, str(request.url)
            )

        # Check for cached response
        result = await manager.check(idempotency_key, fingerprint)

        if result.cached and result.response:
            cached = result.response.value
            return httpx.Response(
                status_code=cached.status_code,
                headers=cached.headers,
                content=cached.content,
            )

        # Add idempotency key to headers if not present
        if not existing_key:
            request.headers[header_name] = idempotency_key

        # Execute request
        response = await self._inner.handle_async_request(request)

        # Cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            # Read response content to cache it
            content = await response.aread()
            cached_data = CachedResponseData(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )
            await manager.store(idempotency_key, cached_data, fingerprint)

            # Create new response with the content we read
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )

        return response

    async def _handle_singleflight_request(
        self, request: httpx.Request, fingerprint: RequestFingerprint
    ) -> httpx.Response:
        """Handle singleflight request with coalescing."""
        sf = self._singleflight

        async def execute() -> CachedResponseData:
            response = await self._inner.handle_async_request(request)
            content = await response.aread()
            return CachedResponseData(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )

        result = await sf.do(fingerprint, execute)

        if self._on_request_coalesced and result.shared:
            self._on_request_coalesced(
                sf.generate_fingerprint(fingerprint), result.subscribers
            )

        return httpx.Response(
            status_code=result.value.status_code,
            headers=result.value.headers,
            content=result.value.content,
        )

    async def aclose(self) -> None:
        """Close the transport."""
        if self._idempotency_manager:
            await self._idempotency_manager.close()
        if self._singleflight:
            self._singleflight.close()
        await self._inner.aclose()


class SyncCacheRequestTransport(httpx.BaseTransport):
    """
    Synchronous cache request transport wrapper for httpx.

    Note: Singleflight is not available in sync mode due to concurrency requirements.
    Only idempotency key management is supported.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        enable_idempotency: bool = True,
        idempotency_config: Optional[IdempotencyConfig] = None,
        on_idempotency_key_generated: Optional[Callable[[str, str, str], None]] = None,
    ) -> None:
        """
        Create a new SyncCacheRequestTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            enable_idempotency: Enable idempotency key management. Default: True
            idempotency_config: Idempotency configuration
            on_idempotency_key_generated: Callback when idempotency key is generated
        """
        self._inner = inner
        self._enable_idempotency = enable_idempotency
        self._on_idempotency_key_generated = on_idempotency_key_generated

        # For sync mode, we need to use a simple dict-based cache
        # as the async store requires an event loop
        self._idempotency_config = idempotency_config or IdempotencyConfig()
        self._cache: dict[str, tuple[CachedResponseData, float, str]] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with idempotency capabilities."""
        method = request.method

        # Only handle idempotency for mutating methods
        methods = self._idempotency_config.methods or ["POST", "PATCH"]
        if not self._enable_idempotency or method.upper() not in methods:
            return self._inner.handle_request(request)

        return self._handle_idempotent_request(request)

    def _handle_idempotent_request(self, request: httpx.Request) -> httpx.Response:
        """Handle idempotent request with key management."""
        header_name = self._idempotency_config.header_name or "Idempotency-Key"
        ttl = self._idempotency_config.ttl_seconds or 86400

        # Check if idempotency key already exists in headers
        existing_key = request.headers.get(header_name)

        # Generate or use existing key
        import uuid

        idempotency_key = existing_key or str(uuid.uuid4())

        if not existing_key and self._on_idempotency_key_generated:
            self._on_idempotency_key_generated(
                idempotency_key, request.method, str(request.url)
            )

        # Build fingerprint
        fingerprint = f"{request.method}|{request.url}"
        if request.content:
            fingerprint += f"|{request.content.decode('utf-8', errors='replace')}"

        # Check for cached response
        if idempotency_key in self._cache:
            cached, expires_at, cached_fingerprint = self._cache[idempotency_key]
            if time.time() < expires_at:
                # Validate fingerprint
                if cached_fingerprint == fingerprint:
                    return httpx.Response(
                        status_code=cached.status_code,
                        headers=cached.headers,
                        content=cached.content,
                    )
            else:
                # Expired, remove from cache
                del self._cache[idempotency_key]

        # Add idempotency key to headers if not present
        if not existing_key:
            request.headers[header_name] = idempotency_key

        # Execute request
        response = self._inner.handle_request(request)

        # Cache successful responses (2xx)
        if 200 <= response.status_code < 300:
            content = response.read()
            cached_data = CachedResponseData(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )
            self._cache[idempotency_key] = (
                cached_data,
                time.time() + ttl,
                fingerprint,
            )

            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )

        return response

    def close(self) -> None:
        """Close the transport."""
        self._cache.clear()
        self._inner.close()
