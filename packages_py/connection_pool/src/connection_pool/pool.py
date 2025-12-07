"""
Connection pool implementation
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Set

from .config import generate_connection_id, get_host_key, merge_config
from .stores.memory import MemoryConnectionStore
from .types import (
    AcquiredConnection,
    AcquireOptions,
    ConnectionPoolConfig,
    ConnectionPoolEvent,
    ConnectionPoolEventListener,
    ConnectionPoolEventType,
    ConnectionPoolStats,
    ConnectionPoolStore,
    ConnectionState,
    HealthStatus,
    PooledConnection,
)


@dataclass
class PendingRequest:
    """Pending request in the queue"""

    options: AcquireOptions
    future: asyncio.Future
    added_at: float
    timeout_handle: Optional[asyncio.TimerHandle] = None


class ConnectionPool:
    """Connection pool with configurable limits, health tracking, and statistics"""

    def __init__(
        self,
        config: ConnectionPoolConfig,
        store: Optional[ConnectionPoolStore] = None,
    ) -> None:
        self._config = merge_config(config)
        self._store = store or MemoryConnectionStore()
        self._listeners: Dict[
            ConnectionPoolEventType, Set[ConnectionPoolEventListener]
        ] = {}
        self._pending_queue: List[PendingRequest] = []
        self._health_check_task: Optional[asyncio.Task] = None
        self._closed = False

        # Statistics
        self._stats = {
            "total_created": 0,
            "total_closed": 0,
            "total_requests": 0,
            "failed_connections": 0,
            "timed_out_connections": 0,
            "total_request_duration": 0.0,
        }

        if self._config.enable_health_check:
            self._start_health_check()

    @property
    def id(self) -> str:
        """Get the pool ID"""
        return self._config.id

    async def acquire(self, options: AcquireOptions) -> AcquiredConnection:
        """Acquire a connection from the pool"""
        if self._closed:
            raise RuntimeError("Connection pool is closed")

        self._stats["total_requests"] += 1
        host_key = get_host_key(options.host, options.port)

        # Try to find an existing idle connection
        existing = await self._find_idle_connection(host_key)
        if existing:
            return self._wrap_connection(existing)

        # Check if we can create a new connection
        total_count = await self._store.get_count()
        host_count = await self._store.get_count_by_host(host_key)

        if (
            total_count < self._config.max_connections
            and host_count < self._config.max_connections_per_host
        ):
            connection = await self._create_connection(options)
            return self._wrap_connection(connection)

        # Pool is at capacity - queue the request if enabled
        if not self._config.queue_requests:
            self._emit(ConnectionPoolEventType.POOL_FULL, None, options.host)
            raise RuntimeError("Connection pool is full")

        if len(self._pending_queue) >= self._config.max_queue_size:
            self._emit(ConnectionPoolEventType.QUEUE_OVERFLOW, None, options.host)
            raise RuntimeError("Request queue is full")

        return await self._enqueue_request(options)

    async def release(self, connection: PooledConnection) -> None:
        """Release a connection back to the pool"""
        if self._closed:
            await self._close_connection(connection)
            return

        # Check if connection is too old
        age = time.time() - connection.created_at
        if age > self._config.max_connection_age_seconds:
            await self._close_connection(connection)
            return

        # Check if we have too many idle connections
        idle_count = await self._get_idle_count()
        if idle_count >= self._config.max_idle_connections:
            await self._close_connection(connection)
            return

        # Update connection state
        await self._store.update_connection(
            connection.id,
            {"state": ConnectionState.IDLE, "last_used_at": time.time()},
        )

        self._emit(
            ConnectionPoolEventType.CONNECTION_RELEASED, connection.id, connection.host
        )

        # Process pending queue
        await self._process_pending_queue()

    async def fail(
        self, connection: PooledConnection, error: Optional[Exception] = None
    ) -> None:
        """Mark a connection as failed"""
        self._stats["failed_connections"] += 1

        await self._store.update_connection(
            connection.id, {"health": HealthStatus.UNHEALTHY}
        )

        self._emit(
            ConnectionPoolEventType.CONNECTION_ERROR,
            connection.id,
            connection.host,
            {"error": str(error) if error else None},
        )

        await self._close_connection(connection)

    async def get_stats(self) -> ConnectionPoolStats:
        """Get pool statistics"""
        connections = await self._store.get_connections()
        active = sum(1 for c in connections if c.state == ConnectionState.ACTIVE)
        idle = sum(1 for c in connections if c.state == ConnectionState.IDLE)

        connections_by_host: Dict[str, int] = {}
        for conn in connections:
            host_key = get_host_key(conn.host, conn.port)
            connections_by_host[host_key] = connections_by_host.get(host_key, 0) + 1

        now = time.time()
        total_age = sum(now - c.created_at for c in connections)
        avg_age = total_age / len(connections) if connections else 0.0

        total_requests = self._stats["total_requests"]
        avg_duration = (
            self._stats["total_request_duration"] / total_requests
            if total_requests > 0
            else 0.0
        )

        hit_ratio = (
            (total_requests - self._stats["total_created"]) / total_requests
            if total_requests > 0
            else 0.0
        )

        return ConnectionPoolStats(
            total_created=self._stats["total_created"],
            total_closed=self._stats["total_closed"],
            active_connections=active,
            idle_connections=idle,
            pending_requests=len(self._pending_queue),
            total_requests=total_requests,
            failed_connections=self._stats["failed_connections"],
            timed_out_connections=self._stats["timed_out_connections"],
            connections_by_host=connections_by_host,
            avg_connection_age_seconds=avg_age,
            avg_request_duration_seconds=avg_duration,
            hit_ratio=hit_ratio,
        )

    async def drain(self) -> None:
        """Drain the pool (stop accepting new requests, wait for existing)"""
        # Mark all idle connections as draining
        connections = await self._store.get_connections()
        for conn in connections:
            if conn.state == ConnectionState.IDLE:
                await self._store.update_connection(
                    conn.id, {"state": ConnectionState.DRAINING}
                )

        # Reject all pending requests
        for pending in self._pending_queue:
            if pending.timeout_handle:
                pending.timeout_handle.cancel()
            if not pending.future.done():
                pending.future.set_exception(RuntimeError("Pool is draining"))
        self._pending_queue.clear()

        self._emit(ConnectionPoolEventType.POOL_DRAINED)

    async def close(self) -> None:
        """Close the pool and all connections"""
        if self._closed:
            return

        self._closed = True

        # Stop health check
        if self._health_check_task:
            self._health_check_task.cancel()
            try:
                await self._health_check_task
            except asyncio.CancelledError:
                pass
            self._health_check_task = None

        # Drain first
        await self.drain()

        # Close all connections
        connections = await self._store.get_connections()
        for conn in connections:
            await self._close_connection(conn)

        await self._store.close()

    def on(
        self, event_type: ConnectionPoolEventType, listener: ConnectionPoolEventListener
    ) -> None:
        """Add an event listener"""
        if event_type not in self._listeners:
            self._listeners[event_type] = set()
        self._listeners[event_type].add(listener)

    def off(
        self, event_type: ConnectionPoolEventType, listener: ConnectionPoolEventListener
    ) -> None:
        """Remove an event listener"""
        if event_type in self._listeners:
            self._listeners[event_type].discard(listener)

    async def _find_idle_connection(
        self, host_key: str
    ) -> Optional[PooledConnection]:
        """Find an idle connection for the given host"""
        connections = await self._store.get_connections_by_host(host_key)

        for conn in connections:
            if conn.state == ConnectionState.IDLE and conn.health != HealthStatus.UNHEALTHY:
                # Mark as active
                await self._store.update_connection(
                    conn.id,
                    {
                        "state": ConnectionState.ACTIVE,
                        "last_used_at": time.time(),
                        "request_count": conn.request_count + 1,
                    },
                )

                self._emit(
                    ConnectionPoolEventType.CONNECTION_ACQUIRED, conn.id, conn.host
                )

                # Return updated connection
                return PooledConnection(
                    id=conn.id,
                    host=conn.host,
                    port=conn.port,
                    state=ConnectionState.ACTIVE,
                    health=conn.health,
                    created_at=conn.created_at,
                    last_used_at=time.time(),
                    request_count=conn.request_count + 1,
                    protocol=conn.protocol,
                    metadata=conn.metadata,
                )

        return None

    async def _create_connection(self, options: AcquireOptions) -> PooledConnection:
        """Create a new connection"""
        now = time.time()
        connection = PooledConnection(
            id=generate_connection_id(),
            host=options.host,
            port=options.port,
            protocol=options.protocol,
            state=ConnectionState.ACTIVE,
            health=HealthStatus.HEALTHY,
            created_at=now,
            last_used_at=now,
            request_count=1,
            metadata=options.metadata,
        )

        await self._store.add_connection(connection)
        self._stats["total_created"] += 1

        self._emit(
            ConnectionPoolEventType.CONNECTION_CREATED, connection.id, connection.host
        )
        self._emit(
            ConnectionPoolEventType.CONNECTION_ACQUIRED, connection.id, connection.host
        )

        return connection

    async def _close_connection(self, connection: PooledConnection) -> None:
        """Close a connection"""
        await self._store.update_connection(
            connection.id, {"state": ConnectionState.CLOSED}
        )
        await self._store.remove_connection(connection.id)
        self._stats["total_closed"] += 1

        self._emit(
            ConnectionPoolEventType.CONNECTION_CLOSED, connection.id, connection.host
        )

    def _wrap_connection(self, connection: PooledConnection) -> AcquiredConnection:
        """Wrap a connection with release/fail methods"""
        start_time = time.time()

        async def release() -> None:
            self._stats["total_request_duration"] += time.time() - start_time
            await self.release(connection)

        async def fail(error: Optional[Exception] = None) -> None:
            self._stats["total_request_duration"] += time.time() - start_time
            await self.fail(connection, error)

        return AcquiredConnection(
            connection=connection,
            _release=release,
            _fail=fail,
        )

    async def _enqueue_request(self, options: AcquireOptions) -> AcquiredConnection:
        """Enqueue a request when pool is at capacity"""
        loop = asyncio.get_event_loop()
        future: asyncio.Future = loop.create_future()

        pending = PendingRequest(
            options=options,
            future=future,
            added_at=time.time(),
        )

        # Set up timeout
        timeout_seconds = options.timeout_seconds or self._config.queue_timeout_seconds
        if timeout_seconds > 0:

            def on_timeout() -> None:
                if pending in self._pending_queue:
                    self._pending_queue.remove(pending)
                    self._stats["timed_out_connections"] += 1
                    self._emit(
                        ConnectionPoolEventType.QUEUE_TIMEOUT, None, options.host
                    )
                    if not future.done():
                        future.set_exception(
                            TimeoutError("Connection acquisition timed out")
                        )

            pending.timeout_handle = loop.call_later(timeout_seconds, on_timeout)

        # Insert by priority
        self._insert_by_priority(pending)
        self._emit(ConnectionPoolEventType.QUEUE_ADDED, None, options.host)

        return await future

    def _insert_by_priority(self, pending: PendingRequest) -> None:
        """Insert a pending request by priority (higher priority first)"""
        priority = pending.options.priority
        insert_index = len(self._pending_queue)

        for i, existing in enumerate(self._pending_queue):
            if priority > existing.options.priority:
                insert_index = i
                break

        self._pending_queue.insert(insert_index, pending)

    async def _process_pending_queue(self) -> None:
        """Process pending queue after a connection is released"""
        if not self._pending_queue:
            return

        # Try to satisfy pending requests
        while self._pending_queue:
            pending = self._pending_queue[0]
            host_key = get_host_key(pending.options.host, pending.options.port)

            # Try to find an idle connection
            connection = await self._find_idle_connection(host_key)
            if connection:
                self._pending_queue.pop(0)
                if pending.timeout_handle:
                    pending.timeout_handle.cancel()
                if not pending.future.done():
                    pending.future.set_result(self._wrap_connection(connection))
                continue

            # Try to create a new connection
            total_count = await self._store.get_count()
            host_count = await self._store.get_count_by_host(host_key)

            if (
                total_count < self._config.max_connections
                and host_count < self._config.max_connections_per_host
            ):
                self._pending_queue.pop(0)
                if pending.timeout_handle:
                    pending.timeout_handle.cancel()
                try:
                    new_connection = await self._create_connection(pending.options)
                    if not pending.future.done():
                        pending.future.set_result(
                            self._wrap_connection(new_connection)
                        )
                except Exception as e:
                    if not pending.future.done():
                        pending.future.set_exception(e)
                continue

            # Can't satisfy this request yet
            break

    def _start_health_check(self) -> None:
        """Start periodic health check"""

        async def health_check_loop() -> None:
            while not self._closed:
                await asyncio.sleep(self._config.health_check_interval_seconds)
                await self._perform_health_check()

        self._health_check_task = asyncio.create_task(health_check_loop())

    async def _perform_health_check(self) -> None:
        """Perform health check on connections"""
        if isinstance(self._store, MemoryConnectionStore):
            # Check for timed out idle connections
            timed_out = await self._store.get_timed_out_connections(
                self._config.idle_timeout_seconds
            )
            for conn in timed_out:
                self._stats["timed_out_connections"] += 1
                self._emit(
                    ConnectionPoolEventType.CONNECTION_TIMEOUT, conn.id, conn.host
                )
                await self._close_connection(conn)

            # Check for expired connections (max age)
            expired = await self._store.get_expired_connections(
                self._config.max_connection_age_seconds
            )
            for conn in expired:
                if conn.state == ConnectionState.IDLE:
                    await self._close_connection(conn)

    async def _get_idle_count(self) -> int:
        """Get count of idle connections"""
        connections = await self._store.get_connections()
        return sum(1 for c in connections if c.state == ConnectionState.IDLE)

    def _emit(
        self,
        event_type: ConnectionPoolEventType,
        connection_id: Optional[str] = None,
        host: Optional[str] = None,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Emit an event"""
        event = ConnectionPoolEvent(
            type=event_type,
            connection_id=connection_id,
            host=host,
            data=data,
            timestamp=time.time(),
        )

        listeners = self._listeners.get(event_type, set())
        for listener in listeners:
            try:
                listener(event)
            except Exception:
                # Ignore listener errors
                pass
