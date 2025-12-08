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

    def test_empty_headers(self):
        assert normalize_headers({}) == {}


# =============================================================================
# LOGIC TESTING COVERAGE
# =============================================================================
# The following tests cover additional logic testing methodologies:
# - Decision/Branch Coverage
# - Boundary Value Analysis
# - Path Coverage
# - MC/DC (Modified Condition/Decision Coverage)
# - State Transition Testing
# =============================================================================


class TestParseCacheControlDecisionBranch:
    """Decision/Branch Coverage tests."""

    def test_parse_proxy_revalidate(self):
        result = parse_cache_control("proxy-revalidate")
        assert result.proxy_revalidate is True

    def test_parse_no_transform(self):
        result = parse_cache_control("no-transform")
        assert result.no_transform is True

    def test_parse_invalid_max_age(self):
        result = parse_cache_control("max-age=invalid")
        assert result.max_age is None

    def test_parse_whitespace_in_directives(self):
        result = parse_cache_control("  max-age=300  ,  no-cache  ")
        assert result.max_age == 300
        assert result.no_cache is True

    def test_parse_unknown_directives(self):
        result = parse_cache_control("max-age=300, unknown-directive=value")
        assert result.max_age == 300

    def test_parse_all_directives(self):
        header = (
            "public, private, no-cache, no-store, max-age=100, s-maxage=200, "
            "must-revalidate, proxy-revalidate, no-transform, stale-while-revalidate=30, "
            "stale-if-error=60, immutable"
        )
        result = parse_cache_control(header)
        assert result.public is True
        assert result.private is True
        assert result.no_cache is True
        assert result.no_store is True
        assert result.max_age == 100
        assert result.s_maxage == 200
        assert result.must_revalidate is True
        assert result.proxy_revalidate is True
        assert result.no_transform is True
        assert result.stale_while_revalidate == 30
        assert result.stale_if_error == 60
        assert result.immutable is True


class TestBuildCacheControlPathCoverage:
    """Path Coverage tests."""

    def test_build_with_all_directives(self):
        result = build_cache_control(
            CacheControlDirectives(
                no_store=True,
                no_cache=True,
                private=True,
                public=True,
                must_revalidate=True,
                proxy_revalidate=True,
                no_transform=True,
                immutable=True,
                max_age=300,
                s_maxage=600,
                stale_while_revalidate=30,
                stale_if_error=60,
            )
        )
        assert "no-store" in result
        assert "no-cache" in result
        assert "private" in result
        assert "public" in result
        assert "must-revalidate" in result
        assert "proxy-revalidate" in result
        assert "no-transform" in result
        assert "immutable" in result
        assert "max-age=300" in result
        assert "s-maxage=600" in result
        assert "stale-while-revalidate=30" in result
        assert "stale-if-error=60" in result

    def test_build_with_zero_values(self):
        result = build_cache_control(
            CacheControlDirectives(max_age=0, stale_while_revalidate=0)
        )
        assert "max-age=0" in result
        assert "stale-while-revalidate=0" in result


class TestCalculateExpirationBoundary:
    """Boundary Value Analysis tests."""

    def test_zero_max_age(self):
        now = time.time()
        result = calculate_expiration({}, CacheControlDirectives(max_age=0))
        assert abs(result - now) < 1

    def test_zero_s_maxage(self):
        now = time.time()
        result = calculate_expiration({}, CacheControlDirectives(s_maxage=0, max_age=100))
        assert abs(result - now) < 1

    def test_max_age_equals_max_ttl(self):
        now = time.time()
        result = calculate_expiration(
            {}, CacheControlDirectives(max_age=3600), max_ttl_seconds=3600
        )
        assert abs(result - (now + 3600)) < 1

    def test_max_age_greater_than_max_ttl(self):
        now = time.time()
        result = calculate_expiration(
            {}, CacheControlDirectives(max_age=99999), max_ttl_seconds=3600
        )
        assert abs(result - (now + 3600)) < 1

    def test_default_ttl_equals_max_ttl(self):
        now = time.time()
        result = calculate_expiration(
            {}, CacheControlDirectives(), default_ttl_seconds=3600, max_ttl_seconds=3600
        )
        assert abs(result - (now + 3600)) < 1


class TestDetermineFreshnessStateTesting:
    """State Transition Testing."""

    def test_fresh_immutable_before_expiration(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 1,
            expires_at=now + 1000,
            directives=CacheControlDirectives(immutable=True),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.FRESH

    def test_stale_immutable_with_swr(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now - 1,
            directives=CacheControlDirectives(immutable=True, stale_while_revalidate=60),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.STALE

    def test_stale_with_stale_if_error(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now - 1,
            directives=CacheControlDirectives(stale_if_error=60),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.STALE

    def test_expired_outside_stale_windows(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 200000,
            expires_at=now - 100000,
            directives=CacheControlDirectives(stale_while_revalidate=60, stale_if_error=30),
        )
        assert determine_freshness(metadata, now) == CacheFreshness.EXPIRED

    def test_expired_no_stale_directives(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now - 1000,
        )
        assert determine_freshness(metadata, now) == CacheFreshness.EXPIRED

    def test_no_directives(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now + 10000,
        )
        assert determine_freshness(metadata, now) == CacheFreshness.FRESH

    def test_exactly_at_expiration_boundary(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now,
        )
        assert determine_freshness(metadata, now) == CacheFreshness.EXPIRED


class TestShouldCacheMCDC:
    """MC/DC (Modified Condition/Decision Coverage) tests."""

    def test_cache_with_safe_directives(self):
        assert (
            should_cache(
                CacheControlDirectives(public=True, max_age=3600),
                respect_no_store=True,
                respect_private=True,
            )
            is True
        )

    def test_no_cache_when_no_store_respected(self):
        assert (
            should_cache(CacheControlDirectives(no_store=True), respect_no_store=True)
            is False
        )

    def test_cache_when_no_store_not_respected(self):
        assert (
            should_cache(CacheControlDirectives(no_store=True), respect_no_store=False)
            is True
        )

    def test_no_cache_when_private_respected(self):
        assert (
            should_cache(CacheControlDirectives(private=True), respect_private=True)
            is False
        )

    def test_cache_when_private_not_respected(self):
        assert (
            should_cache(CacheControlDirectives(private=True), respect_private=False)
            is True
        )

    def test_cache_with_no_cache(self):
        assert should_cache(CacheControlDirectives(no_cache=True)) is True

    def test_cache_with_empty_directives(self):
        assert should_cache(CacheControlDirectives()) is True

    def test_no_cache_both_restrictions(self):
        assert (
            should_cache(
                CacheControlDirectives(no_store=True, private=True),
                respect_no_store=True,
                respect_private=True,
            )
            is False
        )


class TestNeedsRevalidationBranch:
    """Branch Coverage tests."""

    def test_must_revalidate_stale(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now - 10000,
            expires_at=now - 1000,
            directives=CacheControlDirectives(must_revalidate=True),
        )
        assert needs_revalidation(metadata) is True

    def test_must_revalidate_fresh(self):
        now = time.time()
        metadata = CacheEntryMetadata(
            url="https://example.com",
            method="GET",
            status_code=200,
            headers={},
            cached_at=now,
            expires_at=now + 10000,
            directives=CacheControlDirectives(must_revalidate=True),
        )
        assert needs_revalidation(metadata) is False

    def test_no_cache_not_respected(self):
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
        assert needs_revalidation(metadata, respect_no_cache=False) is False

    def test_no_directives(self):
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


class TestVaryHandlingPath:
    """Path Coverage for Vary handling."""

    def test_multiple_headers_different_cases(self):
        headers = {
            "accept": "application/json",
            "ACCEPT-ENCODING": "gzip, deflate",
            "Accept-Language": "en-US",
        }
        result = extract_vary_headers(
            headers, ["Accept", "accept-encoding", "ACCEPT-LANGUAGE"]
        )
        assert "accept" in result
        assert "accept-encoding" in result
        assert "accept-language" in result

    def test_missing_vary_headers(self):
        headers = {"content-type": "text/html"}
        result = extract_vary_headers(headers, ["accept", "accept-encoding"])
        assert result == {}

    def test_match_subset_headers(self):
        request = {"accept": "application/json", "accept-encoding": "gzip"}
        cached = {"accept": "application/json"}
        assert match_vary_headers(request, cached) is True

    def test_no_match_missing_in_request(self):
        request = {}
        cached = {"accept": "application/json"}
        assert match_vary_headers(request, cached) is False


class TestCacheableStatusBoundary:
    """Boundary Value tests for status codes."""

    def test_all_default_cacheable(self):
        default_cacheable = [200, 203, 204, 206, 300, 301, 404, 405, 410, 414, 501]
        for status in default_cacheable:
            assert is_cacheable_status(status) is True

    def test_common_non_cacheable(self):
        non_cacheable = [201, 202, 302, 303, 304, 307, 308, 400, 401, 403, 500, 502, 503]
        for status in non_cacheable:
            assert is_cacheable_status(status) is False

    def test_empty_custom_statuses(self):
        assert is_cacheable_status(200, []) is False

    def test_single_status_array(self):
        assert is_cacheable_status(200, [200]) is True
        assert is_cacheable_status(201, [200]) is False


class TestCacheableMethodCase:
    """Case sensitivity tests for methods."""

    def test_lowercase_methods(self):
        assert is_cacheable_method("get") is True
        assert is_cacheable_method("head") is True
        assert is_cacheable_method("post") is False

    def test_mixed_case_methods(self):
        assert is_cacheable_method("Get") is True
        assert is_cacheable_method("HeAd") is True

    def test_custom_methods(self):
        assert is_cacheable_method("POST", ["GET", "POST"]) is True
        assert is_cacheable_method("PUT", ["GET", "POST"]) is False

    def test_empty_custom_methods(self):
        assert is_cacheable_method("GET", []) is False
