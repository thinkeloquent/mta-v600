"""
Comprehensive tests for FigmaApiToken.

Tests cover:
- Decision/Branch coverage for all control flow
- Log verification for defensive programming
"""
import logging
import pytest

from provider_api_getters.api_token.figma import FigmaApiToken
from tests.conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestFigmaApiToken:
    """Tests for FigmaApiToken class."""

    @pytest.fixture
    def figma_token(self, figma_config):
        """Create FigmaApiToken instance with standard config."""
        mock_store = MockConfigStore(figma_config)
        return FigmaApiToken(config_store=mock_store)

    @pytest.fixture
    def figma_token_no_config(self):
        """Create FigmaApiToken instance without config."""
        mock_store = MockConfigStore({"providers": {}})
        return FigmaApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, figma_token):
        """Test provider_name returns 'figma'."""
        assert figma_token.provider_name == "figma"

    # Health endpoint tests
    def test_health_endpoint(self, figma_token, caplog):
        """Test health_endpoint returns /v1/me."""
        with caplog.at_level(logging.DEBUG):
            endpoint = figma_token.health_endpoint

        assert endpoint == "/v1/me"
        assert "Returning /v1/me" in caplog.text

    # get_api_key branch tests

    def test_get_api_key_with_valid_token(self, figma_token, clean_env, caplog):
        """Test get_api_key when FIGMA_TOKEN is set."""
        clean_env(FIGMA_TOKEN="figd_test_token_12345")

        with caplog.at_level(logging.DEBUG):
            result = figma_token.get_api_key()

        assert result.api_key == "figd_test_token_12345"
        assert result.auth_type == "x-api-key"
        assert result.header_name == "X-Figma-Token"
        assert result.has_credentials is True
        assert "Found API key" in caplog.text
        assert "has_credentials=True" in caplog.text

    def test_get_api_key_without_token(self, figma_token, clean_env, caplog):
        """Test get_api_key when FIGMA_TOKEN is not set."""
        # clean_env already clears FIGMA_TOKEN

        with caplog.at_level(logging.WARNING):
            result = figma_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "x-api-key"
        assert result.header_name == "X-Figma-Token"
        assert result.has_credentials is False
        assert "No API key found" in caplog.text
        assert "Ensure FIGMA_TOKEN environment variable is set" in caplog.text

    def test_get_api_key_with_empty_token(self, figma_token, clean_env, caplog):
        """Test get_api_key when FIGMA_TOKEN is empty string."""
        clean_env(FIGMA_TOKEN="")

        with caplog.at_level(logging.WARNING):
            result = figma_token.get_api_key()

        # Empty string should be treated as not set
        assert result.api_key is None
        assert result.has_credentials is False

    def test_get_api_key_logs_masked_token(self, figma_token, clean_env, caplog):
        """Test that API key is properly masked in logs."""
        clean_env(FIGMA_TOKEN="super_secret_figma_key")

        with caplog.at_level(logging.DEBUG):
            figma_token.get_api_key()

        # Verify token is masked
        assert "super_secret_figma_key" not in caplog.text
        assert "supe" in caplog.text  # First 4 chars
        assert "****" in caplog.text  # Masked portion

    # Custom env_api_key config tests
    def test_get_api_key_with_custom_env_var(self, clean_env, caplog):
        """Test get_api_key with custom env_api_key config."""
        config = {
            "providers": {
                "figma": {
                    "base_url": "https://api.figma.com/v1",
                    "env_api_key": "CUSTOM_FIGMA_TOKEN",
                }
            }
        }
        clean_env(CUSTOM_FIGMA_TOKEN="custom_token_value")
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = figma_token.get_api_key()

        assert result.api_key == "custom_token_value"
        assert "CUSTOM_FIGMA_TOKEN" in caplog.text

    # Base URL tests
    def test_get_base_url(self, figma_token, caplog):
        """Test get_base_url returns configured URL."""
        with caplog.at_level(logging.DEBUG):
            url = figma_token.get_base_url()

        assert url == "https://api.figma.com/v1"

    # Validation tests
    def test_validate_with_valid_config(self, figma_token, clean_env):
        """Test validate with valid configuration."""
        clean_env(FIGMA_TOKEN="test_token")

        result = figma_token.validate()

        assert result["valid"] is True
        assert result["has_credentials"] is True
        assert result["has_base_url"] is True
        assert len(result["issues"]) == 0

    def test_validate_without_credentials(self, figma_token, clean_env):
        """Test validate detects missing credentials."""
        result = figma_token.validate()

        assert result["valid"] is False
        assert "No API credentials available" in result["issues"]

    def test_validate_without_base_url(self, clean_env):
        """Test validate detects missing base_url."""
        config = {"providers": {"figma": {"env_api_key": "FIGMA_TOKEN"}}}
        clean_env(FIGMA_TOKEN="test")
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        result = figma_token.validate()

        assert result["valid"] is False
        assert "No base_url configured" in result["issues"]

    # get_api_key_for_request tests
    def test_get_api_key_for_request(self, figma_token, clean_env, caplog):
        """Test get_api_key_for_request uses standard get_api_key."""
        from provider_api_getters.api_token.base import RequestContext

        clean_env(FIGMA_TOKEN="request_token")
        ctx = RequestContext(tenant_id="tenant1")

        with caplog.at_level(logging.DEBUG):
            result = figma_token.get_api_key_for_request(ctx)

        assert result.api_key == "request_token"
        assert "tenant_id=tenant1" in caplog.text


class TestFigmaApiTokenEdgeCases:
    """Edge case and boundary tests for FigmaApiToken."""

    def test_very_long_token(self, clean_env, caplog):
        """Test handling of very long token."""
        long_token = "figd_" + "x" * 1000
        clean_env(FIGMA_TOKEN=long_token)

        config = {"providers": {"figma": {"env_api_key": "FIGMA_TOKEN"}}}
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = figma_token.get_api_key()

        assert result.api_key == long_token
        assert len(result.api_key) == 1005

    def test_token_with_special_characters(self, clean_env):
        """Test token with special characters."""
        special_token = "figd_!@#$%^&*()_+-=[]{}|;':\",./<>?"
        clean_env(FIGMA_TOKEN=special_token)

        config = {"providers": {"figma": {"env_api_key": "FIGMA_TOKEN"}}}
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        result = figma_token.get_api_key()

        assert result.api_key == special_token

    def test_multiple_get_api_key_calls(self, clean_env, caplog):
        """Test multiple get_api_key calls are consistent."""
        clean_env(FIGMA_TOKEN="consistent_token")

        config = {"providers": {"figma": {"env_api_key": "FIGMA_TOKEN"}}}
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        result1 = figma_token.get_api_key()
        result2 = figma_token.get_api_key()

        assert result1.api_key == result2.api_key
        assert result1.auth_type == result2.auth_type

    def test_clear_cache_and_reload(self, clean_env, caplog):
        """Test clearing cache and reloading config."""
        clean_env(FIGMA_TOKEN="initial_token")

        config = {"providers": {"figma": {"env_api_key": "FIGMA_TOKEN"}}}
        mock_store = MockConfigStore(config)
        figma_token = FigmaApiToken(config_store=mock_store)

        # Get initial value
        result1 = figma_token.get_api_key()
        assert result1.api_key == "initial_token"

        # Clear cache
        figma_token.clear_cache()

        # Change token
        clean_env(FIGMA_TOKEN="new_token")

        # Get new value
        result2 = figma_token.get_api_key()
        assert result2.api_key == "new_token"
