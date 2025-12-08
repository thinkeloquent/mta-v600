"""
Tests for cache_dsn configuration utilities

Coverage includes:
- merge_config with defaults
- clamp_ttl boundary conditions
- is_expired timestamp checks
- is_within_grace_period calculations
- select_endpoint for all load balancing strategies
- parse_dsn for various formats
- LoadBalanceState management
"""

import pytest
import time
from cache_dsn.config import (
    merge_config,
    clamp_ttl,
    is_expired,
    is_within_grace_period,
    select_endpoint,
    create_load_balance_state,
    get_endpoint_key,
    parse_dsn,
    LoadBalanceState,
)
from cache_dsn.types import DnsCacheConfig, ResolvedEndpoint, HealthCheckConfig


class TestMergeConfig:
    """Tests for merge_config function"""

    def test_merge_with_missing_health_check(self):
        """Should add default health check config"""
        config = DnsCacheConfig(id="test", default_ttl_seconds=60.0)
        merged = merge_config(config)
        assert merged.health_check is not None
        assert merged.health_check.enabled is False

    def test_merge_with_existing_health_check(self):
        """Should preserve existing health check config"""
        health_check = HealthCheckConfig(enabled=True, interval_seconds=10.0)
        config = DnsCacheConfig(id="test", health_check=health_check)
        merged = merge_config(config)
        assert merged.health_check.enabled is True
        assert merged.health_check.interval_seconds == 10.0

    def test_merge_preserves_all_fields(self):
        """Should preserve all config fields"""
        config = DnsCacheConfig(
            id="test",
            default_ttl_seconds=120.0,
            min_ttl_seconds=5.0,
            max_ttl_seconds=600.0,
            max_entries=500,
            load_balance_strategy="random",
        )
        merged = merge_config(config)
        assert merged.id == "test"
        assert merged.default_ttl_seconds == 120.0
        assert merged.min_ttl_seconds == 5.0
        assert merged.max_ttl_seconds == 600.0
        assert merged.max_entries == 500
        assert merged.load_balance_strategy == "random"


class TestClampTtl:
    """Tests for clamp_ttl function"""

    def test_clamp_within_bounds(self):
        """Should return value when within bounds"""
        result = clamp_ttl(60.0, 1.0, 300.0)
        assert result == 60.0

    def test_clamp_below_min(self):
        """Should clamp to min when below bounds"""
        result = clamp_ttl(0.5, 1.0, 300.0)
        assert result == 1.0

    def test_clamp_above_max(self):
        """Should clamp to max when above bounds"""
        result = clamp_ttl(600.0, 1.0, 300.0)
        assert result == 300.0

    def test_clamp_at_min_boundary(self):
        """Should return value at min boundary"""
        result = clamp_ttl(1.0, 1.0, 300.0)
        assert result == 1.0

    def test_clamp_at_max_boundary(self):
        """Should return value at max boundary"""
        result = clamp_ttl(300.0, 1.0, 300.0)
        assert result == 300.0

    def test_clamp_with_same_min_max(self):
        """Should return bounded value when min equals max"""
        result = clamp_ttl(50.0, 60.0, 60.0)
        assert result == 60.0

    def test_clamp_with_zero(self):
        """Should handle zero TTL"""
        result = clamp_ttl(0.0, 1.0, 300.0)
        assert result == 1.0

    def test_clamp_with_negative(self):
        """Should handle negative TTL"""
        result = clamp_ttl(-10.0, 1.0, 300.0)
        assert result == 1.0


class TestIsExpired:
    """Tests for is_expired function"""

    def test_not_expired(self):
        """Should return False when not expired"""
        future = time.time() + 60
        assert is_expired(future) is False

    def test_expired(self):
        """Should return True when expired"""
        past = time.time() - 60
        assert is_expired(past) is True

    def test_exactly_at_expiry(self):
        """Should return True when exactly at expiry time"""
        now = time.time()
        assert is_expired(now, now) is True

    def test_with_custom_now(self):
        """Should use custom now timestamp"""
        expires_at = 1000.0
        assert is_expired(expires_at, now=999.0) is False
        assert is_expired(expires_at, now=1000.0) is True
        assert is_expired(expires_at, now=1001.0) is True


class TestIsWithinGracePeriod:
    """Tests for is_within_grace_period function"""

    def test_within_grace_period(self):
        """Should return True when within grace period"""
        now = time.time()
        expires_at = now - 2  # Expired 2 seconds ago
        assert is_within_grace_period(expires_at, 5.0, now) is True

    def test_outside_grace_period(self):
        """Should return False when outside grace period"""
        now = time.time()
        expires_at = now - 10  # Expired 10 seconds ago
        assert is_within_grace_period(expires_at, 5.0, now) is False

    def test_not_yet_expired(self):
        """Should return True when not yet expired"""
        now = time.time()
        expires_at = now + 10  # Expires in 10 seconds
        assert is_within_grace_period(expires_at, 5.0, now) is True

    def test_at_grace_period_boundary(self):
        """Should return False at exact boundary"""
        now = time.time()
        expires_at = now - 5  # Expired exactly 5 seconds ago
        assert is_within_grace_period(expires_at, 5.0, now) is False

    def test_with_zero_grace_period(self):
        """Should handle zero grace period"""
        now = time.time()
        expires_at = now - 1
        assert is_within_grace_period(expires_at, 0.0, now) is False


class TestSelectEndpoint:
    """Tests for select_endpoint function"""

    def create_endpoint(
        self, host: str, port: int = 80, healthy: bool = True, weight: int = 1
    ) -> ResolvedEndpoint:
        return ResolvedEndpoint(host=host, port=port, healthy=healthy, weight=weight)

    def test_empty_endpoints(self):
        """Should return None for empty list"""
        state = create_load_balance_state()
        result = select_endpoint([], "round-robin", state)
        assert result is None

    def test_single_endpoint(self):
        """Should return the only endpoint"""
        state = create_load_balance_state()
        endpoints = [self.create_endpoint("10.0.0.1")]
        result = select_endpoint(endpoints, "round-robin", state)
        assert result is not None
        assert result.host == "10.0.0.1"

    def test_all_unhealthy_fallback(self):
        """Should fall back to first endpoint when all unhealthy"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1", healthy=False),
            self.create_endpoint("10.0.0.2", healthy=False),
        ]
        result = select_endpoint(endpoints, "round-robin", state)
        assert result is not None
        assert result.host == "10.0.0.1"

    def test_round_robin(self):
        """Should cycle through endpoints"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1"),
            self.create_endpoint("10.0.0.2"),
            self.create_endpoint("10.0.0.3"),
        ]

        results = [
            select_endpoint(endpoints, "round-robin", state) for _ in range(6)
        ]
        hosts = [r.host for r in results if r]

        # Should cycle through all endpoints twice
        assert hosts == [
            "10.0.0.1", "10.0.0.2", "10.0.0.3",
            "10.0.0.1", "10.0.0.2", "10.0.0.3",
        ]

    def test_round_robin_skips_unhealthy(self):
        """Should skip unhealthy endpoints in round-robin"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1"),
            self.create_endpoint("10.0.0.2", healthy=False),
            self.create_endpoint("10.0.0.3"),
        ]

        results = [
            select_endpoint(endpoints, "round-robin", state) for _ in range(4)
        ]
        hosts = [r.host for r in results if r]

        # Should only return healthy endpoints
        assert all(h in ["10.0.0.1", "10.0.0.3"] for h in hosts)

    def test_random(self):
        """Should return random endpoints"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1"),
            self.create_endpoint("10.0.0.2"),
            self.create_endpoint("10.0.0.3"),
        ]

        results = [
            select_endpoint(endpoints, "random", state) for _ in range(100)
        ]
        hosts = set(r.host for r in results if r)

        # Should eventually hit all endpoints
        assert len(hosts) == 3

    def test_weighted(self):
        """Should prefer higher weight endpoints"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1", weight=1),
            self.create_endpoint("10.0.0.2", weight=10),
        ]

        results = [
            select_endpoint(endpoints, "weighted", state) for _ in range(100)
        ]
        hosts = [r.host for r in results if r]

        # Higher weight should be selected more often
        count_1 = hosts.count("10.0.0.1")
        count_2 = hosts.count("10.0.0.2")
        assert count_2 > count_1

    def test_least_connections(self):
        """Should select endpoint with fewest connections"""
        state = create_load_balance_state()
        state.active_connections["10.0.0.1:80"] = 10
        state.active_connections["10.0.0.2:80"] = 5
        state.active_connections["10.0.0.3:80"] = 1

        endpoints = [
            self.create_endpoint("10.0.0.1"),
            self.create_endpoint("10.0.0.2"),
            self.create_endpoint("10.0.0.3"),
        ]

        result = select_endpoint(endpoints, "least-connections", state)
        assert result is not None
        assert result.host == "10.0.0.3"

    def test_power_of_two(self):
        """Should select better of two random choices"""
        state = create_load_balance_state()
        endpoints = [
            self.create_endpoint("10.0.0.1"),
            self.create_endpoint("10.0.0.2"),
            self.create_endpoint("10.0.0.3"),
        ]

        results = [
            select_endpoint(endpoints, "power-of-two", state) for _ in range(100)
        ]
        hosts = set(r.host for r in results if r)

        # Should eventually hit all endpoints
        assert len(hosts) == 3

    def test_power_of_two_single_endpoint(self):
        """Should handle single endpoint for P2C"""
        state = create_load_balance_state()
        endpoints = [self.create_endpoint("10.0.0.1")]

        result = select_endpoint(endpoints, "power-of-two", state)
        assert result is not None
        assert result.host == "10.0.0.1"


class TestGetEndpointKey:
    """Tests for get_endpoint_key function"""

    def test_basic_key(self):
        """Should create host:port key"""
        endpoint = ResolvedEndpoint(host="10.0.0.1", port=80)
        assert get_endpoint_key(endpoint) == "10.0.0.1:80"

    def test_different_ports(self):
        """Should differentiate by port"""
        endpoint1 = ResolvedEndpoint(host="10.0.0.1", port=80)
        endpoint2 = ResolvedEndpoint(host="10.0.0.1", port=8080)
        assert get_endpoint_key(endpoint1) != get_endpoint_key(endpoint2)


class TestParseDsn:
    """Tests for parse_dsn function"""

    def test_simple_hostname(self):
        """Should parse simple hostname"""
        result = parse_dsn("example.com")
        assert result.host == "example.com"
        assert result.port is None
        assert result.protocol is None

    def test_hostname_with_port(self):
        """Should parse hostname:port"""
        result = parse_dsn("example.com:8080")
        assert result.host == "example.com"
        assert result.port == 8080

    def test_http_url(self):
        """Should parse HTTP URL"""
        result = parse_dsn("http://example.com:8080/path")
        assert result.host == "example.com"
        assert result.port == 8080
        assert result.protocol == "http"

    def test_https_url(self):
        """Should parse HTTPS URL"""
        result = parse_dsn("https://api.example.com")
        assert result.host == "api.example.com"
        assert result.port is None
        assert result.protocol == "https"

    def test_url_with_path(self):
        """Should extract host from URL with path"""
        result = parse_dsn("https://api.example.com/v2/resource")
        assert result.host == "api.example.com"

    def test_ipv4_address(self):
        """Should parse IPv4 address"""
        result = parse_dsn("192.168.1.100")
        assert result.host == "192.168.1.100"

    def test_ipv4_with_port(self):
        """Should parse IPv4:port"""
        result = parse_dsn("192.168.1.100:3000")
        assert result.host == "192.168.1.100"
        assert result.port == 3000

    def test_empty_string(self):
        """Should handle empty string"""
        result = parse_dsn("")
        assert result.host == ""

    def test_invalid_port(self):
        """Should treat invalid port as part of host"""
        result = parse_dsn("example.com:abc")
        assert result.host == "example.com:abc"
        assert result.port is None


class TestLoadBalanceState:
    """Tests for LoadBalanceState"""

    def test_create_state(self):
        """Should create empty state"""
        state = create_load_balance_state()
        assert state.round_robin_index == {}
        assert state.active_connections == {}

    def test_state_persistence(self):
        """State should persist across calls"""
        state = create_load_balance_state()
        state.active_connections["10.0.0.1:80"] = 5
        assert state.active_connections["10.0.0.1:80"] == 5
