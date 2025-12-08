"""Tests for ResponseCache."""
import asyncio
import time
import pytest

from cache_response import (
    ResponseCache,
    create_response_cache,
    CacheResponseConfig,
    CacheResponseEvent,
    CacheResponseEventType,
    CacheFreshness,
    MemoryCacheStore,
)


@pytest.fixture
async def cache():
    """Create a ResponseCache for testing."""
    c = ResponseCache(
        CacheResponseConfig(
            default_ttl_seconds=300,  # 5 minutes
            max_ttl_seconds=3600,  # 1 hour
        )
    )
    yield c
    await c.close()


class TestIsCacheable:
    def test_get_and_head_are_cacheable(self, cache):
        assert cache.is_cacheable("GET") is True
        assert cache.is_cacheable("HEAD") is True

    def test_other_methods_not_cacheable(self, cache):
        assert cache.is_cacheable("POST") is False
        assert cache.is_cacheable("PUT") is False
        assert cache.is_cacheable("DELETE") is False


class TestGenerateKey:
    def test_simple_url(self, cache):
        key = cache.generate_key("GET", "https://example.com/api/users")
        assert key == "GET:https://example.com/api/users"

    def test_includes_query_string(self, cache):
        key = cache.generate_key("GET", "https://example.com/api/users?page=1")
        assert "page=1" in key

    def test_different_methods_different_keys(self, cache):
        get_key = cache.generate_key("GET", "https://example.com/api")
        head_key = cache.generate_key("HEAD", "https://example.com/api")
        assert get_key != head_key


class TestStoreAndLookup:
    @pytest.mark.asyncio
    async def test_store_and_retrieve(self, cache):
        url = "https://example.com/api/users"
        headers = {
            "content-type": "application/json",
            "cache-control": "max-age=3600",
        }
        body = b'{"users": []}'

        stored = await cache.store("GET", url, 200, headers, body)
        assert stored is True

        lookup = await cache.lookup("GET", url)
        assert lookup.found is True
        assert lookup.freshness == CacheFreshness.FRESH
        assert lookup.response.body == body
        assert lookup.response.metadata.status_code == 200

    @pytest.mark.asyncio
    async def test_not_found_for_nonexistent_key(self, cache):
        lookup = await cache.lookup("GET", "https://example.com/not-cached")
        assert lookup.found is False

    @pytest.mark.asyncio
    async def test_no_store_non_cacheable_methods(self, cache):
        url = "https://example.com/api/users"
        headers = {"cache-control": "max-age=3600"}
        stored = await cache.store("POST", url, 200, headers, b"body")
        assert stored is False

    @pytest.mark.asyncio
    async def test_no_store_non_cacheable_status(self, cache):
        url = "https://example.com/api/users"
        headers = {"cache-control": "max-age=3600"}
        stored = await cache.store("GET", url, 500, headers, b"body")
        assert stored is False

    @pytest.mark.asyncio
    async def test_no_store_directive(self, cache):
        url = "https://example.com/api/users"
        headers = {"cache-control": "no-store"}
        stored = await cache.store("GET", url, 200, headers, b"body")
        assert stored is False

    @pytest.mark.asyncio
    async def test_no_store_private_directive(self, cache):
        url = "https://example.com/api/users"
        headers = {"cache-control": "private, max-age=3600"}
        stored = await cache.store("GET", url, 200, headers, b"body")
        assert stored is False


class TestConditionalRequests:
    @pytest.mark.asyncio
    async def test_returns_etag(self, cache):
        url = "https://example.com/api/users"
        headers = {
            "cache-control": "max-age=3600",
            "etag": '"abc123"',
        }
        await cache.store("GET", url, 200, headers, b"body")

        lookup = await cache.lookup("GET", url)
        assert lookup.etag == '"abc123"'

    @pytest.mark.asyncio
    async def test_returns_last_modified(self, cache):
        url = "https://example.com/api/users"
        last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"
        headers = {
            "cache-control": "max-age=3600",
            "last-modified": last_modified,
        }
        await cache.store("GET", url, 200, headers, b"body")

        lookup = await cache.lookup("GET", url)
        assert lookup.last_modified == last_modified


class TestRevalidation:
    @pytest.mark.asyncio
    async def test_update_expiration(self, cache):
        url = "https://example.com/api/users"
        # Store with short TTL
        headers = {"cache-control": "max-age=1"}
        await cache.store("GET", url, 200, headers, b"body")

        # Wait for it to become stale
        await asyncio.sleep(1.1)

        lookup = await cache.lookup("GET", url)
        assert lookup.freshness != CacheFreshness.FRESH

        # Revalidate
        new_headers = {"cache-control": "max-age=3600"}
        await cache.revalidate("GET", url, new_headers)

        lookup = await cache.lookup("GET", url)
        assert lookup.freshness == CacheFreshness.FRESH


class TestInvalidation:
    @pytest.mark.asyncio
    async def test_invalidate_cached_response(self, cache):
        url = "https://example.com/api/users"
        headers = {"cache-control": "max-age=3600"}
        await cache.store("GET", url, 200, headers, b"body")

        lookup = await cache.lookup("GET", url)
        assert lookup.found is True

        invalidated = await cache.invalidate("GET", url)
        assert invalidated is True

        lookup = await cache.lookup("GET", url)
        assert lookup.found is False


class TestEvents:
    @pytest.mark.asyncio
    async def test_cache_hit_event(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        url = "https://example.com/api/users"
        await cache.store("GET", url, 200, {"cache-control": "max-age=3600"}, b"body")
        await cache.lookup("GET", url)

        hit_event = next(
            (e for e in events if e.type == CacheResponseEventType.CACHE_HIT), None
        )
        assert hit_event is not None
        assert hit_event.url == url

    @pytest.mark.asyncio
    async def test_cache_miss_event(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.lookup("GET", "https://example.com/not-cached")

        miss_event = next(
            (e for e in events if e.type == CacheResponseEventType.CACHE_MISS), None
        )
        assert miss_event is not None

    @pytest.mark.asyncio
    async def test_cache_store_event(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.store(
            "GET", "https://example.com/api", 200, {"cache-control": "max-age=3600"}, b"body"
        )

        store_event = next(
            (e for e in events if e.type == CacheResponseEventType.CACHE_STORE), None
        )
        assert store_event is not None

    @pytest.mark.asyncio
    async def test_remove_event_listener(self, cache):
        events = []
        listener = lambda e: events.append(e)
        unsubscribe = cache.on(listener)

        await cache.lookup("GET", "https://example.com/test1")
        assert len(events) > 0

        count_before = len(events)
        unsubscribe()

        await cache.lookup("GET", "https://example.com/test2")
        assert len(events) == count_before


class TestVaryHandling:
    @pytest.mark.asyncio
    async def test_no_cache_vary_star(self, cache):
        url = "https://example.com/api/data"
        headers = {
            "cache-control": "max-age=3600",
            "vary": "*",
        }
        stored = await cache.store("GET", url, 200, headers, b"body")
        assert stored is False

    @pytest.mark.asyncio
    async def test_match_vary_headers(self, cache):
        url = "https://example.com/api/data"
        response_headers = {
            "cache-control": "max-age=3600",
            "vary": "Accept",
        }
        request_headers = {"Accept": "application/json"}

        await cache.store("GET", url, 200, response_headers, b"json body", request_headers)

        # Same accept header should hit cache
        lookup = await cache.lookup("GET", url, {"Accept": "application/json"})
        assert lookup.found is True


class TestStaleWhileRevalidate:
    @pytest.mark.asyncio
    async def test_trigger_background_revalidation(self):
        url = "https://example.com/api/data"
        revalidate_called = False

        stale_cache = ResponseCache(
            CacheResponseConfig(stale_while_revalidate=True)
        )

        async def mock_revalidator(url, headers):
            nonlocal revalidate_called
            revalidate_called = True

        stale_cache.set_background_revalidator(mock_revalidator)

        # Store with very short TTL
        await stale_cache.store(
            "GET",
            url,
            200,
            {"cache-control": "max-age=0, stale-while-revalidate=60"},
            b"body",
        )

        # Wait for it to become stale
        await asyncio.sleep(0.05)

        lookup = await stale_cache.lookup("GET", url)
        assert lookup.found is True
        assert lookup.freshness == CacheFreshness.STALE

        # Wait for background revalidation
        await asyncio.sleep(0.1)
        assert revalidate_called is True

        await stale_cache.close()


class TestCreateResponseCache:
    def test_create_with_default_config(self):
        cache = create_response_cache()
        assert isinstance(cache, ResponseCache)

    def test_create_with_custom_config(self):
        cache = create_response_cache(CacheResponseConfig(default_ttl_seconds=60))
        assert cache.get_config().default_ttl_seconds == 60

    def test_create_with_custom_store(self):
        store = MemoryCacheStore(max_entries=10)
        cache = create_response_cache(store=store)
        assert isinstance(cache, ResponseCache)
