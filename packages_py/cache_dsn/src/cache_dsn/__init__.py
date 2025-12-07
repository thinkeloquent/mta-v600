"""
Standalone DNS/service discovery cache with TTL, health-aware invalidation, and pluggable backends.
"""
from .types import (
    ResolvedEndpoint,
    CachedEntry,
    ResolutionResult,
    LoadBalanceStrategy,
    HealthCheckConfig,
    DnsCacheConfig,
    DnsCacheStats,
    DnsCacheEvent,
    DnsCacheEventListener,
    ResolverFunction,
    DnsCacheStore,
)
from .config import (
    DEFAULT_HEALTH_CHECK_CONFIG,
    merge_config,
    clamp_ttl,
    is_expired,
    is_within_grace_period,
    create_load_balance_state,
    get_endpoint_key,
    select_endpoint,
    parse_dsn,
    ParsedDsn,
    LoadBalanceState,
    async_sleep,
)
from .stores import MemoryStore, create_memory_store
from .resolver import DnsCacheResolver, create_dns_cache_resolver


__all__ = [
    # Types
    "ResolvedEndpoint",
    "CachedEntry",
    "ResolutionResult",
    "LoadBalanceStrategy",
    "HealthCheckConfig",
    "DnsCacheConfig",
    "DnsCacheStats",
    "DnsCacheEvent",
    "DnsCacheEventListener",
    "ResolverFunction",
    "DnsCacheStore",
    # Config
    "DEFAULT_HEALTH_CHECK_CONFIG",
    "merge_config",
    "clamp_ttl",
    "is_expired",
    "is_within_grace_period",
    "create_load_balance_state",
    "get_endpoint_key",
    "select_endpoint",
    "parse_dsn",
    "ParsedDsn",
    "LoadBalanceState",
    "async_sleep",
    # Stores
    "MemoryStore",
    "create_memory_store",
    # Resolver
    "DnsCacheResolver",
    "create_dns_cache_resolver",
]


__version__ = "1.0.0"
