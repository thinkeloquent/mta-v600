"""
fetch_compose_connection_pool - Connection pool HTTPX transport wrapper
"""

from .transport import ConnectionPoolTransport, SyncConnectionPoolTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_pooled_client,
    create_pooled_sync_client,
    create_api_connection_pool,
    create_from_preset,
    create_shared_connection_pool,
    HIGH_CONCURRENCY_POOL,
    LOW_LATENCY_POOL,
    MINIMAL_POOL,
    ConnectionPoolPreset,
)

# Re-export useful types from connection_pool
from connection_pool import (
    ConnectionPool,
    ConnectionPoolConfig,
    ConnectionPoolStats,
    ConnectionPoolEventType,
    ConnectionPoolEvent,
    ConnectionPoolEventListener,
    AcquireOptions,
    ConnectionPoolStore,
    PooledConnection,
    ConnectionState,
    HealthStatus,
)

__all__ = [
    # Transport
    "ConnectionPoolTransport",
    "SyncConnectionPoolTransport",
    # Factory
    "compose_transport",
    "compose_sync_transport",
    "create_pooled_client",
    "create_pooled_sync_client",
    "create_api_connection_pool",
    "create_from_preset",
    "create_shared_connection_pool",
    # Presets
    "HIGH_CONCURRENCY_POOL",
    "LOW_LATENCY_POOL",
    "MINIMAL_POOL",
    "ConnectionPoolPreset",
    # Re-exports from connection_pool
    "ConnectionPool",
    "ConnectionPoolConfig",
    "ConnectionPoolStats",
    "ConnectionPoolEventType",
    "ConnectionPoolEvent",
    "ConnectionPoolEventListener",
    "AcquireOptions",
    "ConnectionPoolStore",
    "PooledConnection",
    "ConnectionState",
    "HealthStatus",
]
