"""Tests for Cache-Control parser and utilities."""
import time
import pytest

from cache_response import (
    parse_cache_control,
    build_cache_control,
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
    CacheControlDirectives,
    CacheEntryMetadata,
    CacheFreshness,
)


class TestParseCacheControl:
    def test_parse_empty_header(self):
        assert parse_cache_control(None) == CacheControlDirectives()
        assert parse_cache_control("") == CacheControlDirectives()

    def test_parse_no_store(self):
        result = parse_cache_control("no-store")
        assert result.no_store is True

    def test_parse_no_cache(self):
        result = parse_cache_control("no-cache")
        assert result.no_cache is True

    def test_parse_max_age(self):
        result = parse_cache_control("max-age=3600")
        assert result.max_age == 3600

    def test_parse_s_maxage(self):
        result = parse_cache_control("s-maxage=7200")
        assert result.s_maxage == 7200

    def test_parse_private(self):
        result = parse_cache_control("private")
        assert result.private is True

    def test_parse_public(self):
        result = parse_cache_control("public")
        assert result.public is True

    def test_parse_must_revalidate(self):
        result = parse_cache_control("must-revalidate")
        assert result.must_revalidate is True

    def test_parse_stale_while_revalidate(self):
        result = parse_cache_control("stale-while-revalidate=60")
        assert result.stale_while_revalidate == 60

    def test_parse_stale_if_error(self):
        result = parse_cache_control("stale-if-error=300")
        assert result.stale_if_error == 300

    def test_parse_immutable(self):
        result = parse_cache_control("immutable")
        assert result.immutable is True

    def test_parse_multiple_directives(self):
        result = parse_cache_control("public, max-age=3600, must-revalidate")
        assert result.public is True
        assert result.max_age == 3600
        assert result.must_revalidate is True

    def test_parse_complex_header(self):
        header = "public, max-age=86400, s-maxage=3600, stale-while-revalidate=60, immutable"
        result = parse_cache_control(header)
        assert result.public is True
        assert result.max_age == 86400
        assert result.s_maxage == 3600
        assert result.stale_while_revalidate == 60
        assert result.immutable is True

    def test_case_insensitivity(self):
        result = parse_cache_control("Max-Age=100, No-Store")
        assert result.max_age == 100
        assert result.no_store is True


class TestBuildCacheControl:
    def test_build_empty(self):
        assert build_cache_control(CacheControlDirectives()) == ""

    def test_build_single_directive(self):
        assert build_cache_control(CacheControlDirectives(no_store=True)) == "no-store"
        assert build_cache_control(CacheControlDirectives(max_age=3600)) == "max-age=3600"

    def test_build_multiple_directives(self):
        result = build_cache_control(
            CacheControlDirectives(public=True, max_age=3600, must_revalidate=True)
        )
        assert "public" in result
        assert "max-age=3600" in result
        assert "must-revalidate" in result


class TestExtractHeaders:
    def test_extract_etag(self):
        assert extract_etag({"etag": '"abc123"'}) == '"abc123"'
        assert extract_etag({"ETag": '"def456"'}) == '"def456"'
        assert extract_etag({}) is None

    def test_extract_last_modified(self):
        date = "Wed, 21 Oct 2015 07:28:00 GMT"
        assert extract_last_modified({"last-modified": date}) == date
        assert extract_last_modified({"Last-Modified": date}) == date
        assert extract_last_modified({}) is None


class TestCalculateExpiration:
    def test_no_store_returns_now(self):
        now = time.time()
        result = calculate_expiration({}, CacheControlDirectives(no_store=True))
        assert result <= now + 1

    def test_s_maxage_over_max_age(self):
        now = time.time()
        result = calculate_expiration(
            {}, CacheControlDirectives(s_maxage=7200, max_age=3600)
        )
        assert abs(result - (now + 7200)) < 1

    def test_max_age(self):
        now = time.time()
        result = calculate_expiration({}, CacheControlDirectives(max_age=3600))
        assert abs(result - (now + 3600)) < 1

    def test_default_ttl(self):
        now = time.time()
        result = calculate_expiration({}, CacheControlDirectives(), default_ttl_seconds=300)
        assert abs(result - (now + 300)) < 1

    def test_max_ttl_limit(self):
        now = time.time()
        result = calculate_expiration(
            {}, CacheControlDirectives(max_age=999999), max_ttl_seconds=3600
        )
        assert abs(result - (now + 3600)) < 1


class TestDetermineFreshness:
    def test_fresh_response(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 1,
            expires_at=now + 1000,
        )
        assert determine_freshness(metadata, now) == CacheFreshness.FRESH

    def test_stale_within_swr_window(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now - 1,
            directives=CacheControlDirectives(stale_while_revalidate=60),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.STALE

    def test_expired_outside_swr_window(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 100000,
            expires_at=now - 90000,
            directives=CacheControlDirectives(stale_while_revalidate=60),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.EXPIRED


class TestCacheability:
    def test_cacheable_status(self):
        assert is_cacheable_status(200) is True
        assert is_cacheable_status(301) is True
        assert is_cacheable_status(404) is True
        assert is_cacheable_status(201) is False
        assert is_cacheable_status(500) is False

    def test_custom_cacheable_statuses(self):
        assert is_cacheable_status(201, [200, 201]) is True

    def test_cacheable_method(self):
        assert is_cacheable_method("GET") is True
        assert is_cacheable_method("HEAD") is True
        assert is_cacheable_method("get") is True
        assert is_cacheable_method("POST") is False
        assert is_cacheable_method("PUT") is False


class TestShouldCache:
    def test_no_store(self):
        assert should_cache(CacheControlDirectives(no_store=True)) is False

    def test_private(self):
        assert should_cache(CacheControlDirectives(private=True)) is False

    def test_public(self):
        assert should_cache(CacheControlDirectives(public=True)) is True

    def test_max_age_without_restrictions(self):
        assert should_cache(CacheControlDirectives(max_age=3600)) is True

    def test_respect_config_options(self):
        assert (
            should_cache(CacheControlDirectives(no_store=True), respect_no_store=False)
            is True
        )
        assert (
            should_cache(CacheControlDirectives(private=True), respect_private=False)
            is True
        )


class TestNeedsRevalidation:
    def test_no_cache_directive(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now,
            expires_at=now + 10000,
            directives=CacheControlDirectives(no_cache=True),
        )
        assert needs_revalidation(metadata) is True

    def test_fresh_without_no_cache(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now,
            expires_at=now + 10000,
        )
        assert needs_revalidation(metadata) is False


class TestVaryHandling:
    def test_parse_vary_single(self):
        assert parse_vary("Accept") == ["accept"]

    def test_parse_vary_multiple(self):
        assert parse_vary("Accept, Accept-Encoding, Origin") == [
            "accept",
            "accept-encoding",
            "origin",
        ]

    def test_parse_vary_star(self):
        assert parse_vary("*") == ["*"]

    def test_parse_vary_empty(self):
        assert parse_vary(None) == []

    def test_is_vary_uncacheable(self):
        assert is_vary_uncacheable("*") is True
        assert is_vary_uncacheable("Accept") is False

    def test_extract_vary_headers(self):
        headers = {
            "Accept": "application/json",
            "Accept-Encoding": "gzip",
            "Content-Type": "text/html",
        }
        result = extract_vary_headers(headers, ["accept", "accept-encoding"])
        assert result == {
            "accept": "application/json",
            "accept-encoding": "gzip",
        }

    def test_match_vary_headers_matching(self):
        request = {"accept": "application/json"}
        cached = {"accept": "application/json"}
        assert match_vary_headers(request, cached) is True

    def test_match_vary_headers_not_matching(self):
        request = {"accept": "text/html"}
        cached = {"accept": "application/json"}
        assert match_vary_headers(request, cached) is False


class TestNormalizeHeaders:
    def test_lowercase_keys(self):
        headers = {
            "Content-Type": "application/json",
            "Accept": "text/html",
            "X-Custom-Header": "value",
        }
        assert normalize_headers(headers) == {
            "content-type": "application/json",
            "accept": "text/html",
            "x-custom-header": "value",
        }
