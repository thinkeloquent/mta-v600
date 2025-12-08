"""
Request deduplication with Idempotency Keys and Request Coalescing (Singleflight) support.
"""
from .types import (
    IdempotencyConfig,
    SingleflightConfig,
    RequestFingerprint,
    StoredResponse,
    InFlightRequest,
    CacheRequestStore,
    SingleflightStore,
    CacheRequestConfig,
    IdempotencyCheckResult,
    SingleflightResult,
    CacheRequestEventType,
    CacheRequestEvent,
    CacheRequestEventListener,
)
from .idempotency import (
    IdempotencyManager,
    IdempotencyConflictError,
    create_idempotency_manager,
    DEFAULT_IDEMPOTENCY_CONFIG,
    merge_idempotency_config,
    generate_fingerprint,
)
from .singleflight import (
    Singleflight,
    create_singleflight,
    DEFAULT_SINGLEFLIGHT_CONFIG,
    merge_singleflight_config,
)
from .stores import (
    MemoryCacheStore,
    MemorySingleflightStore,
    create_memory_cache_store,
    create_memory_singleflight_store,
)


__all__ = [
    # Types
    "IdempotencyConfig",
    "SingleflightConfig",
    "RequestFingerprint",
    "StoredResponse",
    "InFlightRequest",
    "CacheRequestStore",
    "SingleflightStore",
    "CacheRequestConfig",
    "IdempotencyCheckResult",
    "SingleflightResult",
    "CacheRequestEventType",
    "CacheRequestEvent",
    "CacheRequestEventListener",
    # Idempotency
    "IdempotencyManager",
    "IdempotencyConflictError",
    "create_idempotency_manager",
    "DEFAULT_IDEMPOTENCY_CONFIG",
    "merge_idempotency_config",
    "generate_fingerprint",
    # Singleflight
    "Singleflight",
    "create_singleflight",
    "DEFAULT_SINGLEFLIGHT_CONFIG",
    "merge_singleflight_config",
    # Stores
    "MemoryCacheStore",
    "MemorySingleflightStore",
    "create_memory_cache_store",
    "create_memory_singleflight_store",
]

__version__ = "1.0.0"
