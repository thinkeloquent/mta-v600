"""
Tests for connection_pool config module

Coverage includes:
- Decision/Branch Coverage: All branches in validation logic
- Boundary Value Analysis: Edge cases for numeric limits
- Equivalence Partitioning: Valid/invalid configuration values
"""

import time
import pytest

from connection_pool.config import (
    DEFAULT_CONNECTION_POOL_CONFIG,
    merge_config,
    validate_config,
    get_host_key,
    parse_host_key,
    generate_connection_id,
)
from connection_pool.types import ConnectionPoolConfig


class TestDefaultConnectionPoolConfig:
    """Tests for default configuration values"""

    def test_default_id(self):
        """Should have default pool ID"""
        assert DEFAULT_CONNECTION_POOL_CONFIG.id == "default-pool"

    def test_default_connection_limits(self):
        """Should have sensible connection limits"""
        assert DEFAULT_CONNECTION_POOL_CONFIG.max_connections == 100
        assert DEFAULT_CONNECTION_POOL_CONFIG.max_connections_per_host == 10
        assert DEFAULT_CONNECTION_POOL_CONFIG.max_idle_connections == 20

    def test_default_timeouts(self):
        """Should have sensible timeout defaults"""
        assert DEFAULT_CONNECTION_POOL_CONFIG.idle_timeout_seconds == 60.0
        assert DEFAULT_CONNECTION_POOL_CONFIG.keep_alive_timeout_seconds == 30.0
        assert DEFAULT_CONNECTION_POOL_CONFIG.connect_timeout_seconds == 10.0

    def test_default_health_check(self):
        """Should have health check enabled by default"""
        assert DEFAULT_CONNECTION_POOL_CONFIG.enable_health_check is True
        assert DEFAULT_CONNECTION_POOL_CONFIG.health_check_interval_seconds == 30.0
        assert DEFAULT_CONNECTION_POOL_CONFIG.max_connection_age_seconds == 300.0

    def test_default_queue_settings(self):
        """Should have queue enabled by default"""
        assert DEFAULT_CONNECTION_POOL_CONFIG.queue_requests is True
        assert DEFAULT_CONNECTION_POOL_CONFIG.max_queue_size == 1000
        assert DEFAULT_CONNECTION_POOL_CONFIG.queue_timeout_seconds == 30.0


class TestMergeConfig:
    """Tests for merge_config function"""

    def test_returns_user_config(self):
        """Should return user config as-is"""
        user_config = ConnectionPoolConfig(
            id="custom-pool",
            max_connections=50,
        )

        merged = merge_config(user_config)

        assert merged.id == "custom-pool"
        assert merged.max_connections == 50

    def test_preserves_all_fields(self):
        """Should preserve all user-specified fields"""
        user_config = ConnectionPoolConfig(
            id="full-custom",
            max_connections=200,
            max_connections_per_host=20,
            max_idle_connections=50,
            idle_timeout_seconds=120.0,
            keep_alive=False,
        )

        merged = merge_config(user_config)

        assert merged.max_connections == 200
        assert merged.max_connections_per_host == 20
        assert merged.max_idle_connections == 50
        assert merged.idle_timeout_seconds == 120.0
        assert merged.keep_alive is False


class TestValidateConfig:
    """Tests for validate_config function"""

    class TestDecisionBranch:
        """Decision/Branch Coverage tests"""

        def test_valid_config_returns_empty_errors(self):
            """Should return empty array for valid config"""
            config = ConnectionPoolConfig(
                id="valid-pool",
                max_connections=100,
                max_connections_per_host=10,
                max_idle_connections=20,
            )

            errors = validate_config(config)
            assert errors == []

        def test_max_connections_less_than_one(self):
            """Should detect maxConnections < 1"""
            config = ConnectionPoolConfig(id="test", max_connections=0)

            errors = validate_config(config)
            assert "max_connections must be at least 1" in errors

        def test_max_connections_per_host_less_than_one(self):
            """Should detect maxConnectionsPerHost < 1"""
            config = ConnectionPoolConfig(id="test", max_connections_per_host=0)

            errors = validate_config(config)
            assert "max_connections_per_host must be at least 1" in errors

        def test_negative_max_idle_connections(self):
            """Should detect negative maxIdleConnections"""
            config = ConnectionPoolConfig(id="test", max_idle_connections=-1)

            errors = validate_config(config)
            assert "max_idle_connections must be non-negative" in errors

        def test_negative_idle_timeout(self):
            """Should detect negative idleTimeoutSeconds"""
            config = ConnectionPoolConfig(id="test", idle_timeout_seconds=-1.0)

            errors = validate_config(config)
            assert "idle_timeout_seconds must be non-negative" in errors

        def test_negative_keep_alive_timeout(self):
            """Should detect negative keepAliveTimeoutSeconds"""
            config = ConnectionPoolConfig(id="test", keep_alive_timeout_seconds=-1.0)

            errors = validate_config(config)
            assert "keep_alive_timeout_seconds must be non-negative" in errors

        def test_negative_connect_timeout(self):
            """Should detect negative connectTimeoutSeconds"""
            config = ConnectionPoolConfig(id="test", connect_timeout_seconds=-1.0)

            errors = validate_config(config)
            assert "connect_timeout_seconds must be non-negative" in errors

        def test_health_check_interval_too_small(self):
            """Should detect healthCheckIntervalSeconds < 1.0"""
            config = ConnectionPoolConfig(id="test", health_check_interval_seconds=0.5)

            errors = validate_config(config)
            assert "health_check_interval_seconds must be at least 1.0" in errors

        def test_negative_max_connection_age(self):
            """Should detect negative maxConnectionAgeSeconds"""
            config = ConnectionPoolConfig(id="test", max_connection_age_seconds=-1.0)

            errors = validate_config(config)
            assert "max_connection_age_seconds must be non-negative" in errors

        def test_negative_max_queue_size(self):
            """Should detect negative maxQueueSize"""
            config = ConnectionPoolConfig(id="test", max_queue_size=-1)

            errors = validate_config(config)
            assert "max_queue_size must be non-negative" in errors

        def test_negative_queue_timeout(self):
            """Should detect negative queueTimeoutSeconds"""
            config = ConnectionPoolConfig(id="test", queue_timeout_seconds=-1.0)

            errors = validate_config(config)
            assert "queue_timeout_seconds must be non-negative" in errors

    class TestCrossFieldValidation:
        """Cross-field validation tests"""

        def test_max_connections_per_host_exceeds_max_connections(self):
            """Should detect maxConnectionsPerHost > maxConnections"""
            config = ConnectionPoolConfig(
                id="test",
                max_connections=10,
                max_connections_per_host=20,
            )

            errors = validate_config(config)
            assert "max_connections_per_host cannot exceed max_connections" in errors

        def test_max_idle_connections_exceeds_max_connections(self):
            """Should detect maxIdleConnections > maxConnections"""
            config = ConnectionPoolConfig(
                id="test",
                max_connections=10,
                max_idle_connections=20,
            )

            errors = validate_config(config)
            assert "max_idle_connections cannot exceed max_connections" in errors

        def test_equal_max_connections_per_host(self):
            """Should allow maxConnectionsPerHost == maxConnections"""
            config = ConnectionPoolConfig(
                id="test",
                max_connections=10,
                max_connections_per_host=10,
            )

            errors = validate_config(config)
            assert "max_connections_per_host cannot exceed max_connections" not in errors

    class TestBoundaryValueAnalysis:
        """Boundary Value Analysis tests"""

        def test_max_connections_at_minimum(self):
            """Should accept max_connections = 1 (minimum valid)"""
            config = ConnectionPoolConfig(id="test", max_connections=1)

            errors = validate_config(config)
            assert "max_connections must be at least 1" not in errors

        def test_max_idle_connections_at_zero(self):
            """Should accept max_idle_connections = 0 (boundary)"""
            config = ConnectionPoolConfig(id="test", max_idle_connections=0)

            errors = validate_config(config)
            assert "max_idle_connections must be non-negative" not in errors

        def test_health_check_interval_at_minimum(self):
            """Should accept health_check_interval_seconds = 1.0 (minimum valid)"""
            config = ConnectionPoolConfig(id="test", health_check_interval_seconds=1.0)

            errors = validate_config(config)
            assert "health_check_interval_seconds must be at least 1.0" not in errors

        def test_very_large_values(self):
            """Should accept very large values"""
            config = ConnectionPoolConfig(
                id="test",
                max_connections=1000000,
                max_connections_per_host=100000,
                idle_timeout_seconds=86400.0,  # 24 hours
            )

            errors = validate_config(config)
            assert len(errors) == 0

    class TestMultipleErrors:
        """Tests for multiple validation errors"""

        def test_returns_all_errors(self):
            """Should return all errors for invalid config"""
            config = ConnectionPoolConfig(
                id="test",
                max_connections=0,
                max_connections_per_host=0,
                max_idle_connections=-1,
                idle_timeout_seconds=-1.0,
            )

            errors = validate_config(config)
            assert len(errors) >= 4


class TestGetHostKey:
    """Tests for get_host_key function"""

    def test_generates_host_port_format(self):
        """Should generate host:port format"""
        assert get_host_key("example.com", 443) == "example.com:443"
        assert get_host_key("localhost", 8080) == "localhost:8080"

    def test_handles_ipv4_addresses(self):
        """Should handle IPv4 addresses"""
        assert get_host_key("192.168.1.1", 80) == "192.168.1.1:80"

    def test_handles_ipv6_addresses(self):
        """Should handle IPv6 addresses"""
        assert get_host_key("::1", 8080) == "::1:8080"
        assert get_host_key("2001:db8::1", 443) == "2001:db8::1:443"

    def test_handles_subdomains(self):
        """Should handle subdomains"""
        assert get_host_key("sub.domain.example.com", 443) == "sub.domain.example.com:443"


class TestParseHostKey:
    """Tests for parse_host_key function"""

    def test_parses_host_port_format(self):
        """Should parse host:port format"""
        host, port = parse_host_key("example.com:443")
        assert host == "example.com"
        assert port == 443

    def test_parses_localhost(self):
        """Should parse localhost"""
        host, port = parse_host_key("localhost:8080")
        assert host == "localhost"
        assert port == 8080

    def test_handles_ipv4_addresses(self):
        """Should handle IPv4 addresses"""
        host, port = parse_host_key("192.168.1.1:80")
        assert host == "192.168.1.1"
        assert port == 80

    def test_handles_ipv6_addresses(self):
        """Should handle IPv6 addresses (last colon is port)"""
        host, port = parse_host_key("::1:8080")
        assert host == "::1"
        assert port == 8080

    def test_raises_for_invalid_host_key(self):
        """Should raise for invalid host key without colon"""
        with pytest.raises(ValueError, match="Invalid host key: example.com"):
            parse_host_key("example.com")

    def test_inverse_of_get_host_key(self):
        """Should be inverse of get_host_key"""
        original_host = "example.com"
        original_port = 443
        host_key = get_host_key(original_host, original_port)
        parsed_host, parsed_port = parse_host_key(host_key)
        assert parsed_host == original_host
        assert parsed_port == original_port


class TestGenerateConnectionId:
    """Tests for generate_connection_id function"""

    def test_generates_unique_ids(self):
        """Should generate unique IDs"""
        ids = set()
        for _ in range(1000):
            ids.add(generate_connection_id())
        assert len(ids) == 1000

    def test_starts_with_conn_prefix(self):
        """Should start with 'conn-' prefix"""
        conn_id = generate_connection_id()
        assert conn_id.startswith("conn-")

    def test_contains_timestamp(self):
        """Should contain timestamp"""
        before = int(time.time() * 1000)
        conn_id = generate_connection_id()
        after = int(time.time() * 1000)

        # Extract timestamp from ID (conn-{timestamp}-{random})
        parts = conn_id.split("-")
        timestamp = int(parts[1])

        assert timestamp >= before
        assert timestamp <= after

    def test_has_random_suffix(self):
        """Should have random suffix"""
        conn_id = generate_connection_id()
        parts = conn_id.split("-")
        assert len(parts) == 3
        assert len(parts[2]) > 0
