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


# =============================================================================
# LOGIC TESTING - COMPREHENSIVE COVERAGE
# =============================================================================
# Additional tests for:
# - Decision/Branch Coverage
# - Boundary Value Analysis
# - State Transition Testing
# - Path Coverage
# - Error Handling
# =============================================================================


class TestConfigurationMerging:
    @pytest.mark.asyncio
    async def test_default_config_values(self):
        cache = ResponseCache()
        config = cache.get_config()

        assert config.methods == ["GET", "HEAD"]
        assert config.cacheable_statuses == [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501]
        assert config.default_ttl_seconds == 0
        assert config.max_ttl_seconds == 86400
        assert config.respect_no_cache is True
        assert config.respect_no_store is True
        assert config.respect_private is True

        await cache.close()

    @pytest.mark.asyncio
    async def test_partial_config_merge(self):
        cache = ResponseCache(
            CacheResponseConfig(
                default_ttl_seconds=60,
                respect_no_store=False,
            )
        )
        config = cache.get_config()

        assert config.default_ttl_seconds == 60
        assert config.respect_no_store is False
        assert config.respect_no_cache is True  # default

        await cache.close()


class TestKeyGeneration:
    @pytest.fixture
    async def cache(self):
        c = ResponseCache()
        yield c
        await c.close()

    @pytest.mark.asyncio
    async def test_key_without_query(self):
        cache = ResponseCache(CacheResponseConfig(include_query_in_key=False))
        key = cache.generate_key("GET", "https://example.com/api?page=1&limit=10")
        assert "page" not in key
        await cache.close()

    def test_include_vary_headers(self, cache):
        request_headers = {"accept": "application/json", "accept-encoding": "gzip"}
        key = cache.generate_key("GET", "https://example.com/api", request_headers, ["accept"])
        assert "accept" in key

    def test_different_vary_headers_different_keys(self, cache):
        headers1 = {"accept": "application/json"}
        headers2 = {"accept": "text/html"}

        key1 = cache.generate_key("GET", "https://example.com/api", headers1, ["accept"])
        key2 = cache.generate_key("GET", "https://example.com/api", headers2, ["accept"])

        assert key1 != key2


class TestStoreAndLookupPathCoverage:
    @pytest.fixture
    async def cache(self):
        c = ResponseCache(
            CacheResponseConfig(
                default_ttl_seconds=300,
                max_ttl_seconds=3600,
            )
        )
        yield c
        await c.close()

    @pytest.mark.asyncio
    async def test_no_cache_directive_still_caches(self, cache):
        url = "https://example.com/api"
        headers = {"cache-control": "no-cache, max-age=3600"}

        stored = await cache.store("GET", url, 200, headers, b"body")
        assert stored is True

        lookup = await cache.lookup("GET", url)
        assert lookup.found is True
        assert lookup.should_revalidate is True

    @pytest.mark.asyncio
    async def test_already_expired_not_cached(self, cache):
        url = "https://example.com/api/expired"
        headers = {"cache-control": "max-age=0"}

        stored = await cache.store("GET", url, 200, headers, b"body")
        assert stored is False

    @pytest.mark.asyncio
    async def test_handle_none_body(self, cache):
        url = "https://example.com/api"
        headers = {"cache-control": "max-age=3600"}

        stored = await cache.store("GET", url, 204, headers, None)
        assert stored is True

        lookup = await cache.lookup("GET", url)
        assert lookup.found is True
        assert lookup.response.body is None

    @pytest.mark.asyncio
    async def test_handle_bytes_body(self, cache):
        url = "https://example.com/api"
        headers = {"cache-control": "max-age=3600"}
        body = b"binary data"

        stored = await cache.store("GET", url, 200, headers, body)
        assert stored is True

        lookup = await cache.lookup("GET", url)
        assert lookup.response.body == body


class TestVaryHeaderHandling:
    @pytest.fixture
    async def cache(self):
        c = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))
        yield c
        await c.close()

    @pytest.mark.asyncio
    async def test_vary_headers_no_match(self, cache):
        url = "https://example.com/api"
        response_headers = {
            "cache-control": "max-age=3600",
            "vary": "Accept",
        }

        await cache.store("GET", url, 200, response_headers, b"body", {"Accept": "application/json"})

        lookup = await cache.lookup("GET", url, {"Accept": "text/html"})
        assert lookup.found is False


class TestEventEmission:
    @pytest.fixture
    async def cache(self):
        c = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))
        yield c
        await c.close()

    @pytest.mark.asyncio
    async def test_bypass_event_non_cacheable_method(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.store("POST", "https://example.com/api", 200, {"cache-control": "max-age=3600"}, b"body")

        bypass_event = next((e for e in events if e.type == CacheResponseEventType.CACHE_BYPASS), None)
        assert bypass_event is not None

    @pytest.mark.asyncio
    async def test_bypass_event_non_cacheable_status(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.store("GET", "https://example.com/api", 500, {"cache-control": "max-age=3600"}, b"body")

        bypass_event = next((e for e in events if e.type == CacheResponseEventType.CACHE_BYPASS), None)
        assert bypass_event is not None

    @pytest.mark.asyncio
    async def test_bypass_event_no_store(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.store("GET", "https://example.com/api", 200, {"cache-control": "no-store"}, b"body")

        bypass_event = next((e for e in events if e.type == CacheResponseEventType.CACHE_BYPASS), None)
        assert bypass_event is not None

    @pytest.mark.asyncio
    async def test_expire_event_on_invalidation(self, cache):
        events = []
        cache.on(lambda e: events.append(e))

        await cache.store("GET", "https://example.com/api", 200, {"cache-control": "max-age=3600"}, b"body")
        await cache.invalidate("GET", "https://example.com/api")

        expire_event = next((e for e in events if e.type == CacheResponseEventType.CACHE_EXPIRE), None)
        assert expire_event is not None


class TestRevalidation:
    @pytest.fixture
    async def cache(self):
        c = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))
        yield c
        await c.close()

    @pytest.mark.asyncio
    async def test_revalidate_nonexistent(self, cache):
        result = await cache.revalidate("GET", "https://example.com/nonexistent")
        assert result is False

    @pytest.mark.asyncio
    async def test_preserve_original_body(self, cache):
        url = "https://example.com/api"
        original_body = b"original body content"

        # Use stale-while-revalidate to keep entry available for revalidation
        await cache.store("GET", url, 200, {"cache-control": "max-age=1, stale-while-revalidate=60"}, original_body)
        await asyncio.sleep(1.1)
        await cache.revalidate("GET", url, {"cache-control": "max-age=3600"})

        lookup = await cache.lookup("GET", url)
        assert lookup.response.body == original_body

    @pytest.mark.asyncio
    async def test_update_etag(self, cache):
        url = "https://example.com/api"

        await cache.store("GET", url, 200, {"cache-control": "max-age=3600", "etag": '"old"'}, b"body")
        await cache.revalidate("GET", url, {"cache-control": "max-age=3600", "etag": '"new"'})

        lookup = await cache.lookup("GET", url)
        assert lookup.etag == '"new"'


class TestBackgroundRevalidation:
    @pytest.mark.asyncio
    async def test_no_trigger_for_fresh(self):
        revalidate_called = False
        cache = ResponseCache(CacheResponseConfig(stale_while_revalidate=True))

        async def mock_revalidator(url, headers):
            nonlocal revalidate_called
            revalidate_called = True

        cache.set_background_revalidator(mock_revalidator)

        await cache.store("GET", "https://example.com/api", 200, {"cache-control": "max-age=3600"}, b"body")
        await cache.lookup("GET", "https://example.com/api")

        await asyncio.sleep(0.1)

        assert revalidate_called is False

        await cache.close()


class TestClearAndClose:
    @pytest.mark.asyncio
    async def test_clear_all_entries(self):
        cache = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))

        await cache.store("GET", "https://example.com/api1", 200, {"cache-control": "max-age=3600"}, b"body1")
        await cache.store("GET", "https://example.com/api2", 200, {"cache-control": "max-age=3600"}, b"body2")

        stats = await cache.get_stats()
        assert stats.entries == 2

        await cache.clear()

        stats = await cache.get_stats()
        assert stats.entries == 0

        await cache.close()

    @pytest.mark.asyncio
    async def test_close_cleans_up(self):
        cache = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))
        await cache.store("GET", "https://example.com/api", 200, {"cache-control": "max-age=3600"}, b"body")
        await cache.close()


class TestGetStats:
    @pytest.mark.asyncio
    async def test_correct_stats(self):
        cache = ResponseCache(CacheResponseConfig(default_ttl_seconds=300))

        stats1 = await cache.get_stats()
        assert stats1.entries == 0

        await cache.store("GET", "https://example.com/api1", 200, {"cache-control": "max-age=3600"}, b"body1")

        stats2 = await cache.get_stats()
        assert stats2.entries == 1

        await cache.close()
