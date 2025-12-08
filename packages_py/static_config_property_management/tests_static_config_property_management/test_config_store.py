"""Tests for ConfigStore singleton."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from static_config import (
    config,
    ConfigStore,
    load_yaml_config,
    ServerConfig,
)


@pytest.fixture(autouse=True)
def reset_config():
    """Reset config store before each test."""
    config.reset()
    yield
    config.reset()


@pytest.fixture
def sample_config():
    """Sample configuration data."""
    return {
        "providers": {
            "gemini": {
                "base_url": "https://api.gemini.test",
                "model": "gemini-test",
                "env_api_key": "GEMINI_API_KEY",
            },
            "openai": {
                "base_url": "https://api.openai.test",
                "model": "gpt-4-test",
                "env_api_key": "OPENAI_API_KEY",
            },
        },
        "default_provider": "gemini",
        "client": {
            "timeout_seconds": 30.0,
            "max_connections": 5,
        },
        "display": {
            "separator_char": "=",
            "separator_length": 60,
        },
        "proxy": {
            "default_environment": "test",
            "cert_verify": True,
        },
    }


@pytest.fixture
def temp_config_dir(sample_config):
    """Create a temporary config directory with sample config."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_path = Path(tmpdir) / "server.dev.yaml"
        with open(config_path, "w") as f:
            yaml.dump(sample_config, f)
        yield tmpdir


class TestConfigStore:
    """Tests for ConfigStore class."""

    def test_singleton_pattern(self):
        """ConfigStore should be a singleton."""
        store1 = ConfigStore()
        store2 = ConfigStore()
        assert store1 is store2

    def test_initial_state(self):
        """ConfigStore should start uninitialized."""
        assert not config.is_initialized()
        assert config.get_load_result() is None
        assert config.get_config() is None

    def test_load_from_directory(self, temp_config_dir, sample_config):
        """Should load config from directory."""
        result = config.load(config_dir=temp_config_dir, app_env="dev")

        assert config.is_initialized()
        assert len(result.files_loaded) == 1
        assert len(result.errors) == 0
        assert result.app_env == "dev"

    def test_load_nonexistent_directory(self):
        """Should handle nonexistent directory gracefully."""
        result = config.load(config_dir="/nonexistent/path", app_env="dev")

        assert config.is_initialized()
        assert len(result.files_loaded) == 0
        assert len(result.errors) == 1

    def test_get_top_level_value(self, temp_config_dir, sample_config):
        """Should get top-level config values."""
        config.load(config_dir=temp_config_dir, app_env="dev")

        assert config.get("default_provider") == "gemini"
        assert config.get("nonexistent") is None
        assert config.get("nonexistent", "default") == "default"

    def test_get_nested_value(self, temp_config_dir, sample_config):
        """Should get nested config values."""
        config.load(config_dir=temp_config_dir, app_env="dev")

        gemini_url = config.get_nested("providers", "gemini", "base_url")
        assert gemini_url == "https://api.gemini.test"

        timeout = config.get_nested("client", "timeout_seconds")
        assert timeout == 30.0

        nonexistent = config.get_nested("foo", "bar", default="missing")
        assert nonexistent == "missing"

    def test_get_all(self, temp_config_dir, sample_config):
        """Should return all config as dict."""
        config.load(config_dir=temp_config_dir, app_env="dev")

        all_config = config.get_all()
        assert "providers" in all_config
        assert "client" in all_config

    def test_get_config_returns_validated_model(self, temp_config_dir, sample_config):
        """Should return validated ServerConfig model."""
        config.load(config_dir=temp_config_dir, app_env="dev")

        server_config = config.get_config()
        assert isinstance(server_config, ServerConfig)
        assert server_config.default_provider == "gemini"
        assert server_config.client.timeout_seconds == 30.0

    def test_reset(self, temp_config_dir):
        """Should reset config to initial state."""
        config.load(config_dir=temp_config_dir, app_env="dev")
        assert config.is_initialized()

        config.reset()
        assert not config.is_initialized()
        assert config.get_all() == {}

    def test_env_specific_config(self, sample_config):
        """Should load environment-specific config file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Create prod config
            prod_config = sample_config.copy()
            prod_config["default_provider"] = "openai"

            prod_path = Path(tmpdir) / "server.prod.yaml"
            with open(prod_path, "w") as f:
                yaml.dump(prod_config, f)

            result = config.load(config_dir=tmpdir, app_env="prod")

            assert config.get("default_provider") == "openai"
            assert result.app_env == "prod"


class TestLoadYamlConfig:
    """Tests for load_yaml_config function."""

    def test_load_with_env_var(self, temp_config_dir, monkeypatch):
        """Should use APP_ENV from environment."""
        monkeypatch.setenv("APP_ENV", "dev")

        result = load_yaml_config(config_dir=temp_config_dir)

        assert config.is_initialized()
        assert result.app_env == "dev"

    def test_load_with_explicit_app_env(self, temp_config_dir):
        """Should use explicit app_env parameter."""
        result = load_yaml_config(config_dir=temp_config_dir, app_env="dev")

        assert result.app_env == "dev"

    def test_defaults_to_dev(self, temp_config_dir, monkeypatch):
        """Should default to 'dev' environment."""
        monkeypatch.delenv("APP_ENV", raising=False)

        result = load_yaml_config(config_dir=temp_config_dir)

        assert result.app_env == "dev"
