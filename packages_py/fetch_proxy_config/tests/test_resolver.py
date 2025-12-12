
import os
from unittest import mock
import pytest
from fetch_proxy_config.resolver import resolve_proxy_url
from fetch_proxy_config.types import NetworkConfig, AgentProxyConfig

@pytest.fixture
def clean_env():
    with mock.patch.dict(os.environ, {}, clear=True):
        yield

def test_resolve_proxy_url_direct_override(clean_env):
    """Should prioritize direct override"""
    config = NetworkConfig()
    result = resolve_proxy_url(config, "http://override:8080")
    assert result == "http://override:8080"

def test_resolve_proxy_url_config_default_env(clean_env):
    """Should use config for default environment"""
    config = NetworkConfig(
        default_environment="QA",
        proxy_urls={"QA": "http://qa-proxy:8080"}
    )
    result = resolve_proxy_url(config)
    assert result == "http://qa-proxy:8080"

def test_resolve_proxy_url_env_var_specific(clean_env):
    """Should prioritize specific env var if config missing"""
    with mock.patch.dict(os.environ, {"PROXY_URL": "http://env-proxy:8080"}):
        config = NetworkConfig()
        result = resolve_proxy_url(config)
        assert result == "http://env-proxy:8080"

def test_resolve_proxy_url_env_var_fallback(clean_env):
    """Should fallback to generic env vars"""
    with mock.patch.dict(os.environ, {"HTTPS_PROXY": "http://https-proxy:8080"}):
        config = NetworkConfig()
        result = resolve_proxy_url(config)
        assert result == "http://https-proxy:8080"
