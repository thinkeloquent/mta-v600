"""
DNS Cache Resolver - Main implementation
"""
import asyncio
import socket
import time
from typing import Optional, Callable

from .types import (
    CachedEntry,
    DnsCacheConfig,
    DnsCacheEvent,
    DnsCacheEventListener,
    DnsCacheStats,
    DnsCacheStore,
    ResolvedEndpoint,
    ResolverFunction,
    ResolutionResult,
)
from .config import (
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
from .stores.memory import MemoryStore


class DnsCacheResolver:
    """
    DNS Cache Resolver

    Provides cached DNS/service discovery resolution with:
    - Configurable TTL with min/max bounds
    - Stale-while-revalidate support
    - Multiple load balancing strategies
    - Health-aware endpoint selection
    - Event emission for observability

    Example:
        resolver = DnsCacheResolver(DnsCacheConfig(
            id='api-resolver',
            default_ttl_seconds=60.0,
            load_balance_strategy='power-of-two'
        ))

        result = await resolver.resolve('api.example.com')
        endpoint = await resolver.select_endpoint('api.example.com')
    """

    def __init__(
        self,
        config: DnsCacheConfig,
        store: Optional[DnsCacheStore] = None,
    ) -> None:
        self._config = merge_config(config)
        self._store = store or MemoryStore(self._config.max_entries)
        self._listeners: set[DnsCacheEventListener] = set()
        self._load_balance_state = create_load_balance_state()
        self._custom_resolvers: dict[str, ResolverFunction] = {}
        self._revalidating: set[str] = set()

        # Statistics
        self._cache_hits = 0
        self._cache_misses = 0
        self._stale_hits = 0
        self._total_resolution_time = 0.0
        self._resolution_count = 0

    async def resolve(
        self,
        dsn: str,
        *,
        force_refresh: bool = False,
        ttl_seconds: Optional[float] = None,
    ) -> ResolutionResult:
        """
        Resolve a DSN to endpoints, using cache when available

        Args:
            dsn: The DSN/hostname to resolve
            force_refresh: Force a fresh resolution, bypassing cache
            ttl_seconds: Custom TTL for this resolution

        Returns:
            Resolution result with endpoints
        """
        start_time = time.time()

        # Check cache first (unless forcing refresh)
        if not force_refresh:
            cached = await self._store.get(dsn)

            if cached:
                now = time.time()
                expired = is_expired(cached.expires_at, now)

                if not expired:
                    # Cache hit - valid entry
                    self._cache_hits += 1
                    cached.hit_count += 1
                    await self._store.set(dsn, cached)

                    self._emit(DnsCacheEvent(
                        type="cache:hit",
                        data={"dsn": dsn, "ttl_remaining_seconds": cached.expires_at - now},
                    ))

                    return ResolutionResult(
                        endpoints=cached.endpoints,
                        from_cache=True,
                        ttl_remaining_seconds=cached.expires_at - now,
                        resolution_time_seconds=time.time() - start_time,
                    )

                # Entry is expired, check if within grace period
                if (
                    self._config.stale_while_revalidate
                    and is_within_grace_period(
                        cached.expires_at,
                        self._config.stale_grace_period_seconds,
                        now,
                    )
                ):
                    self._stale_hits += 1

                    # Trigger background revalidation
                    is_revalidating = dsn in self._revalidating
                    if not is_revalidating:
                        asyncio.create_task(
                            self._revalidate_in_background(dsn, ttl_seconds)
                        )

                    self._emit(DnsCacheEvent(
                        type="cache:stale",
                        data={"dsn": dsn, "revalidating": not is_revalidating},
                    ))

                    return ResolutionResult(
                        endpoints=cached.endpoints,
                        from_cache=True,
                        ttl_remaining_seconds=0,
                        resolution_time_seconds=time.time() - start_time,
                    )

                # Entry is fully expired
                self._emit(DnsCacheEvent(type="cache:expired", data={"dsn": dsn}))
            else:
                self._emit(DnsCacheEvent(type="cache:miss", data={"dsn": dsn}))

        # Cache miss - perform fresh resolution
        self._cache_misses += 1
        return await self._fresh_resolve(dsn, ttl_seconds)

    async def _fresh_resolve(
        self,
        dsn: str,
        custom_ttl_seconds: Optional[float] = None,
    ) -> ResolutionResult:
        """Perform a fresh DNS resolution"""
        start_time = time.time()

        self._emit(DnsCacheEvent(type="resolve:start", data={"dsn": dsn}))

        try:
            # Use custom resolver if registered, otherwise use system DNS
            resolver = self._custom_resolvers.get(dsn) or self._default_resolver
            endpoints = await resolver(dsn)

            duration_seconds = time.time() - start_time
            self._total_resolution_time += duration_seconds
            self._resolution_count += 1

            # Calculate TTL
            ttl_seconds = clamp_ttl(
                custom_ttl_seconds or self._config.default_ttl_seconds,
                self._config.min_ttl_seconds,
                self._config.max_ttl_seconds,
            )

            now = time.time()

            # Cache the result
            entry = CachedEntry(
                dsn=dsn,
                endpoints=endpoints,
                resolved_at=now,
                expires_at=now + ttl_seconds,
                ttl_seconds=ttl_seconds,
                hit_count=0,
            )

            await self._store.set(dsn, entry)

            self._emit(DnsCacheEvent(
                type="resolve:success",
                data={
                    "dsn": dsn,
                    "endpoint_count": len(endpoints),
                    "duration_seconds": duration_seconds,
                },
            ))

            return ResolutionResult(
                endpoints=endpoints,
                from_cache=False,
                ttl_remaining_seconds=ttl_seconds,
                resolution_time_seconds=duration_seconds,
            )

        except Exception as e:
            self._emit(DnsCacheEvent(
                type="resolve:error",
                data={"dsn": dsn, "error": str(e)},
            ))

            # Cache negative result if configured
            if self._config.negative_ttl_seconds > 0:
                now = time.time()
                entry = CachedEntry(
                    dsn=dsn,
                    endpoints=[],
                    resolved_at=now,
                    expires_at=now + self._config.negative_ttl_seconds,
                    ttl_seconds=self._config.negative_ttl_seconds,
                    hit_count=0,
                )
                await self._store.set(dsn, entry)

            raise

    async def _default_resolver(self, dsn: str) -> list[ResolvedEndpoint]:
        """Default DNS resolver using socket.getaddrinfo"""
        parsed = parse_dsn(dsn)
        host = parsed.host

        try:
            # Perform DNS resolution in a thread pool
            loop = asyncio.get_event_loop()
            addresses = await loop.run_in_executor(
                None,
                lambda: socket.getaddrinfo(
                    host,
                    parsed.port or 80,
                    socket.AF_INET,
                    socket.SOCK_STREAM,
                ),
            )

            endpoints: list[ResolvedEndpoint] = []
            seen_hosts: set[str] = set()

            for family, socktype, proto, canonname, sockaddr in addresses:
                addr_host = sockaddr[0]
                addr_port = sockaddr[1]

                if addr_host not in seen_hosts:
                    seen_hosts.add(addr_host)
                    endpoints.append(ResolvedEndpoint(
                        host=addr_host,
                        port=addr_port,
                        healthy=True,
                        last_checked=time.time(),
                    ))

            return endpoints

        except socket.gaierror:
            # If DNS resolution fails, treat as literal address
            return [ResolvedEndpoint(
                host=host,
                port=parsed.port or 80,
                healthy=True,
                last_checked=time.time(),
            )]

    async def _revalidate_in_background(
        self,
        dsn: str,
        custom_ttl_seconds: Optional[float] = None,
    ) -> None:
        """Revalidate a cache entry in the background"""
        if dsn in self._revalidating:
            return

        self._revalidating.add(dsn)

        try:
            await self._fresh_resolve(dsn, custom_ttl_seconds)
        except Exception:
            # Ignore errors in background revalidation
            pass
        finally:
            self._revalidating.discard(dsn)

    async def select_endpoint(self, dsn: str) -> Optional[ResolvedEndpoint]:
        """
        Select an endpoint for a DSN using the configured load balancing strategy

        Args:
            dsn: The DSN to select an endpoint for

        Returns:
            The selected endpoint, or None if not cached
        """
        cached = await self._store.get(dsn)
        if not cached or not cached.endpoints:
            return None

        return select_endpoint(
            cached.endpoints,
            self._config.load_balance_strategy,
            self._load_balance_state,
        )

    async def resolve_one(
        self,
        dsn: str,
        *,
        force_refresh: bool = False,
        ttl_seconds: Optional[float] = None,
    ) -> Optional[ResolvedEndpoint]:
        """Resolve and select a single endpoint"""
        result = await self.resolve(dsn, force_refresh=force_refresh, ttl_seconds=ttl_seconds)
        if not result.endpoints:
            return None

        return select_endpoint(
            result.endpoints,
            self._config.load_balance_strategy,
            self._load_balance_state,
        )

    def register_resolver(self, dsn: str, resolver: ResolverFunction) -> None:
        """Register a custom resolver for a specific DSN pattern"""
        self._custom_resolvers[dsn] = resolver

    def unregister_resolver(self, dsn: str) -> bool:
        """Unregister a custom resolver"""
        if dsn in self._custom_resolvers:
            del self._custom_resolvers[dsn]
            return True
        return False

    async def mark_unhealthy(self, dsn: str, endpoint: ResolvedEndpoint) -> None:
        """Mark an endpoint as unhealthy"""
        cached = await self._store.get(dsn)
        if not cached:
            return

        key = get_endpoint_key(endpoint)
        for target in cached.endpoints:
            if get_endpoint_key(target) == key and target.healthy:
                target.healthy = False
                target.last_checked = time.time()
                await self._store.set(dsn, cached)

                self._emit(DnsCacheEvent(
                    type="health:changed",
                    data={"endpoint": key, "previous_healthy": True},
                ))
                break

    async def mark_healthy(self, dsn: str, endpoint: ResolvedEndpoint) -> None:
        """Mark an endpoint as healthy"""
        cached = await self._store.get(dsn)
        if not cached:
            return

        key = get_endpoint_key(endpoint)
        for target in cached.endpoints:
            if get_endpoint_key(target) == key and not target.healthy:
                target.healthy = True
                target.last_checked = time.time()
                await self._store.set(dsn, cached)

                self._emit(DnsCacheEvent(
                    type="health:changed",
                    data={"endpoint": key, "previous_healthy": False},
                ))
                break

    def increment_connections(self, endpoint: ResolvedEndpoint) -> None:
        """Increment active connections for an endpoint (for least-connections/P2C)"""
        key = get_endpoint_key(endpoint)
        current = self._load_balance_state.active_connections.get(key, 0)
        self._load_balance_state.active_connections[key] = current + 1

    def decrement_connections(self, endpoint: ResolvedEndpoint) -> None:
        """Decrement active connections for an endpoint"""
        key = get_endpoint_key(endpoint)
        current = self._load_balance_state.active_connections.get(key, 0)
        self._load_balance_state.active_connections[key] = max(0, current - 1)

    async def invalidate(self, dsn: str) -> bool:
        """Invalidate a cached entry"""
        deleted = await self._store.delete(dsn)
        if deleted:
            self._emit(DnsCacheEvent(
                type="cache:evicted",
                data={"dsn": dsn, "reason": "manual"},
            ))
        return deleted

    async def clear(self) -> None:
        """Clear all cached entries"""
        keys = await self._store.keys()
        await self._store.clear()
        for dsn in keys:
            self._emit(DnsCacheEvent(
                type="cache:evicted",
                data={"dsn": dsn, "reason": "manual"},
            ))

    async def get_stats(self) -> DnsCacheStats:
        """Get cache statistics"""
        entries = await self._store.size()
        keys = await self._store.keys()

        healthy_endpoints = 0
        unhealthy_endpoints = 0

        for key in keys:
            entry = await self._store.get(key)
            if entry:
                for endpoint in entry.endpoints:
                    if endpoint.healthy:
                        healthy_endpoints += 1
                    else:
                        unhealthy_endpoints += 1

        total_requests = self._cache_hits + self._cache_misses

        return DnsCacheStats(
            total_entries=entries,
            cache_hits=self._cache_hits,
            cache_misses=self._cache_misses,
            hit_ratio=self._cache_hits / total_requests if total_requests > 0 else 0,
            stale_hits=self._stale_hits,
            avg_resolution_time_seconds=(
                self._total_resolution_time / self._resolution_count
                if self._resolution_count > 0 else 0
            ),
            healthy_endpoints=healthy_endpoints,
            unhealthy_endpoints=unhealthy_endpoints,
        )

    def on(self, listener: DnsCacheEventListener) -> Callable[[], None]:
        """Subscribe to events"""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def off(self, listener: DnsCacheEventListener) -> None:
        """Unsubscribe from events"""
        self._listeners.discard(listener)

    def _emit(self, event: DnsCacheEvent) -> None:
        """Emit an event"""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                # Ignore listener errors
                pass

    async def destroy(self) -> None:
        """Destroy the resolver, releasing resources"""
        self._listeners.clear()
        self._custom_resolvers.clear()
        self._revalidating.clear()
        await self._store.close()


def create_dns_cache_resolver(
    config: DnsCacheConfig,
    store: Optional[DnsCacheStore] = None,
) -> DnsCacheResolver:
    """Factory function to create a DNS cache resolver"""
    return DnsCacheResolver(config, store)
