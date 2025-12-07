"""
Configuration utilities for cache_dsn
"""
import random
from dataclasses import dataclass, field
from typing import Optional
from urllib.parse import urlparse

from .types import (
    DnsCacheConfig,
    HealthCheckConfig,
    LoadBalanceStrategy,
    ResolvedEndpoint,
)


# Default configurations
DEFAULT_HEALTH_CHECK_CONFIG = HealthCheckConfig(
    enabled=False,
    interval_seconds=30.0,
    timeout_seconds=5.0,
    unhealthy_threshold=3,
    healthy_threshold=2,
)


def merge_config(config: DnsCacheConfig) -> DnsCacheConfig:
    """Merge user config with defaults"""
    if config.health_check is None:
        config.health_check = DEFAULT_HEALTH_CHECK_CONFIG
    return config


def clamp_ttl(ttl_seconds: float, min_ttl: float, max_ttl: float) -> float:
    """Clamp TTL within configured bounds"""
    return min(max(ttl_seconds, min_ttl), max_ttl)


def is_expired(expires_at: float, now: Optional[float] = None) -> bool:
    """Calculate if a cached entry is expired"""
    import time
    if now is None:
        now = time.time()
    return now >= expires_at


def is_within_grace_period(
    expires_at: float,
    grace_period_seconds: float,
    now: Optional[float] = None,
) -> bool:
    """Calculate if a cached entry is within the stale grace period"""
    import time
    if now is None:
        now = time.time()
    return now < expires_at + grace_period_seconds


@dataclass
class LoadBalanceState:
    """Load balance state for stateful strategies"""

    round_robin_index: dict[str, int] = field(default_factory=dict)
    """Current index for round-robin"""

    active_connections: dict[str, int] = field(default_factory=dict)
    """Active connections per endpoint"""


def create_load_balance_state() -> LoadBalanceState:
    """Create initial load balance state"""
    return LoadBalanceState()


def get_endpoint_key(endpoint: ResolvedEndpoint) -> str:
    """Get endpoint key for state tracking"""
    return f"{endpoint.host}:{endpoint.port}"


def select_endpoint(
    endpoints: list[ResolvedEndpoint],
    strategy: LoadBalanceStrategy,
    state: LoadBalanceState,
) -> Optional[ResolvedEndpoint]:
    """Select an endpoint using the specified load balancing strategy"""
    # Filter to only healthy endpoints
    healthy_endpoints = [e for e in endpoints if e.healthy]
    if not healthy_endpoints:
        # Fall back to all endpoints if none are healthy
        if not endpoints:
            return None
        return endpoints[0]

    if strategy == "round-robin":
        return _select_round_robin(healthy_endpoints, state)
    elif strategy == "random":
        return _select_random(healthy_endpoints)
    elif strategy == "weighted":
        return _select_weighted(healthy_endpoints)
    elif strategy == "least-connections":
        return _select_least_connections(healthy_endpoints, state)
    elif strategy == "power-of-two":
        return _select_power_of_two(healthy_endpoints, state)
    else:
        return healthy_endpoints[0]


def _select_round_robin(
    endpoints: list[ResolvedEndpoint],
    state: LoadBalanceState,
) -> ResolvedEndpoint:
    """Round-robin selection"""
    # Use a global key for round-robin across all DSNs
    key = ",".join(sorted(get_endpoint_key(e) for e in endpoints))
    current_index = state.round_robin_index.get(key, 0)
    endpoint = endpoints[current_index % len(endpoints)]
    state.round_robin_index[key] = (current_index + 1) % len(endpoints)
    return endpoint


def _select_random(endpoints: list[ResolvedEndpoint]) -> ResolvedEndpoint:
    """Random selection"""
    return random.choice(endpoints)


def _select_weighted(endpoints: list[ResolvedEndpoint]) -> ResolvedEndpoint:
    """Weighted random selection"""
    total_weight = sum(e.weight or 1 for e in endpoints)
    r = random.random() * total_weight

    for endpoint in endpoints:
        r -= endpoint.weight or 1
        if r <= 0:
            return endpoint

    return endpoints[-1]


def _select_least_connections(
    endpoints: list[ResolvedEndpoint],
    state: LoadBalanceState,
) -> ResolvedEndpoint:
    """Least connections selection"""
    min_connections = float("inf")
    selected = endpoints[0]

    for endpoint in endpoints:
        key = get_endpoint_key(endpoint)
        connections = state.active_connections.get(key, 0)
        if connections < min_connections:
            min_connections = connections
            selected = endpoint

    return selected


def _select_power_of_two(
    endpoints: list[ResolvedEndpoint],
    state: LoadBalanceState,
) -> ResolvedEndpoint:
    """Power of Two Choices selection"""
    if len(endpoints) == 1:
        return endpoints[0]

    # Pick two random endpoints
    idx1 = random.randint(0, len(endpoints) - 1)
    idx2 = random.randint(0, len(endpoints) - 2)
    if idx2 >= idx1:
        idx2 += 1

    endpoint1 = endpoints[idx1]
    endpoint2 = endpoints[idx2]

    conn1 = state.active_connections.get(get_endpoint_key(endpoint1), 0)
    conn2 = state.active_connections.get(get_endpoint_key(endpoint2), 0)

    return endpoint1 if conn1 <= conn2 else endpoint2


@dataclass
class ParsedDsn:
    """Parsed DSN components"""

    host: str
    port: Optional[int] = None
    protocol: Optional[str] = None


def parse_dsn(dsn: str) -> ParsedDsn:
    """Parse a DSN string into components"""
    # Handle URLs
    if "://" in dsn:
        try:
            parsed = urlparse(dsn)
            return ParsedDsn(
                protocol=parsed.scheme,
                host=parsed.hostname or "",
                port=parsed.port,
            )
        except Exception:
            pass

    # Handle host:port format
    colon_index = dsn.rfind(":")
    if colon_index > 0:
        try:
            port = int(dsn[colon_index + 1:])
            return ParsedDsn(
                host=dsn[:colon_index],
                port=port,
            )
        except ValueError:
            pass

    return ParsedDsn(host=dsn)


async def async_sleep(seconds: float) -> None:
    """Async sleep for a specified duration"""
    import asyncio
    await asyncio.sleep(seconds)
