"""
Comprehensive tests for ConfluenceApiToken.

Tests cover:
- Decision/Branch coverage for all control flow (4 branches in get_api_key)
- Basic Auth encoding
- Log verification for defensive programming
"""
import base64
import logging
import pytest

from provider_api_getters.api_token.confluence import (
    ConfluenceApiToken,
    DEFAULT_EMAIL_ENV_VAR,
    DEFAULT_BASE_URL_ENV_VAR,
)
from .conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestConfluenceApiToken:
    """Tests for ConfluenceApiToken class."""

    @pytest.fixture
    def confluence_config(self):
        """Standard Confluence config."""
        return {
            "providers": {
                "confluence": {
                    "base_url": None,
                    "env_api_key": "CONFLUENCE_API_TOKEN",
                    "env_email": "CONFLUENCE_EMAIL",
                    "health_endpoint": "/user/current",
                    "api_auth_type": "basic_email_token",
                }
            }
        }

    @pytest.fixture
    def confluence_token(self, confluence_config):
        """Create ConfluenceApiToken instance with standard config."""
        mock_store = MockConfigStore(confluence_config)
        return ConfluenceApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, confluence_token):
        """Test provider_name returns 'confluence'."""
        assert confluence_token.provider_name == "confluence"

    # Health endpoint tests
    def test_health_endpoint_from_config(self, confluence_token, caplog):
        """Test health_endpoint returns value from config."""
        with caplog.at_level(logging.DEBUG):
            endpoint = confluence_token.health_endpoint

        # Value comes from confluence_config fixture which sets health_endpoint: "/user/current"
        assert endpoint == "/user/current"

    def test_health_endpoint_custom_from_config(self, clean_env, caplog):
        """Test health_endpoint returns custom value from config."""
        config = {
            "providers": {
                "confluence": {
                    "env_api_key": "CONFLUENCE_API_TOKEN",
                    "health_endpoint": "/rest/api/user/current",
                }
            }
        }
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        endpoint = confluence_token.health_endpoint
        assert endpoint == "/rest/api/user/current"

    def test_health_endpoint_default_when_not_in_config(self, clean_env):
        """Test health_endpoint returns default when not in config."""
        config = {
            "providers": {
                "confluence": {
                    "env_api_key": "CONFLUENCE_API_TOKEN",
                    # No health_endpoint specified
                }
            }
        }
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        endpoint = confluence_token.health_endpoint
        # BaseApiToken returns "/" as default when health_endpoint not specified
        assert endpoint == "/"

    # Default constants tests
    def test_default_constants(self):
        """Test default env var constants."""
        assert DEFAULT_EMAIL_ENV_VAR == "CONFLUENCE_EMAIL"
        assert DEFAULT_BASE_URL_ENV_VAR == "CONFLUENCE_BASE_URL"

    # _get_email tests
    def test_get_email_found(self, confluence_token, clean_env, caplog):
        """Test _get_email when email is set."""
        clean_env(CONFLUENCE_EMAIL="wiki@company.com")

        with caplog.at_level(logging.DEBUG):
            result = confluence_token._get_email()

        assert result == "wiki@company.com"
        assert "Found email in env var 'CONFLUENCE_EMAIL'" in caplog.text

    def test_get_email_not_found(self, confluence_config, clean_env, caplog):
        """Test _get_email when email is not set."""
        # Create token AFTER clean_env clears env vars
        mock_store = MockConfigStore(confluence_config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = confluence_token._get_email()

        assert result is None
        # Log says "not set, trying fallback" or "Neither ... is set"
        assert "'CONFLUENCE_EMAIL' not set" in caplog.text or "Neither" in caplog.text

    # _encode_auth tests
    def test_encode_auth_valid_basic(self, confluence_token, caplog):
        """Test _encode_auth with valid inputs for basic_email_token."""
        with caplog.at_level(logging.DEBUG):
            result = confluence_token._encode_auth("wiki@test.com", "api_token", "basic_email_token")

        expected = base64.b64encode(b"wiki@test.com:api_token").decode("utf-8")
        assert result == f"Basic {expected}"
        assert "Encoding credentials" in caplog.text

    def test_encode_auth_valid_bearer(self, confluence_token, caplog):
        """Test _encode_auth with valid inputs for bearer_email_token."""
        with caplog.at_level(logging.DEBUG):
            result = confluence_token._encode_auth("wiki@test.com", "api_token", "bearer_email_token")

        expected = base64.b64encode(b"wiki@test.com:api_token").decode("utf-8")
        assert result == f"Bearer {expected}"
        assert "Encoding credentials" in caplog.text

    def test_encode_auth_empty_email_raises(self, confluence_token, caplog):
        """Test _encode_auth with empty email raises."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError) as exc_info:
                confluence_token._encode_auth("", "token", "basic_email_token")

        assert "Both email and token are required" in str(exc_info.value)
        assert "email_empty=True" in caplog.text

    def test_encode_auth_empty_token_raises(self, confluence_token, caplog):
        """Test _encode_auth with empty token raises."""
        with caplog.at_level(logging.ERROR):
            with pytest.raises(ValueError):
                confluence_token._encode_auth("email@test.com", "", "basic_email_token")

        assert "token_empty=True" in caplog.text

    # get_api_key branch tests - All 4 branches

    def test_get_api_key_both_present(self, confluence_token, clean_env, caplog):
        """Branch 1: Both token and email present - success."""
        clean_env(
            CONFLUENCE_API_TOKEN="confluence_token_123",
            CONFLUENCE_EMAIL="wiki@company.com"
        )

        with caplog.at_level(logging.DEBUG):
            result = confluence_token.get_api_key()

        assert result.api_key is not None
        assert result.api_key.startswith("Basic ")
        assert result.auth_type == "basic_email_token"
        assert result.header_name == "Authorization"
        assert result.username == "wiki@company.com"
        assert result.has_credentials is True

        assert "has_token=True, has_email=True" in caplog.text
        assert "Both email and token found" in caplog.text
        assert "Successfully created auth result" in caplog.text

    def test_get_api_key_token_only(self, confluence_token, clean_env, caplog):
        """Branch 2: Token present but email missing."""
        clean_env(CONFLUENCE_API_TOKEN="confluence_token_123")

        with caplog.at_level(logging.WARNING):
            result = confluence_token.get_api_key()

        assert result.api_key is None
        assert result.username is None
        assert result.has_credentials is False

        assert "API token found but email is missing" in caplog.text
        assert "Set CONFLUENCE_EMAIL environment variable" in caplog.text

    def test_get_api_key_email_only(self, confluence_token, clean_env, caplog):
        """Branch 3: Email present but token missing."""
        clean_env(CONFLUENCE_EMAIL="wiki@company.com")

        with caplog.at_level(logging.WARNING):
            result = confluence_token.get_api_key()

        assert result.api_key is None
        assert result.username == "wiki@company.com"
        assert result.has_credentials is False

        assert "Email found but API token is missing" in caplog.text
        assert "Set CONFLUENCE_API_TOKEN environment variable" in caplog.text

    def test_get_api_key_neither(self, confluence_token, clean_env, caplog):
        """Branch 4: Neither token nor email present."""
        with caplog.at_level(logging.WARNING):
            result = confluence_token.get_api_key()

        assert result.api_key is None
        assert result.username is None
        assert result.has_credentials is False

        assert "Neither email nor token found" in caplog.text
        assert "Set both CONFLUENCE_EMAIL and CONFLUENCE_API_TOKEN" in caplog.text

    # get_base_url tests
    def test_get_base_url_from_env(self, confluence_token, clean_env, caplog):
        """Test get_base_url from environment variable."""
        clean_env(CONFLUENCE_BASE_URL="https://company.atlassian.net/wiki")

        with caplog.at_level(logging.DEBUG):
            result = confluence_token.get_base_url()

        assert result == "https://company.atlassian.net/wiki"
        assert "Found base URL from env var" in caplog.text

    def test_get_base_url_from_config(self, clean_env, caplog):
        """Test get_base_url from config takes precedence."""
        config = {
            "providers": {
                "confluence": {
                    "base_url": "https://config.atlassian.net/wiki",
                    "env_api_key": "CONFLUENCE_API_TOKEN",
                }
            }
        }
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = confluence_token.get_base_url()

        assert result == "https://config.atlassian.net/wiki"
        assert "Found base URL from config" in caplog.text

    def test_get_base_url_not_configured(self, confluence_config, clean_env, caplog):
        """Test get_base_url when not configured."""
        # Create token AFTER clean_env clears env vars
        mock_store = MockConfigStore(confluence_config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        with caplog.at_level(logging.WARNING):
            result = confluence_token.get_base_url()

        assert result is None
        assert "No base URL configured" in caplog.text
        # Implementation says "Set CONFLUENCE_BASE_URL or JIRA_BASE_URL environment variable"
        assert "CONFLUENCE_BASE_URL" in caplog.text

    # Validation tests
    def test_validate_fully_configured(self, clean_env):
        """Test validate with full configuration."""
        clean_env(
            CONFLUENCE_API_TOKEN="token",
            CONFLUENCE_EMAIL="wiki@test.com",
            CONFLUENCE_BASE_URL="https://company.atlassian.net/wiki"
        )

        config = {"providers": {"confluence": {"env_api_key": "CONFLUENCE_API_TOKEN"}}}
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        result = confluence_token.validate()

        assert result["valid"] is True
        assert result["has_credentials"] is True
        assert result["has_base_url"] is True


class TestConfluenceApiTokenEdgeCases:
    """Edge case tests for ConfluenceApiToken."""

    def test_basic_auth_encoding_verification(self, clean_env):
        """Test Basic Auth encoding produces correct format."""
        clean_env(
            CONFLUENCE_API_TOKEN="test_token",
            CONFLUENCE_EMAIL="user@test.com"
        )

        config = {"providers": {"confluence": {"env_api_key": "CONFLUENCE_API_TOKEN", "api_auth_type": "basic_email_token"}}}
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        result = confluence_token.get_api_key()

        # Decode and verify
        encoded_part = result.api_key.replace("Basic ", "")
        decoded = base64.b64decode(encoded_part).decode("utf-8")
        assert decoded == "user@test.com:test_token"

    def test_credentials_with_colons(self, clean_env):
        """Test credentials containing colons."""
        clean_env(
            CONFLUENCE_API_TOKEN="token:with:colons",
            CONFLUENCE_EMAIL="user@test.com"
        )

        config = {"providers": {"confluence": {"env_api_key": "CONFLUENCE_API_TOKEN", "api_auth_type": "basic_email_token"}}}
        mock_store = MockConfigStore(config)
        confluence_token = ConfluenceApiToken(config_store=mock_store)

        result = confluence_token.get_api_key()

        assert result.has_credentials is True
        # Verify colons are preserved correctly
        encoded_part = result.api_key.replace("Basic ", "")
        decoded = base64.b64decode(encoded_part).decode("utf-8")
        assert decoded == "user@test.com:token:with:colons"
