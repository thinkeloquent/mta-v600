"""
Connection pool transport wrapper for HTTPX
"""

import fnmatch
import time
from typing import Any, Dict, List, Optional, Set

import httpx

from connection_pool import (
    ConnectionPool,
    ConnectionPoolConfig,
    ConnectionPoolStore,
    AcquireOptions,
)


class ConnectionPoolTransport(httpx.AsyncBaseTransport):
    """Async HTTPX transport that wraps requests with connection pooling"""

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        max_idle_connections: int = 20,
        idle_timeout_seconds: float = 60.0,
        keep_alive_timeout_seconds: float = 30.0,
        connect_timeout_seconds: float = 10.0,
        queue_requests: bool = True,
        max_queue_size: int = 1000,
        queue_timeout_seconds: float = 30.0,
        config: Optional[ConnectionPoolConfig] = None,
        store: Optional[ConnectionPoolStore] = None,
        hosts: Optional[List[str]] = None,
        exclude_hosts: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
    ):
        self._inner = inner
        self._hosts = hosts
        self._exclude_hosts = exclude_hosts
        self._methods = set(m.upper() for m in methods) if methods else None

        # Build config
        pool_config = config or ConnectionPoolConfig(
            id=f"transport-{int(time.time() * 1000)}",
            max_connections=max_connections,
            max_connections_per_host=max_connections_per_host,
            max_idle_connections=max_idle_connections,
            idle_timeout_seconds=idle_timeout_seconds,
            keep_alive_timeout_seconds=keep_alive_timeout_seconds,
            connect_timeout_seconds=connect_timeout_seconds,
            queue_requests=queue_requests,
            max_queue_size=max_queue_size,
            queue_timeout_seconds=queue_timeout_seconds,
            enable_health_check=True,
            health_check_interval_seconds=30.0,
            max_connection_age_seconds=300.0,
            keep_alive=True,
        )

        self._pool = ConnectionPool(pool_config, store)

    @property
    def pool(self) -> ConnectionPool:
        """Get the underlying connection pool"""
        return self._pool

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with connection pooling"""
        # Check method filter
        if self._methods and request.method.upper() not in self._methods:
            return await self._inner.handle_async_request(request)

        # Extract host info
        host = request.url.host or ""
        port = request.url.port or (443 if request.url.scheme == "https" else 80)
        protocol = request.url.scheme

        # Check host filters
        if not self._should_pool_host(host):
            return await self._inner.handle_async_request(request)

        # Acquire connection from pool
        acquired = await self._pool.acquire(
            AcquireOptions(
                host=host,
                port=port,
                protocol=protocol,
            )
        )

        try:
            # Execute request
            response = await self._inner.handle_async_request(request)
            return response
        except Exception as e:
            # Mark connection as failed
            await acquired.fail(e)
            raise
        finally:
            # Release connection on success
            try:
                await acquired.release()
            except Exception:
                pass

    def _should_pool_host(self, host: str) -> bool:
        """Check if a host should use connection pooling"""
        # Check exclude list first
        if self._exclude_hosts:
            for pattern in self._exclude_hosts:
                if self._host_matches(host, pattern):
                    return False

        # If hosts list specified, only pool those
        if self._hosts:
            for pattern in self._hosts:
                if self._host_matches(host, pattern):
                    return True
            return False

        # No filters, pool all
        return True

    def _host_matches(self, host: str, pattern: str) -> bool:
        """Check if a host matches a pattern (supports wildcards)"""
        if host == pattern:
            return True

        if pattern.startswith("*."):
            suffix = pattern[1:]  # .example.com
            return host.endswith(suffix) or host == pattern[2:]

        return fnmatch.fnmatch(host, pattern)

    async def aclose(self) -> None:
        """Close the transport"""
        await self._pool.close()
        if hasattr(self._inner, "aclose"):
            await self._inner.aclose()


class SyncConnectionPoolTransport(httpx.BaseTransport):
    """Sync HTTPX transport that wraps requests with connection tracking"""

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        max_connections: int = 100,
        max_connections_per_host: int = 10,
        hosts: Optional[List[str]] = None,
        exclude_hosts: Optional[List[str]] = None,
        methods: Optional[List[str]] = None,
    ):
        self._inner = inner
        self._hosts = hosts
        self._exclude_hosts = exclude_hosts
        self._methods = set(m.upper() for m in methods) if methods else None

        # Simple connection tracking (sync version doesn't use full pool)
        self._active_connections: Dict[str, int] = {}
        self._max_connections = max_connections
        self._max_per_host = max_connections_per_host

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with connection tracking"""
        # Check method filter
        if self._methods and request.method.upper() not in self._methods:
            return self._inner.handle_request(request)

        host = request.url.host or ""

        # Check host filters
        if not self._should_pool_host(host):
            return self._inner.handle_request(request)

        # Track connection
        host_key = f"{host}:{request.url.port or 80}"
        self._active_connections[host_key] = (
            self._active_connections.get(host_key, 0) + 1
        )

        try:
            response = self._inner.handle_request(request)
            return response
        finally:
            self._active_connections[host_key] = max(
                0, self._active_connections.get(host_key, 1) - 1
            )

    def _should_pool_host(self, host: str) -> bool:
        """Check if a host should use connection pooling"""
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
        """Check if a host matches a pattern"""
        if host == pattern:
            return True

        if pattern.startswith("*."):
            suffix = pattern[1:]
            return host.endswith(suffix) or host == pattern[2:]

        return fnmatch.fnmatch(host, pattern)

    def close(self) -> None:
        """Close the transport"""
        self._active_connections.clear()
        if hasattr(self._inner, "close"):
            self._inner.close()
