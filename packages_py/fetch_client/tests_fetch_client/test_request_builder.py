"""
Tests for request_builder.py
Logic testing: Decision/Branch, Boundary Value, Path coverage
"""
import pytest

from fetch_client.core.request_builder import (
    build_url,
    build_headers,
    resolve_auth_header,
    build_body,
    create_request_context,
)
from fetch_client.config import (
    AuthConfig,
    ClientConfig,
    ResolvedConfig,
    TimeoutConfig,
    DefaultSerializer,
    resolve_config,
)
from fetch_client.types import RequestContext


@pytest.fixture
def sample_config():
    """Create sample resolved config for tests."""
    return resolve_config(ClientConfig(base_url="https://api.example.com"))


class TestBuildUrl:
    """Tests for build_url function."""

    # Decision: absolute path
    def test_build_url_absolute_path(self):
        result = build_url("https://api.example.com", "/users")
        assert result == "https://api.example.com/users"

    # Decision: relative path
    def test_build_url_relative_path(self):
        result = build_url("https://api.example.com/v1/", "users")
        assert result == "https://api.example.com/v1/users"

    # Path: with query params
    def test_build_url_with_query_params(self):
        result = build_url("https://api.example.com", "/users", {"page": 1, "limit": 10})
        assert "page=1" in result
        assert "limit=10" in result

    # Path: query params with boolean
    def test_build_url_boolean_query_params(self):
        result = build_url("https://api.example.com", "/users", {"active": True})
        assert "active=True" in result

    # Boundary: empty path
    def test_build_url_empty_path(self):
        result = build_url("https://api.example.com", "")
        assert result == "https://api.example.com"

    # Path: URL already has query string
    def test_build_url_existing_query(self):
        result = build_url("https://api.example.com/users?foo=bar", "", {"page": 1})
        assert "foo=bar" in result
        assert "page=1" in result
        assert "&page=1" in result

    # Boundary: empty query dict
    def test_build_url_empty_query(self):
        result = build_url("https://api.example.com", "/users", {})
        assert result == "https://api.example.com/users"

    # Path: no query params
    def test_build_url_no_query(self):
        result = build_url("https://api.example.com", "/users")
        assert result == "https://api.example.com/users"


class TestBuildHeaders:
    """Tests for build_headers function."""

    # Path: merges config and options headers
    def test_build_headers_merge(self, sample_config):
        sample_config.headers = {"User-Agent": "TestClient"}
        options_headers = {"X-Custom": "value"}
        context = RequestContext(method="GET", path="/users")

        result = build_headers(sample_config, options_headers, context)

        assert result["User-Agent"] == "TestClient"
        assert result["X-Custom"] == "value"

    # Path: options headers override config headers
    def test_build_headers_override(self, sample_config):
        sample_config.headers = {"User-Agent": "ConfigClient"}
        options_headers = {"User-Agent": "OptionsClient"}
        context = RequestContext(method="GET", path="/users")

        result = build_headers(sample_config, options_headers, context)

        assert result["User-Agent"] == "OptionsClient"

    # Condition: sets content-type when body present
    def test_build_headers_content_type_with_body(self, sample_config):
        context = RequestContext(method="POST", path="/users")
        result = build_headers(sample_config, None, context, has_body=True)

        assert result["content-type"] == "application/json"

    # Condition: does not set content-type without body
    def test_build_headers_no_content_type_without_body(self, sample_config):
        context = RequestContext(method="GET", path="/users")
        result = build_headers(sample_config, None, context, has_body=False)

        assert "content-type" not in result

    # Condition: does not override existing content-type
    def test_build_headers_preserve_content_type(self, sample_config):
        context = RequestContext(method="POST", path="/users")
        options_headers = {"content-type": "text/plain"}

        result = build_headers(sample_config, options_headers, context, has_body=True)

        assert result["content-type"] == "text/plain"

    # Decision: sets accept default
    def test_build_headers_accept_default(self, sample_config):
        context = RequestContext(method="GET", path="/users")
        result = build_headers(sample_config, None, context)

        assert result["accept"] == "application/json"

    # Decision: does not override existing accept
    def test_build_headers_preserve_accept(self, sample_config):
        context = RequestContext(method="GET", path="/users")
        options_headers = {"accept": "text/html"}

        result = build_headers(sample_config, options_headers, context)

        assert result["accept"] == "text/html"

    # Path: auth header injection
    def test_build_headers_auth_injection(self, sample_config):
        sample_config.auth = AuthConfig(type="bearer", raw_api_key="test-key")
        context = RequestContext(method="GET", path="/users")

        result = build_headers(sample_config, None, context)

        assert result["Authorization"] == "Bearer test-key"


class TestResolveAuthHeader:
    """Tests for resolve_auth_header function."""

    # Decision: callback returns key
    def test_resolve_auth_header_callback(self):
        auth = AuthConfig(
            type="bearer",
            raw_api_key="static-key",
            get_api_key_for_request=lambda ctx: "dynamic-key",
        )
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        assert result == {"Authorization": "Bearer dynamic-key"}

    # Decision: callback returns None, fallback to static
    def test_resolve_auth_header_callback_none(self):
        auth = AuthConfig(
            type="bearer",
            raw_api_key="static-key",
            get_api_key_for_request=lambda ctx: None,
        )
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        assert result == {"Authorization": "Bearer static-key"}

    # Decision: no callback, uses static key
    def test_resolve_auth_header_static(self):
        auth = AuthConfig(type="bearer", raw_api_key="static-key")
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        assert result == {"Authorization": "Bearer static-key"}

    # Boundary: no key available
    def test_resolve_auth_header_no_key(self):
        auth = AuthConfig(type="bearer")
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        assert result is None

    # Path: x-api-key type
    def test_resolve_auth_header_x_api_key(self):
        auth = AuthConfig(type="x-api-key", raw_api_key="api-key-123")
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        # resolve_auth_header uses get_auth_header_name which returns canonical form
        assert result == {"X-API-Key": "api-key-123"}

    # Path: custom type
    def test_resolve_auth_header_custom(self):
        auth = AuthConfig(type="custom", header_name="X-Auth-Token", raw_api_key="token-123")
        context = RequestContext(method="GET", path="/users")

        result = resolve_auth_header(auth, context)

        assert result == {"X-Auth-Token": "token-123"}


class TestBuildBody:
    """Tests for build_body function."""

    # Decision: body takes precedence
    def test_build_body_with_body(self):
        result = build_body(body="raw body", serializer=DefaultSerializer())
        assert result == "raw body"

    # Decision: serialize json
    def test_build_body_with_json(self):
        result = build_body(json_data={"key": "value"}, serializer=DefaultSerializer())
        assert result == '{"key": "value"}'

    # Decision: body takes precedence over json
    def test_build_body_body_over_json(self):
        result = build_body(
            json_data={"key": "value"}, body="raw", serializer=DefaultSerializer()
        )
        assert result == "raw"

    # Boundary: neither body nor json
    def test_build_body_neither(self):
        result = build_body(serializer=DefaultSerializer())
        assert result is None

    # Path: complex json object
    def test_build_body_complex_json(self):
        data = {"user": {"name": "test", "tags": ["a", "b"]}}
        result = build_body(json_data=data, serializer=DefaultSerializer())
        assert '"user"' in result
        assert '"tags"' in result


class TestCreateRequestContext:
    """Tests for create_request_context function."""

    # Path: creates context with all fields
    def test_create_context_all_fields(self):
        result = create_request_context(
            method="POST",
            path="/users",
            headers={"X-Custom": "value"},
            json_data={"data": "test"},
        )

        assert result.method == "POST"
        assert result.path == "/users"
        assert result.headers == {"X-Custom": "value"}
        assert result.json == {"data": "test"}

    # Boundary: minimal fields
    def test_create_context_minimal(self):
        result = create_request_context(method="GET", path="/users")

        assert result.method == "GET"
        assert result.path == "/users"
        assert result.headers is None
        assert result.json is None

    # Path: only headers
    def test_create_context_headers_only(self):
        result = create_request_context(
            method="GET", path="/users", headers={"Accept": "text/html"}
        )

        assert result.headers == {"Accept": "text/html"}
        assert result.json is None
