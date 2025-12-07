"""
Type definitions for connection-pool
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Protocol


class ConnectionState(str, Enum):
    """Connection state"""

    IDLE = "idle"
    ACTIVE = "active"
    DRAINING = "draining"
    CLOSED = "closed"


class HealthStatus(str, Enum):
    """Connection health status"""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class PooledConnection:
    """A pooled connection"""

    id: str
    host: str
    port: int
    state: ConnectionState
    health: HealthStatus
    created_at: float  # Unix timestamp
    last_used_at: float  # Unix timestamp
    request_count: int
    protocol: str  # 'http' or 'https'
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ConnectionPoolConfig:
    """Connection pool configuration"""

    id: str
    max_connections: int = 100
    max_connections_per_host: int = 10
    max_idle_connections: int = 20
    idle_timeout_seconds: float = 60.0
    keep_alive_timeout_seconds: float = 30.0
    connect_timeout_seconds: float = 10.0
    enable_health_check: bool = True
    health_check_interval_seconds: float = 30.0
    max_connection_age_seconds: float = 300.0
    keep_alive: bool = True
    queue_requests: bool = True
    max_queue_size: int = 1000
    queue_timeout_seconds: float = 30.0


@dataclass
class ConnectionPoolStats:
    """Connection pool statistics"""

    total_created: int
    total_closed: int
    active_connections: int
    idle_connections: int
    pending_requests: int
    total_requests: int
    failed_connections: int
    timed_out_connections: int
    connections_by_host: Dict[str, int]
    avg_connection_age_seconds: float
    avg_request_duration_seconds: float
    hit_ratio: float


class ConnectionPoolEventType(str, Enum):
    """Pool event types"""

    CONNECTION_CREATED = "connection:created"
    CONNECTION_ACQUIRED = "connection:acquired"
    CONNECTION_RELEASED = "connection:released"
    CONNECTION_CLOSED = "connection:closed"
    CONNECTION_TIMEOUT = "connection:timeout"
    CONNECTION_ERROR = "connection:error"
    CONNECTION_HEALTH_CHANGED = "connection:health:changed"
    POOL_DRAINED = "pool:drained"
    POOL_FULL = "pool:full"
    QUEUE_ADDED = "queue:added"
    QUEUE_TIMEOUT = "queue:timeout"
    QUEUE_OVERFLOW = "queue:overflow"


@dataclass
class ConnectionPoolEvent:
    """Pool event"""

    type: ConnectionPoolEventType
    timestamp: float
    connection_id: Optional[str] = None
    host: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


# Type alias for event listeners
ConnectionPoolEventListener = Callable[[ConnectionPoolEvent], None]


@dataclass
class AcquireOptions:
    """Connection acquisition options"""

    host: str
    port: int
    protocol: str  # 'http' or 'https'
    priority: int = 0
    timeout_seconds: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None


class ConnectionPoolStore(Protocol):
    """Store interface for connection pool state"""

    async def get_connections(self) -> List[PooledConnection]:
        """Get all connections"""
        ...

    async def get_connections_by_host(self, host_key: str) -> List[PooledConnection]:
        """Get connections for a specific host"""
        ...

    async def add_connection(self, connection: PooledConnection) -> None:
        """Add a connection to the store"""
        ...

    async def update_connection(
        self, connection_id: str, updates: Dict[str, Any]
    ) -> None:
        """Update a connection"""
        ...

    async def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection"""
        ...

    async def get_count(self) -> int:
        """Get connection count"""
        ...

    async def get_count_by_host(self, host_key: str) -> int:
        """Get connection count by host"""
        ...

    async def clear(self) -> None:
        """Clear all connections"""
        ...

    async def close(self) -> None:
        """Close the store"""
        ...


@dataclass
class AcquiredConnection:
    """Acquired connection handle"""

    connection: PooledConnection
    _release: Callable[[], Any]
    _fail: Callable[[Optional[Exception]], Any]

    async def release(self) -> None:
        """Release the connection back to the pool"""
        await self._release()

    async def fail(self, error: Optional[Exception] = None) -> None:
        """Mark the connection as failed and remove from pool"""
        await self._fail(error)
