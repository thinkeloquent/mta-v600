"""
Cache response transport wrapper for httpx.

Implements RFC 7234 compliant HTTP response caching with:
- Cache-Control directive parsing and compliance
- ETag and Last-Modified conditional request support
- Vary header handling
- Stale-while-revalidate pattern
"""
import asyncio
from typing import Callable, Dict, Optional

import httpx

from cache_response import (
    ResponseCache,
    CacheResponseConfig,
    CacheResponseStore,
    CacheFreshness,
    create_memory_cache_store,
)


class CacheResponseTransport(httpx.AsyncBaseTransport):
    """
    Cache response transport wrapper for httpx.

    Wraps another transport and provides RFC 7234 compliant HTTP response caching.

    Example:
        base = httpx.AsyncHTTPTransport()
        transport = CacheResponseTransport(base)
        client = httpx.AsyncClient(transport=transport)
    """

    def __init__(
        self,
        inner: httpx.AsyncBaseTransport,
        *,
        config: Optional[CacheResponseConfig] = None,
        store: Optional[CacheResponseStore] = None,
        enable_background_revalidation: bool = True,
        on_cache_hit: Optional[Callable[[str, CacheFreshness], None]] = None,
        on_cache_miss: Optional[Callable[[str], None]] = None,
        on_cache_store: Optional[Callable[[str, int, float], None]] = None,
        on_revalidated: Optional[Callable[[str], None]] = None,
    ) -> None:
        """
        Create a new CacheResponseTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            config: Cache configuration
            store: Custom cache store
            enable_background_revalidation: Enable stale-while-revalidate. Default: True
            on_cache_hit: Callback when cache hit occurs
            on_cache_miss: Callback when cache miss occurs
            on_cache_store: Callback when response is cached
            on_revalidated: Callback when conditional request results in 304
        """
        self._inner = inner
        self._cache = ResponseCache(config, store or create_memory_cache_store())
        self._enable_background_revalidation = enable_background_revalidation
        self._on_cache_hit = on_cache_hit
        self._on_cache_miss = on_cache_miss
        self._on_cache_store = on_cache_store
        self._on_revalidated = on_revalidated
        self._revalidating: set = set()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Handle an async HTTP request with caching capabilities."""
        method = request.method
        url = str(request.url)

        # Check if method is cacheable
        if not self._cache.is_cacheable(method):
            return await self._inner.handle_async_request(request)

        request_headers = dict(request.headers)

        # Check cache
        lookup = await self._cache.lookup(method, url, request_headers)

        if lookup.found and lookup.response and lookup.freshness == CacheFreshness.FRESH:
            # Serve from cache
            if self._on_cache_hit:
                self._on_cache_hit(url, lookup.freshness)
            return self._build_response(lookup.response)

        if lookup.found and lookup.response and lookup.freshness == CacheFreshness.STALE:
            # Stale-while-revalidate: serve stale and revalidate in background
            if self._on_cache_hit:
                self._on_cache_hit(url, lookup.freshness)

            if self._enable_background_revalidation and url not in self._revalidating:
                self._trigger_background_revalidation(
                    request, lookup.etag, lookup.last_modified
                )

            return self._build_response(lookup.response)

        # Cache miss or need revalidation
        if self._on_cache_miss:
            self._on_cache_miss(url)

        # Build conditional request
        conditional_request = self._build_conditional_request(
            request, lookup.etag, lookup.last_modified
        )

        # Execute request
        response = await self._inner.handle_async_request(conditional_request)

        # Handle 304 Not Modified
        if response.status_code == 304 and lookup.response:
            if self._on_revalidated:
                self._on_revalidated(url)

            # Update cache expiration
            await self._cache.revalidate(
                method, url, dict(response.headers), request_headers
            )

            return self._build_response(lookup.response)

        # Read response body for caching
        content = await response.aread()

        # Cache the response
        stored = await self._cache.store(
            method,
            url,
            response.status_code,
            dict(response.headers),
            content,
            request_headers,
        )

        if stored and self._on_cache_store:
            cache_control = response.headers.get("cache-control", "")
            max_age = self._parse_max_age(cache_control)
            self._on_cache_store(url, response.status_code, max_age)

        # Return response with the content we read
        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
        )

    def _build_response(self, cached) -> httpx.Response:
        """Build an httpx.Response from cached data."""
        return httpx.Response(
            status_code=cached.metadata.status_code,
            headers=cached.metadata.headers,
            content=cached.body or b"",
        )

    def _build_conditional_request(
        self,
        request: httpx.Request,
        etag: Optional[str],
        last_modified: Optional[str],
    ) -> httpx.Request:
        """Build a conditional request with If-None-Match/If-Modified-Since."""
        headers = dict(request.headers)

        if etag and "if-none-match" not in [k.lower() for k in headers]:
            headers["If-None-Match"] = etag

        if last_modified and "if-modified-since" not in [k.lower() for k in headers]:
            headers["If-Modified-Since"] = last_modified

        return httpx.Request(
            method=request.method,
            url=request.url,
            headers=headers,
            content=request.content,
        )

    def _trigger_background_revalidation(
        self,
        request: httpx.Request,
        etag: Optional[str],
        last_modified: Optional[str],
    ) -> None:
        """Trigger background revalidation for stale-while-revalidate."""
        url = str(request.url)
        self._revalidating.add(url)

        async def _revalidate():
            try:
                conditional_request = self._build_conditional_request(
                    request, etag, last_modified
                )
                response = await self._inner.handle_async_request(conditional_request)
                content = await response.aread()

                request_headers = dict(request.headers)

                if response.status_code == 304:
                    if self._on_revalidated:
                        self._on_revalidated(url)
                    await self._cache.revalidate(
                        request.method,
                        url,
                        dict(response.headers),
                        request_headers,
                    )
                else:
                    stored = await self._cache.store(
                        request.method,
                        url,
                        response.status_code,
                        dict(response.headers),
                        content,
                        request_headers,
                    )
                    if stored and self._on_cache_store:
                        cache_control = response.headers.get("cache-control", "")
                        max_age = self._parse_max_age(cache_control)
                        self._on_cache_store(url, response.status_code, max_age)
            except Exception:
                pass  # Silently ignore background revalidation errors
            finally:
                self._revalidating.discard(url)

        asyncio.create_task(_revalidate())

    def _parse_max_age(self, cache_control: str) -> float:
        """Parse max-age from Cache-Control header."""
        import re

        match = re.search(r"max-age=(\d+)", cache_control, re.IGNORECASE)
        if match:
            return float(match.group(1))

        match = re.search(r"s-maxage=(\d+)", cache_control, re.IGNORECASE)
        if match:
            return float(match.group(1))

        return 0

    async def aclose(self) -> None:
        """Close the transport."""
        await self._cache.close()
        await self._inner.aclose()


class SyncCacheResponseTransport(httpx.BaseTransport):
    """
    Synchronous cache response transport wrapper for httpx.

    Note: Background revalidation is not available in sync mode.
    """

    def __init__(
        self,
        inner: httpx.BaseTransport,
        *,
        config: Optional[CacheResponseConfig] = None,
        on_cache_hit: Optional[Callable[[str, str], None]] = None,
        on_cache_miss: Optional[Callable[[str], None]] = None,
        on_cache_store: Optional[Callable[[str, int, float], None]] = None,
    ) -> None:
        """
        Create a new SyncCacheResponseTransport.

        Args:
            inner: The wrapped transport to delegate requests to
            config: Cache configuration
            on_cache_hit: Callback when cache hit occurs
            on_cache_miss: Callback when cache miss occurs
            on_cache_store: Callback when response is cached
        """
        self._inner = inner
        self._config = config or CacheResponseConfig()
        self._on_cache_hit = on_cache_hit
        self._on_cache_miss = on_cache_miss
        self._on_cache_store = on_cache_store

        # Simple sync cache (dict-based)
        self._cache: Dict[str, tuple] = {}

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Handle a sync HTTP request with caching capabilities."""
        import time
        from cache_response import (
            is_cacheable_method,
            is_cacheable_status,
            parse_cache_control,
            should_cache,
            calculate_expiration,
            extract_etag,
            extract_last_modified,
            normalize_headers,
        )

        method = request.method
        url = str(request.url)

        # Check if method is cacheable
        cacheable_methods = self._config.methods or ["GET", "HEAD"]
        if not is_cacheable_method(method, cacheable_methods):
            return self._inner.handle_request(request)

        cache_key = f"{method}:{url}"
        now = time.time()

        # Check cache
        if cache_key in self._cache:
            cached_data, expires_at, cached_headers, etag, last_modified = self._cache[cache_key]
            if now < expires_at:
                if self._on_cache_hit:
                    self._on_cache_hit(url, "fresh")
                return httpx.Response(
                    status_code=cached_data["status_code"],
                    headers=cached_data["headers"],
                    content=cached_data["content"],
                )

        # Cache miss
        if self._on_cache_miss:
            self._on_cache_miss(url)

        # Execute request
        response = self._inner.handle_request(request)
        content = response.read()

        # Check if cacheable
        cacheable_statuses = self._config.cacheable_statuses or [
            200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501
        ]
        if not is_cacheable_status(response.status_code, cacheable_statuses):
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )

        # Check cache-control
        response_headers = normalize_headers(dict(response.headers))
        cache_control = response_headers.get("cache-control")
        directives = parse_cache_control(cache_control)

        if not should_cache(
            directives,
            respect_no_store=self._config.respect_no_store,
            respect_no_cache=self._config.respect_no_cache,
            respect_private=self._config.respect_private,
        ):
            return httpx.Response(
                status_code=response.status_code,
                headers=response.headers,
                content=content,
            )

        # Calculate expiration
        expires_at = calculate_expiration(
            response_headers,
            directives,
            self._config.default_ttl_seconds,
            self._config.max_ttl_seconds,
        )

        if expires_at > now:
            # Cache the response
            cached_data = {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "content": content,
            }
            etag = extract_etag(response_headers)
            last_modified = extract_last_modified(response_headers)
            self._cache[cache_key] = (
                cached_data,
                expires_at,
                response_headers,
                etag,
                last_modified,
            )

            if self._on_cache_store:
                max_age = directives.max_age or directives.s_maxage or 0
                self._on_cache_store(url, response.status_code, float(max_age))

        return httpx.Response(
            status_code=response.status_code,
            headers=response.headers,
            content=content,
        )

    def close(self) -> None:
        """Close the transport."""
        self._cache.clear()
        self._inner.close()
