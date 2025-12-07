"""
DNS cache transport wrapper for httpx
"""
import asyncio
import time
import fnmatch
from typing import Optional, Callable
from urllib.parse import urlparse

import httpx

from cache_dsn import (
    DnsCacheResolver,
    DnsCacheConfig,
    DnsCacheStore,
    LoadBalanceStrategy,
    ResolvedEndpoint,
    create_memory_store,
)


# Connection error codes that indicate endpoint unhealthiness
CONNECTION_ERROR_TYPES = (
    httpx.ConnectError,
    httpx.ConnectTimeout,
    httpx.NetworkError,
)


class DnsCacheTransport(httpx.AsyncBaseTransport):
    """
    DNS caching transport wrapper for httpx.

    Wraps another transport and provides cached DNS resolution
    with load balancing across resolved endpoints.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = DnsCacheTransport(
            base,
            load_balance_strategy='power-of-two',
        )
        client = httpx.AsyncClient(transport=transport)
    """

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        default_ttl_seconds: float = 60.0,
        load_balance_strategy: LoadBalanceStrategy = "round-robin",
        config: Optional[DnsCacheConfig] = None,
        store: Optional[DnsCacheStore] = None,
        mark_unhealthy_on_error: bool = True,
        methods: Optional[list[str]] = None,
        hosts: Optional[list[str]] = None,
        exclude_hosts: Optional[list[str]] = None,
    ) -> None:
        """
        Create a new DnsCacheTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            default_ttl_seconds: Default TTL for cached entries. Default: 60.0
            load_balance_strategy: Load balancing strategy. Default: 'round-robin'
            config: Custom DNS cache config (alternative to simple options)
            store: Custom store for DNS cache
            mark_unhealthy_on_error: Mark endpoints unhealthy on errors. Default: True
            methods: HTTP methods to apply DNS caching to. Default: all
            hosts: Hosts to apply DNS caching to. Default: all
            exclude_hosts: Hosts to exclude from DNS caching
        """
        self._inner = inner
        self._mark_unhealthy_on_error = mark_unhealthy_on_error
        self._methods = methods
        self._hosts = hosts
        self._exclude_hosts = exclude_hosts

        # Build DNS cache config
        if config:
            resolver_config = config
        else:
            resolver_config = DnsCacheConfig(
                id=f"transport-{id(self)}",
                default_ttl_seconds=default_ttl_seconds,
                load_balance_strategy=load_balance_strategy,
                stale_while_revalidate=True,
            )

        self._resolver = DnsCacheResolver(
            resolver_config,
            store or create_memory_store(),
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with DNS caching"""

        # Check if this method should use DNS caching
        if self._methods and request.method not in self._methods:
            return await self._inner.handle_async_request(request)

        # Extract host from URL
        host = request.url.host or ""
        port = request.url.port
        scheme = request.url.scheme

        # Check host filters
        if not self._should_cache_host(host):
            return await self._inner.handle_async_request(request)

        # Resolve the hostname and select an endpoint
        endpoint = await self._resolver.resolve_one(host)

        if not endpoint:
            # No endpoints available, pass through to original
            return await self._inner.handle_async_request(request)

        # Track connection for load balancing
        self._resolver.increment_connections(endpoint)

        try:
            # Build new URL with resolved IP
            resolved_port = endpoint.port or port or (443 if scheme == "https" else 80)
            resolved_url = request.url.copy_with(
                host=endpoint.host,
                port=resolved_port,
            )

            # Ensure Host header is set to original hostname
            headers = httpx.Headers(request.headers)
            if "host" not in headers:
                host_value = f"{host}:{port}" if port else host
                headers["host"] = host_value

            # Create modified request
            modified_request = httpx.Request(
                method=request.method,
                url=resolved_url,
                headers=headers,
                content=request.content,
                extensions=request.extensions,
            )

            # Make the request
            response = await self._inner.handle_async_request(modified_request)
            return response

        except CONNECTION_ERROR_TYPES as e:
            # Mark endpoint as unhealthy on connection errors
            if self._mark_unhealthy_on_error:
                await self._resolver.mark_unhealthy(host, endpoint)
            raise

        finally:
            # Decrement connection count
            self._resolver.decrement_connections(endpoint)

    def _should_cache_host(self, host: str) -> bool:
        """Check if DNS caching should be applied to this host"""
        # Check exclude list first
        if self._exclude_hosts:
            for pattern in self._exclude_hosts:
                if self._host_matches(host, pattern):
                    return False

        # Check include list
        if self._hosts:
            for pattern in self._hosts:
                if self._host_matches(host, pattern):
                    return True
            return False

        return True

    def _host_matches(self, host: str, pattern: str) -> bool:
        """Check if a hostname matches a pattern"""
        # Exact match
        if host == pattern:
            return True

        # Wildcard match (e.g., *.example.com)
        if pattern.startswith("*."):
            suffix = pattern[1:]  # .example.com
            return host.endswith(suffix) or host == pattern[2:]

        # fnmatch for more complex patterns
        return fnmatch.fnmatch(host, pattern)

    @property
    def resolver(self) -> DnsCacheResolver:
        """Get the underlying DNS cache resolver"""
        return self._resolver

    async def aclose(self) -> None:
        """Close the transport"""
        await self._resolver.destroy()
        await self._inner.aclose()


class SyncDnsCacheTransport(httpx.BaseTransport):
    """
    Synchronous DNS caching transport wrapper for httpx.

    Note: Uses a simpler caching mechanism suitable for sync contexts.
    For async applications, use DnsCacheTransport instead.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        default_ttl_seconds: float = 60.0,
        mark_unhealthy_on_error: bool = True,
        methods: Optional[list[str]] = None,
        hosts: Optional[list[str]] = None,
        exclude_hosts: Optional[list[str]] = None,
    ) -> None:
        """
        Create a new SyncDnsCacheTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            default_ttl_seconds: Default TTL for cached entries. Default: 60.0
            mark_unhealthy_on_error: Mark endpoints unhealthy on errors. Default: True
            methods: HTTP methods to apply DNS caching to. Default: all
            hosts: Hosts to apply DNS caching to. Default: all
            exclude_hosts: Hosts to exclude from DNS caching
        """
        self._inner = inner
        self._default_ttl_seconds = default_ttl_seconds
        self._mark_unhealthy_on_error = mark_unhealthy_on_error
        self._methods = methods
        self._hosts = hosts
        self._exclude_hosts = exclude_hosts

        # Simple in-memory cache for sync operations
        self._cache: dict[str, tuple[list[ResolvedEndpoint], float]] = {}
        self._round_robin_index: dict[str, int] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with DNS caching"""
        import socket

        # Check if this method should use DNS caching
        if self._methods and request.method not in self._methods:
            return self._inner.handle_request(request)

        # Extract host from URL
        host = request.url.host or ""
        port = request.url.port
        scheme = request.url.scheme

        # Check host filters
        if not self._should_cache_host(host):
            return self._inner.handle_request(request)

        # Get or resolve endpoints
        now = time.time()
        cached = self._cache.get(host)

        if cached and cached[1] > now:
            endpoints = cached[0]
        else:
            # Resolve DNS
            try:
                addresses = socket.getaddrinfo(
                    host,
                    port or 80,
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                )
                endpoints = []
                seen: set[str] = set()
                for family, socktype, proto, canonname, sockaddr in addresses:
                    addr_host = sockaddr[0]
                    addr_port = sockaddr[1]
                    if addr_host not in seen:
                        seen.add(addr_host)
                        endpoints.append(ResolvedEndpoint(
                            host=addr_host,
                            port=addr_port,
                            healthy=True,
                            last_checked=now,
                        ))
            except socket.gaierror:
                endpoints = [ResolvedEndpoint(
                    host=host,
                    port=port or 80,
                    healthy=True,
                    last_checked=now,
                )]

            self._cache[host] = (endpoints, now + self._default_ttl_seconds)

        if not endpoints:
            return self._inner.handle_request(request)

        # Round-robin endpoint selection
        healthy = [e for e in endpoints if e.healthy]
        if not healthy:
            healthy = endpoints

        index = self._round_robin_index.get(host, 0)
        endpoint = healthy[index % len(healthy)]
        self._round_robin_index[host] = (index + 1) % len(healthy)

        try:
            # Build new URL with resolved IP
            resolved_port = endpoint.port or port or (443 if scheme == "https" else 80)
            resolved_url = request.url.copy_with(
                host=endpoint.host,
                port=resolved_port,
            )

            # Ensure Host header is set to original hostname
            headers = httpx.Headers(request.headers)
            if "host" not in headers:
                host_value = f"{host}:{port}" if port else host
                headers["host"] = host_value

            # Create modified request
            modified_request = httpx.Request(
                method=request.method,
                url=resolved_url,
                headers=headers,
                content=request.content,
                extensions=request.extensions,
            )

            return self._inner.handle_request(modified_request)

        except (httpx.ConnectError, httpx.ConnectTimeout, httpx.NetworkError):
            if self._mark_unhealthy_on_error:
                endpoint.healthy = False
            raise

    def _should_cache_host(self, host: str) -> bool:
        """Check if DNS caching should be applied to this host"""
        if self._exclude_hosts:
            for pattern in self._exclude_hosts:
                if self._host_matches(host, pattern):
                    return False

        if self._hosts:
            for pattern in self._hosts:
                if self._host_matches(host, pattern):
                    return True
            return False

        return True

    def _host_matches(self, host: str, pattern: str) -> bool:
        """Check if a hostname matches a pattern"""
        if host == pattern:
            return True

        if pattern.startswith("*."):
            suffix = pattern[1:]
            return host.endswith(suffix) or host == pattern[2:]

        return fnmatch.fnmatch(host, pattern)

    def close(self) -> None:
        """Close the transport"""
        self._cache.clear()
        self._round_robin_index.clear()
        self._inner.close()
