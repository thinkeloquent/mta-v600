"""
Tests for connection_pool memory store

Coverage includes:
- State Transition Testing: Connection state changes
- CRUD operations coverage
- Concurrent operations testing
- Boundary conditions for eviction
"""

import time
import pytest
import asyncio

from connection_pool.stores.memory import MemoryConnectionStore
from connection_pool.types import (
    PooledConnection,
    ConnectionState,
    HealthStatus,
)


def create_connection(**overrides) -> PooledConnection:
    """Create a test connection with optional overrides"""
    now = time.time()
    defaults = {
        "id": f"conn-{int(now * 1000)}-{hash(str(now)) % 1000000:06d}",
        "host": "example.com",
        "port": 443,
        "state": ConnectionState.IDLE,
        "health": HealthStatus.HEALTHY,
        "created_at": now,
        "last_used_at": now,
        "request_count": 0,
        "protocol": "https",
        "metadata": None,
    }
    defaults.update(overrides)
    return PooledConnection(**defaults)


class TestMemoryConnectionStore:
    """Tests for MemoryConnectionStore"""

    @pytest.fixture
    def store(self):
        """Create a fresh store for each test"""
        return MemoryConnectionStore()

    class TestCRUDOperations:
        """Tests for CRUD operations"""

        class TestAddConnection:
            """Tests for addConnection"""

            async def test_adds_connection(self):
                """Should add a connection"""
                store = MemoryConnectionStore()
                conn = create_connection()
                await store.add_connection(conn)

                connections = await store.get_connections()
                assert len(connections) == 1
                assert connections[0].id == conn.id

            async def test_adds_multiple_connections(self):
                """Should add multiple connections"""
                store = MemoryConnectionStore()
                conn1 = create_connection(id="conn-1")
                conn2 = create_connection(id="conn-2")

                await store.add_connection(conn1)
                await store.add_connection(conn2)

                connections = await store.get_connections()
                assert len(connections) == 2

            async def test_tracks_connections_by_host(self):
                """Should track connections by host"""
                store = MemoryConnectionStore()
                conn1 = create_connection(id="conn-1", host="api.example.com", port=443)
                conn2 = create_connection(id="conn-2", host="api.example.com", port=443)
                conn3 = create_connection(id="conn-3", host="other.example.com", port=443)

                await store.add_connection(conn1)
                await store.add_connection(conn2)
                await store.add_connection(conn3)

                api_connections = await store.get_connections_by_host("api.example.com:443")
                assert len(api_connections) == 2

                other_connections = await store.get_connections_by_host("other.example.com:443")
                assert len(other_connections) == 1

        class TestGetConnections:
            """Tests for getConnections"""

            async def test_returns_empty_when_no_connections(self):
                """Should return empty array when no connections"""
                store = MemoryConnectionStore()
                connections = await store.get_connections()
                assert connections == []

            async def test_returns_all_connections(self):
                """Should return all connections"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1"))
                await store.add_connection(create_connection(id="conn-2"))
                await store.add_connection(create_connection(id="conn-3"))

                connections = await store.get_connections()
                assert len(connections) == 3

        class TestGetConnectionsByHost:
            """Tests for getConnectionsByHost"""

            async def test_returns_empty_for_unknown_host(self):
                """Should return empty array for unknown host"""
                store = MemoryConnectionStore()
                connections = await store.get_connections_by_host("unknown.com:443")
                assert connections == []

            async def test_filters_by_host_key(self):
                """Should filter by host key correctly"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1", host="a.com", port=80))
                await store.add_connection(create_connection(id="conn-2", host="a.com", port=443))
                await store.add_connection(create_connection(id="conn-3", host="b.com", port=80))

                assert len(await store.get_connections_by_host("a.com:80")) == 1
                assert len(await store.get_connections_by_host("a.com:443")) == 1
                assert len(await store.get_connections_by_host("b.com:80")) == 1

        class TestUpdateConnection:
            """Tests for updateConnection"""

            async def test_updates_properties(self):
                """Should update connection properties"""
                store = MemoryConnectionStore()
                conn = create_connection(id="conn-1", state=ConnectionState.IDLE)
                await store.add_connection(conn)

                await store.update_connection("conn-1", {
                    "state": ConnectionState.ACTIVE,
                    "request_count": 5,
                })

                connections = await store.get_connections()
                assert connections[0].state == ConnectionState.ACTIVE
                assert connections[0].request_count == 5

            async def test_does_nothing_for_nonexistent(self):
                """Should do nothing for non-existent connection"""
                store = MemoryConnectionStore()
                await store.update_connection("non-existent", {"state": ConnectionState.ACTIVE})
                connections = await store.get_connections()
                assert len(connections) == 0

            async def test_updates_host_index_on_host_change(self):
                """Should update host index when host changes"""
                store = MemoryConnectionStore()
                conn = create_connection(id="conn-1", host="old.com", port=80)
                await store.add_connection(conn)

                await store.update_connection("conn-1", {"host": "new.com"})

                assert len(await store.get_connections_by_host("old.com:80")) == 0
                assert len(await store.get_connections_by_host("new.com:80")) == 1

            async def test_updates_host_index_on_port_change(self):
                """Should update host index when port changes"""
                store = MemoryConnectionStore()
                conn = create_connection(id="conn-1", host="example.com", port=80)
                await store.add_connection(conn)

                await store.update_connection("conn-1", {"port": 443})

                assert len(await store.get_connections_by_host("example.com:80")) == 0
                assert len(await store.get_connections_by_host("example.com:443")) == 1

        class TestRemoveConnection:
            """Tests for removeConnection"""

            async def test_removes_connection(self):
                """Should remove connection"""
                store = MemoryConnectionStore()
                conn = create_connection(id="conn-1")
                await store.add_connection(conn)

                removed = await store.remove_connection("conn-1")

                assert removed is True
                assert len(await store.get_connections()) == 0

            async def test_returns_false_for_nonexistent(self):
                """Should return false for non-existent connection"""
                store = MemoryConnectionStore()
                removed = await store.remove_connection("non-existent")
                assert removed is False

            async def test_removes_from_host_index(self):
                """Should remove from host index"""
                store = MemoryConnectionStore()
                conn = create_connection(id="conn-1", host="example.com", port=443)
                await store.add_connection(conn)

                await store.remove_connection("conn-1")

                assert len(await store.get_connections_by_host("example.com:443")) == 0

        class TestGetCount:
            """Tests for getCount"""

            async def test_returns_zero_for_empty(self):
                """Should return 0 for empty store"""
                store = MemoryConnectionStore()
                assert await store.get_count() == 0

            async def test_returns_correct_count(self):
                """Should return correct count"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1"))
                await store.add_connection(create_connection(id="conn-2"))

                assert await store.get_count() == 2

            async def test_updates_after_removal(self):
                """Should update count after removal"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1"))
                await store.add_connection(create_connection(id="conn-2"))
                await store.remove_connection("conn-1")

                assert await store.get_count() == 1

        class TestGetCountByHost:
            """Tests for getCountByHost"""

            async def test_returns_zero_for_unknown_host(self):
                """Should return 0 for unknown host"""
                store = MemoryConnectionStore()
                assert await store.get_count_by_host("unknown.com:443") == 0

            async def test_returns_correct_count_per_host(self):
                """Should return correct count per host"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1", host="a.com", port=80))
                await store.add_connection(create_connection(id="conn-2", host="a.com", port=80))
                await store.add_connection(create_connection(id="conn-3", host="b.com", port=80))

                assert await store.get_count_by_host("a.com:80") == 2
                assert await store.get_count_by_host("b.com:80") == 1

        class TestClear:
            """Tests for clear"""

            async def test_removes_all_connections(self):
                """Should remove all connections"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1"))
                await store.add_connection(create_connection(id="conn-2"))

                await store.clear()

                assert len(await store.get_connections()) == 0
                assert await store.get_count() == 0

            async def test_clears_host_index(self):
                """Should clear host index"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1", host="a.com", port=80))
                await store.add_connection(create_connection(id="conn-2", host="b.com", port=80))

                await store.clear()

                assert len(await store.get_connections_by_host("a.com:80")) == 0
                assert len(await store.get_connections_by_host("b.com:80")) == 0

        class TestClose:
            """Tests for close"""

            async def test_clears_all_data(self):
                """Should clear all data"""
                store = MemoryConnectionStore()
                await store.add_connection(create_connection(id="conn-1"))

                await store.close()

                assert len(await store.get_connections()) == 0

    class TestStateTransition:
        """State Transition Testing"""

        async def test_idle_to_active_transition(self):
            """Should track idle -> active transition"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", state=ConnectionState.IDLE)
            await store.add_connection(conn)

            await store.update_connection("conn-1", {"state": ConnectionState.ACTIVE})

            connections = await store.get_connections()
            assert connections[0].state == ConnectionState.ACTIVE

        async def test_active_to_idle_transition(self):
            """Should track active -> idle transition"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", state=ConnectionState.ACTIVE)
            await store.add_connection(conn)

            await store.update_connection("conn-1", {"state": ConnectionState.IDLE})

            connections = await store.get_connections()
            assert connections[0].state == ConnectionState.IDLE

        async def test_idle_to_draining_transition(self):
            """Should track idle -> draining transition"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", state=ConnectionState.IDLE)
            await store.add_connection(conn)

            await store.update_connection("conn-1", {"state": ConnectionState.DRAINING})

            connections = await store.get_connections()
            assert connections[0].state == ConnectionState.DRAINING

        async def test_any_to_closed_transition(self):
            """Should track any -> closed transition"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", state=ConnectionState.ACTIVE)
            await store.add_connection(conn)

            await store.update_connection("conn-1", {"state": ConnectionState.CLOSED})

            connections = await store.get_connections()
            assert connections[0].state == ConnectionState.CLOSED

        async def test_health_status_transitions(self):
            """Should track health status transitions"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", health=HealthStatus.HEALTHY)
            await store.add_connection(conn)

            await store.update_connection("conn-1", {"health": HealthStatus.UNHEALTHY})
            connections = await store.get_connections()
            assert connections[0].health == HealthStatus.UNHEALTHY

            await store.update_connection("conn-1", {"health": HealthStatus.UNKNOWN})
            connections = await store.get_connections()
            assert connections[0].health == HealthStatus.UNKNOWN

            await store.update_connection("conn-1", {"health": HealthStatus.HEALTHY})
            connections = await store.get_connections()
            assert connections[0].health == HealthStatus.HEALTHY

    class TestGetIdleConnections:
        """Tests for getIdleConnections"""

        async def test_returns_only_idle_connections(self):
            """Should return only idle connections"""
            store = MemoryConnectionStore()
            await store.add_connection(create_connection(id="conn-1", state=ConnectionState.IDLE))
            await store.add_connection(create_connection(id="conn-2", state=ConnectionState.ACTIVE))
            await store.add_connection(create_connection(id="conn-3", state=ConnectionState.IDLE))

            idle = await store.get_idle_connections()

            assert len(idle) == 2
            assert all(c.state == ConnectionState.IDLE for c in idle)

        async def test_sorts_by_last_used_oldest_first(self):
            """Should sort by last used time (oldest first)"""
            store = MemoryConnectionStore()
            now = time.time()
            await store.add_connection(
                create_connection(id="conn-1", state=ConnectionState.IDLE, last_used_at=now - 1.0)
            )
            await store.add_connection(
                create_connection(id="conn-2", state=ConnectionState.IDLE, last_used_at=now - 3.0)
            )
            await store.add_connection(
                create_connection(id="conn-3", state=ConnectionState.IDLE, last_used_at=now - 2.0)
            )

            idle = await store.get_idle_connections()

            assert idle[0].id == "conn-2"  # oldest
            assert idle[1].id == "conn-3"
            assert idle[2].id == "conn-1"  # newest

        async def test_returns_empty_when_no_idle(self):
            """Should return empty array when no idle connections"""
            store = MemoryConnectionStore()
            await store.add_connection(create_connection(id="conn-1", state=ConnectionState.ACTIVE))

            idle = await store.get_idle_connections()
            assert len(idle) == 0

    class TestGetExpiredConnections:
        """Tests for getExpiredConnections"""

        async def test_returns_connections_older_than_max_age(self):
            """Should return connections older than max age"""
            store = MemoryConnectionStore()
            now = time.time()
            await store.add_connection(
                create_connection(id="conn-1", created_at=now - 10.0)  # 10 seconds old
            )
            await store.add_connection(
                create_connection(id="conn-2", created_at=now - 5.0)  # 5 seconds old
            )
            await store.add_connection(
                create_connection(id="conn-3", created_at=now - 1.0)  # 1 second old
            )

            expired = await store.get_expired_connections(6.0)  # 6 second max age

            assert len(expired) == 1
            assert expired[0].id == "conn-1"

        async def test_returns_empty_when_no_expired(self):
            """Should return empty array when no expired connections"""
            store = MemoryConnectionStore()
            now = time.time()
            await store.add_connection(create_connection(id="conn-1", created_at=now))

            expired = await store.get_expired_connections(60.0)
            assert len(expired) == 0

    class TestGetTimedOutConnections:
        """Tests for getTimedOutConnections"""

        async def test_returns_idle_connections_past_timeout(self):
            """Should return idle connections past timeout"""
            store = MemoryConnectionStore()
            now = time.time()
            await store.add_connection(
                create_connection(
                    id="conn-1", state=ConnectionState.IDLE, last_used_at=now - 10.0
                )
            )
            await store.add_connection(
                create_connection(
                    id="conn-2", state=ConnectionState.IDLE, last_used_at=now - 1.0
                )
            )
            await store.add_connection(
                create_connection(
                    id="conn-3", state=ConnectionState.ACTIVE, last_used_at=now - 10.0
                )
            )

            timed_out = await store.get_timed_out_connections(5.0)

            assert len(timed_out) == 1
            assert timed_out[0].id == "conn-1"

        async def test_does_not_include_active_connections(self):
            """Should not include active connections"""
            store = MemoryConnectionStore()
            now = time.time()
            await store.add_connection(
                create_connection(
                    id="conn-1", state=ConnectionState.ACTIVE, last_used_at=now - 10.0
                )
            )

            timed_out = await store.get_timed_out_connections(5.0)
            assert len(timed_out) == 0

    class TestConcurrentOperations:
        """Tests for concurrent operations"""

        async def test_handles_concurrent_adds(self):
            """Should handle concurrent adds"""
            store = MemoryConnectionStore()

            async def add_connection(i):
                await store.add_connection(create_connection(id=f"conn-{i}"))

            await asyncio.gather(*[add_connection(i) for i in range(100)])

            assert await store.get_count() == 100

        async def test_handles_concurrent_removes(self):
            """Should handle concurrent removes"""
            store = MemoryConnectionStore()

            # Add 100 connections
            for i in range(100):
                await store.add_connection(create_connection(id=f"conn-{i}"))

            # Remove 50 concurrently
            async def remove_connection(i):
                await store.remove_connection(f"conn-{i}")

            await asyncio.gather(*[remove_connection(i) for i in range(50)])

            assert await store.get_count() == 50

        async def test_handles_mixed_operations(self):
            """Should handle mixed operations"""
            store = MemoryConnectionStore()

            # Add 20 connections
            for i in range(20):
                await store.add_connection(create_connection(id=f"conn-{i}"))

            # Mix of removes and updates
            operations = []
            for i in range(10):
                operations.append(store.remove_connection(f"conn-{i}"))
                operations.append(
                    store.update_connection(f"conn-{i + 10}", {"state": ConnectionState.ACTIVE})
                )

            await asyncio.gather(*operations)

            count = await store.get_count()
            assert count == 10

    class TestBoundaryConditions:
        """Tests for boundary conditions"""

        async def test_handles_empty_string_connection_id(self):
            """Should handle empty string connection ID"""
            store = MemoryConnectionStore()
            conn = create_connection(id="")
            await store.add_connection(conn)

            assert await store.get_count() == 1

            removed = await store.remove_connection("")
            assert removed is True

        async def test_handles_very_long_connection_id(self):
            """Should handle very long connection ID"""
            store = MemoryConnectionStore()
            long_id = "conn-" + "a" * 1000
            conn = create_connection(id=long_id)
            await store.add_connection(conn)

            assert await store.get_count() == 1

        async def test_handles_port_zero(self):
            """Should handle port 0"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", host="example.com", port=0)
            await store.add_connection(conn)

            connections = await store.get_connections_by_host("example.com:0")
            assert len(connections) == 1

        async def test_handles_maximum_port(self):
            """Should handle maximum port number"""
            store = MemoryConnectionStore()
            conn = create_connection(id="conn-1", host="example.com", port=65535)
            await store.add_connection(conn)

            connections = await store.get_connections_by_host("example.com:65535")
            assert len(connections) == 1
