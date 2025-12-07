"""
Tests for ConnectionPool main class

Coverage includes:
- Decision/Branch Coverage: acquire/release/fail paths
- State Transition Testing: Pool and connection states
- Queue logic testing
- Event emission testing
- Health check logic
"""

import time
import asyncio
import pytest
from typing import List

from connection_pool.pool import ConnectionPool
from connection_pool.stores.memory import MemoryConnectionStore
from connection_pool.types import (
    ConnectionPoolConfig,
    ConnectionPoolEvent,
    ConnectionPoolEventType,
    AcquireOptions,
)


def create_config(**overrides) -> ConnectionPoolConfig:
    """Create a test configuration"""
    defaults = {
        "id": "test-pool",
        "max_connections": 10,
        "max_connections_per_host": 5,
        "max_idle_connections": 5,
        "idle_timeout_seconds": 60.0,
        "keep_alive_timeout_seconds": 30.0,
        "connect_timeout_seconds": 10.0,
        "enable_health_check": False,  # Disable by default for tests
        "health_check_interval_seconds": 30.0,
        "max_connection_age_seconds": 300.0,
        "keep_alive": True,
        "queue_requests": True,
        "max_queue_size": 100,
        "queue_timeout_seconds": 5.0,
    }
    defaults.update(overrides)
    return ConnectionPoolConfig(**defaults)


def create_acquire_options(**overrides) -> AcquireOptions:
    """Create acquire options for testing"""
    defaults = {
        "host": "api.example.com",
        "port": 443,
        "protocol": "https",
    }
    defaults.update(overrides)
    return AcquireOptions(**defaults)


class TestConnectionPool:
    """Tests for ConnectionPool"""

    class TestConstruction:
        """Tests for pool construction"""

        async def test_creates_pool_with_config(self):
            """Should create pool with config"""
            pool = ConnectionPool(create_config())
            assert pool.id == "test-pool"
            await pool.close()

        async def test_uses_custom_store(self):
            """Should use custom store"""
            store = MemoryConnectionStore()
            pool = ConnectionPool(create_config(), store)
            assert pool.id == "test-pool"
            await pool.close()

        async def test_starts_health_check_when_enabled(self):
            """Should start health check when enabled"""
            pool = ConnectionPool(
                create_config(
                    enable_health_check=True,
                    health_check_interval_seconds=0.1,
                )
            )

            # Wait for health check to run
            await asyncio.sleep(0.15)

            # Pool should still be operational
            acquired = await pool.acquire(create_acquire_options())
            assert acquired.connection is not None
            await acquired.release()
            await pool.close()

    class TestAcquire:
        """Tests for acquire method"""

        async def test_creates_new_connection_when_empty(self):
            """Should create new connection when pool is empty"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())

            assert acquired.connection is not None
            assert acquired.connection.host == "api.example.com"
            assert acquired.connection.port == 443
            assert acquired.connection.protocol == "https"

            await acquired.release()
            await pool.close()

        async def test_reuses_idle_connection(self):
            """Should reuse idle connection"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options())
            connection_id = acquired1.connection.id
            await acquired1.release()

            acquired2 = await pool.acquire(create_acquire_options())

            assert acquired2.connection.id == connection_id
            assert acquired2.connection.request_count > 1

            await acquired2.release()
            await pool.close()

        async def test_creates_connection_for_different_host(self):
            """Should create connection for different host"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options(host="api1.example.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="api2.example.com"))

            assert acquired1.connection.id != acquired2.connection.id
            assert acquired1.connection.host == "api1.example.com"
            assert acquired2.connection.host == "api2.example.com"

            await acquired1.release()
            await acquired2.release()
            await pool.close()

        async def test_throws_when_pool_closed(self):
            """Should throw when pool is closed"""
            pool = ConnectionPool(create_config())
            await pool.close()

            with pytest.raises(RuntimeError, match="Connection pool is closed"):
                await pool.acquire(create_acquire_options())

        async def test_respects_max_connections_limit(self):
            """Should respect maxConnections limit"""
            pool = ConnectionPool(
                create_config(
                    max_connections=2,
                    max_connections_per_host=2,
                    queue_requests=False,
                )
            )

            acquired1 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="b.com"))

            with pytest.raises(RuntimeError, match="Connection pool is full"):
                await pool.acquire(create_acquire_options(host="c.com"))

            await acquired1.release()
            await acquired2.release()
            await pool.close()

        async def test_respects_max_connections_per_host_limit(self):
            """Should respect maxConnectionsPerHost limit"""
            pool = ConnectionPool(
                create_config(
                    max_connections=10,
                    max_connections_per_host=2,
                    queue_requests=False,
                )
            )

            acquired1 = await pool.acquire(create_acquire_options())
            acquired2 = await pool.acquire(create_acquire_options())

            with pytest.raises(RuntimeError, match="Connection pool is full"):
                await pool.acquire(create_acquire_options())

            await acquired1.release()
            await acquired2.release()
            await pool.close()

        async def test_includes_metadata_in_connection(self):
            """Should include metadata in connection"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(
                create_acquire_options(
                    metadata={"request_id": "123", "user_id": "user-1"}
                )
            )

            assert acquired.connection.metadata == {"request_id": "123", "user_id": "user-1"}

            await acquired.release()
            await pool.close()

    class TestQueueLogic:
        """Tests for queue logic"""

        async def test_queues_request_when_at_capacity(self):
            """Should queue request when at capacity"""
            pool = ConnectionPool(
                create_config(
                    max_connections=2,
                    max_connections_per_host=2,
                    queue_requests=True,
                    max_queue_size=10,
                    queue_timeout_seconds=5.0,
                )
            )

            acquired1 = await pool.acquire(create_acquire_options())
            acquired2 = await pool.acquire(create_acquire_options())

            # This should be queued
            acquire_task = asyncio.create_task(pool.acquire(create_acquire_options()))

            # Wait for task to be queued
            await asyncio.sleep(0.01)

            # Release one to allow queued request
            await acquired1.release()

            acquired3 = await acquire_task
            assert acquired3.connection is not None

            await acquired2.release()
            await acquired3.release()
            await pool.close()

        async def test_times_out_queued_requests(self):
            """Should timeout queued requests"""
            pool = ConnectionPool(
                create_config(
                    max_connections=1,
                    max_connections_per_host=1,
                    queue_requests=True,
                    queue_timeout_seconds=0.1,
                )
            )

            acquired = await pool.acquire(create_acquire_options())

            with pytest.raises(TimeoutError, match="Connection acquisition timed out"):
                await pool.acquire(create_acquire_options())

            await acquired.release()
            await pool.close()

        async def test_respects_custom_timeout_in_options(self):
            """Should respect custom timeout in options"""
            pool = ConnectionPool(
                create_config(
                    max_connections=1,
                    max_connections_per_host=1,
                    queue_requests=True,
                    queue_timeout_seconds=10.0,  # long default
                )
            )

            acquired = await pool.acquire(create_acquire_options())

            # Use short timeout in options
            with pytest.raises(TimeoutError, match="Connection acquisition timed out"):
                await pool.acquire(create_acquire_options(timeout_seconds=0.05))

            await acquired.release()
            await pool.close()

        async def test_throws_when_queue_full(self):
            """Should throw when queue is full"""
            pool = ConnectionPool(
                create_config(
                    max_connections=1,
                    max_connections_per_host=1,
                    queue_requests=True,
                    max_queue_size=1,
                    queue_timeout_seconds=10.0,
                )
            )

            acquired = await pool.acquire(create_acquire_options())

            # Fill the queue
            queued = asyncio.create_task(pool.acquire(create_acquire_options()))
            await asyncio.sleep(0.01)

            # This should fail
            with pytest.raises(RuntimeError, match="Request queue is full"):
                await pool.acquire(create_acquire_options())

            await acquired.release()
            await queued
            await pool.close()

        async def test_skips_unhealthy_connections(self):
            """Should skip unhealthy connections when reusing"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options())
            await acquired1.fail(Exception("Connection failed"))

            # Should create new connection, not reuse unhealthy one
            acquired2 = await pool.acquire(create_acquire_options())
            assert acquired2.connection.health.value == "healthy"

            await acquired2.release()
            await pool.close()

    class TestRelease:
        """Tests for release method"""

        async def test_marks_connection_as_idle(self):
            """Should mark connection as idle"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())
            assert acquired.connection.state.value == "active"

            await acquired.release()

            stats = await pool.get_stats()
            assert stats.idle_connections == 1
            assert stats.active_connections == 0

            await pool.close()

        async def test_closes_connection_if_pool_closed(self):
            """Should close connection if pool is closed"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())
            await pool.close()

            # Release after close should not error
            await acquired.release()

            stats = await pool.get_stats()
            assert stats.idle_connections == 0

        async def test_closes_connection_if_too_old(self):
            """Should close connection if too old"""
            pool = ConnectionPool(create_config(max_connection_age_seconds=0.0))

            acquired = await pool.acquire(create_acquire_options())

            # Wait for connection to age
            await asyncio.sleep(0.01)

            await acquired.release()

            stats = await pool.get_stats()
            assert stats.total_closed == 1

            await pool.close()

        async def test_closes_connection_if_too_many_idle(self):
            """Should close connection if too many idle"""
            pool = ConnectionPool(create_config(max_idle_connections=1))

            acquired1 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="b.com"))

            await acquired1.release()
            await acquired2.release()

            stats = await pool.get_stats()
            assert stats.idle_connections == 1
            assert stats.total_closed == 1

            await pool.close()

    class TestFail:
        """Tests for fail method"""

        async def test_marks_connection_as_unhealthy_and_closes(self):
            """Should mark connection as unhealthy and close it"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())
            await acquired.fail(Exception("Test error"))

            stats = await pool.get_stats()
            assert stats.failed_connections == 1
            assert stats.total_closed == 1

            await pool.close()

        async def test_works_without_error_argument(self):
            """Should work without error argument"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())
            await acquired.fail()

            stats = await pool.get_stats()
            assert stats.failed_connections == 1

            await pool.close()

    class TestGetStats:
        """Tests for getStats method"""

        async def test_returns_correct_stats_for_empty_pool(self):
            """Should return correct stats for empty pool"""
            pool = ConnectionPool(create_config())

            stats = await pool.get_stats()

            assert stats.total_created == 0
            assert stats.total_closed == 0
            assert stats.active_connections == 0
            assert stats.idle_connections == 0
            assert stats.pending_requests == 0
            assert stats.total_requests == 0
            assert stats.failed_connections == 0
            assert stats.timed_out_connections == 0
            assert stats.avg_connection_age_seconds == 0
            assert stats.avg_request_duration_seconds == 0
            assert stats.hit_ratio == 0

            await pool.close()

        async def test_tracks_active_and_idle_connections(self):
            """Should track active and idle connections"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="b.com"))
            await acquired1.release()

            stats = await pool.get_stats()

            assert stats.active_connections == 1
            assert stats.idle_connections == 1
            assert stats.total_created == 2

            await acquired2.release()
            await pool.close()

        async def test_tracks_connections_by_host(self):
            """Should track connections by host"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired3 = await pool.acquire(create_acquire_options(host="b.com"))

            stats = await pool.get_stats()

            assert stats.connections_by_host["a.com:443"] == 2
            assert stats.connections_by_host["b.com:443"] == 1

            await acquired1.release()
            await acquired2.release()
            await acquired3.release()
            await pool.close()

        async def test_calculates_hit_ratio(self):
            """Should calculate hit ratio"""
            pool = ConnectionPool(create_config())

            # First request creates connection
            acquired1 = await pool.acquire(create_acquire_options())
            await acquired1.release()

            # Second request reuses connection
            acquired2 = await pool.acquire(create_acquire_options())
            await acquired2.release()

            # Third request reuses connection
            acquired3 = await pool.acquire(create_acquire_options())
            await acquired3.release()

            stats = await pool.get_stats()

            # 1 created, 3 total requests = 2/3 hit ratio
            assert abs(stats.hit_ratio - 0.667) < 0.01

            await pool.close()

    class TestDrain:
        """Tests for drain method"""

        async def test_rejects_pending_requests(self):
            """Should reject pending requests"""
            pool = ConnectionPool(
                create_config(
                    max_connections=1,
                    max_connections_per_host=1,
                    queue_requests=True,
                    queue_timeout_seconds=10.0,
                )
            )

            acquired = await pool.acquire(create_acquire_options())

            # Start pending request
            pending = asyncio.create_task(pool.acquire(create_acquire_options()))
            await asyncio.sleep(0.01)

            # Drain should reject pending
            await pool.drain()

            with pytest.raises(RuntimeError, match="Pool is draining"):
                await pending

            await acquired.release()
            await pool.close()

    class TestClose:
        """Tests for close method"""

        async def test_closes_all_connections(self):
            """Should close all connections"""
            pool = ConnectionPool(create_config())

            acquired1 = await pool.acquire(create_acquire_options(host="a.com"))
            acquired2 = await pool.acquire(create_acquire_options(host="b.com"))
            await acquired1.release()

            await pool.close()

            stats = await pool.get_stats()
            assert stats.active_connections == 0
            assert stats.idle_connections == 0

        async def test_is_idempotent(self):
            """Should be idempotent"""
            pool = ConnectionPool(create_config())

            await pool.close()
            await pool.close()  # Should not throw

        async def test_stops_health_check(self):
            """Should stop health check"""
            pool = ConnectionPool(
                create_config(
                    enable_health_check=True,
                    health_check_interval_seconds=0.05,
                )
            )

            await pool.close()

            # Wait to ensure no health check runs
            await asyncio.sleep(0.1)
            # Should be closed without errors

    class TestEventListeners:
        """Tests for event listeners"""

        async def test_emits_connection_created_event(self):
            """Should emit connection:created event"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.CONNECTION_CREATED, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.CONNECTION_CREATED
            assert events[0].connection_id == acquired.connection.id
            assert events[0].host == "api.example.com"

            await acquired.release()
            await pool.close()

        async def test_emits_connection_acquired_event(self):
            """Should emit connection:acquired event"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.CONNECTION_ACQUIRED, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.CONNECTION_ACQUIRED

            await acquired.release()
            await pool.close()

        async def test_emits_connection_released_event(self):
            """Should emit connection:released event"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.CONNECTION_RELEASED, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())
            await acquired.release()

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.CONNECTION_RELEASED

            await pool.close()

        async def test_emits_connection_closed_event(self):
            """Should emit connection:closed event"""
            pool = ConnectionPool(create_config(max_idle_connections=0))
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.CONNECTION_CLOSED, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())
            await acquired.release()

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.CONNECTION_CLOSED

            await pool.close()

        async def test_emits_connection_error_event(self):
            """Should emit connection:error event"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.CONNECTION_ERROR, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())
            await acquired.fail(Exception("Test error"))

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.CONNECTION_ERROR
            assert events[0].data["error"] == "Test error"

            await pool.close()

        async def test_emits_pool_full_event(self):
            """Should emit pool:full event"""
            pool = ConnectionPool(
                create_config(max_connections=1, queue_requests=False)
            )
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.POOL_FULL, lambda e: events.append(e))

            acquired = await pool.acquire(create_acquire_options())

            try:
                await pool.acquire(create_acquire_options())
            except RuntimeError:
                pass

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.POOL_FULL

            await acquired.release()
            await pool.close()

        async def test_emits_pool_drained_event(self):
            """Should emit pool:drained event"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []
            pool.on(ConnectionPoolEventType.POOL_DRAINED, lambda e: events.append(e))

            await pool.drain()

            assert len(events) == 1
            assert events[0].type == ConnectionPoolEventType.POOL_DRAINED

            await pool.close()

        async def test_allows_removing_listeners(self):
            """Should allow removing listeners"""
            pool = ConnectionPool(create_config())
            events: List[ConnectionPoolEvent] = []

            def listener(e: ConnectionPoolEvent):
                events.append(e)

            pool.on(ConnectionPoolEventType.CONNECTION_CREATED, listener)
            pool.off(ConnectionPoolEventType.CONNECTION_CREATED, listener)

            acquired = await pool.acquire(create_acquire_options())

            assert len(events) == 0

            await acquired.release()
            await pool.close()

        async def test_handles_listener_errors_gracefully(self):
            """Should handle listener errors gracefully"""
            pool = ConnectionPool(create_config())

            def bad_listener(e: ConnectionPoolEvent):
                raise Exception("Listener error")

            pool.on(ConnectionPoolEventType.CONNECTION_CREATED, bad_listener)

            # Should not throw
            acquired = await pool.acquire(create_acquire_options())
            assert acquired.connection is not None

            await acquired.release()
            await pool.close()

    class TestRequestDurationTracking:
        """Tests for request duration tracking"""

        async def test_tracks_request_duration(self):
            """Should track request duration"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())

            # Simulate request time
            await asyncio.sleep(0.05)

            await acquired.release()

            stats = await pool.get_stats()
            assert stats.avg_request_duration_seconds >= 0.05

            await pool.close()

        async def test_tracks_duration_on_failure(self):
            """Should track duration even on failure"""
            pool = ConnectionPool(create_config())

            acquired = await pool.acquire(create_acquire_options())

            # Simulate request time
            await asyncio.sleep(0.05)

            await acquired.fail(Exception("Test"))

            stats = await pool.get_stats()
            assert stats.avg_request_duration_seconds >= 0.05

            await pool.close()
