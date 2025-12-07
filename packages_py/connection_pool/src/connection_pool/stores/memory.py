"""
In-memory connection pool store
"""

import time
from typing import Any, Dict, List, Set

from ..config import get_host_key
from ..types import ConnectionPoolStore, ConnectionState, PooledConnection


class MemoryConnectionStore(ConnectionPoolStore):
    """In-memory implementation of ConnectionPoolStore"""

    def __init__(self) -> None:
        self._connections: Dict[str, PooledConnection] = {}
        self._connections_by_host: Dict[str, Set[str]] = {}

    async def get_connections(self) -> List[PooledConnection]:
        """Get all connections"""
        return list(self._connections.values())

    async def get_connections_by_host(self, host_key: str) -> List[PooledConnection]:
        """Get connections for a specific host"""
        connection_ids = self._connections_by_host.get(host_key, set())
        connections = []
        for conn_id in connection_ids:
            conn = self._connections.get(conn_id)
            if conn:
                connections.append(conn)
        return connections

    async def add_connection(self, connection: PooledConnection) -> None:
        """Add a connection to the store"""
        self._connections[connection.id] = connection

        host_key = get_host_key(connection.host, connection.port)
        if host_key not in self._connections_by_host:
            self._connections_by_host[host_key] = set()
        self._connections_by_host[host_key].add(connection.id)

    async def update_connection(
        self, connection_id: str, updates: Dict[str, Any]
    ) -> None:
        """Update a connection"""
        connection = self._connections.get(connection_id)
        if not connection:
            return

        old_host = connection.host
        old_port = connection.port

        # Apply updates by creating new dataclass instance
        for key, value in updates.items():
            if hasattr(connection, key):
                object.__setattr__(connection, key, value)

        # If host/port changed, update host index
        new_host = updates.get("host", old_host)
        new_port = updates.get("port", old_port)

        if new_host != old_host or new_port != old_port:
            old_host_key = get_host_key(old_host, old_port)
            new_host_key = get_host_key(new_host, new_port)

            # Remove from old host set
            if old_host_key in self._connections_by_host:
                self._connections_by_host[old_host_key].discard(connection_id)
                if not self._connections_by_host[old_host_key]:
                    del self._connections_by_host[old_host_key]

            # Add to new host set
            if new_host_key not in self._connections_by_host:
                self._connections_by_host[new_host_key] = set()
            self._connections_by_host[new_host_key].add(connection_id)

    async def remove_connection(self, connection_id: str) -> bool:
        """Remove a connection"""
        connection = self._connections.get(connection_id)
        if not connection:
            return False

        # Remove from host index
        host_key = get_host_key(connection.host, connection.port)
        if host_key in self._connections_by_host:
            self._connections_by_host[host_key].discard(connection_id)
            if not self._connections_by_host[host_key]:
                del self._connections_by_host[host_key]

        # Remove from main map
        del self._connections[connection_id]
        return True

    async def get_count(self) -> int:
        """Get connection count"""
        return len(self._connections)

    async def get_count_by_host(self, host_key: str) -> int:
        """Get connection count by host"""
        return len(self._connections_by_host.get(host_key, set()))

    async def clear(self) -> None:
        """Clear all connections"""
        self._connections.clear()
        self._connections_by_host.clear()

    async def close(self) -> None:
        """Close the store"""
        await self.clear()

    async def get_idle_connections(self) -> List[PooledConnection]:
        """Get idle connections sorted by last used time (oldest first)"""
        idle = [
            conn
            for conn in self._connections.values()
            if conn.state == ConnectionState.IDLE
        ]
        return sorted(idle, key=lambda c: c.last_used_at)

    async def get_expired_connections(
        self, max_age_seconds: float
    ) -> List[PooledConnection]:
        """Get connections that have exceeded max age"""
        now = time.time()
        return [
            conn
            for conn in self._connections.values()
            if now - conn.created_at > max_age_seconds
        ]

    async def get_timed_out_connections(
        self, idle_timeout_seconds: float
    ) -> List[PooledConnection]:
        """Get connections that have been idle too long"""
        now = time.time()
        return [
            conn
            for conn in self._connections.values()
            if conn.state == ConnectionState.IDLE
            and now - conn.last_used_at > idle_timeout_seconds
        ]
