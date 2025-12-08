"""
Comprehensive tests for GeminiOpenAIApiToken.

Tests cover:
- Decision/Branch coverage for all control flow
- Log verification for defensive programming
"""
import logging
import pytest

from provider_api_getters.api_token.gemini_openai import GeminiOpenAIApiToken
from tests.conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestGeminiOpenAIApiToken:
    """Tests for GeminiOpenAIApiToken class."""

    @pytest.fixture
    def gemini_config(self):
        """Standard Gemini config."""
        return {
            "providers": {
                "gemini": {
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                    "env_api_key": "GEMINI_API_KEY",
                }
            }
        }

    @pytest.fixture
    def gemini_token(self, gemini_config):
        """Create GeminiOpenAIApiToken instance with standard config."""
        mock_store = MockConfigStore(gemini_config)
        return GeminiOpenAIApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, gemini_token):
        """Test provider_name returns 'gemini'."""
        assert gemini_token.provider_name == "gemini"

    # Health endpoint tests
    def test_health_endpoint(self, gemini_token, caplog):
        """Test health_endpoint returns models (relative path)."""
        with caplog.at_level(logging.DEBUG):
            endpoint = gemini_token.health_endpoint

        assert endpoint == "models"
        assert "Returning models" in caplog.text

    # get_api_key tests - Branch coverage

    def test_get_api_key_with_valid_key(self, gemini_token, clean_env, caplog):
        """Test get_api_key when GEMINI_API_KEY is set."""
        clean_env(GEMINI_API_KEY="AIzaSyTestKey12345")

        with caplog.at_level(logging.DEBUG):
            result = gemini_token.get_api_key()

        assert result.api_key == "AIzaSyTestKey12345"
        assert result.auth_type == "bearer"
        assert result.header_name == "Authorization"
        assert result.has_credentials is True

        assert "Found API key" in caplog.text
        assert "has_credentials=True" in caplog.text

    def test_get_api_key_without_key(self, gemini_token, clean_env, caplog):
        """Test get_api_key when GEMINI_API_KEY is not set."""
        with caplog.at_level(logging.WARNING):
            result = gemini_token.get_api_key()

        assert result.api_key is None
        assert result.auth_type == "bearer"
        assert result.header_name == "Authorization"
        assert result.has_credentials is False

        assert "No API key found" in caplog.text
        assert "Ensure GEMINI_API_KEY environment variable is set" in caplog.text

    def test_get_api_key_logs_masked_key(self, gemini_token, clean_env, caplog):
        """Test that API key is properly masked in logs."""
        clean_env(GEMINI_API_KEY="AIzaSyVerySecretKey")

        with caplog.at_level(logging.DEBUG):
            gemini_token.get_api_key()

        # Verify key is masked
        assert "AIzaSyVerySecretKey" not in caplog.text
        assert "AIza" in caplog.text  # First 4 chars
        assert "****" in caplog.text  # Masked portion

    def test_get_api_key_with_empty_key(self, gemini_token, clean_env, caplog):
        """Test get_api_key when GEMINI_API_KEY is empty."""
        clean_env(GEMINI_API_KEY="")

        with caplog.at_level(logging.WARNING):
            result = gemini_token.get_api_key()

        assert result.api_key is None
        assert result.has_credentials is False

    # Custom env_api_key config tests
    def test_get_api_key_custom_env_var(self, clean_env, caplog):
        """Test get_api_key with custom env_api_key config."""
        config = {
            "providers": {
                "gemini": {
                    "env_api_key": "MY_CUSTOM_GEMINI_KEY",
                }
            }
        }
        clean_env(MY_CUSTOM_GEMINI_KEY="custom_key_value")
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = gemini_token.get_api_key()

        assert result.api_key == "custom_key_value"
        assert "MY_CUSTOM_GEMINI_KEY" in caplog.text

    # Base URL tests
    def test_get_base_url(self, gemini_token, caplog):
        """Test get_base_url returns configured URL."""
        with caplog.at_level(logging.DEBUG):
            url = gemini_token.get_base_url()

        assert url == "https://generativelanguage.googleapis.com/v1beta/openai"

    # Validation tests
    def test_validate_with_valid_config(self, gemini_token, clean_env):
        """Test validate with valid configuration."""
        clean_env(GEMINI_API_KEY="test_key")

        result = gemini_token.validate()

        assert result["valid"] is True
        assert result["has_credentials"] is True
        assert result["has_base_url"] is True
        assert len(result["issues"]) == 0

    def test_validate_without_credentials(self, gemini_token, clean_env):
        """Test validate detects missing credentials."""
        result = gemini_token.validate()

        assert result["valid"] is False
        assert "No API credentials available" in result["issues"]

    def test_validate_with_default_base_url(self, clean_env):
        """Test validate uses default base_url when not configured."""
        config = {"providers": {"gemini": {"env_api_key": "GEMINI_API_KEY"}}}
        clean_env(GEMINI_API_KEY="test_key")
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        result = gemini_token.validate()

        # Gemini has a hardcoded default base_url, so validation should pass
        assert result["valid"] is True
        assert result["has_base_url"] is True
        assert "No base_url configured" not in result.get("issues", [])

    # get_api_key_for_request tests
    def test_get_api_key_for_request(self, gemini_token, clean_env, caplog):
        """Test get_api_key_for_request uses standard get_api_key."""
        from provider_api_getters.api_token.base import RequestContext

        clean_env(GEMINI_API_KEY="request_key")
        ctx = RequestContext(tenant_id="tenant1")

        with caplog.at_level(logging.DEBUG):
            result = gemini_token.get_api_key_for_request(ctx)

        assert result.api_key == "request_key"


class TestGeminiOpenAIApiTokenEdgeCases:
    """Edge case tests for GeminiOpenAIApiToken."""

    def test_key_with_standard_prefix(self, clean_env):
        """Test handling of key with AIzaSy prefix."""
        clean_env(GEMINI_API_KEY="AIzaSyC1234567890abcdef")

        config = {"providers": {"gemini": {"env_api_key": "GEMINI_API_KEY"}}}
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        result = gemini_token.get_api_key()

        assert result.api_key == "AIzaSyC1234567890abcdef"

    def test_very_long_key(self, clean_env):
        """Test handling of very long API key."""
        long_key = "AIza" + "x" * 100
        clean_env(GEMINI_API_KEY=long_key)

        config = {"providers": {"gemini": {"env_api_key": "GEMINI_API_KEY"}}}
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        result = gemini_token.get_api_key()

        assert result.api_key == long_key

    def test_multiple_get_api_key_calls(self, clean_env):
        """Test multiple get_api_key calls are consistent."""
        clean_env(GEMINI_API_KEY="consistent_key")

        config = {"providers": {"gemini": {"env_api_key": "GEMINI_API_KEY"}}}
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        result1 = gemini_token.get_api_key()
        result2 = gemini_token.get_api_key()

        assert result1.api_key == result2.api_key
        assert result1.auth_type == result2.auth_type

    def test_openai_compatibility(self, clean_env):
        """Test that result is compatible with OpenAI clients."""
        clean_env(GEMINI_API_KEY="test_key")

        config = {
            "providers": {
                "gemini": {
                    "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
                    "env_api_key": "GEMINI_API_KEY",
                }
            }
        }
        mock_store = MockConfigStore(config)
        gemini_token = GeminiOpenAIApiToken(config_store=mock_store)

        result = gemini_token.get_api_key()

        # Verify OpenAI-compatible auth header
        assert result.auth_type == "bearer"
        assert result.header_name == "Authorization"
