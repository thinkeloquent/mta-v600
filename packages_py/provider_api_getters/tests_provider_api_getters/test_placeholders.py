"""
Comprehensive tests for placeholder providers (Rally, Elasticsearch).

Tests cover:
- Decision/Branch coverage for placeholder logic
- Log verification for defensive programming
"""
import logging
import pytest

from provider_api_getters.api_token.rally import RallyApiToken
from provider_api_getters.api_token.elasticsearch import ElasticsearchApiToken
from .conftest import MockConfigStore

# Enable debug logging for tests
logging.getLogger("provider_api_getters").setLevel(logging.DEBUG)


class TestRallyApiToken:
    """Tests for RallyApiToken placeholder class."""

    @pytest.fixture
    def rally_config(self):
        """Standard Rally placeholder config."""
        return {
            "providers": {
                "rally": {
                    "placeholder": True,
                    "message": "Rally integration not implemented",
                }
            }
        }

    @pytest.fixture
    def rally_token(self, rally_config):
        """Create RallyApiToken instance with standard config."""
        mock_store = MockConfigStore(rally_config)
        return RallyApiToken(config_store=mock_store)

    # Provider name tests
    def test_provider_name(self, rally_token):
        """Test provider_name returns 'rally'."""
        assert rally_token.provider_name == "rally"

    # Health endpoint tests
    def test_health_endpoint(self, rally_token, caplog):
        """Test health_endpoint returns placeholder endpoint."""
        with caplog.at_level(logging.DEBUG):
            endpoint = rally_token.health_endpoint

        assert endpoint == "/"
        assert "Returning placeholder endpoint /" in caplog.text

    # get_api_key tests - Branch coverage

    def test_get_api_key_placeholder_true(self, rally_token, caplog):
        """Test get_api_key when placeholder is True."""
        with caplog.at_level(logging.INFO):
            result = rally_token.get_api_key()

        assert result.api_key is None
        assert result.is_placeholder is True
        assert result.placeholder_message == "Rally integration not implemented"
        assert result.has_credentials is False

        assert "is_placeholder=True" in caplog.text
        assert "Returning placeholder result" in caplog.text

    def test_get_api_key_placeholder_false(self, caplog):
        """Test get_api_key when placeholder is explicitly False."""
        config = {
            "providers": {
                "rally": {
                    "placeholder": False,
                }
            }
        }
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        with caplog.at_level(logging.WARNING):
            result = rally_token.get_api_key()

        assert result.api_key is None
        assert result.is_placeholder is False
        assert result.has_credentials is False

        assert "Rally is not a placeholder but no implementation exists" in caplog.text

    def test_get_api_key_custom_message(self, caplog):
        """Test get_api_key with custom placeholder message."""
        config = {
            "providers": {
                "rally": {
                    "placeholder": True,
                    "message": "Custom Rally message",
                }
            }
        }
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        with caplog.at_level(logging.INFO):
            result = rally_token.get_api_key()

        assert result.placeholder_message == "Custom Rally message"
        assert "Custom Rally message" in caplog.text

    def test_get_api_key_default_config(self, caplog):
        """Test get_api_key with no config (uses defaults)."""
        config = {"providers": {}}
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        with caplog.at_level(logging.INFO):
            result = rally_token.get_api_key()

        # Defaults to placeholder=True
        assert result.is_placeholder is True
        assert result.placeholder_message == "Rally integration not implemented"

    def test_get_api_key_logs_config_state(self, rally_token, caplog):
        """Test that config state is logged."""
        with caplog.at_level(logging.DEBUG):
            rally_token.get_api_key()

        assert "is_placeholder=True" in caplog.text
        assert "message='Rally integration not implemented'" in caplog.text


class TestElasticsearchApiToken:
    """Tests for ElasticsearchApiToken connection-based class.

    NOTE: Elasticsearch is NOT a placeholder provider. It's a real connection-based
    provider that builds connection URLs from environment variables.
    """

    @pytest.fixture
    def elasticsearch_config(self):
        """Standard Elasticsearch config."""
        return {
            "providers": {
                "elasticsearch": {
                    "env_connection_url": "ELASTIC_DB_URL",
                }
            }
        }

    @pytest.fixture
    def elasticsearch_token(self, elasticsearch_config):
        """Create ElasticsearchApiToken instance with standard config."""
        mock_store = MockConfigStore(elasticsearch_config)
        return ElasticsearchApiToken(config_store=mock_store)

    @pytest.fixture
    def clean_es_env(self, monkeypatch):
        """Clear Elasticsearch-related env vars."""
        env_vars = [
            "ELASTIC_DB_URL",
            "ELASTIC_DB_HOST",
            "ELASTIC_DB_PORT",
            "ELASTIC_DB_USERNAME",
            "ELASTIC_DB_ACCESS_KEY",
            "ELASTIC_DB_TLS",
        ]
        for var in env_vars:
            monkeypatch.delenv(var, raising=False)

        def set_env(**kwargs):
            for key, value in kwargs.items():
                if value is None:
                    monkeypatch.delenv(key, raising=False)
                else:
                    monkeypatch.setenv(key, value)
        return set_env

    # Provider name tests
    def test_provider_name(self, elasticsearch_token):
        """Test provider_name returns 'elasticsearch'."""
        assert elasticsearch_token.provider_name == "elasticsearch"

    # Health endpoint tests
    def test_health_endpoint(self, elasticsearch_token, caplog):
        """Test health_endpoint returns cluster health endpoint."""
        with caplog.at_level(logging.DEBUG):
            endpoint = elasticsearch_token.health_endpoint

        assert endpoint == "/_cluster/health"
        assert "Returning /_cluster/health" in caplog.text

    # get_api_key tests - Elasticsearch returns connection URLs, not placeholder

    def test_get_api_key_with_url_env_var(self, elasticsearch_token, clean_es_env, caplog):
        """Test get_api_key when ELASTIC_DB_URL is set."""
        clean_es_env(ELASTIC_DB_URL="https://user:pass@es.example.com:9243")

        with caplog.at_level(logging.DEBUG):
            result = elasticsearch_token.get_api_key()

        assert result.api_key == "https://user:pass@es.example.com:9243"
        assert result.auth_type == "connection_string"
        assert result.has_credentials is True
        assert result.is_placeholder is False

    def test_get_api_key_builds_from_components(self, elasticsearch_token, clean_es_env, caplog):
        """Test get_api_key builds URL from individual env vars."""
        clean_es_env(
            ELASTIC_DB_HOST="localhost",
            ELASTIC_DB_PORT="9200",
        )

        with caplog.at_level(logging.DEBUG):
            result = elasticsearch_token.get_api_key()

        # When no URL env var, builds from components
        assert result.api_key is not None
        assert "localhost:9200" in result.api_key
        assert result.auth_type == "connection_string"
        assert result.has_credentials is True

    def test_get_api_key_default_url(self, elasticsearch_config, clean_es_env, caplog):
        """Test get_api_key with no env vars uses defaults."""
        mock_store = MockConfigStore(elasticsearch_config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = elasticsearch_token.get_api_key()

        # Default is http://localhost:9200
        assert result.api_key == "http://localhost:9200"
        assert result.auth_type == "connection_string"
        assert result.has_credentials is True

    def test_get_api_key_with_auth(self, elasticsearch_config, clean_es_env, caplog):
        """Test get_api_key with username and password."""
        clean_es_env(
            ELASTIC_DB_HOST="es.example.com",
            ELASTIC_DB_PORT="9243",
            ELASTIC_DB_USERNAME="elastic",
            ELASTIC_DB_ACCESS_KEY="secretkey",
        )
        mock_store = MockConfigStore(elasticsearch_config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        with caplog.at_level(logging.DEBUG):
            result = elasticsearch_token.get_api_key()

        # Port 9243 is TLS by default
        assert "https://" in result.api_key
        assert "elastic:secretkey@" in result.api_key
        assert result.has_credentials is True


class TestPlaceholderValidation:
    """Test validate() behavior for placeholder providers."""

    def test_rally_validate_reports_placeholder(self):
        """Test Rally validate reports placeholder status."""
        config = {
            "providers": {
                "rally": {
                    "placeholder": True,
                    "message": "Not implemented",
                    "base_url": "https://rally.com"
                }
            }
        }
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        result = rally_token.validate()

        assert result["is_placeholder"] is True
        assert "Provider is placeholder" in result["warnings"][0]

    def test_elasticsearch_validate_reports_connection_url(self, monkeypatch):
        """Test Elasticsearch validate reports connection status."""
        # Clear env vars
        for var in ["ELASTIC_DB_URL", "ELASTIC_DB_HOST", "ELASTIC_DB_PORT",
                    "ELASTIC_DB_USERNAME", "ELASTIC_DB_ACCESS_KEY", "ELASTIC_DB_TLS"]:
            monkeypatch.delenv(var, raising=False)

        config = {
            "providers": {
                "elasticsearch": {
                    "env_connection_url": "ELASTIC_DB_URL",
                }
            }
        }
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        result = elasticsearch_token.validate()

        # Elasticsearch is NOT a placeholder - it builds connection URLs
        assert result["is_placeholder"] is False


class TestPlaceholderEdgeCases:
    """Edge case tests for placeholder providers."""

    def test_rally_empty_message(self):
        """Test Rally with empty message."""
        config = {
            "providers": {
                "rally": {
                    "placeholder": True,
                    "message": "",
                }
            }
        }
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        result = rally_token.get_api_key()

        assert result.placeholder_message == ""

    def test_elasticsearch_no_tls_explicit(self, monkeypatch):
        """Test Elasticsearch with explicit TLS disabled."""
        # Clear env vars first
        for var in ["ELASTIC_DB_URL", "ELASTIC_DB_HOST", "ELASTIC_DB_PORT",
                    "ELASTIC_DB_USERNAME", "ELASTIC_DB_ACCESS_KEY", "ELASTIC_DB_TLS"]:
            monkeypatch.delenv(var, raising=False)

        monkeypatch.setenv("ELASTIC_DB_HOST", "localhost")
        monkeypatch.setenv("ELASTIC_DB_PORT", "9200")

        config = {"providers": {"elasticsearch": {}}}
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        result = elasticsearch_token.get_api_key()

        # Port 9200 with no TLS env var should use http
        assert "http://" in result.api_key
        assert result.is_placeholder is False

    def test_multiple_calls_consistency(self):
        """Test multiple get_api_key calls return consistent results."""
        config = {"providers": {"rally": {"placeholder": True}}}
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        results = [rally_token.get_api_key() for _ in range(5)]

        for result in results:
            assert result.is_placeholder is True
            assert result.api_key is None
