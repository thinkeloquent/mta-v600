"""
connection_pool - Standalone HTTP connection pool with configurable limits
"""

from .types import (
    ConnectionState,
    HealthStatus,
    PooledConnection,
    ConnectionPoolConfig,
    ConnectionPoolStats,
    ConnectionPoolEventType,
    ConnectionPoolEvent,
    ConnectionPoolEventListener,
    AcquireOptions,
    ConnectionPoolStore,
    AcquiredConnection,
)
from .config import (
    DEFAULT_CONNECTION_POOL_CONFIG,
    merge_config,
    validate_config,
    get_host_key,
    parse_host_key,
    generate_connection_id,
)
from .stores.memory import MemoryConnectionStore
from .pool import ConnectionPool

__all__ = [
    # Types
    "ConnectionState",
    "HealthStatus",
    "PooledConnection",
    "ConnectionPoolConfig",
    "ConnectionPoolStats",
    "ConnectionPoolEventType",
    "ConnectionPoolEvent",
    "ConnectionPoolEventListener",
    "AcquireOptions",
    "ConnectionPoolStore",
    "AcquiredConnection",
    # Config
    "DEFAULT_CONNECTION_POOL_CONFIG",
    "merge_config",
    "validate_config",
    "get_host_key",
    "parse_host_key",
    "generate_connection_id",
    # Stores
    "MemoryConnectionStore",
    # Pool
    "ConnectionPool",
]
