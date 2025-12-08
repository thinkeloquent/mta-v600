"""
Tests for auth_handler.py
Logic testing: Decision/Branch, Boundary, Path coverage
"""
import pytest

from fetch_client.auth.auth_handler import (
    BearerAuthHandler,
    XApiKeyAuthHandler,
    CustomAuthHandler,
    create_auth_handler,
)
from fetch_client.config import AuthConfig
from fetch_client.types import RequestContext


@pytest.fixture
def sample_context():
    """Sample request context for testing."""
    return RequestContext(method="GET", path="/users", headers={})


class TestBearerAuthHandler:
    """Tests for BearerAuthHandler class."""

    # Decision: static key
    def test_bearer_static_key(self, sample_context):
        handler = BearerAuthHandler("my-api-key")
        result = handler.get_header(sample_context)

        assert result == {"Authorization": "Bearer my-api-key"}

    # Decision: callback invoked first
    def test_bearer_callback(self, sample_context):
        callback = lambda ctx: "dynamic-key"
        handler = BearerAuthHandler("static-key", callback)
        result = handler.get_header(sample_context)

        assert result == {"Authorization": "Bearer dynamic-key"}

    # Decision: callback returns None, fallback to static
    def test_bearer_callback_fallback(self, sample_context):
        callback = lambda ctx: None
        handler = BearerAuthHandler("fallback-key", callback)
        result = handler.get_header(sample_context)

        assert result == {"Authorization": "Bearer fallback-key"}

    # Boundary: no key available
    def test_bearer_no_key(self, sample_context):
        handler = BearerAuthHandler()
        result = handler.get_header(sample_context)

        assert result is None

    # Boundary: callback returns empty string (falsy)
    def test_bearer_callback_empty(self, sample_context):
        callback = lambda ctx: ""
        handler = BearerAuthHandler("static-key", callback)
        result = handler.get_header(sample_context)

        assert result == {"Authorization": "Bearer static-key"}

    # Path: callback only
    def test_bearer_callback_only(self, sample_context):
        callback = lambda ctx: "callback-only-key"
        handler = BearerAuthHandler(None, callback)
        result = handler.get_header(sample_context)

        assert result == {"Authorization": "Bearer callback-only-key"}


class TestXApiKeyAuthHandler:
    """Tests for XApiKeyAuthHandler class."""

    # Decision: static key
    def test_x_api_key_static(self, sample_context):
        handler = XApiKeyAuthHandler("my-api-key")
        result = handler.get_header(sample_context)

        assert result == {"x-api-key": "my-api-key"}

    # Decision: callback invoked first
    def test_x_api_key_callback(self, sample_context):
        callback = lambda ctx: "dynamic-key"
        handler = XApiKeyAuthHandler("static-key", callback)
        result = handler.get_header(sample_context)

        assert result == {"x-api-key": "dynamic-key"}

    # Decision: callback returns None, fallback to static
    def test_x_api_key_callback_fallback(self, sample_context):
        callback = lambda ctx: None
        handler = XApiKeyAuthHandler("fallback-key", callback)
        result = handler.get_header(sample_context)

        assert result == {"x-api-key": "fallback-key"}

    # Boundary: no key available
    def test_x_api_key_no_key(self, sample_context):
        handler = XApiKeyAuthHandler()
        result = handler.get_header(sample_context)

        assert result is None


class TestCustomAuthHandler:
    """Tests for CustomAuthHandler class."""

    # Decision: custom header name
    def test_custom_header_name(self, sample_context):
        handler = CustomAuthHandler("X-My-Auth", "secret")
        result = handler.get_header(sample_context)

        assert result == {"X-My-Auth": "secret"}

    # Decision: callback invoked first
    def test_custom_callback(self, sample_context):
        callback = lambda ctx: "dynamic-secret"
        handler = CustomAuthHandler("X-Token", "static-secret", callback)
        result = handler.get_header(sample_context)

        assert result == {"X-Token": "dynamic-secret"}

    # Decision: callback returns None, fallback to static
    def test_custom_callback_fallback(self, sample_context):
        callback = lambda ctx: None
        handler = CustomAuthHandler("X-Auth", "fallback", callback)
        result = handler.get_header(sample_context)

        assert result == {"X-Auth": "fallback"}

    # Boundary: no key available
    def test_custom_no_key(self, sample_context):
        handler = CustomAuthHandler("X-Auth")
        result = handler.get_header(sample_context)

        assert result is None

    # Path: preserves header name case
    def test_custom_preserves_case(self, sample_context):
        handler = CustomAuthHandler("X-Custom-Header-Name", "value")
        result = handler.get_header(sample_context)

        assert result == {"X-Custom-Header-Name": "value"}


class TestCreateAuthHandler:
    """Tests for create_auth_handler function."""

    # Decision: bearer type
    def test_create_bearer(self, sample_context):
        config = AuthConfig(type="bearer", api_key="key")
        handler = create_auth_handler(config)

        assert isinstance(handler, BearerAuthHandler)
        assert handler.get_header(sample_context) == {"Authorization": "Bearer key"}

    # Decision: x-api-key type
    def test_create_x_api_key(self, sample_context):
        config = AuthConfig(type="x-api-key", api_key="key")
        handler = create_auth_handler(config)

        assert isinstance(handler, XApiKeyAuthHandler)
        assert handler.get_header(sample_context) == {"x-api-key": "key"}

    # Decision: custom type
    def test_create_custom(self, sample_context):
        config = AuthConfig(type="custom", header_name="X-Auth", api_key="key")
        handler = create_auth_handler(config)

        assert isinstance(handler, CustomAuthHandler)
        assert handler.get_header(sample_context) == {"X-Auth": "key"}

    # Decision: custom type without header_name uses Authorization
    def test_create_custom_default_header(self, sample_context):
        config = AuthConfig(type="custom", api_key="key")
        handler = create_auth_handler(config)

        assert handler.get_header(sample_context) == {"Authorization": "key"}

    # Decision: default case (unknown type)
    def test_create_default(self, sample_context):
        config = AuthConfig(type="unknown", api_key="key")  # type: ignore
        handler = create_auth_handler(config)

        assert isinstance(handler, BearerAuthHandler)

    # Path: with callback
    def test_create_with_callback(self, sample_context):
        callback = lambda ctx: "dynamic"
        config = AuthConfig(type="bearer", api_key="static", get_api_key_for_request=callback)
        handler = create_auth_handler(config)

        result = handler.get_header(sample_context)
        assert result == {"Authorization": "Bearer dynamic"}
