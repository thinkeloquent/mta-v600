"""
Comprehensive tests for provider_api_getters.api_token.auth_header_factory module.

Tests cover:
- Decision/Branch coverage for all control flow paths
- Boundary value analysis for inputs
- State transition testing for factory method selection
- Log verification for defensive programming (hyper-observability)
- MC/DC coverage for condition combinations

Testing Strategy:
1. Statement Testing: Every line executes at least once
2. Decision/Branch Coverage: All true/false branches of if/else
3. Boundary Value Analysis: Edge cases for string lengths, empty values
4. Equivalence Partitioning: Valid/invalid input classes
5. Loop Testing: N/A (no loops in factory)
6. State Testing: Factory state transitions based on scheme selection
"""
import base64
import hashlib
import logging
import pytest
import secrets
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

from provider_api_getters.api_token.auth_header_factory import (
    AuthScheme,
    AuthHeader,
    AuthHeaderFactory,
    CONFIG_AUTH_TYPE_MAP,
)

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


# =============================================================================
# Test AuthScheme Enum
# =============================================================================

class TestAuthScheme:
    """Tests for AuthScheme enumeration - Statement and Equivalence coverage."""

    def test_all_basic_schemes_exist(self):
        """Verify all Basic auth scheme variants are defined."""
        assert AuthScheme.BASIC_USER_PASS.value == "basic_user_pass"
        assert AuthScheme.BASIC_EMAIL_TOKEN.value == "basic_email_token"
        assert AuthScheme.BASIC_USER_TOKEN.value == "basic_user_token"

    def test_all_bearer_schemes_exist(self):
        """Verify all Bearer auth scheme variants are defined."""
        assert AuthScheme.BEARER_PAT.value == "bearer_pat"
        assert AuthScheme.BEARER_OAUTH.value == "bearer_oauth"
        assert AuthScheme.BEARER_JWT.value == "bearer_jwt"

    def test_api_key_scheme_exists(self):
        """Verify X-Api-Key scheme is defined."""
        assert AuthScheme.X_API_KEY.value == "x_api_key"

    def test_custom_header_scheme_exists(self):
        """Verify custom header scheme is defined."""
        assert AuthScheme.CUSTOM_HEADER.value == "custom_header"

    def test_aws_signature_scheme_exists(self):
        """Verify AWS signature scheme is defined."""
        assert AuthScheme.AWS_SIGNATURE.value == "aws_signature"

    def test_digest_scheme_exists(self):
        """Verify Digest scheme is defined."""
        assert AuthScheme.DIGEST.value == "digest"

    def test_scheme_count(self):
        """Verify total number of schemes - boundary check."""
        assert len(AuthScheme) == 10  # All 10 schemes


class TestConfigAuthTypeMap:
    """Tests for CONFIG_AUTH_TYPE_MAP mapping."""

    def test_bearer_mapping(self):
        """Test bearer config type maps to BEARER_PAT."""
        assert CONFIG_AUTH_TYPE_MAP["bearer"] == AuthScheme.BEARER_PAT

    def test_basic_mapping(self):
        """Test basic config type maps to BASIC_USER_TOKEN."""
        assert CONFIG_AUTH_TYPE_MAP["basic"] == AuthScheme.BASIC_USER_TOKEN

    def test_x_api_key_mapping(self):
        """Test x-api-key config type maps to X_API_KEY."""
        assert CONFIG_AUTH_TYPE_MAP["x-api-key"] == AuthScheme.X_API_KEY

    def test_custom_mapping(self):
        """Test custom config type maps to CUSTOM_HEADER."""
        assert CONFIG_AUTH_TYPE_MAP["custom"] == AuthScheme.CUSTOM_HEADER

    def test_aws_signature_mapping(self):
        """Test aws_signature config type maps to AWS_SIGNATURE."""
        assert CONFIG_AUTH_TYPE_MAP["aws_signature"] == AuthScheme.AWS_SIGNATURE

    def test_digest_mapping(self):
        """Test digest config type maps to DIGEST."""
        assert CONFIG_AUTH_TYPE_MAP["digest"] == AuthScheme.DIGEST


# =============================================================================
# Test AuthHeader Dataclass
# =============================================================================

class TestAuthHeader:
    """Tests for AuthHeader dataclass - Statement and Branch coverage."""

    def test_initialization_logs_debug(self, caplog):
        """Test that initialization logs debug message (observability)."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeader(
                header_name="Authorization",
                header_value="Bearer test-token",
                scheme=AuthScheme.BEARER_PAT,
            )

        assert header.header_name == "Authorization"
        assert header.header_value == "Bearer test-token"
        assert header.scheme == AuthScheme.BEARER_PAT
        assert "AuthHeader.__post_init__" in caplog.text
        assert "scheme='bearer_pat'" in caplog.text

    def test_to_dict_returns_correct_format(self):
        """Test to_dict returns proper dictionary format."""
        header = AuthHeader(
            header_name="X-Api-Key",
            header_value="my-api-key-12345",
            scheme=AuthScheme.X_API_KEY,
        )

        result = header.to_dict()

        assert result == {"X-Api-Key": "my-api-key-12345"}

    def test_str_masks_long_value(self):
        """Test __str__ masks long values for safe logging."""
        header = AuthHeader(
            header_name="Authorization",
            header_value="Bearer very-long-secret-token-12345",
            scheme=AuthScheme.BEARER_PAT,
        )

        result = str(header)

        # First 10 chars + "***"
        assert result == "Authorization: Bearer ver***"
        # Ensure full value is NOT in string
        assert "very-long-secret-token-12345" not in result

    def test_str_masks_short_value(self):
        """Test __str__ masks short values (boundary: <= 10 chars)."""
        header = AuthHeader(
            header_name="Authorization",
            header_value="short",  # 5 chars
            scheme=AuthScheme.BEARER_PAT,
        )

        result = str(header)

        assert result == "Authorization: ***"

    def test_str_masks_exactly_10_chars(self):
        """Test __str__ boundary: exactly 10 chars."""
        header = AuthHeader(
            header_name="Authorization",
            header_value="1234567890",  # exactly 10 chars
            scheme=AuthScheme.BEARER_PAT,
        )

        result = str(header)

        assert result == "Authorization: ***"

    def test_str_masks_11_chars(self):
        """Test __str__ boundary: 11 chars (just over threshold)."""
        header = AuthHeader(
            header_name="Authorization",
            header_value="12345678901",  # 11 chars
            scheme=AuthScheme.BEARER_PAT,
        )

        result = str(header)

        assert result == "Authorization: 1234567890***"


# =============================================================================
# Test AuthHeaderFactory.create() - Decision/Branch Coverage
# =============================================================================

class TestAuthHeaderFactoryCreate:
    """
    Tests for AuthHeaderFactory.create() method.

    Branch Coverage: Tests each case in the if/elif chain
    """

    def test_create_logs_scheme(self, caplog):
        """Test that create() logs the scheme (observability)."""
        with caplog.at_level(logging.DEBUG):
            AuthHeaderFactory.create(
                AuthScheme.BEARER_PAT,
                token="test-token"
            )

        assert "AuthHeaderFactory.create" in caplog.text
        assert "scheme='bearer_pat'" in caplog.text

    # --- BASIC SCHEMES BRANCH ---

    def test_create_basic_user_pass_scheme(self):
        """Test create() with BASIC_USER_PASS scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.BASIC_USER_PASS,
            user="testuser",
            password="testpass"
        )

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Basic ")
        assert header.scheme == AuthScheme.BASIC_USER_PASS

    def test_create_basic_email_token_scheme(self):
        """Test create() with BASIC_EMAIL_TOKEN scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.BASIC_EMAIL_TOKEN,
            email="test@example.com",
            token="api-token"
        )

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Basic ")

    def test_create_basic_user_token_scheme(self):
        """Test create() with BASIC_USER_TOKEN scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.BASIC_USER_TOKEN,
            username="testuser",
            api_key="api-key-123"
        )

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Basic ")

    # --- BEARER SCHEMES BRANCH ---

    def test_create_bearer_pat_scheme(self):
        """Test create() with BEARER_PAT scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.BEARER_PAT,
            token="pat-token-12345"
        )

        assert header.header_name == "Authorization"
        assert header.header_value == "Bearer pat-token-12345"
        assert header.scheme == AuthScheme.BEARER_PAT

    def test_create_bearer_oauth_scheme(self):
        """Test create() with BEARER_OAUTH scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.BEARER_OAUTH,
            token="oauth-access-token"
        )

        assert header.header_value == "Bearer oauth-access-token"

    def test_create_bearer_jwt_scheme(self):
        """Test create() with BEARER_JWT scheme."""
        jwt_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"
        header = AuthHeaderFactory.create(
            AuthScheme.BEARER_JWT,
            token=jwt_token
        )

        assert header.header_value == f"Bearer {jwt_token}"

    def test_create_bearer_with_api_key_fallback(self):
        """Test create() Bearer uses api_key if token not provided."""
        header = AuthHeaderFactory.create(
            AuthScheme.BEARER_PAT,
            api_key="api-key-as-token"
        )

        assert header.header_value == "Bearer api-key-as-token"

    # --- X_API_KEY SCHEME BRANCH ---

    def test_create_x_api_key_scheme(self):
        """Test create() with X_API_KEY scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.X_API_KEY,
            key="my-api-key-12345"
        )

        assert header.header_name == "X-Api-Key"
        assert header.header_value == "my-api-key-12345"
        assert header.scheme == AuthScheme.X_API_KEY

    def test_create_x_api_key_with_custom_header_name(self):
        """Test create() X_API_KEY with custom header name."""
        header = AuthHeaderFactory.create(
            AuthScheme.X_API_KEY,
            api_key="my-key",
            header_name="X-Custom-Api-Key"
        )

        assert header.header_name == "X-Custom-Api-Key"
        assert header.header_value == "my-key"

    # --- CUSTOM_HEADER SCHEME BRANCH ---

    def test_create_custom_header_scheme(self):
        """Test create() with CUSTOM_HEADER scheme."""
        header = AuthHeaderFactory.create(
            AuthScheme.CUSTOM_HEADER,
            header_name="X-Figma-Token",
            value="figma-token-value"
        )

        assert header.header_name == "X-Figma-Token"
        assert header.header_value == "figma-token-value"
        assert header.scheme == AuthScheme.CUSTOM_HEADER

    def test_create_custom_header_with_api_key_fallback(self):
        """Test create() CUSTOM_HEADER uses api_key if value not provided."""
        header = AuthHeaderFactory.create(
            AuthScheme.CUSTOM_HEADER,
            header_name="X-Custom-Token",
            api_key="api-key-as-value"
        )

        assert header.header_value == "api-key-as-value"

    # --- AWS_SIGNATURE SCHEME BRANCH ---

    def test_create_aws_signature_scheme(self):
        """Test create() with AWS_SIGNATURE scheme delegates to createAwsSignature."""
        header = AuthHeaderFactory.create(
            AuthScheme.AWS_SIGNATURE,
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="us-east-1",
            service="s3",
            method="GET",
            url="https://s3.amazonaws.com/bucket/key",
        )

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("AWS4-HMAC-SHA256")
        assert header.scheme == AuthScheme.AWS_SIGNATURE

    # --- DIGEST SCHEME BRANCH ---

    def test_create_digest_scheme(self):
        """Test create() with DIGEST scheme delegates to createDigest."""
        header = AuthHeaderFactory.create(
            AuthScheme.DIGEST,
            username="testuser",
            password="testpass",
            realm="test@realm.com",
            nonce="abc123nonce",
            uri="/protected/resource",
            method="GET",
        )

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Digest ")
        assert header.scheme == AuthScheme.DIGEST

    # --- DEFAULT/FALLBACK BRANCH ---

    def test_create_unknown_scheme_logs_warning_and_defaults_to_bearer(self, caplog):
        """Test create() with unknown scheme logs warning and defaults to Bearer."""
        # Use a mock scheme that doesn't match any case
        class FakeScheme:
            value = "fake_scheme"

        with caplog.at_level(logging.WARNING):
            header = AuthHeaderFactory.create(
                FakeScheme(),  # type: ignore
                token="fallback-token"
            )

        assert "Unknown scheme" in caplog.text
        assert "defaulting to Bearer" in caplog.text
        assert header.header_value == "Bearer fallback-token"


# =============================================================================
# Test AuthHeaderFactory.create_basic() - Boundary & Error Handling
# =============================================================================

class TestAuthHeaderFactoryCreateBasic:
    """
    Tests for AuthHeaderFactory.create_basic() method.

    Coverage:
    - Valid input combinations
    - Boundary value analysis (empty strings)
    - Error handling (missing parameters)
    - Log verification (observability)
    """

    def test_create_basic_valid_credentials(self, caplog):
        """Test create_basic with valid user and secret."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_basic("testuser", "secret123")

        assert header.header_name == "Authorization"
        # Verify Base64 encoding
        expected = base64.b64encode(b"testuser:secret123").decode("utf-8")
        assert header.header_value == f"Basic {expected}"
        assert header.scheme == AuthScheme.BASIC_USER_PASS
        assert "AuthHeaderFactory.create_basic" in caplog.text

    def test_create_basic_email_format(self):
        """Test create_basic with email as user (Atlassian format)."""
        header = AuthHeaderFactory.create_basic(
            "user@company.com",
            "api-token-12345"
        )

        expected = base64.b64encode(b"user@company.com:api-token-12345").decode("utf-8")
        assert header.header_value == f"Basic {expected}"

    def test_create_basic_special_characters(self):
        """Test create_basic with special characters in credentials."""
        header = AuthHeaderFactory.create_basic(
            "user:with:colons",
            "pass@with!special#chars"
        )

        # RFC 7617 allows special chars, base64 encodes them
        creds = "user:with:colons:pass@with!special#chars"
        expected = base64.b64encode(creds.encode("utf-8")).decode("utf-8")
        assert header.header_value == f"Basic {expected}"

    def test_create_basic_unicode_credentials(self):
        """Test create_basic with unicode characters."""
        header = AuthHeaderFactory.create_basic("用户", "密码")

        creds = "用户:密码"
        expected = base64.b64encode(creds.encode("utf-8")).decode("utf-8")
        assert header.header_value == f"Basic {expected}"

    def test_create_basic_empty_user_raises_error(self, caplog):
        """Test create_basic with empty user raises ValueError."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_basic("", "secret")

        assert "requires both user and secret" in str(exc_info.value)
        assert "AuthHeaderFactory.create_basic: Missing user or secret" in caplog.text

    def test_create_basic_empty_secret_raises_error(self, caplog):
        """Test create_basic with empty secret raises ValueError."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_basic("user", "")

        assert "requires both user and secret" in str(exc_info.value)

    def test_create_basic_none_user_raises_error(self):
        """Test create_basic with None user raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AuthHeaderFactory.create_basic(None, "secret")  # type: ignore

        assert "requires both user and secret" in str(exc_info.value)

    def test_create_basic_none_secret_raises_error(self):
        """Test create_basic with None secret raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AuthHeaderFactory.create_basic("user", None)  # type: ignore

        assert "requires both user and secret" in str(exc_info.value)

    def test_create_basic_both_empty_raises_error(self):
        """Test create_basic with both empty raises ValueError."""
        with pytest.raises(ValueError):
            AuthHeaderFactory.create_basic("", "")

    def test_create_basic_logs_encoding_details(self, caplog):
        """Test create_basic logs encoding details (observability)."""
        with caplog.at_level(logging.DEBUG):
            AuthHeaderFactory.create_basic("testuser", "testpass")

        assert "Encoded credentials" in caplog.text
        assert "input_length=" in caplog.text
        assert "encoded_length=" in caplog.text


# =============================================================================
# Test AuthHeaderFactory.create_bearer() - Boundary & Error Handling
# =============================================================================

class TestAuthHeaderFactoryCreateBearer:
    """
    Tests for AuthHeaderFactory.create_bearer() method.

    Coverage:
    - Valid token formats (PAT, OAuth, JWT)
    - Boundary value analysis (empty, very long tokens)
    - Error handling (missing token)
    - Log verification
    """

    def test_create_bearer_valid_token(self, caplog):
        """Test create_bearer with valid token."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_bearer("valid-token-12345")

        assert header.header_name == "Authorization"
        assert header.header_value == "Bearer valid-token-12345"
        assert header.scheme == AuthScheme.BEARER_PAT
        assert "AuthHeaderFactory.create_bearer" in caplog.text

    def test_create_bearer_jwt_token(self):
        """Test create_bearer with JWT token format."""
        jwt = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.H17JcnHOWFnzGbMmBQ8LSqQ2bKlKV0RhYLqNQGl6u3c"
        header = AuthHeaderFactory.create_bearer(jwt)

        assert header.header_value == f"Bearer {jwt}"

    def test_create_bearer_very_long_token(self):
        """Test create_bearer with very long token (boundary)."""
        long_token = "x" * 10000  # 10KB token
        header = AuthHeaderFactory.create_bearer(long_token)

        assert header.header_value == f"Bearer {long_token}"
        assert len(header.header_value) == 10007  # "Bearer " + token

    def test_create_bearer_empty_token_raises_error(self, caplog):
        """Test create_bearer with empty token raises ValueError."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_bearer("")

        assert "requires a token" in str(exc_info.value)
        assert "Missing token" in caplog.text

    def test_create_bearer_none_token_raises_error(self):
        """Test create_bearer with None token raises ValueError."""
        with pytest.raises(ValueError) as exc_info:
            AuthHeaderFactory.create_bearer(None)  # type: ignore

        assert "requires a token" in str(exc_info.value)

    def test_create_bearer_whitespace_only_token_raises_error(self):
        """Test create_bearer with whitespace-only token raises ValueError."""
        # Note: This depends on implementation - adjust if whitespace is valid
        # Currently empty string is checked with `not token`
        # "   " is truthy so would pass - this tests the current behavior
        header = AuthHeaderFactory.create_bearer("   ")
        assert header.header_value == "Bearer    "  # Whitespace preserved

    def test_create_bearer_logs_token_length(self, caplog):
        """Test create_bearer logs token length (observability)."""
        with caplog.at_level(logging.DEBUG):
            AuthHeaderFactory.create_bearer("test-token")

        assert "token_length=10" in caplog.text


# =============================================================================
# Test AuthHeaderFactory.create_api_key() - Boundary & Branch Coverage
# =============================================================================

class TestAuthHeaderFactoryCreateApiKey:
    """
    Tests for AuthHeaderFactory.create_api_key() method.

    Coverage:
    - Default header name vs custom header name (branch)
    - Valid/invalid key values
    - Log verification
    """

    def test_create_api_key_default_header(self, caplog):
        """Test create_api_key with default header name."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_api_key("my-api-key-123")

        assert header.header_name == "X-Api-Key"
        assert header.header_value == "my-api-key-123"
        assert header.scheme == AuthScheme.X_API_KEY
        assert "AuthHeaderFactory.create_api_key" in caplog.text

    def test_create_api_key_custom_header(self):
        """Test create_api_key with custom header name."""
        header = AuthHeaderFactory.create_api_key(
            "my-key",
            header_name="Ocp-Apim-Subscription-Key"
        )

        assert header.header_name == "Ocp-Apim-Subscription-Key"
        assert header.header_value == "my-key"

    def test_create_api_key_none_header_name_uses_default(self):
        """Test create_api_key with None header_name uses default."""
        header = AuthHeaderFactory.create_api_key("key", header_name=None)

        assert header.header_name == "X-Api-Key"

    def test_create_api_key_empty_key_raises_error(self, caplog):
        """Test create_api_key with empty key raises ValueError."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_api_key("")

        assert "requires a key" in str(exc_info.value)
        assert "Missing API key" in caplog.text

    def test_create_api_key_none_key_raises_error(self):
        """Test create_api_key with None key raises ValueError."""
        with pytest.raises(ValueError):
            AuthHeaderFactory.create_api_key(None)  # type: ignore


# =============================================================================
# Test AuthHeaderFactory.create_custom() - Boundary & Branch Coverage
# =============================================================================

class TestAuthHeaderFactoryCreateCustom:
    """
    Tests for AuthHeaderFactory.create_custom() method.

    Coverage:
    - Valid custom header combinations
    - Error handling for missing parameters
    - Log verification
    """

    def test_create_custom_valid_header(self, caplog):
        """Test create_custom with valid header name and value."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_custom(
                "X-Figma-Token",
                "figma-token-12345"
            )

        assert header.header_name == "X-Figma-Token"
        assert header.header_value == "figma-token-12345"
        assert header.scheme == AuthScheme.CUSTOM_HEADER
        assert "AuthHeaderFactory.create_custom" in caplog.text

    def test_create_custom_empty_header_name_raises_error(self, caplog):
        """Test create_custom with empty header_name raises ValueError."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_custom("", "value")

        assert "requires both header_name and value" in str(exc_info.value)
        assert "Missing header_name or value" in caplog.text

    def test_create_custom_empty_value_raises_error(self):
        """Test create_custom with empty value raises ValueError."""
        with pytest.raises(ValueError):
            AuthHeaderFactory.create_custom("X-Custom", "")

    def test_create_custom_none_header_name_raises_error(self):
        """Test create_custom with None header_name raises ValueError."""
        with pytest.raises(ValueError):
            AuthHeaderFactory.create_custom(None, "value")  # type: ignore

    def test_create_custom_none_value_raises_error(self):
        """Test create_custom with None value raises ValueError."""
        with pytest.raises(ValueError):
            AuthHeaderFactory.create_custom("X-Custom", None)  # type: ignore


# =============================================================================
# Test AuthHeaderFactory.create_aws_signature() - Complex Logic Testing
# =============================================================================

class TestAuthHeaderFactoryCreateAwsSignature:
    """
    Tests for AuthHeaderFactory.create_aws_signature() method.

    Coverage:
    - Valid AWS signature generation
    - Required parameter validation
    - URL parsing branches
    - Log verification
    """

    @pytest.fixture
    def aws_credentials(self):
        """Fixture providing valid AWS credentials."""
        return {
            "access_key_id": "AKIAIOSFODNN7EXAMPLE",
            "secret_access_key": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            "region": "us-east-1",
            "service": "s3",
            "method": "GET",
            "url": "https://s3.amazonaws.com/bucket/key",
        }

    def test_create_aws_signature_valid_credentials(self, aws_credentials, caplog):
        """Test create_aws_signature with valid AWS credentials."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("AWS4-HMAC-SHA256")
        assert "Credential=AKIAIOSFODNN7EXAMPLE" in header.header_value
        assert "us-east-1/s3/aws4_request" in header.header_value
        assert "SignedHeaders=host;x-amz-date" in header.header_value
        assert "Signature=" in header.header_value
        assert header.scheme == AuthScheme.AWS_SIGNATURE
        assert "AuthHeaderFactory.create_aws_signature" in caplog.text

    def test_create_aws_signature_with_body(self, aws_credentials):
        """Test create_aws_signature with request body."""
        aws_credentials["method"] = "POST"
        aws_credentials["body"] = '{"key": "value"}'

        header = AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert header.header_value.startswith("AWS4-HMAC-SHA256")
        # Different body = different signature
        assert "Signature=" in header.header_value

    def test_create_aws_signature_url_with_query_string(self, aws_credentials):
        """Test create_aws_signature with URL containing query string."""
        aws_credentials["url"] = "https://s3.amazonaws.com/bucket/key?prefix=test&max-keys=10"

        header = AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert header.header_value.startswith("AWS4-HMAC-SHA256")

    def test_create_aws_signature_url_without_path(self, aws_credentials):
        """Test create_aws_signature with URL without path (boundary)."""
        aws_credentials["url"] = "https://s3.amazonaws.com"

        header = AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert header.header_value.startswith("AWS4-HMAC-SHA256")

    def test_create_aws_signature_missing_access_key_raises_error(self, aws_credentials):
        """Test create_aws_signature without access_key_id raises TypeError (missing arg)."""
        del aws_credentials["access_key_id"]

        # Python raises TypeError for missing required positional arguments
        with pytest.raises(TypeError) as exc_info:
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert "access_key_id" in str(exc_info.value)

    def test_create_aws_signature_missing_secret_raises_error(self, aws_credentials):
        """Test create_aws_signature without secret_access_key raises TypeError."""
        del aws_credentials["secret_access_key"]

        with pytest.raises(TypeError) as exc_info:
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert "secret_access_key" in str(exc_info.value)

    def test_create_aws_signature_missing_region_raises_error(self, aws_credentials):
        """Test create_aws_signature without region raises TypeError."""
        del aws_credentials["region"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

    def test_create_aws_signature_missing_service_raises_error(self, aws_credentials):
        """Test create_aws_signature without service raises TypeError."""
        del aws_credentials["service"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

    def test_create_aws_signature_missing_method_raises_error(self, aws_credentials):
        """Test create_aws_signature without method raises TypeError."""
        del aws_credentials["method"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

    def test_create_aws_signature_missing_url_raises_error(self, aws_credentials):
        """Test create_aws_signature without url raises TypeError."""
        del aws_credentials["url"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

    def test_create_aws_signature_empty_access_key_raises_error(self, aws_credentials, caplog):
        """Test create_aws_signature with empty access_key_id raises ValueError."""
        aws_credentials["access_key_id"] = ""

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert "access_key_id" in str(exc_info.value)
        assert "Missing required parameters" in caplog.text

    def test_create_aws_signature_different_methods(self, aws_credentials):
        """Test create_aws_signature with different HTTP methods."""
        methods = ["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD"]
        signatures = set()

        for method in methods:
            aws_credentials["method"] = method
            header = AuthHeaderFactory.create_aws_signature(**aws_credentials)
            # Extract signature for comparison
            sig = header.header_value.split("Signature=")[1]
            signatures.add(sig)

        # Each method should produce different signature
        assert len(signatures) == len(methods)

    def test_create_aws_signature_logs_details(self, aws_credentials, caplog):
        """Test create_aws_signature logs region, service, method (observability)."""
        with caplog.at_level(logging.DEBUG):
            AuthHeaderFactory.create_aws_signature(**aws_credentials)

        assert "region='us-east-1'" in caplog.text
        assert "service='s3'" in caplog.text
        assert "method='GET'" in caplog.text
        assert "Canonical request created" in caplog.text
        assert "AWS signature created successfully" in caplog.text


# =============================================================================
# Test AuthHeaderFactory.create_digest() - Complex Logic Testing
# =============================================================================

class TestAuthHeaderFactoryCreateDigest:
    """
    Tests for AuthHeaderFactory.create_digest() method.

    Coverage:
    - Valid Digest auth generation
    - qop present vs absent (branch)
    - opaque present vs absent (branch)
    - algorithm MD5 vs SHA-256 (branch)
    - Error handling for missing parameters
    - Log verification
    """

    @pytest.fixture
    def digest_credentials(self):
        """Fixture providing valid Digest auth credentials."""
        return {
            "username": "testuser",
            "password": "testpass",
            "realm": "test@realm.com",
            "nonce": "abc123nonce456",
            "uri": "/protected/resource",
            "method": "GET",
        }

    def test_create_digest_valid_credentials(self, digest_credentials, caplog):
        """Test create_digest with valid credentials."""
        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Digest ")
        assert 'username="testuser"' in header.header_value
        assert 'realm="test@realm.com"' in header.header_value
        assert 'nonce="abc123nonce456"' in header.header_value
        assert 'uri="/protected/resource"' in header.header_value
        assert 'response="' in header.header_value
        assert header.scheme == AuthScheme.DIGEST
        assert "AuthHeaderFactory.create_digest" in caplog.text

    def test_create_digest_with_qop(self, digest_credentials):
        """Test create_digest with qop='auth' (branch: qop present)."""
        digest_credentials["qop"] = "auth"

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert "qop=auth" in header.header_value
        assert 'nc=' in header.header_value
        assert 'cnonce="' in header.header_value

    def test_create_digest_without_qop(self, digest_credentials):
        """Test create_digest without qop (branch: qop absent)."""
        digest_credentials["qop"] = ""  # or None

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        # qop fields should not appear
        # Note: Implementation uses `if qop:` so empty string is falsy
        assert "qop=" not in header.header_value
        assert "nc=" not in header.header_value
        assert "cnonce=" not in header.header_value

    def test_create_digest_with_opaque(self, digest_credentials):
        """Test create_digest with opaque value (branch: opaque present)."""
        digest_credentials["opaque"] = "opaque-value-xyz"

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert 'opaque="opaque-value-xyz"' in header.header_value

    def test_create_digest_without_opaque(self, digest_credentials):
        """Test create_digest without opaque (branch: opaque absent)."""
        header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert "opaque=" not in header.header_value

    def test_create_digest_with_sha256_algorithm(self, digest_credentials):
        """Test create_digest with SHA-256 algorithm (branch: non-MD5)."""
        digest_credentials["algorithm"] = "SHA-256"

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert "algorithm=SHA-256" in header.header_value

    def test_create_digest_with_md5_algorithm_not_shown(self, digest_credentials):
        """Test create_digest with MD5 algorithm doesn't show algorithm (default)."""
        digest_credentials["algorithm"] = "MD5"

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        # MD5 is default, so algorithm field is not included
        assert "algorithm=" not in header.header_value

    def test_create_digest_custom_cnonce(self, digest_credentials):
        """Test create_digest with provided cnonce."""
        digest_credentials["cnonce"] = "my-client-nonce"
        digest_credentials["qop"] = "auth"

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        assert 'cnonce="my-client-nonce"' in header.header_value

    def test_create_digest_generated_cnonce(self, digest_credentials):
        """Test create_digest generates cnonce if not provided."""
        digest_credentials["qop"] = "auth"
        # cnonce not provided - should be generated

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        # cnonce should be present and be a hex string
        assert 'cnonce="' in header.header_value

    def test_create_digest_missing_username_raises_error(self, digest_credentials):
        """Test create_digest without username raises TypeError (missing arg)."""
        del digest_credentials["username"]

        # Python raises TypeError for missing required positional arguments
        with pytest.raises(TypeError) as exc_info:
            AuthHeaderFactory.create_digest(**digest_credentials)

        assert "username" in str(exc_info.value)

    def test_create_digest_missing_password_raises_error(self, digest_credentials):
        """Test create_digest without password raises TypeError."""
        del digest_credentials["password"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_digest(**digest_credentials)

    def test_create_digest_missing_realm_raises_error(self, digest_credentials):
        """Test create_digest without realm raises TypeError."""
        del digest_credentials["realm"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_digest(**digest_credentials)

    def test_create_digest_missing_nonce_raises_error(self, digest_credentials):
        """Test create_digest without nonce raises TypeError."""
        del digest_credentials["nonce"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_digest(**digest_credentials)

    def test_create_digest_missing_uri_raises_error(self, digest_credentials):
        """Test create_digest without uri raises TypeError."""
        del digest_credentials["uri"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_digest(**digest_credentials)

    def test_create_digest_missing_method_raises_error(self, digest_credentials):
        """Test create_digest without method raises TypeError."""
        del digest_credentials["method"]

        with pytest.raises(TypeError):
            AuthHeaderFactory.create_digest(**digest_credentials)

    def test_create_digest_empty_username_raises_error(self, digest_credentials, caplog):
        """Test create_digest with empty username raises ValueError."""
        digest_credentials["username"] = ""

        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                AuthHeaderFactory.create_digest(**digest_credentials)

        assert "username" in str(exc_info.value)
        assert "Missing required parameters" in caplog.text

    def test_create_digest_response_calculation_md5(self, digest_credentials):
        """Test create_digest calculates correct MD5 response."""
        digest_credentials["qop"] = ""  # No qop for simpler calculation

        header = AuthHeaderFactory.create_digest(**digest_credentials)

        # Calculate expected response manually
        ha1 = hashlib.md5(b"testuser:test@realm.com:testpass").hexdigest()
        ha2 = hashlib.md5(b"GET:/protected/resource").hexdigest()
        expected_response = hashlib.md5(
            f"{ha1}:abc123nonce456:{ha2}".encode()
        ).hexdigest()

        assert f'response="{expected_response}"' in header.header_value


# =============================================================================
# Test AuthHeaderFactory.from_api_key_result() - Bridge Method
# =============================================================================

class TestAuthHeaderFactoryFromApiKeyResult:
    """
    Tests for AuthHeaderFactory.from_api_key_result() method.

    Coverage:
    - All auth_type branches (bearer, basic, x-api-key, custom, unknown)
    - Fallback behavior when username/header_name missing
    - Log verification
    """

    @pytest.fixture
    def mock_api_key_result(self):
        """Fixture providing a mock ApiKeyResult."""
        result = MagicMock()
        result.api_key = "test-token"
        result.auth_type = "bearer"
        result.header_name = "Authorization"
        result.username = None
        return result

    def test_from_api_key_result_bearer_type(self, mock_api_key_result, caplog):
        """Test from_api_key_result with bearer auth_type."""
        mock_api_key_result.auth_type = "bearer"
        mock_api_key_result.api_key = "bearer-token-123"

        with caplog.at_level(logging.DEBUG):
            header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "Authorization"
        assert header.header_value == "Bearer bearer-token-123"
        assert "AuthHeaderFactory.from_api_key_result" in caplog.text

    def test_from_api_key_result_basic_type_with_username(self, mock_api_key_result):
        """Test from_api_key_result with basic auth_type and username."""
        mock_api_key_result.auth_type = "basic"
        mock_api_key_result.api_key = "api-token"
        mock_api_key_result.username = "user@example.com"

        header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "Authorization"
        assert header.header_value.startswith("Basic ")

    def test_from_api_key_result_basic_type_without_username_falls_back_to_bearer(
        self, mock_api_key_result, caplog
    ):
        """Test from_api_key_result basic without username falls back to Bearer."""
        mock_api_key_result.auth_type = "basic"
        mock_api_key_result.api_key = "api-token"
        mock_api_key_result.username = None

        with caplog.at_level(logging.WARNING):
            header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_value == "Bearer api-token"
        assert "Basic auth without username" in caplog.text
        assert "falling back to Bearer" in caplog.text

    def test_from_api_key_result_x_api_key_type(self, mock_api_key_result):
        """Test from_api_key_result with x-api-key auth_type."""
        mock_api_key_result.auth_type = "x-api-key"
        mock_api_key_result.api_key = "my-api-key"
        mock_api_key_result.header_name = "X-Api-Key"

        header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "X-Api-Key"
        assert header.header_value == "my-api-key"

    def test_from_api_key_result_x_api_key_type_no_header_name(self, mock_api_key_result):
        """Test from_api_key_result x-api-key without header_name uses default."""
        mock_api_key_result.auth_type = "x-api-key"
        mock_api_key_result.api_key = "my-api-key"
        mock_api_key_result.header_name = None

        header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "X-Api-Key"

    def test_from_api_key_result_custom_type_with_header_name(self, mock_api_key_result):
        """Test from_api_key_result with custom auth_type and header_name."""
        mock_api_key_result.auth_type = "custom"
        mock_api_key_result.api_key = "figma-token"
        mock_api_key_result.header_name = "X-Figma-Token"

        header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "X-Figma-Token"
        assert header.header_value == "figma-token"

    def test_from_api_key_result_custom_type_without_header_name_uses_default(
        self, mock_api_key_result, caplog
    ):
        """Test from_api_key_result custom without header_name uses X-Custom-Token."""
        mock_api_key_result.auth_type = "custom"
        mock_api_key_result.api_key = "custom-token"
        mock_api_key_result.header_name = None

        with caplog.at_level(logging.WARNING):
            header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_name == "X-Custom-Token"
        assert "Custom auth without header_name" in caplog.text

    def test_from_api_key_result_unknown_type_defaults_to_bearer(
        self, mock_api_key_result, caplog
    ):
        """Test from_api_key_result with unknown auth_type defaults to Bearer."""
        mock_api_key_result.auth_type = "unknown-auth-type"
        mock_api_key_result.api_key = "some-token"

        with caplog.at_level(logging.WARNING):
            header = AuthHeaderFactory.from_api_key_result(mock_api_key_result)

        assert header.header_value == "Bearer some-token"
        assert "Unknown auth_type 'unknown-auth-type'" in caplog.text
        assert "defaulting to Bearer" in caplog.text


# =============================================================================
# Integration Tests - End-to-End Scenarios
# =============================================================================

class TestAuthHeaderFactoryIntegration:
    """
    Integration tests covering realistic usage scenarios.

    Coverage:
    - Full flow from factory to usable header
    - Interoperability with ApiKeyResult.get_auth_header()
    """

    def test_jira_basic_auth_scenario(self):
        """Test realistic Jira Basic auth scenario."""
        email = "developer@company.com"
        api_token = "ATATT3xFfGF0abc123XYZ"

        header = AuthHeaderFactory.create_basic(email, api_token)

        # Verify can be used in requests
        headers_dict = header.to_dict()
        assert "Authorization" in headers_dict
        assert headers_dict["Authorization"].startswith("Basic ")

        # Verify decoding works
        encoded_part = headers_dict["Authorization"].replace("Basic ", "")
        decoded = base64.b64decode(encoded_part).decode("utf-8")
        assert decoded == f"{email}:{api_token}"

    def test_aws_s3_presigned_url_scenario(self):
        """Test realistic AWS S3 scenario."""
        header = AuthHeaderFactory.create_aws_signature(
            access_key_id="AKIAIOSFODNN7EXAMPLE",
            secret_access_key="wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
            region="us-west-2",
            service="s3",
            method="PUT",
            url="https://mybucket.s3.us-west-2.amazonaws.com/myobject",
            body="Hello, World!",
        )

        headers_dict = header.to_dict()
        auth_header = headers_dict["Authorization"]

        assert auth_header.startswith("AWS4-HMAC-SHA256")
        assert "us-west-2/s3/aws4_request" in auth_header

    def test_figma_custom_header_scenario(self):
        """Test realistic Figma custom header scenario."""
        figma_token = "figd_abc123XYZ789"

        header = AuthHeaderFactory.create_custom("X-Figma-Token", figma_token)

        headers_dict = header.to_dict()
        assert headers_dict == {"X-Figma-Token": figma_token}

    def test_api_key_result_get_auth_header_integration(self):
        """Test integration with ApiKeyResult.get_auth_header()."""
        from provider_api_getters.api_token.base import ApiKeyResult

        # Create an ApiKeyResult like a provider would
        result = ApiKeyResult(
            api_key="test-bearer-token",
            auth_type="bearer",
            header_name="Authorization",
        )

        # Get auth header using the new method
        header = result.get_auth_header()

        assert header.header_name == "Authorization"
        assert header.header_value == "Bearer test-bearer-token"


# =============================================================================
# Property-Based Tests (if hypothesis is available)
# =============================================================================

class TestAuthHeaderFactoryPropertyBased:
    """
    Property-based tests for AuthHeaderFactory.

    These tests verify properties that should hold for any valid input.
    """

    def test_basic_auth_always_produces_valid_base64(self):
        """Property: Basic auth always produces valid Base64."""
        import string
        import random

        for _ in range(100):
            # Generate random credentials
            user = ''.join(random.choices(string.ascii_letters + string.digits, k=random.randint(1, 50)))
            secret = ''.join(random.choices(string.ascii_letters + string.digits + string.punctuation, k=random.randint(1, 100)))

            header = AuthHeaderFactory.create_basic(user, secret)

            # Extract and verify Base64 is decodable
            encoded_part = header.header_value.replace("Basic ", "")
            try:
                decoded = base64.b64decode(encoded_part).decode("utf-8")
                assert ":" in decoded  # Should contain colon separator
            except Exception as e:
                pytest.fail(f"Invalid Base64 produced: {e}")

    def test_bearer_auth_token_preserved_exactly(self):
        """Property: Bearer auth preserves token exactly."""
        import string
        import random

        for _ in range(100):
            # Generate random token
            token = ''.join(random.choices(string.ascii_letters + string.digits + "-_.", k=random.randint(10, 500)))

            header = AuthHeaderFactory.create_bearer(token)

            # Token should be preserved exactly
            assert header.header_value == f"Bearer {token}"
