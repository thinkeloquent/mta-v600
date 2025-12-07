"""
DNS cache transport wrapper for httpx's compose pattern.
"""
from cache_dsn import (
    DnsCacheConfig,
    DnsCacheStats,
    DnsCacheEvent,
    DnsCacheStore,
    LoadBalanceStrategy,
    ResolvedEndpoint,
    CachedEntry,
    ResolutionResult,
    HealthCheckConfig,
)
from .transport import DnsCacheTransport, SyncDnsCacheTransport
from .factory import (
    compose_transport,
    compose_sync_transport,
    create_dns_cached_client,
    create_dns_cached_sync_client,
    create_api_dns_cache,
    create_from_preset,
    AGGRESSIVE_DNS_CACHE,
    CONSERVATIVE_DNS_CACHE,
    HIGH_AVAILABILITY_DNS_CACHE,
)


__all__ = [
    # Re-exported types from base package
    "DnsCacheConfig",
    "DnsCacheStats",
    "DnsCacheEvent",
    "DnsCacheStore",
    "LoadBalanceStrategy",
    "ResolvedEndpoint",
    "CachedEntry",
    "ResolutionResult",
    "HealthCheckConfig",
    # Transport wrappers
    "DnsCacheTransport",
    "SyncDnsCacheTransport",
    # Factory functions
    "compose_transport",
    "compose_sync_transport",
    "create_dns_cached_client",
    "create_dns_cached_sync_client",
    "create_api_dns_cache",
    "create_from_preset",
    # Presets
    "AGGRESSIVE_DNS_CACHE",
    "CONSERVATIVE_DNS_CACHE",
    "HIGH_AVAILABILITY_DNS_CACHE",
]

__version__ = "1.0.0"
