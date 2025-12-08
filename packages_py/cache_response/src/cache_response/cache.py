"""
RFC 7234 HTTP Response Cache Manager.
"""
import asyncio
import time
from typing import Callable, Dict, Optional, Set

from .types import (
    CacheResponseConfig,
    CacheResponseStore,
    CachedResponse,
    CacheEntryMetadata,
    CacheLookupResult,
    CacheResponseEvent,
    CacheResponseEventType,
    CacheResponseEventListener,
    CacheFreshness,
)
from .parser import (
    parse_cache_control,
    extract_etag,
    extract_last_modified,
    calculate_expiration,
    determine_freshness,
    is_cacheable_status,
    is_cacheable_method,
    should_cache,
    needs_revalidation,
    parse_vary,
    is_vary_uncacheable,
    extract_vary_headers,
    match_vary_headers,
    normalize_headers,
)
from .stores.memory import MemoryCacheStore


def _default_key_generator(
    method: str, url: str, headers: Optional[Dict[str, str]] = None
) -> str:
    """Default cache key generator."""
    key = f"{method.upper()}:{url}"
    if headers and len(headers) > 0:
        sorted_headers = "&".join(
            f"{k}={v}" for k, v in sorted(headers.items())
        )
        key += f"|{sorted_headers}"
    return key


DEFAULT_CACHE_RESPONSE_CONFIG = CacheResponseConfig(
    methods=["GET", "HEAD"],
    cacheable_statuses=[200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501],
    default_ttl_seconds=0,
    max_ttl_seconds=86400,  # 24 hours
    respect_no_cache=True,
    respect_no_store=True,
    respect_private=True,
    stale_while_revalidate=True,
    stale_if_error=True,
    include_query_in_key=True,
    key_generator=_default_key_generator,
    vary_headers=[],
)


def merge_cache_response_config(
    config: Optional[CacheResponseConfig] = None,
) -> CacheResponseConfig:
    """Merge user config with defaults."""
    if config is None:
        return CacheResponseConfig(
            methods=list(DEFAULT_CACHE_RESPONSE_CONFIG.methods),
            cacheable_statuses=list(DEFAULT_CACHE_RESPONSE_CONFIG.cacheable_statuses),
            default_ttl_seconds=DEFAULT_CACHE_RESPONSE_CONFIG.default_ttl_seconds,
            max_ttl_seconds=DEFAULT_CACHE_RESPONSE_CONFIG.max_ttl_seconds,
            respect_no_cache=DEFAULT_CACHE_RESPONSE_CONFIG.respect_no_cache,
            respect_no_store=DEFAULT_CACHE_RESPONSE_CONFIG.respect_no_store,
            respect_private=DEFAULT_CACHE_RESPONSE_CONFIG.respect_private,
            stale_while_revalidate=DEFAULT_CACHE_RESPONSE_CONFIG.stale_while_revalidate,
            stale_if_error=DEFAULT_CACHE_RESPONSE_CONFIG.stale_if_error,
            include_query_in_key=DEFAULT_CACHE_RESPONSE_CONFIG.include_query_in_key,
            key_generator=DEFAULT_CACHE_RESPONSE_CONFIG.key_generator,
            vary_headers=list(DEFAULT_CACHE_RESPONSE_CONFIG.vary_headers),
        )

    return CacheResponseConfig(
        methods=config.methods if config.methods else list(DEFAULT_CACHE_RESPONSE_CONFIG.methods),
        cacheable_statuses=config.cacheable_statuses
        if config.cacheable_statuses
        else list(DEFAULT_CACHE_RESPONSE_CONFIG.cacheable_statuses),
        default_ttl_seconds=config.default_ttl_seconds
        if config.default_ttl_seconds is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.default_ttl_seconds,
        max_ttl_seconds=config.max_ttl_seconds
        if config.max_ttl_seconds is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.max_ttl_seconds,
        respect_no_cache=config.respect_no_cache
        if config.respect_no_cache is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.respect_no_cache,
        respect_no_store=config.respect_no_store
        if config.respect_no_store is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.respect_no_store,
        respect_private=config.respect_private
        if config.respect_private is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.respect_private,
        stale_while_revalidate=config.stale_while_revalidate
        if config.stale_while_revalidate is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.stale_while_revalidate,
        stale_if_error=config.stale_if_error
        if config.stale_if_error is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.stale_if_error,
        include_query_in_key=config.include_query_in_key
        if config.include_query_in_key is not None
        else DEFAULT_CACHE_RESPONSE_CONFIG.include_query_in_key,
        key_generator=config.key_generator or DEFAULT_CACHE_RESPONSE_CONFIG.key_generator,
        vary_headers=config.vary_headers
        if config.vary_headers
        else list(DEFAULT_CACHE_RESPONSE_CONFIG.vary_headers),
    )


class ResponseCache:
    """
    RFC 7234 compliant HTTP response cache.

    Implements:
    - Cache-Control directive parsing and compliance
    - ETag and Last-Modified conditional request support
    - Vary header handling
    - Stale-while-revalidate pattern
    - Stale-if-error pattern
    - LRU eviction (via store)

    Example:
        cache = ResponseCache()

        # Check cache before making request
        lookup = await cache.lookup('GET', 'https://api.example.com/data')
        if lookup.found and lookup.freshness == CacheFreshness.FRESH:
            return lookup.response

        # Make request (with conditional headers if available)
        headers = {}
        if lookup.etag:
            headers['If-None-Match'] = lookup.etag
        if lookup.last_modified:
            headers['If-Modified-Since'] = lookup.last_modified

        response = await http_client.get(url, headers=headers)

        # Handle 304 Not Modified
        if response.status_code == 304 and lookup.response:
            await cache.revalidate('GET', url)
            return lookup.response

        # Store new response
        await cache.store('GET', url, response.status_code, dict(response.headers), response.content)
    """

    def __init__(
        self,
        config: Optional[CacheResponseConfig] = None,
        store: Optional[CacheResponseStore] = None,
    ) -> None:
        self._config = merge_cache_response_config(config)
        self._store = store or MemoryCacheStore()
        self._listeners: Set[CacheResponseEventListener] = set()
        self._background_revalidator: Optional[Callable] = None
        self._revalidating_keys: Set[str] = set()

    def generate_key(
        self,
        method: str,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
        vary_headers: Optional[list] = None,
    ) -> str:
        """Generate cache key for a request."""
        cache_url = url
        if not self._config.include_query_in_key:
            query_index = url.find("?")
            if query_index != -1:
                cache_url = url[:query_index]

        vary_header_values: Optional[Dict[str, str]] = None
        if request_headers and vary_headers and len(vary_headers) > 0:
            vary_header_values = extract_vary_headers(request_headers, vary_headers)

        key_generator = self._config.key_generator or _default_key_generator
        return key_generator(method, cache_url, vary_header_values)

    def is_cacheable(self, method: str) -> bool:
        """Check if a request method is cacheable."""
        return is_cacheable_method(method, self._config.methods)

    async def lookup(
        self,
        method: str,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> CacheLookupResult:
        """Look up a cached response."""
        if not self.is_cacheable(method):
            return CacheLookupResult(found=False)

        key = self.generate_key(method, url, request_headers)
        cached = await self._store.get(key)

        if not cached:
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_MISS,
                    key=key,
                    url=url,
                    timestamp=time.time(),
                )
            )
            return CacheLookupResult(found=False)

        # Check Vary header matching
        if cached.metadata.vary and request_headers:
            vary_list = parse_vary(cached.metadata.vary)
            if is_vary_uncacheable(cached.metadata.vary):
                return CacheLookupResult(found=False)
            if cached.metadata.vary_headers:
                request_vary_headers = extract_vary_headers(request_headers, vary_list)
                if not match_vary_headers(request_vary_headers, cached.metadata.vary_headers):
                    return CacheLookupResult(found=False)

        freshness = determine_freshness(cached.metadata)
        should_revalidate = (
            freshness != CacheFreshness.FRESH
            or needs_revalidation(cached.metadata, self._config.respect_no_cache)
        )

        # Emit appropriate event
        if freshness == CacheFreshness.FRESH and not should_revalidate:
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_HIT,
                    key=key,
                    url=url,
                    timestamp=time.time(),
                    metadata={"freshness": freshness.value},
                )
            )
        elif freshness == CacheFreshness.STALE:
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_STALE_SERVE,
                    key=key,
                    url=url,
                    timestamp=time.time(),
                    metadata={"freshness": freshness.value},
                )
            )

        # Trigger background revalidation for stale-while-revalidate
        if (
            self._config.stale_while_revalidate
            and freshness == CacheFreshness.STALE
            and self._background_revalidator
            and key not in self._revalidating_keys
        ):
            self._trigger_background_revalidation(key, url, request_headers)

        return CacheLookupResult(
            found=True,
            response=cached,
            freshness=freshness,
            should_revalidate=should_revalidate,
            etag=cached.metadata.etag,
            last_modified=cached.metadata.last_modified,
        )

    async def store(
        self,
        method: str,
        url: str,
        status_code: int,
        response_headers: Dict[str, str],
        body: Optional[bytes] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Store a response in the cache."""
        if not self.is_cacheable(method):
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_BYPASS,
                    key=self.generate_key(method, url, request_headers),
                    url=url,
                    timestamp=time.time(),
                    metadata={"reason": "method-not-cacheable"},
                )
            )
            return False

        if not is_cacheable_status(status_code, self._config.cacheable_statuses):
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_BYPASS,
                    key=self.generate_key(method, url, request_headers),
                    url=url,
                    timestamp=time.time(),
                    metadata={"reason": "status-not-cacheable", "status_code": status_code},
                )
            )
            return False

        normalized_headers = normalize_headers(response_headers)
        cache_control = normalized_headers.get("cache-control")
        directives = parse_cache_control(cache_control)

        if not should_cache(
            directives,
            respect_no_store=self._config.respect_no_store,
            respect_no_cache=self._config.respect_no_cache,
            respect_private=self._config.respect_private,
        ):
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_BYPASS,
                    key=self.generate_key(method, url, request_headers),
                    url=url,
                    timestamp=time.time(),
                    metadata={"reason": "cache-control", "cache_control": cache_control},
                )
            )
            return False

        vary = normalized_headers.get("vary")
        if is_vary_uncacheable(vary):
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_BYPASS,
                    key=self.generate_key(method, url, request_headers),
                    url=url,
                    timestamp=time.time(),
                    metadata={"reason": "vary-star"},
                )
            )
            return False

        vary_list = parse_vary(vary)
        vary_headers = (
            extract_vary_headers(request_headers, vary_list) if request_headers else None
        )

        now = time.time()
        expires_at = calculate_expiration(
            normalized_headers,
            directives,
            self._config.default_ttl_seconds,
            self._config.max_ttl_seconds,
        )

        if expires_at <= now:
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_BYPASS,
                    key=self.generate_key(method, url, request_headers, vary_list),
                    url=url,
                    timestamp=now,
                    metadata={"reason": "already-expired"},
                )
            )
            return False

        metadata = CacheEntryMetadata(
            url=url,
            method=method.upper(),
            status_code=status_code,
            headers=normalized_headers,
            cached_at=now,
            expires_at=expires_at,
            etag=extract_etag(normalized_headers),
            last_modified=extract_last_modified(normalized_headers),
            cache_control=cache_control,
            directives=directives,
            vary=vary,
            vary_headers=vary_headers,
        )

        cached_response = CachedResponse(metadata=metadata, body=body)

        key = self.generate_key(method, url, request_headers, vary_list)
        await self._store.set(key, cached_response)

        self._emit(
            CacheResponseEvent(
                type=CacheResponseEventType.CACHE_STORE,
                key=key,
                url=url,
                timestamp=now,
                metadata={"expires_at": expires_at, "status_code": status_code},
            )
        )

        return True

    async def revalidate(
        self,
        method: str,
        url: str,
        response_headers: Optional[Dict[str, str]] = None,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Revalidate a cached response (update expiration after 304 Not Modified)."""
        key = self.generate_key(method, url, request_headers)
        cached = await self._store.get(key)

        if not cached:
            return False

        now = time.time()
        normalized_headers = (
            normalize_headers(response_headers) if response_headers else cached.metadata.headers
        )
        cache_control = normalized_headers.get("cache-control") or cached.metadata.cache_control
        directives = parse_cache_control(cache_control)

        expires_at = calculate_expiration(
            normalized_headers,
            directives,
            self._config.default_ttl_seconds,
            self._config.max_ttl_seconds,
        )

        updated_metadata = CacheEntryMetadata(
            url=cached.metadata.url,
            method=cached.metadata.method,
            status_code=cached.metadata.status_code,
            headers=cached.metadata.headers,
            cached_at=now,
            expires_at=expires_at,
            etag=extract_etag(normalized_headers) or cached.metadata.etag,
            last_modified=extract_last_modified(normalized_headers) or cached.metadata.last_modified,
            cache_control=cache_control,
            directives=directives,
            vary=cached.metadata.vary,
            vary_headers=cached.metadata.vary_headers,
        )

        updated_response = CachedResponse(metadata=updated_metadata, body=cached.body)

        await self._store.set(key, updated_response)
        self._revalidating_keys.discard(key)

        self._emit(
            CacheResponseEvent(
                type=CacheResponseEventType.CACHE_REVALIDATE,
                key=key,
                url=url,
                timestamp=now,
                metadata={"expires_at": expires_at},
            )
        )

        return True

    async def invalidate(
        self,
        method: str,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> bool:
        """Invalidate a cached response."""
        key = self.generate_key(method, url, request_headers)
        deleted = await self._store.delete(key)

        if deleted:
            self._emit(
                CacheResponseEvent(
                    type=CacheResponseEventType.CACHE_EXPIRE,
                    key=key,
                    url=url,
                    timestamp=time.time(),
                )
            )

        return deleted

    def set_background_revalidator(
        self, revalidator: Callable[[str, Optional[Dict[str, str]]], None]
    ) -> None:
        """Set background revalidator for stale-while-revalidate."""
        self._background_revalidator = revalidator

    def _trigger_background_revalidation(
        self,
        key: str,
        url: str,
        request_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Trigger background revalidation."""
        if not self._background_revalidator:
            return

        self._revalidating_keys.add(key)

        async def _revalidate():
            try:
                await self._background_revalidator(url, request_headers)
            except Exception:
                pass
            finally:
                self._revalidating_keys.discard(key)

        asyncio.create_task(_revalidate())

    def get_config(self) -> CacheResponseConfig:
        """Get configuration."""
        return self._config

    async def get_stats(self) -> Dict:
        """Get store statistics."""
        return {"size": await self._store.size()}

    def on(self, listener: CacheResponseEventListener) -> Callable[[], None]:
        """Add event listener."""
        self._listeners.add(listener)
        return lambda: self._listeners.discard(listener)

    def off(self, listener: CacheResponseEventListener) -> None:
        """Remove event listener."""
        self._listeners.discard(listener)

    def _emit(self, event: CacheResponseEvent) -> None:
        """Emit an event to all listeners."""
        for listener in self._listeners:
            try:
                listener(event)
            except Exception:
                pass

    async def clear(self) -> None:
        """Clear all cached responses."""
        await self._store.clear()

    async def close(self) -> None:
        """Close the cache and release resources."""
        await self._store.close()
        self._listeners.clear()
        self._revalidating_keys.clear()


def create_response_cache(
    config: Optional[CacheResponseConfig] = None,
    store: Optional[CacheResponseStore] = None,
) -> ResponseCache:
    """Create a response cache instance."""
    return ResponseCache(config, store)
