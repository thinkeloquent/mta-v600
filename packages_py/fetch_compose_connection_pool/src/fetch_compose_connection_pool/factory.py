"""
Factory functions for connection pool transport
"""

from typing import Any, Callable, Dict, List, Optional, TypedDict

import httpx

from connection_pool import ConnectionPool, ConnectionPoolConfig, ConnectionPoolStore

from .transport import ConnectionPoolTransport, SyncConnectionPoolTransport


class ConnectionPoolPreset(TypedDict, total=False):
    """Preset configuration for connection pool"""

    max_connections: int
    max_connections_per_host: int
    max_idle_connections: int
    idle_timeout_seconds: float
    keep_alive_timeout_seconds: float
    queue_requests: bool
    max_queue_size: int


# Preset for high-concurrency workloads
HIGH_CONCURRENCY_POOL: ConnectionPoolPreset = {
    "max_connections": 200,
    "max_connections_per_host": 20,
    "max_idle_connections": 50,
    "idle_timeout_seconds": 30.0,
    "keep_alive_timeout_seconds": 15.0,
    "queue_requests": True,
    "max_queue_size": 2000,
}

# Preset for low-latency workloads
LOW_LATENCY_POOL: ConnectionPoolPreset = {
    "max_connections": 100,
    "max_connections_per_host": 10,
    "max_idle_connections": 30,
    "idle_timeout_seconds": 120.0,
    "keep_alive_timeout_seconds": 60.0,
    "queue_requests": True,
    "max_queue_size": 500,
}

# Preset for resource-constrained environments
MINIMAL_POOL: ConnectionPoolPreset = {
    "max_connections": 20,
    "max_connections_per_host": 5,
    "max_idle_connections": 5,
    "idle_timeout_seconds": 10.0,
    "keep_alive_timeout_seconds": 5.0,
    "queue_requests": True,
    "max_queue_size": 100,
}


def compose_transport(
    base: httpx.AsyncBaseTransport,
    *wrappers: Callable[[httpx.AsyncBaseTransport], httpx.AsyncBaseTransport],
) -> httpx.AsyncBaseTransport:
    """Compose multiple transport wrappers"""
    result = base
    for wrapper in wrappers:
        result = wrapper(result)
    return result


def compose_sync_transport(
    base: httpx.BaseTransport,
    *wrappers: Callable[[httpx.BaseTransport], httpx.BaseTransport],
) -> httpx.BaseTransport:
    """Compose multiple sync transport wrappers"""
    result = base
    for wrapper in wrappers:
        result = wrapper(result)
    return result


def create_pooled_client(
    *,
    max_connections: int = 100,
    max_connections_per_host: int = 10,
    max_idle_connections: int = 20,
    idle_timeout_seconds: float = 60.0,
    hosts: Optional[List[str]] = None,
    exclude_hosts: Optional[List[str]] = None,
    **client_kwargs: Any,
) -> httpx.AsyncClient:
    """Create an async HTTPX client with connection pooling"""
    transport = ConnectionPoolTransport(
        httpx.AsyncHTTPTransport(),
        max_connections=max_connections,
        max_connections_per_host=max_connections_per_host,
        max_idle_connections=max_idle_connections,
        idle_timeout_seconds=idle_timeout_seconds,
        hosts=hosts,
        exclude_hosts=exclude_hosts,
    )

    return httpx.AsyncClient(transport=transport, **client_kwargs)


def create_pooled_sync_client(
    *,
    max_connections: int = 100,
    max_connections_per_host: int = 10,
    hosts: Optional[List[str]] = None,
    exclude_hosts: Optional[List[str]] = None,
    **client_kwargs: Any,
) -> httpx.Client:
    """Create a sync HTTPX client with connection pooling"""
    transport = SyncConnectionPoolTransport(
        httpx.HTTPTransport(),
        max_connections=max_connections,
        max_connections_per_host=max_connections_per_host,
        hosts=hosts,
        exclude_hosts=exclude_hosts,
    )

    return httpx.Client(transport=transport, **client_kwargs)


def create_api_connection_pool(
    api_id: str,
    *,
    max_connections_per_host: int = 10,
    max_idle_connections: int = 20,
    idle_timeout_seconds: float = 60.0,
    hosts: Optional[List[str]] = None,
) -> Callable[[httpx.AsyncBaseTransport], ConnectionPoolTransport]:
    """Create a connection pool wrapper for a specific API"""

    def wrapper(inner: httpx.AsyncBaseTransport) -> ConnectionPoolTransport:
        config = ConnectionPoolConfig(
            id=api_id,
            max_connections=100,
            max_connections_per_host=max_connections_per_host,
            max_idle_connections=max_idle_connections,
            idle_timeout_seconds=idle_timeout_seconds,
            keep_alive_timeout_seconds=30.0,
            connect_timeout_seconds=10.0,
            queue_requests=True,
            max_queue_size=1000,
            queue_timeout_seconds=30.0,
            enable_health_check=True,
            health_check_interval_seconds=30.0,
            max_connection_age_seconds=300.0,
            keep_alive=True,
        )
        return ConnectionPoolTransport(inner, config=config, hosts=hosts)

    return wrapper


def create_from_preset(
    preset: ConnectionPoolPreset,
    inner: httpx.AsyncBaseTransport,
    **overrides: Any,
) -> ConnectionPoolTransport:
    """Create a transport from a preset configuration"""
    merged = {**preset, **overrides}
    return ConnectionPoolTransport(inner, **merged)


def create_shared_connection_pool(
    config: ConnectionPoolConfig,
    store: Optional[ConnectionPoolStore] = None,
) -> tuple[
    ConnectionPool,
    Callable[
        [Optional[List[str]], Optional[List[str]]],
        Callable[[httpx.AsyncBaseTransport], ConnectionPoolTransport],
    ],
]:
    """Create a shared connection pool for multiple transports"""
    pool = ConnectionPool(config, store)

    def create_transport_wrapper(
        hosts: Optional[List[str]] = None,
        exclude_hosts: Optional[List[str]] = None,
    ) -> Callable[[httpx.AsyncBaseTransport], ConnectionPoolTransport]:
        def wrapper(inner: httpx.AsyncBaseTransport) -> ConnectionPoolTransport:
            return ConnectionPoolTransport(
                inner,
                config=config,
                store=store,
                hosts=hosts,
                exclude_hosts=exclude_hosts,
            )

        return wrapper

    return pool, create_transport_wrapper
