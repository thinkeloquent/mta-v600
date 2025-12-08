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
    """Tests for ElasticsearchApiToken placeholder class."""

    @pytest.fixture
    def elasticsearch_config(self):
        """Standard Elasticsearch placeholder config."""
        return {
            "providers": {
                "elasticsearch": {
                    "placeholder": True,
                    "message": "Elasticsearch integration not implemented",
                }
            }
        }

    @pytest.fixture
    def elasticsearch_token(self, elasticsearch_config):
        """Create ElasticsearchApiToken instance with standard config."""
        mock_store = MockConfigStore(elasticsearch_config)
        return ElasticsearchApiToken(config_store=mock_store)

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

    # get_api_key tests - Branch coverage

    def test_get_api_key_placeholder_true(self, elasticsearch_token, caplog):
        """Test get_api_key when placeholder is True."""
        with caplog.at_level(logging.INFO):
            result = elasticsearch_token.get_api_key()

        assert result.api_key is None
        assert result.is_placeholder is True
        assert result.placeholder_message == "Elasticsearch integration not implemented"
        assert result.has_credentials is False

        assert "is_placeholder=True" in caplog.text
        assert "Returning placeholder result" in caplog.text

    def test_get_api_key_placeholder_false(self, caplog):
        """Test get_api_key when placeholder is explicitly False."""
        config = {
            "providers": {
                "elasticsearch": {
                    "placeholder": False,
                }
            }
        }
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        with caplog.at_level(logging.WARNING):
            result = elasticsearch_token.get_api_key()

        assert result.api_key is None
        assert result.is_placeholder is False
        assert result.has_credentials is False

        assert "Elasticsearch is not a placeholder but no implementation exists" in caplog.text

    def test_get_api_key_custom_message(self, caplog):
        """Test get_api_key with custom placeholder message."""
        config = {
            "providers": {
                "elasticsearch": {
                    "placeholder": True,
                    "message": "Custom ES message",
                }
            }
        }
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        with caplog.at_level(logging.INFO):
            result = elasticsearch_token.get_api_key()

        assert result.placeholder_message == "Custom ES message"
        assert "Custom ES message" in caplog.text

    def test_get_api_key_default_config(self, caplog):
        """Test get_api_key with no config (uses defaults)."""
        config = {"providers": {}}
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        with caplog.at_level(logging.INFO):
            result = elasticsearch_token.get_api_key()

        # Defaults to placeholder=True
        assert result.is_placeholder is True
        assert result.placeholder_message == "Elasticsearch integration not implemented"


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

    def test_elasticsearch_validate_reports_placeholder(self):
        """Test Elasticsearch validate reports placeholder status."""
        config = {
            "providers": {
                "elasticsearch": {
                    "placeholder": True,
                    "message": "Not implemented",
                    "base_url": "https://es.com"
                }
            }
        }
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        result = elasticsearch_token.validate()

        assert result["is_placeholder"] is True


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

    def test_elasticsearch_empty_message(self):
        """Test Elasticsearch with empty message."""
        config = {
            "providers": {
                "elasticsearch": {
                    "placeholder": True,
                    "message": "",
                }
            }
        }
        mock_store = MockConfigStore(config)
        elasticsearch_token = ElasticsearchApiToken(config_store=mock_store)

        result = elasticsearch_token.get_api_key()

        assert result.placeholder_message == ""

    def test_multiple_calls_consistency(self):
        """Test multiple get_api_key calls return consistent results."""
        config = {"providers": {"rally": {"placeholder": True}}}
        mock_store = MockConfigStore(config)
        rally_token = RallyApiToken(config_store=mock_store)

        results = [rally_token.get_api_key() for _ in range(5)]

        for result in results:
            assert result.is_placeholder is True
            assert result.api_key is None
