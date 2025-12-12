import os
import logging
from typing import Optional, Dict
from .types import NetworkConfig

logger = logging.getLogger("fetch_proxy_config")


def resolve_proxy_url(
    network_config: Optional[NetworkConfig],
    proxy_url_override: Optional[str] = None
) -> Optional[str]:
    """
    Resolve the proxy URL based on configuration and environment variables.

    Precedence (Waterfall):
    1. proxy_url_override (e.g. from provider.proxy_url)
    2. network_config.proxy_urls[default_environment]
    3. PROXY_URL environment variable
    4. HTTPS_PROXY environment variable
    5. HTTP_PROXY environment variable

    Args:
        network_config: Network configuration object
        proxy_url_override: Optional override URL (highest priority)

    Returns:
        Resolved proxy URL string or None if no proxy should be used.
    """
    # 1. Check override
    if proxy_url_override:
        logger.debug(f"resolve_proxy_url: Using override: {proxy_url_override}")
        return proxy_url_override

    # 2. Check network config
    if network_config and network_config.proxy_urls and network_config.default_environment:
        env_key = network_config.default_environment
        # Normalize environment keys? Assuming direct match for now based on YAML
        # But commonly config keys like 'dev' might map to 'DEV' in override logic elsewhere.
        # Here we stick to the provided dictionary.
        
        # Try exact match
        url = network_config.proxy_urls.get(env_key)
        
        if url:
             logger.debug(f"resolve_proxy_url: Used network_config[{env_key}]: {url}")
             return url
    
    # 3. PROXY_URL
    proxy_url_env = os.environ.get("PROXY_URL")
    if proxy_url_env:
        logger.debug(f"resolve_proxy_url: Using PROXY_URL env: {proxy_url_env}")
        return proxy_url_env

    # 4. HTTPS_PROXY
    https_proxy = os.environ.get("HTTPS_PROXY")
    if https_proxy:
        logger.debug(f"resolve_proxy_url: Using HTTPS_PROXY env: {https_proxy}")
        return https_proxy
        
    # 5. HTTP_PROXY
    http_proxy = os.environ.get("HTTP_PROXY")
    if http_proxy:
        logger.debug(f"resolve_proxy_url: Using HTTP_PROXY env: {http_proxy}")
        return http_proxy

    logger.debug("resolve_proxy_url: No proxy URL found")
    return None
